#!/usr/bin/env bash
# launch.sh — one-shot launcher for a superagent EXTERNAL loop. Given only a root
# master plan, it prepares the loop-status file and arms the per-goal scheduler
# entry (systemd user timer on Linux, launchd LaunchAgent on macOS), so the loop
# runs unattended in the background with no separate console.
#
#   launch.sh <PLAN.md> [--interval 30m]
#             [--timeout <secs>] [--slug <goal-slug>]
#
# Only <PLAN.md> (the goal's ROOT seed/master plan) is required. Defaults:
#   interval=$SUPER_TICK_INTERVAL (else 30m)  timeout=none (unlimited)  slug=<goal-folder name, date-stamp stripped>
#
# Deterministic + idempotent: it creates the loop-status file directly in the
# superloop L1 format (no LLM call) if none exists for this master plan, or reuses
# the existing one (so re-running just re-arms / resumes). It fails fast if the
# claude binary or gh auth is missing, before arming anything.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
[[ -n "$REPO" ]] || { echo "superagent: set REPO or run from inside the target repo" >&2; exit 1; }
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
# Project launch from a linked checkout uses the primary checkout's config.
previous_arg=""
for launch_arg in "$@"; do
  if [[ "$previous_arg" == --supervisor && "$launch_arg" == supercode ]]; then
    primary_git="$(git -C "$REPO" rev-parse --path-format=absolute --git-common-dir)"
    REPO="$(cd "$primary_git/.." && pwd -P)"
    break
  fi
  previous_arg="$launch_arg"
done
load_superenv "$REPO"

usage() {
  echo "usage: launch.sh <PLAN.md|PROJECT> [--supervisor superagent|supercode] [--interval 30m] [--timeout <secs>] [--slug <goal-slug>] [--output stream|text] [--model <slug>] [--harness claude|cursor|codex|pi] [--dry-run]" >&2
  exit 2
}

PLAN="${1:-}"
[[ -z "$PLAN" || "$PLAN" == -* ]] && usage
shift

INTERVAL="${SUPER_TICK_INTERVAL:-30m}"; TICK_TIMEOUT=""; SLUG=""; OUTPUT_FORMAT="stream"; MODEL=""; DRY=0
SUPERVISOR=superagent
HARNESS="$(superagent_harness)" || exit 2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --interval) INTERVAL="${2:?--interval needs a value}"; shift 2 ;;
    --timeout)  TICK_TIMEOUT="${2:?--timeout needs a value}"; shift 2 ;;
    --slug)     SLUG="${2:?--slug needs a value}"; shift 2 ;;
    --output)   OUTPUT_FORMAT="${2:?--output needs a value}"; shift 2 ;;
    --model)    MODEL="${2:?--model needs a value}"; shift 2 ;;
    --supervisor) SUPERVISOR="${2:?--supervisor needs a value}"; shift 2 ;;
    --harness)  HARNESS="${2:?--harness needs a value}"; shift 2 ;;
    --dry-run)  DRY=1; shift ;;
    *) echo "unknown arg: $1" >&2; usage ;;
  esac
done
case "$OUTPUT_FORMAT" in stream|text) ;; *) echo "bad --output '$OUTPUT_FORMAT' (want stream|text)" >&2; exit 2 ;; esac
case "$HARNESS" in claude|cursor|codex|pi) ;; *) echo "bad --harness '$HARNESS' (want claude|cursor|codex|pi)" >&2; exit 2 ;; esac
case "$SUPERVISOR" in superagent|supercode) ;; *) echo "invalid supervisor: $SUPERVISOR" >&2; exit 2 ;; esac
export SUPER_HARNESS="$HARNESS"
if [[ "$SUPERVISOR" == supercode ]]; then
  command -v python3 >/dev/null || { echo "supercode requires python3" >&2; exit 2; }
  # Internal vault resolution is anchored to the physical primary checkout.
  REPO="$(git -C "$REPO" rev-parse --path-format=absolute --git-common-dir)"
  REPO="$(cd "$REPO/.." && pwd -P)"
  export REPO
  [[ -n "$SLUG" ]] || SLUG="$(basename "$PLAN" | sed -E 's/^[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}_[0-9]{2}-//; s/[^A-Za-z0-9_.-]/-/g')"
  prepare_args=(prepare-project --repo "$REPO" --vault "$(vault_root "$REPO")" --project "$PLAN"
    --conf "${XDG_CONFIG_HOME:-$HOME/.config}/superagent" --slug "$SLUG"
    --max-rounds "${SUPER_CODE_MAX_ITERATIONS:-10}" --dirname "${SUPER_LOOP_STATUS_DIRNAME:-loop-status}")
  prepared="$(python3 "$SCRIPT_DIR/_coding_loop_state.py" "${prepare_args[@]}")" || exit 2
  project_values=(); while IFS= read -r value; do project_values+=("$value"); done <<<"$prepared"
  REPO="${project_values[0]}"; PROJECT="${project_values[1]}"; PLAN_REL="${project_values[2]}"; LOOP_FILE="${project_values[3]}"; SLUG="${project_values[4]}"
  PRD_LINT_REPO_ROOT="$REPO" "$SCRIPT_DIR/prd-lint.sh" "$PROJECT" >/dev/null || { echo "project PRD lint failed" >&2; exit 2; }
  set -a; [[ -f "$REPO/.env" ]] && . "$REPO/.env"; set +a
  ensure_cli_bin; ensure_gh_auth
  if [[ "$DRY" == 1 ]]; then
    echo "[dry-run] supercode project: $PLAN_REL; slug: $SLUG; loop: $LOOP_FILE"
    exit 0
  fi
  mkdir -p "$(dirname "$LOOP_FILE")"
  launch_lock="$(dirname "$LOOP_FILE")/.$(basename "$LOOP_FILE").lockd"
  if SUPERAGENT_TICK_PID=$$ superagent_acquire_gate_lock "$launch_lock"; then
    trap '[[ "$(cat "$launch_lock/owner" 2>/dev/null)" != "$$" ]] || rm -rf "$launch_lock"' EXIT
    python3 "$SCRIPT_DIR/_coding_loop_state.py" "${prepare_args[@]}" --write >/dev/null || exit 2
    rm -rf "$launch_lock"; trap - EXIT
  elif [[ ! -f "$LOOP_FILE" ]]; then
    echo "project bootstrap in progress; retry launch" >&2; exit 2
  fi
  install_args=(--supervisor supercode --interval "$INTERVAL" --output "$OUTPUT_FORMAT" --harness "$HARNESS")
  [[ -n "$TICK_TIMEOUT" ]] && install_args+=(--timeout "$TICK_TIMEOUT")
  [[ -n "$MODEL" ]] && install_args+=(--model "$MODEL")
  "$SCRIPT_DIR/install-timer.sh" "$SLUG" "$LOOP_FILE" "${install_args[@]}"
  superagent_kick_tick "$SLUG" 2>/dev/null || true
  echo "Launched supercode external loop: $SLUG; project: $PLAN_REL; loop: $LOOP_FILE"
  exit 0
fi
# Effective model shown in reports (the wrapper's default when unset).
if [[ -n "$MODEL" ]]; then MODEL_SHOWN="$MODEL"
elif [[ "$HARNESS" == codex ]]; then MODEL_SHOWN="config default"
elif [[ "$HARNESS" == cursor ]]; then MODEL_SHOWN="auto (default)"
elif [[ "$HARNESS" == pi ]]; then MODEL_SHOWN="settings default"
else MODEL_SHOWN="opus (default)"; fi

# Resolve the plan to an absolute path, then to the form superloop stores in master_plan:
# repo-relative when the plan lies inside the checkout (internal vault), absolute when it lies
# under an EXTERNAL vault (SUPER_GOAL_ROOT absolute or ~-prefixed — see vault_root in _common.sh).
[[ -f "$PLAN" ]] || { echo "plan file not found: $PLAN" >&2; exit 2; }
PLAN_ABS="$(cd "$(dirname "$PLAN")" && pwd -P)/$(basename "$PLAN")"
VAULT="$(vault_root "$REPO")"
# Compare against the physical vault path too: $REPO is physical (git), the vault may be a symlink.
VAULT_P="$( [[ -d "$VAULT" ]] && cd "$VAULT" && pwd -P || printf '%s' "$VAULT" )"
case "$PLAN_ABS" in
  "$REPO"/*) PLAN_REL="${PLAN_ABS#"$REPO"/}" ;;
  "$VAULT"/*|"$VAULT_P"/*)
    if vault_is_external; then PLAN_REL="$PLAN_ABS"
    else echo "plan must live inside the repo checkout ($REPO): $PLAN_ABS" >&2; exit 2; fi ;;
  *) if vault_is_external; then
       echo "plan must live inside the repo checkout ($REPO) or the external vault ($VAULT): $PLAN_ABS" >&2
     else
       echo "plan must live inside the repo checkout ($REPO): $PLAN_ABS" >&2
     fi
     exit 2 ;;
esac

# Goal folder = parent of the master-plans/ dir holding the plan (superloop L1).
GOAL_FOLDER="$(cd "$(dirname "$PLAN_ABS")/.." && pwd -P)"
LOOP_DIR="$GOAL_FOLDER/${SUPER_LOOP_STATUS_DIRNAME:-loop-status}"

# Default slug = goal-folder basename with a leading YYYY-MM-DD-hh_mm- stamp stripped.
if [[ -z "$SLUG" ]]; then
  SLUG="$(basename "$GOAL_FOLDER" | sed -E 's/^[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}_[0-9]{2}-//')"
fi

# Fail fast on missing agent-CLI binary / gh auth BEFORE creating or arming anything.
set -a; [[ -f "$REPO/.env" ]] && . "$REPO/.env"; set +a
ensure_cli_bin
ensure_gh_auth

# Find an existing loop file for this master plan (idempotent re-arm / resume).
LOOP_FILE=""
if [[ -d "$LOOP_DIR" ]]; then
  shopt -s nullglob
  for f in "$LOOP_DIR"/*.md; do
    mp="$(sed -n 's/^master_plan:[[:space:]]*//p' "$f" | head -1)"
    [[ "$mp" == "$PLAN_REL" ]] && { LOOP_FILE="$f"; break; }
  done
fi

prospective_loop="${LOOP_FILE:-$LOOP_DIR/$(date +%Y-%m-%d)-$SLUG.md}"
superagent_check_registration "$SLUG" "$prospective_loop" "$SUPERVISOR" || exit 2
[[ -z "$LOOP_FILE" ]] || superagent_supervisor "$LOOP_FILE" "$SUPERVISOR" >/dev/null || exit 2

if [[ "$DRY" == 1 ]]; then
  echo "[dry-run] would launch superagent external loop:"
  echo "  goal slug:  $SLUG"
  echo "  harness:    $HARNESS"
  echo "  model:      $MODEL_SHOWN"
  echo "  interval:   $INTERVAL   timeout: ${TICK_TIMEOUT:-none}   output: $OUTPUT_FORMAT"
  echo "  plan:       $PLAN_REL"
  if [[ -n "$LOOP_FILE" ]]; then
    echo "  loop file:  $LOOP_FILE  (existing — would reuse)"
  else
    echo "  loop file:  $LOOP_DIR/$(date +%Y-%m-%d)-$SLUG.md  (would create)"
  fi
  if [[ "$(superagent_scheduler)" == launchd ]]; then
    echo "  scheduler:  $(superagent_launchd_label "$SLUG")  (would bootstrap + kickstart, interval $INTERVAL)"
  else
    echo "  scheduler:  superagent-tick@$SLUG.timer  (would enable --now, interval $INTERVAL)"
  fi
  echo "[dry-run] nothing created or armed."
  exit 0
fi

if [[ -n "$LOOP_FILE" ]]; then
  echo "Reusing existing loop file: $LOOP_FILE"
else
  mkdir -p "$LOOP_DIR"
  LOOP_FILE="$LOOP_DIR/$(date +%Y-%m-%d)-$SLUG.md"
  # FRESH START — superloop L1 loop-status format (gitignored, local-only state).
  cat >"$LOOP_FILE" <<EOF
---
supervisor: superagent
master_plan: $PLAN_REL
status: WAITING FOR PLAN
plan_exhausted: false
prior_status:
driver: external
cron_id:
created: $(date +%Y-%m-%d)
iteration: 0
session_skill_count: 0
---

## Pending decision

## Decisions

## Iteration log
- $(date -u +%Y-%m-%dT%H:%M:%SZ) launched by superagent-external (interval=$INTERVAL)
EOF
  echo "Created loop file: $LOOP_FILE"
fi

# Arm the per-goal systemd user timer. Only forward --timeout when a cap was given;
# passing --timeout "" would trip install-timer's ${2:?} null-check and abort.
install_args=(--supervisor "$SUPERVISOR" --interval "$INTERVAL" --output "$OUTPUT_FORMAT" --harness "$HARNESS")
[[ -n "$TICK_TIMEOUT" ]] && install_args+=(--timeout "$TICK_TIMEOUT")
[[ -n "$MODEL" ]] && install_args+=(--model "$MODEL")
"$SCRIPT_DIR/install-timer.sh" "$SLUG" "$LOOP_FILE" "${install_args[@]}"

# Kick the first tick now (non-blocking) so the loop starts immediately instead of
# waiting for the timer's first interval.
superagent_kick_tick "$SLUG" 2>/dev/null || true

echo
echo "Launched superagent external loop:"
echo "  goal slug:  $SLUG"
echo "  harness:    $HARNESS"
echo "  model:      $MODEL_SHOWN"
echo "  interval:   $INTERVAL   timeout: ${TICK_TIMEOUT:-none}   output: $OUTPUT_FORMAT"
echo "  plan:       $PLAN_REL"
echo "  loop file:  $LOOP_FILE"
if [[ "$(superagent_scheduler)" == launchd ]]; then
  echo "  monitor:    $SCRIPT_DIR/status.sh $SLUG   |   tail -f /tmp/superagent-launchd-$SLUG.log /tmp/superagent-*.log"
else
  echo "  monitor:    $SCRIPT_DIR/status.sh $SLUG   |   journalctl --user -u superagent-tick@$SLUG.service -f"
fi
echo "  stop:       $SCRIPT_DIR/uninstall-timer.sh $SLUG"

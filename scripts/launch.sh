#!/usr/bin/env bash
# launch.sh — one-shot launcher for a superagent EXTERNAL loop. Given only a root
# master plan, it prepares the loop-status file and arms the per-goal systemd user
# timer, so the loop runs unattended in the background with no separate console.
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
load_superenv "$REPO"

usage() {
  echo "usage: launch.sh <PLAN.md> [--interval 30m] [--timeout <secs>] [--slug <goal-slug>] [--output stream|text] [--model <slug>] [--dry-run]" >&2
  exit 2
}

PLAN="${1:-}"
[[ -z "$PLAN" || "$PLAN" == -* ]] && usage
shift

INTERVAL="${SUPER_TICK_INTERVAL:-30m}"; TICK_TIMEOUT=""; SLUG=""; OUTPUT_FORMAT="stream"; MODEL=""; DRY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --interval) INTERVAL="${2:?--interval needs a value}"; shift 2 ;;
    --timeout)  TICK_TIMEOUT="${2:?--timeout needs a value}"; shift 2 ;;
    --slug)     SLUG="${2:?--slug needs a value}"; shift 2 ;;
    --output)   OUTPUT_FORMAT="${2:?--output needs a value}"; shift 2 ;;
    --model)    MODEL="${2:?--model needs a value}"; shift 2 ;;
    --dry-run)  DRY=1; shift ;;
    *) echo "unknown arg: $1" >&2; usage ;;
  esac
done
case "$OUTPUT_FORMAT" in stream|text) ;; *) echo "bad --output '$OUTPUT_FORMAT' (want stream|text)" >&2; exit 2 ;; esac
# Effective model shown in reports (the wrapper's default when unset).
if [[ -n "$MODEL" ]]; then MODEL_SHOWN="$MODEL"; else MODEL_SHOWN="opus (default)"; fi

# Resolve the plan to an absolute path, then to a repo-relative path (superloop
# stores master_plan repo-relative).
[[ -f "$PLAN" ]] || { echo "plan file not found: $PLAN" >&2; exit 2; }
PLAN_ABS="$(cd "$(dirname "$PLAN")" && pwd)/$(basename "$PLAN")"
case "$PLAN_ABS" in
  "$REPO"/*) PLAN_REL="${PLAN_ABS#"$REPO"/}" ;;
  *) echo "plan must live inside the repo checkout ($REPO): $PLAN_ABS" >&2; exit 2 ;;
esac

# Goal folder = parent of the master-plans/ dir holding the plan (superloop L1).
GOAL_FOLDER="$(cd "$(dirname "$PLAN_ABS")/.." && pwd)"
LOOP_DIR="$GOAL_FOLDER/loop-status"

# Default slug = goal-folder basename with a leading YYYY-MM-DD-hh_mm- stamp stripped.
if [[ -z "$SLUG" ]]; then
  SLUG="$(basename "$GOAL_FOLDER" | sed -E 's/^[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}_[0-9]{2}-//')"
fi

# Fail fast on missing claude binary / gh auth BEFORE creating or arming anything.
set -a; [[ -f "$REPO/.env" ]] && . "$REPO/.env"; set +a
ensure_claude_bin
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

if [[ "$DRY" == 1 ]]; then
  echo "[dry-run] would launch superagent external loop:"
  echo "  goal slug:  $SLUG"
  echo "  model:      $MODEL_SHOWN"
  echo "  interval:   $INTERVAL   timeout: ${TICK_TIMEOUT:-none}   output: $OUTPUT_FORMAT"
  echo "  plan:       $PLAN_REL"
  if [[ -n "$LOOP_FILE" ]]; then
    echo "  loop file:  $LOOP_FILE  (existing — would reuse)"
  else
    echo "  loop file:  $LOOP_DIR/$(date +%Y-%m-%d)-$SLUG.md  (would create)"
  fi
  echo "  timer:      superagent-tick@$SLUG.timer  (would enable --now, interval $INTERVAL)"
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
install_args=(--interval "$INTERVAL" --output "$OUTPUT_FORMAT")
[[ -n "$TICK_TIMEOUT" ]] && install_args+=(--timeout "$TICK_TIMEOUT")
[[ -n "$MODEL" ]] && install_args+=(--model "$MODEL")
"$SCRIPT_DIR/install-timer.sh" "$SLUG" "$LOOP_FILE" "${install_args[@]}"

# Kick the first tick now (non-blocking) so the loop starts immediately instead of
# waiting for the timer's first interval.
systemctl --user start --no-block "superagent-tick@$SLUG.service" 2>/dev/null || true

echo
echo "Launched superagent external loop:"
echo "  goal slug:  $SLUG"
echo "  model:      $MODEL_SHOWN"
echo "  interval:   $INTERVAL   timeout: ${TICK_TIMEOUT:-none}   output: $OUTPUT_FORMAT"
echo "  plan:       $PLAN_REL"
echo "  loop file:  $LOOP_FILE"
echo "  monitor:    $SCRIPT_DIR/status.sh $SLUG   |   journalctl --user -u superagent-tick@$SLUG.service -f"
echo "  stop:       $SCRIPT_DIR/uninstall-timer.sh $SLUG"

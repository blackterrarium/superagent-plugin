#!/usr/bin/env bash
# pi-e2e.sh — scripted END-TO-END testbench for the superagent framework on the Pi harness.
#
# From an empty repository it drives a tiny real goal through
#   init → supergoal → external loop (the OS scheduler fires EVERY tick) → DONE
# and asserts the observable results. The script never runs superagent-tick.sh itself: it arms
# the loop with launch.sh and only watches status.sh --json — that is the point (the 2026-08-31
# loop-to-DONE run was driven by hand; nothing had ever proven a scheduler-fired Pi tick).
#
#   scripts/pi-e2e.sh [--dry-run] [--keep]
#     PI_E2E_REPO=<owner>/<name>   remote to (re)use; NEVER deleted, reset to an orphan commit per
#                                  run (default: <gh user>/superagent-pi-e2e)
#     PI_E2E_INTERVAL=2m           scheduler interval (launchd StartInterval / systemd timer)
#     PI_E2E_MAX_MIN=90            wall-clock ceiling for the loop phase
#     PI_E2E_GOAL="…"              goal text (default: the hello-world shell goal below)
#     PI_E2E_SUPERENV_EXTRA="…"    extra .superenv lines (e.g. SUPER_MODEL_TASK_REVIEWER=codex:…)
#
# Needs: pi (authenticated), gh (authenticated), git, python3, launchctl (Darwin) or
# systemctl --user. Cost ≈ 6 Pi sessions (init, supergoal, ~4 ticks); ~20–40 min.
# Report: pi-e2e-report.md at the repo root (gitignored); run artifacts (tick log copy, event
# log, status transitions) under $TMPDIR/pi-e2e-<stamp>/.
# Exit 0 only when every phase passes. Set PI_E2E_LIB=1 and source this file to get the pure
# helpers (e2e_*) without running anything — bridge-test.sh does that.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$ROOT/scripts"

# ---------------------------------------------------------------------------
# Pure helpers (no side effects; unit-tested offline in bridge-test.sh)
# ---------------------------------------------------------------------------

# e2e_status_field <status.sh --json output> <slug> <field>
# Prints the field of the row whose slug matches (booleans as true/false); "" if absent.
e2e_status_field() {
  printf '%s' "$1" | python3 -c '
import json, sys
slug, field = sys.argv[1], sys.argv[2]
try:
    rows = json.load(sys.stdin)
except Exception:
    rows = []
for r in rows if isinstance(rows, list) else []:
    if r.get("slug") == slug:
        v = r.get(field, "")
        print(str(v).lower() if isinstance(v, bool) else v)
        break
' "$2" "$3" 2>/dev/null || true
}

# e2e_render_superenv <interval> <events_log> [extra-lines]
# The throwaway repo's .superenv. SUPER_NOTIFY_CMD is SINGLE-quoted on purpose: .superenv is
# sourced under `set -u`, and an expanded $SUPERAGENT_EVENT would abort every tick (0.4.10).
e2e_render_superenv() {
  printf 'SUPER_HARNESS=pi\nSUPER_TICK_INTERVAL=%s\n' "$1"
  printf "SUPER_NOTIFY_CMD='printf \"%%s\\\\n\" \"\$SUPERAGENT_EVENT\" >>\"%s\"'\n" "$2"
  [[ -n "${3:-}" ]] && printf '%s\n' "$3"
  return 0
}

# e2e_count_ticks <tick_log> — sessions the tick wrapper actually started (its header line).
e2e_count_ticks() {
  if [[ -f "$1" ]]; then grep -c '^=== .* superagent-tick harness=' "$1" || true; else echo 0; fi
}

# e2e_transition <status> <iteration> — prints "<utc-time> <status> iter=<n>" only when the
# pair changed since the previous call (state kept in _E2E_LAST).
_E2E_LAST=""
e2e_transition() {
  local key="$1|$2"
  [[ "$key" == "$_E2E_LAST" ]] && return 0
  _E2E_LAST="$key"
  printf '%s %s iter=%s\n' "$(date -u +%H:%M:%S)" "$1" "$2"
}

# e2e_assert_deliverables <repo_dir> — the default goal's contract: scripts/hello.sh prints
# exactly "hello, world" and scripts/test.sh exits 0. Prints the reason on failure.
e2e_assert_deliverables() {
  local d="$1"
  [[ -f "$d/scripts/hello.sh" && -f "$d/scripts/test.sh" ]] || { echo "missing scripts/hello.sh or scripts/test.sh"; return 1; }
  [[ "$(cd "$d" && sh scripts/hello.sh 2>&1)" == "hello, world" ]] || { echo "scripts/hello.sh output != 'hello, world'"; return 1; }
  (cd "$d" && sh scripts/test.sh >/dev/null 2>&1) || { echo "scripts/test.sh exited non-zero"; return 1; }
  return 0
}

# ---------------------------------------------------------------------------
[[ "${PI_E2E_LIB:-}" == 1 ]] && return 0

# ---------------------------------------------------------------------------
# Arguments and run identity
# ---------------------------------------------------------------------------
usage() { echo "usage: scripts/pi-e2e.sh [--dry-run] [--keep]   (env: PI_E2E_REPO PI_E2E_INTERVAL PI_E2E_MAX_MIN PI_E2E_GOAL PI_E2E_SUPERENV_EXTRA)" >&2; exit 2; }
DRY=0; KEEP=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --keep)    KEEP=1; shift ;;
    *) echo "pi-e2e: unknown arg: $1" >&2; usage ;;
  esac
done

STAMP="$(date -u +%Y%m%d-%H%M%S)"
SLUG="pi-e2e-$STAMP"
INTERVAL="${PI_E2E_INTERVAL:-2m}"
MAX_MIN="${PI_E2E_MAX_MIN:-90}"
GOAL="${PI_E2E_GOAL:-Add scripts/hello.sh (POSIX sh) that prints exactly: hello, world — and scripts/test.sh (POSIX sh) that runs it and exits non-zero unless the output matches exactly. Keep it to ONE implementation plan; no other files beyond the two scripts and the plan-tree bookkeeping.}"
RUN_DIR="${TMPDIR:-/tmp}/pi-e2e-$STAMP"
REPORT="$ROOT/pi-e2e-report.md"
CLONE="$RUN_DIR/repo"
REPO_SLUG="${PI_E2E_REPO:-}"
PLAN=""; LOOP_FILE=""; ENV_FILE=""; TICK_LOG=""; PR_BASE=0
T0=$(date +%s)

# ---------------------------------------------------------------------------
# Report framing (same shape as pi-smoke.sh: sections, fenced output, a Result line)
# ---------------------------------------------------------------------------
PASS=0; FAIL=0; REPORT_OPEN=0
report_open() {
  [[ "$REPORT_OPEN" == 1 ]] && return 0
  REPORT_OPEN=1; mkdir -p "$RUN_DIR"
  {
    echo "# superagent Pi e2e report"
    echo
    echo "- date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "- host: $(uname -a)"
    echo "- plugin repo: $ROOT ($(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo 'no git'))"
    echo "- pi: $(pi --version 2>&1 | head -1)   pi-subagents: ${SUBAGENTS_VERSION:-absent}"
    echo "- remote: $REPO_SLUG   slug: $SLUG   interval: $INTERVAL   ceiling: ${MAX_MIN}m"
    echo "- run dir: $RUN_DIR"
    echo
  } >"$REPORT"
}
report_section() { report_open; { echo "## $1"; echo; } >>"$REPORT"; echo "pi-e2e: == $1"; }
report_note()    { report_open; echo "$1" >>"$REPORT"; }
report_pass()    { PASS=$((PASS+1)); { echo; echo "**Result: PASS** — $1"; echo; } >>"$REPORT"; echo "pi-e2e: PASS — $1"; }
report_fail()    { FAIL=$((FAIL+1)); { echo; echo "**Result: FAIL** — $1"; echo; } >>"$REPORT"; echo "pi-e2e: FAIL — $1" >&2; }
# report_cmd <expected-substring-or-empty> <cmd...> — runs, records, returns non-zero on failure.
report_cmd() {
  local expect="$1"; shift
  local out rc
  { echo '```'; printf '$ %s\n' "$*"; echo '```'; } >>"$REPORT"
  out="$("$@" 2>&1)"; rc=$?
  if [[ "${#out}" -gt 6000 ]]; then out="${out:0:3000}
  [... truncated ...]
${out: -2500}"; fi
  { echo; echo '```'; printf '%s\n' "$out"; echo '```'; echo; } >>"$REPORT"
  [[ $rc -ne 0 ]] && { report_fail "exit $rc: $*"; return 1; }
  if [[ -n "$expect" ]] && ! printf '%s' "$out" | grep -qi -- "$expect"; then report_fail "expected output containing: $expect"; return 1; fi
  return 0
}

# ---------------------------------------------------------------------------
# Phase 0 — preflight (nothing created)
# ---------------------------------------------------------------------------
SUBAGENTS_VERSION=""
phase_preflight() {
  local missing=() c
  for c in pi gh git python3; do command -v "$c" >/dev/null 2>&1 || missing+=("$c"); done
  if [[ "$(uname -s)" == Darwin ]]; then command -v launchctl >/dev/null 2>&1 || missing+=(launchctl)
  else command -v systemctl >/dev/null 2>&1 || missing+=(systemctl); fi
  [[ ${#missing[@]} -eq 0 ]] || { echo "pi-e2e: missing prerequisite(s): ${missing[*]}" >&2; return 2; }
  gh auth status >/dev/null 2>&1 || { echo "pi-e2e: gh is not authenticated (gh auth login)" >&2; return 2; }
  "$SCRIPTS/build-pi-skills.sh" --check >/dev/null 2>&1 || { echo "pi-e2e: pi/ build is stale — run scripts/build-pi-skills.sh" >&2; return 2; }
  if [[ -z "$REPO_SLUG" ]]; then
    local owner; owner="$(gh api user -q .login 2>/dev/null || true)"
    [[ -n "$owner" ]] || { echo "pi-e2e: cannot resolve the gh user for the default PI_E2E_REPO" >&2; return 2; }
    REPO_SLUG="$owner/superagent-pi-e2e"
  fi
  [[ "$REPO_SLUG" == */* ]] || { echo "pi-e2e: PI_E2E_REPO must be <owner>/<name> (got '$REPO_SLUG')" >&2; return 2; }
  SUBAGENTS_VERSION="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$HOME/.pi/agent/npm/node_modules/pi-subagents/package.json" 2>/dev/null | head -1)"
  [[ -n "$SUBAGENTS_VERSION" ]] || echo "pi-e2e: WARN pi-subagents not installed — SDD children run sequentially without pins (SUPER_PI_SUBAGENTS=recommended)" >&2
  local js; js="$("$SCRIPTS/status.sh" --json 2>/dev/null || echo '[]')"
  [[ -z "$(e2e_status_field "$js" "$SLUG" status)" ]] || { echo "pi-e2e: a loop is already registered under $SLUG" >&2; return 2; }
  return 0
}

print_plan() {
  echo "pi-e2e: would run:"
  echo "  remote:    $REPO_SLUG  (reset to an orphan commit; never deleted)"
  echo "  slug:      $SLUG"
  echo "  interval:  $INTERVAL   ceiling: ${MAX_MIN}m   keep clone: $KEEP"
  echo "  run dir:   $RUN_DIR"
  echo "  goal:      $GOAL"
  echo "  phases:    provision → init → supergoal → launch.sh (arm) → watch status.sh until DONE → assert → cleanup"
}

# ---------------------------------------------------------------------------
main() {
  phase_preflight || exit $?
  print_plan
  if [[ "$DRY" == 1 ]]; then echo "[dry-run] nothing created or armed."; exit 0; fi
  echo "pi-e2e: phases not implemented yet" >&2; exit 1
}
main

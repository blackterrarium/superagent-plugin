#!/usr/bin/env bash
# bootstrap.sh — one-time external-mode bootstrap for a superagent loop.
#
# Runs superagent form (B) with --driver=external via `claude -p`. That
# path (superloop L2) creates the loop-status file (FRESH START) if none exists,
# prints the exact scheduler entry to create, and runs the first tick. We ask it
# to also print a machine-readable `LOOP_FILE=<abs path>` line so it can be fed
# straight into install-timer.sh.
#
# Inputs:
#   $1            <PLAN.md> — the goal's ROOT seed/master plan (repo-relative or absolute)
#   REPO          primary checkout root (default: derived)
#   TICK_TIMEOUT  optional first-tick wall-clock cap, seconds (default: none/unlimited)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
[[ -n "$REPO" ]] || { echo "superagent: set REPO or run from inside the target repo" >&2; exit 1; }

PLAN="${1:-}"
if [[ -z "$PLAN" ]]; then
  echo "usage: bootstrap.sh <PLAN.md>   (root seed/master plan)" >&2
  exit 2
fi

# Optional first-tick cap: positive integer => wrap in `timeout`; unset/empty/0 => no cap.
TICK_TIMEOUT="${TICK_TIMEOUT:-}"
TIMEOUT_CMD=()
if [[ "$TICK_TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
  TIMEOUT_CMD=(timeout "$TICK_TIMEOUT")
fi

if [[ -f "$REPO/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "$REPO/.env"
  set +a
fi

# Ensure gh is authenticated (exported so the CLI child inherits GH_TOKEN); the
# first tick opens/merges a PR, so abort loudly if gh cannot authenticate.
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
ensure_claude_bin || exit 5
ensure_gh_auth || exit 4

PROMPT="Invoke the superagent:superagent skill (Skill tool) and run superagent in form (B) with <PLAN.md>=${PLAN} and --driver=external. If no loop-status file exists yet, create it (FRESH START); print the exact scheduler entry to create; then run the first tick. Finally, on a line by itself, print: LOOP_FILE=<absolute path to the loop-status file you created or found>."

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "bootstrap: ANTHROPIC_API_KEY not set (expected in $REPO/.env)" >&2
  exit 3
fi
( cd "$REPO" && "${TIMEOUT_CMD[@]+"${TIMEOUT_CMD[@]}"}" claude -p "$PROMPT" \
    --allowedTools "Read,Edit,Bash,Task" )

echo
echo "Next: capture the LOOP_FILE=... line above, then run:"
echo "  $SCRIPT_DIR/install-timer.sh <goal-slug> <LOOP_FILE>"

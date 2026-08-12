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
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
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
load_superenv "$REPO"
HARNESS="$(superagent_harness)" || exit 6
ensure_cli_bin || exit 5
ensure_gh_auth || exit 4

if [[ "$HARNESS" == cursor ]]; then
  SKILLS_ROOT="$PLUGIN_ROOT/cursor"
  if [[ ! -f "$SKILLS_ROOT/skills/superagent/SKILL.md" ]]; then
    echo "bootstrap: Cursor build missing at $SKILLS_ROOT (run scripts/build-cursor-skills.sh)" >&2
    exit 7
  fi
else
  SKILLS_ROOT="$PLUGIN_ROOT"
fi

# Slash commands are unavailable in headless print mode, so open the skill file
# directly (superloop L2, Driver B) rather than invoking it by name — on Cursor a
# disable-model-invocation skill is invisible to model-driven lookup (verified),
# and on Claude Code the Skill-tool semantics in headless print mode are
# unverified, so the proven file-read entry point is used on both (matches
# superagent-tick.sh). The loop's own internal superagent:superplan /
# superagent:superrun dispatches still go through the skill mechanism once the
# session is running, so the plugin must still be installed AND enabled (claude)
# or passed via --plugin-dir (cursor) for this headless session.
PROMPT="Read ${SKILLS_ROOT}/skills/superagent/SKILL.md and run superagent in form (B) with <PLAN.md>=${PLAN} and --driver=external. If no loop-status file exists yet, create it (FRESH START); print the exact scheduler entry to create; then run the first tick. Finally, on a line by itself, print: LOOP_FILE=<absolute path to the loop-status file you created or found>."

if [[ "$HARNESS" == cursor ]]; then
  if [[ -z "${CURSOR_API_KEY:-}" ]]; then
    echo "bootstrap: note: CURSOR_API_KEY not set (no $REPO/.env entry); relying on the Cursor CLI's own stored login" >&2
  fi
  ( cd "$REPO" && "${TIMEOUT_CMD[@]+"${TIMEOUT_CMD[@]}"}" "$SUPERAGENT_CURSOR_BIN" -p "$PROMPT" \
      --trust --force --plugin-dir "$SKILLS_ROOT" --output-format text )
else
  if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "bootstrap: ANTHROPIC_API_KEY not set (expected in $REPO/.env)" >&2
    exit 3
  fi
  ( cd "$REPO" && "${TIMEOUT_CMD[@]+"${TIMEOUT_CMD[@]}"}" claude -p "$PROMPT" \
      --allowedTools "Read,Edit,Write,Bash,Task,Skill" )
fi

echo
echo "Next: capture the LOOP_FILE=... line above, then run:"
echo "  $SCRIPT_DIR/install-timer.sh <goal-slug> <LOOP_FILE>"

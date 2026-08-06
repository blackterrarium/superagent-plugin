#!/usr/bin/env bash
# superagent-tick.sh — fire exactly ONE external-mode superagent tick in a FRESH
# CLI session (no context accumulation across ticks). Invoked by an OS scheduler
# (systemd user timer / cron). Runs the tick via `claude -p`.
#
# All loop state lives in the gitignored loop-status file, so every tick is
# stateless: read the file, run one tick, write the file, exit. Never resume a
# prior session — a fresh process per tick is what keeps the context bounded and
# lets the loop run straight through to DONE (see superloop L4: the context
# handoff gate is a no-op in external mode).
#
# Inputs (env or args; env wins for scheduler use):
#   LOOP_FILE     absolute path to the loop-status file (or $1)
#   REPO          primary checkout root                    (default: derived)
#   TICK_TIMEOUT  optional per-tick wall-clock cap, seconds (default: none/unlimited)
#   LOG_FILE      driver log path                          (default: /tmp/superagent-<loop>.log)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO="${REPO:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
[[ -n "$REPO" ]] || { echo "superagent: set REPO or run from inside the target repo" >&2; exit 1; }

LOOP_FILE="${LOOP_FILE:-${1:-}}"
if [[ -z "$LOOP_FILE" ]]; then
  echo "superagent-tick: LOOP_FILE not set (pass as \$1 or env)" >&2
  exit 2
fi

# Optional per-tick wall-clock cap. When TICK_TIMEOUT is a positive integer, wrap
# the CLI in `timeout`; otherwise (unset/empty/0/none) run with NO cap so long
# CI-push ticks are never killed mid-flight. The overlap lock (L3) still serializes
# ticks, so an uncapped tick is safe.
TICK_TIMEOUT="${TICK_TIMEOUT:-}"
TIMEOUT_CMD=()
if [[ "$TICK_TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
  TIMEOUT_CMD=(timeout "$TICK_TIMEOUT")
fi
LOG_FILE="${LOG_FILE:-/tmp/superagent-$(basename "$LOOP_FILE" .md).log}"
# Output format: stream (default) = live incremental console output; text = final only.
TICK_OUTPUT_FORMAT="${TICK_OUTPUT_FORMAT:-stream}"

# Load the API key from .env (repo policy: keys live in .env only).
if [[ -f "$REPO/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "$REPO/.env"
  set +a
fi

# Ensure gh is authenticated and export GH_TOKEN so the CLI child inherits it
# (the tick's sandbox blocks gh from reading its own config). Fail LOUDLY if not,
# so a misconfigured host does not silently break every superrun CI/PR step.
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
# Put the claude binary on PATH (systemd/cron use a minimal PATH without
# ~/.local/bin) and fail fast if it's still missing, then verify gh auth.
ensure_claude_bin || exit 5
ensure_gh_auth || exit 4

load_superenv "$REPO"
# Model: always passed explicitly (--model) so the tick uses THIS model regardless
# of the CLI's own configured default.
# TICK_MODEL > SUPER_MODEL_SUPERVISOR > opus; a headless tick has no session
# model, so "inherit" also resolves to opus.
TICK_MODEL="${TICK_MODEL:-${SUPER_MODEL_SUPERVISOR:-opus}}"
[[ "$TICK_MODEL" == "inherit" ]] && TICK_MODEL="opus"

# Slash commands are unavailable in headless print mode, so open the skill file
# directly (superloop L2, Driver B) rather than invoking it by name — Skill-tool
# semantics for a disable-model-invocation skill in headless print mode are
# unverified, so the proven file-read entry point is used instead. The loop's own
# internal superagent:superplan / superagent:superrun dispatches still go through
# the Skill tool once the session is running, so the superagent plugin must still
# be installed AND enabled for this headless session. Non-interactive: the tick
# must never block on a question.
PROMPT="Read ${PLUGIN_ROOT}/skills/superagent/SKILL.md and execute exactly ONE --tick on loop file ${LOOP_FILE}, in unattended/non-interactive mode: NEVER call AskQuestion/AskUserQuestion; if a decision needs the user, write the ## Pending decision block, set status to WAITING FOR INPUT, and exit per the skill. Then stop."

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

echo "=== $(ts) superagent-tick model=${TICK_MODEL} output=${TICK_OUTPUT_FORMAT} loop=${LOOP_FILE} timeout=${TICK_TIMEOUT:-none} ===" >>"$LOG_FILE"
# Not probed (no live check) — the prompt below reads skills/superagent/SKILL.md
# directly at PLUGIN_ROOT. The loop's own internal superagent:superplan /
# superagent:superrun dispatches still go through the Skill tool once running, so
# the superagent plugin must still be installed AND enabled for this headless
# session. If the tick fails opaquely, check both: the file exists at
# PLUGIN_ROOT, and the plugin is enabled.
echo "    requires: superagent plugin installed+enabled for this session (tick entry reads skills/superagent/SKILL.md directly at ${PLUGIN_ROOT}; superagent:superplan / superagent:superrun still resolved via Skill tool)" >>"$LOG_FILE"

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "superagent-tick: ANTHROPIC_API_KEY not set (expected in $REPO/.env)" >&2
  exit 3
fi

rc=0
if [[ "$TICK_OUTPUT_FORMAT" == stream ]]; then
  # Live streaming (raw stream-json).
  ( cd "$REPO" && "${TIMEOUT_CMD[@]+"${TIMEOUT_CMD[@]}"}" claude -p "$PROMPT" \
      --model "$TICK_MODEL" --allowedTools "Read,Edit,Write,Bash,Task,Skill" --output-format stream-json --verbose ) \
    >>"$LOG_FILE" 2>&1 || rc=$?
else
  ( cd "$REPO" && "${TIMEOUT_CMD[@]+"${TIMEOUT_CMD[@]}"}" claude -p "$PROMPT" \
      --model "$TICK_MODEL" --allowedTools "Read,Edit,Write,Bash,Task,Skill" ) \
    >>"$LOG_FILE" 2>&1 || rc=$?
fi

echo "=== $(ts) superagent-tick exit=${rc} ===" >>"$LOG_FILE"
exit "$rc"

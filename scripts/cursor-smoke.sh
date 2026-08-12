#!/usr/bin/env bash
# cursor-smoke.sh — smoke-test the Cursor build of the superagent plugin.
#
# Run this ON A MACHINE WITH THE CURSOR CLI installed (https://cursor.com/install), from a clone
# of this repository:
#
#   bash scripts/cursor-smoke.sh
#
# It needs Cursor CLI auth (run `agent login` once, or export CURSOR_API_KEY). It makes NO file
# changes outside this repo clone (tests run without --force, so the agent can only propose
# edits). Everything — commands, exit codes, output — is captured into cursor-smoke-report.md
# at the repo root. When it finishes, send that file back to the Claude Code session that is
# driving the Cursor port (paste it, or attach it).
#
# Exit code: 0 even when individual tests fail — failures ARE the data; the report is the result.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="$ROOT/cursor-smoke-report.md"
PLUGIN="$ROOT/cursor"
TIMEOUT_SECS=240

# Rebuild the cursor/ tree if it is missing (e.g. a clone made before it was committed).
if [ ! -d "$PLUGIN" ]; then
  bash "$ROOT/scripts/build-cursor-skills.sh" || {
    echo "cursor-smoke: cursor/ missing and build failed; aborting" >&2
    exit 1
  }
fi

# Find the Cursor CLI binary: current installs ship `agent`, older ones `cursor-agent`.
BIN=""
for c in agent cursor-agent; do
  if command -v "$c" >/dev/null 2>&1; then BIN="$c"; break; fi
done

# Optional timeout wrapper (macOS may lack `timeout` unless coreutils is installed).
TCMD=()
if command -v timeout >/dev/null 2>&1; then TCMD=(timeout "$TIMEOUT_SECS")
elif command -v gtimeout >/dev/null 2>&1; then TCMD=(gtimeout "$TIMEOUT_SECS"); fi

{
  echo "# superagent Cursor smoke report"
  echo
  echo "- date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "- host: $(uname -a)"
  echo "- repo: $ROOT ($(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo 'no git'))"
  echo "- cursor cli binary: ${BIN:-NOT FOUND}"
  if [ -n "$BIN" ]; then echo "- cli version: $($BIN --version 2>&1 | head -1)"; fi
  echo "- timeout wrapper: ${TCMD[*]:-none (tests run uncapped)}"
  echo
} >"$REPORT"

PASS=0; FAIL=0

# run_test <name> <expected-substring-or-empty> <cmd...>
run_test() {
  local name="$1" expect="$2"; shift 2
  local out rc verdict
  echo "## $name" >>"$REPORT"
  { echo; echo '```'; printf '$ %s\n' "$*"; echo '```'; } >>"$REPORT"
  out="$("${TCMD[@]+"${TCMD[@]}"}" "$@" 2>&1)"; rc=$?
  # Truncate very long outputs but keep head AND tail (errors often print last).
  if [ "${#out}" -gt 6000 ]; then
    out="${out:0:3000}
  [... truncated ...]
${out: -2500}"
  fi
  verdict="PASS"
  [ $rc -ne 0 ] && verdict="FAIL (exit $rc)"
  if [ -n "$expect" ] && ! printf '%s' "$out" | grep -qi -- "$expect"; then
    verdict="FAIL (expected output containing: $expect)"
    [ $rc -ne 0 ] && verdict="FAIL (exit $rc; expected output containing: $expect)"
  fi
  case "$verdict" in PASS) PASS=$((PASS+1));; *) FAIL=$((FAIL+1));; esac
  { echo; echo "**Result: $verdict**"; echo; echo '```'; printf '%s\n' "$out"; echo '```'; echo; } >>"$REPORT"
  echo "cursor-smoke: $name → $verdict"
}

if [ -z "$BIN" ]; then
  {
    echo "## FATAL"
    echo
    echo "No Cursor CLI binary found (tried: agent, cursor-agent)."
    echo "Install it: \`curl https://cursor.com/install -fsS | bash\` — then re-run this script."
  } >>"$REPORT"
  echo "cursor-smoke: FATAL — no Cursor CLI found. Report written to $REPORT" >&2
  exit 0
fi

# T3–T5 run in a NEUTRAL, EMPTY workspace — never the repo. With the repo as the workspace the
# agent can pass every test by simply reading the skill files off disk, which proves nothing about
# the plugin mechanism (this bit v1 of this script). In an empty workspace, --plugin-dir is the
# ONLY way the agent can see these skills.
NEUTRAL="$(mktemp -d)"
trap 'rm -rf "$NEUTRAL"' EXIT
echo "cursor-smoke neutral workspace — intentionally empty" >"$NEUTRAL/README.txt"

# T1 — CLI sanity: headless print mode + auth work at all.
run_test "T1 headless sanity" "SMOKE-OK" \
  "$BIN" -p --output-format text "Reply with exactly: SMOKE-OK"

# T2 — model list (also the data we need to map SUPER_MODEL_* keys to Cursor model names).
run_test "T2 model list" "" \
  "$BIN" --list-models

# T3 — skill enumeration (INFORMATIONAL — no expected substring: some harnesses load skills
# without enumerating them; T4/T5 are the load-bearing tests).
run_test "T3 skill enumeration (informational)" "" \
  "$BIN" -p --trust --plugin-dir "$PLUGIN" --output-format text --workspace "$NEUTRAL" \
  "List the names of ALL skills available to you, including plugin-provided ones. Output only the names, one per line. If none, output NONE."

# T4 — model-invoked skill + relative file access: the probe skill reports plugin-root facts.
# In the neutral workspace this can only succeed through the plugin mechanism.
run_test "T4 probe skill (neutral workspace)" "PROBE-BEGIN" \
  "$BIN" -p --trust --plugin-dir "$PLUGIN" --output-format text --workspace "$NEUTRAL" \
  "Run the cursor smoke probe skill (cursor-smoke-probe) and output its report. If you cannot find any such skill, output exactly: NO-SUCH-SKILL"

# T5 — the REAL external-tick mechanism: a file-read prompt, exactly like the production driver.
# `superagent` carries disable-model-invocation, which on Cursor makes it invisible to model-driven
# skill lookup (verified in smoke run 2) — the external tick therefore never invokes it by name;
# it asks the session to read the SKILL.md directly. With no PLAN.md and no loop file, the skill's
# hard gate must fire, and its exact message exists only inside that file.
run_test "T5 tick file-read + superagent hard gate" "requires a master plan" \
  "$BIN" -p --trust --plugin-dir "$PLUGIN" --output-format text --workspace "$NEUTRAL" \
  "Read the file $PLUGIN/skills/superagent/SKILL.md and follow it: execute exactly ONE tick with no arguments (no PLAN.md, no loop file), in unattended/non-interactive mode. Show the skill's response. If you cannot read that file, output exactly: CANNOT-READ."

{
  echo "## Summary"
  echo
  echo "- PASS: $PASS"
  echo "- FAIL: $FAIL"
  echo
  echo "Send this file back to the Claude Code session driving the Cursor port."
} >>"$REPORT"

echo
echo "cursor-smoke: done — $PASS pass, $FAIL fail."
echo "cursor-smoke: report written to: $REPORT"
echo "cursor-smoke: send cursor-smoke-report.md back to the Claude Code session (paste or attach)."

#!/usr/bin/env bash
# codex-smoke.sh — smoke-test the codex build of the superagent plugin.
#
# Run this ON A MACHINE WITH THE CODEX CLI installed, from a clone of this repository:
#
#   bash scripts/codex-smoke.sh
#
# It needs Codex CLI auth (`codex login` once, or export OPENAI_API_KEY). It makes NO file
# changes outside this repo clone (tests run without --yolo, so the agent runs in the default
# read-only-ish sandbox). Everything — commands, exit codes, output — is captured into
# codex-smoke-report.md at the repo root. When it finishes, send that file back to the
# Claude Code session that is driving the Codex port (paste it, or attach it).
#
# Exit code: 0 even when individual tests fail — failures ARE the data; the report is the result.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="$ROOT/codex-smoke-report.md"
PLUGIN="$ROOT/codex"
TIMEOUT_SECS=240

# Rebuild the codex/ tree if it is missing (e.g. a clone made before it was committed).
if [ ! -d "$PLUGIN" ]; then
  bash "$ROOT/scripts/build-codex-skills.sh" || {
    echo "codex-smoke: codex/ missing and build failed; aborting" >&2
    exit 1
  }
fi

# Find the Codex CLI binary: only `codex`.
BIN=""
if command -v codex >/dev/null 2>&1; then BIN="codex"; fi

# Optional timeout wrapper (macOS may lack `timeout` unless coreutils is installed).
TCMD=()
if command -v timeout >/dev/null 2>&1; then TCMD=(timeout "$TIMEOUT_SECS")
elif command -v gtimeout >/dev/null 2>&1; then TCMD=(gtimeout "$TIMEOUT_SECS"); fi

{
  echo "# superagent Codex smoke report"
  echo
  echo "- date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "- host: $(uname -a)"
  echo "- repo: $ROOT ($(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo 'no git'))"
  echo "- codex cli binary: ${BIN:-NOT FOUND}"
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
  echo "codex-smoke: $name → $verdict"
}

if [ -z "$BIN" ]; then
  {
    echo "## FATAL"
    echo
    echo "No Codex CLI binary found (tried: codex)."
    echo "Install it: \`npm install -g @openai/codex\` — then re-run this script."
  } >>"$REPORT"
  echo "codex-smoke: FATAL — no Codex CLI found. Report written to $REPORT" >&2
  exit 0
fi

# T1–T6 run in a NEUTRAL, EMPTY workspace — never the repo. With the repo as the workspace the
# agent can pass every test by simply reading the skill files off disk, which proves nothing about
# the plugin mechanism. In an empty workspace, the plugin mechanism is the ONLY way the agent can
# see these skills.
NEUTRAL="$(mktemp -d)"
trap 'rm -rf "$NEUTRAL"' EXIT
echo "codex-smoke neutral workspace — intentionally empty" >"$NEUTRAL/README.txt"

# T1 — CLI sanity: headless exec + auth work at all.
run_test "T1 headless sanity" "SMOKE-OK" \
  "$BIN" exec --skip-git-repo-check -C "$NEUTRAL" "Reply with exactly: SMOKE-OK"

# T2 — marketplace + plugin install (the skill-delivery mechanism; failure = design-input change).
run_test "T2 marketplace add" "" \
  "$BIN" plugin marketplace add "$PLUGIN"

# T2b — plugin add
run_test "T2b plugin add" "" \
  "$BIN" plugin add superagent@superagent

# T3 — skill enumeration from a neutral workspace (informational).
run_test "T3 skill enumeration (informational)" "" \
  "$BIN" exec --skip-git-repo-check -C "$NEUTRAL" \
  "List the names of ALL skills available to you, including plugin-provided ones. Output only the names, one per line. If none, output NONE."

# T4a — probe skill: plugin mechanism + relative file access.
run_test "T4a probe skill (neutral workspace)" "PROBE-BEGIN" \
  "$BIN" exec --skip-git-repo-check -C "$NEUTRAL" \
  "Run the codex smoke probe skill (codex-smoke-probe) and output its report. If you cannot find any such skill, output exactly: NO-SUCH-SKILL"

# T4b — spawn_agent availability (failure = design-input change for subagent mapping).
run_test "T4b spawn_agent available" "SPAWN-OK" \
  "$BIN" exec --skip-git-repo-check -C "$NEUTRAL" \
  "Do you have a tool named spawn_agent (or an equivalent tool for spawning a sub-agent with its own model/reasoning_effort)? If yes, spawn one agent with the message 'Reply with exactly: CHILD-OK', wait for its result, then output exactly: SPAWN-OK <its reply>. If no such tool exists, output exactly: NO-SPAWN-TOOL."

# T5 — the REAL external-tick mechanism: file-read prompt, superagent hard gate.
run_test "T5 tick file-read + superagent hard gate" "requires a master plan" \
  "$BIN" exec --skip-git-repo-check -C "$NEUTRAL" \
  "Read the file $PLUGIN/plugins/superagent/skills/superagent/SKILL.md and follow it: execute exactly ONE tick with no arguments (no PLAN.md, no loop file), in unattended/non-interactive mode. Show the skill's response. If you cannot read that file, output exactly: CANNOT-READ."

# T6 — effort override pass-through on this CLI version.
run_test "T6 effort override accepted" "SMOKE-OK" \
  "$BIN" exec --skip-git-repo-check -C "$NEUTRAL" -c model_reasoning_effort=low "Reply with exactly: SMOKE-OK"

{
  echo "## Summary"
  echo
  echo "- PASS: $PASS"
  echo "- FAIL: $FAIL"
  echo
  echo "Send this file back to the Claude Code session driving the Codex port."
  echo "Note: T2/T4b failures indicate design-input changes — do not patch around them."
  echo "They signal changes needed in skill delivery or subagent mapping per the spec."
} >>"$REPORT"

echo
echo "codex-smoke: done — $PASS pass, $FAIL fail."
echo "codex-smoke: report written to: $REPORT"
echo "codex-smoke: send codex-smoke-report.md back to the Claude Code session (paste or attach)."

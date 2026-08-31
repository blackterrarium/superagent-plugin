#!/usr/bin/env bash
# pi-smoke.sh — smoke-test the Pi build of the superagent plugin.
#
# Run this ON A MACHINE WITH THE PI CLI installed, from a clone of this repository:
#
#   bash scripts/pi-smoke.sh
#
# It needs Pi CLI auth (an authenticated ~/.pi/agent/settings.json, or the equivalent env vars).
# Live tests make no file changes outside a throwaway temp workspace (never this repo clone).
# Everything — commands, exit codes, output — is captured into
# pi-smoke-report.md at the repo root. When it finishes, send that file back to the
# Claude Code session that is driving the Pi port (paste it, or attach it).
#
# Exit code: 0 even when individual tests fail — failures ARE the data; the report is the result.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="$ROOT/pi-smoke-report.md"
TIMEOUT_SECS=240

# Find the Pi CLI binary: only `pi`.
BIN=""
if command -v pi >/dev/null 2>&1; then BIN="pi"; fi

# Optional timeout wrapper (macOS may lack `timeout` unless coreutils is installed).
TCMD=()
if command -v timeout >/dev/null 2>&1; then TCMD=(timeout "$TIMEOUT_SECS")
elif command -v gtimeout >/dev/null 2>&1; then TCMD=(gtimeout "$TIMEOUT_SECS"); fi

{
  echo "# superagent Pi smoke report"
  echo
  echo "- date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "- host: $(uname -a)"
  echo "- repo: $ROOT ($(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo 'no git'))"
  echo "- pi cli binary: ${BIN:-NOT FOUND}"
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
  echo "pi-smoke: $name → $verdict"
}

if [ -z "$BIN" ]; then
  {
    echo "## FATAL"
    echo
    echo "No Pi CLI binary found (tried: pi)."
    echo "Install it: \`npm install -g @earendil-works/pi-coding-agent\` — then re-run this script."
  } >>"$REPORT"
  echo "pi-smoke: FATAL — no Pi CLI found. Report written to $REPORT" >&2
  exit 0
fi

NEUTRAL="$(mktemp -d)"; trap 'rm -rf "$NEUTRAL"' EXIT
( cd "$NEUTRAL" && git init -q )
PI_MODEL="${PI_SMOKE_MODEL:-}"            # optional: provider/id to pin; empty = the CLI default
MODEL_ARGS=(); [ -n "$PI_MODEL" ] && MODEL_ARGS=(--model "$PI_MODEL")
SUBAGENTS_VERSION="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$HOME/.pi/agent/npm/node_modules/pi-subagents/package.json" 2>/dev/null | head -1)"
echo "- pi-subagents: ${SUBAGENTS_VERSION:-absent}" >>"$REPORT"
echo "- superpowers package: $(pi list 2>/dev/null | grep -c superpowers)" >>"$REPORT"

# P1 — exit status on a failed turn (decides the bridge's 3-vs-4 mapping; informational).
run_test "P1 exit status on bad model (informational)" "" \
  "$BIN" -p --no-session --model "nonexistent-provider/no-such-model" "Reply with exactly: NEVER"

# P2 — --skill delivery + probe skill + superpowers listing.
run_test "P2 --skill delivery (probe skill)" "PROBE-BEGIN" \
  bash -c "cd '$NEUTRAL' && echo 'Run the pi smoke probe skill (pi-smoke-probe) and output its report. If you cannot find any such skill, output exactly: NO-SUCH-SKILL' | '$BIN' -p --no-session --approve --skill '$ROOT/pi/skills' ${MODEL_ARGS[*]:-}"

# P3 — pi-subagents blocking child, model pin, nested foreground wait (skipped when absent).
if [ -n "$SUBAGENTS_VERSION" ]; then
  mkdir -p "$NEUTRAL/.pi/agents"
  cat >"$NEUTRAL/.pi/agents/smoke-child.md" <<'EOF'
---
name: smoke-child
description: smoke child
tools: bash
async: false
---
Reply with exactly what the prompt asks. Also append on a second line: MODEL=<the model id you are running as, if you know it>.
EOF
  cat >"$NEUTRAL/.pi/agents/smoke-parent.md" <<'EOF'
---
name: smoke-parent
description: smoke parent
async: false
allowNestedSubagents: true
---
Use the subagent tool with agent smoke-child and async false, prompt "Reply with exactly: GRANDCHILD-OK". Output exactly: NEST-OK <its reply>.
EOF
  run_test "P3a subagent async:false returns child output" "SUB-OK CHILD-OK" \
    bash -c "cd '$NEUTRAL' && echo 'Use the subagent tool with agent smoke-child, async false, prompt: Reply with exactly: CHILD-OK. Then output exactly: SUB-OK <its first line>.' | '$BIN' -p --no-session --approve ${MODEL_ARGS[*]:-}"
  run_test "P3c nested foreground wait" "NEST-OK GRANDCHILD-OK" \
    bash -c "cd '$NEUTRAL' && echo 'Use the subagent tool with agent smoke-parent, async false, prompt: go. Output its reply verbatim.' | '$BIN' -p --no-session --approve ${MODEL_ARGS[*]:-}"
else
  echo "## P3 pi-subagents probes — SKIPPED (package absent)" >>"$REPORT"
fi

# P4 — --tools allowlist excludes extension tools; no flag includes them (informational).
run_test "P4a --tools role set hides subagent" "" \
  bash -c "echo 'List the names of every tool you have, one per line, nothing else.' | '$BIN' -p --no-session --tools read,edit,write,bash,grep,find,ls ${MODEL_ARGS[*]:-}"
run_test "P4b no --tools shows extension tools" "" \
  bash -c "echo 'List the names of every tool you have, one per line, nothing else.' | '$BIN' -p --no-session ${MODEL_ARGS[*]:-}"

# T1 — bridge echo → pi with the new flags and SUPERAGENT_PI_SKILLS.
printf 'Reply with exactly: BRIDGE-ECHO-OK\n' >"$NEUTRAL/echo.txt"
run_test "T1 bridge → pi (role tools, --skill)" "BRIDGE-ECHO-OK" \
  env SUPERAGENT_PI_SKILLS="$ROOT/pi/skills" "$ROOT/scripts/role-bridge.sh" --harness pi --model "${PI_MODEL:-inherit}" --effort low --cwd "$NEUTRAL" --prompt-file "$NEUTRAL/echo.txt" --role smoke

# T2 — fan-out, three live echoes.
run_test "T2 bridge-fanout ×3" "=== PANELIST 3 exit=0 ===" \
  "$ROOT/scripts/bridge-fanout.sh" --harness pi --model "${PI_MODEL:-inherit}" --effort inherit --cwd "$NEUTRAL" --timeout 300 --prompt-file "$NEUTRAL/echo.txt" --prompt-file "$NEUTRAL/echo.txt" --prompt-file "$NEUTRAL/echo.txt"

# T3 — the REAL tick entry: file-read prompt drives the supervisor skill's hard gate.
run_test "T3 tick file-read + superagent hard gate" "requires a master plan" \
  bash -c "cd '$NEUTRAL' && echo 'Read the file $ROOT/pi/skills/superagent/SKILL.md and follow it: execute exactly ONE tick with no arguments (no PLAN.md, no loop file), in unattended/non-interactive mode. Show the skill response. If you cannot read that file, output exactly: CANNOT-READ.' | '$BIN' -p --no-session --approve --skill '$ROOT/pi/skills' ${MODEL_ARGS[*]:-}"

# T4 — relay definition round trip pi→codex (needs pi-subagents AND codex).
if [ -n "$SUBAGENTS_VERSION" ] && command -v codex >/dev/null 2>&1; then
  sed -e 's/<role>/implementer/g' -e 's/<KEY>/SUPER_MODEL_IMPLEMENTER/g' -e 's/<harness>/codex/g' \
      -e 's/<model>/inherit/g' -e 's/<effort>/low/g' -e '/^model: <relay-model>$/d' \
      -e "s#<bridge-path>#$ROOT/scripts/role-bridge.sh#g" "$ROOT/templates/super-role-pi-bridge-agent.md" >"$NEUTRAL/.pi/agents/super-implementer.md"
  export TMPDIR="$NEUTRAL/tmp"; mkdir -p "$TMPDIR"
  run_test "T4 relay definition round trip (pi→codex)" "RELAY-PROVEN" \
    bash -c "cd '$NEUTRAL' && out=\$(echo 'Use the subagent tool with agent super-implementer, async false, prompt: Reply with exactly: RELAY-OK. Output its reply verbatim.' | '$BIN' -p --no-session --approve ${MODEL_ARGS[*]:-}); echo \"\$out\"; ls '$TMPDIR'/superagent-bridge/implementer-*.log >/dev/null 2>&1 && [[ \"\$out\" == *RELAY-OK* ]] && echo RELAY-PROVEN"
else
  echo "## T4 relay round trip — SKIPPED (needs pi-subagents and codex)" >>"$REPORT"
fi

# T5 — build freshness (offline).
run_test "T5 build-pi-skills --check" "up to date" bash "$ROOT/scripts/build-pi-skills.sh" --check

{
  echo "## Summary"
  echo
  echo "- PASS: $PASS"
  echo "- FAIL: $FAIL"
  echo
  echo "Send this file back to the Claude Code session driving the Pi port."
  echo "Note: P2/P3a failures indicate design-input changes — do not patch around them."
  echo "They signal changes needed in skill delivery / SDD dispatch per the spec."
} >>"$REPORT"

echo
echo "pi-smoke: done — $PASS pass, $FAIL fail."
echo "pi-smoke: report written to: $REPORT"
echo "pi-smoke: send pi-smoke-report.md back to the Claude Code session (paste or attach)."

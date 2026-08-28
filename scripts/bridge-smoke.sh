#!/usr/bin/env bash
# bridge-smoke.sh — live probes for scripts/role-bridge.sh against real CLIs.
# Run on a machine with the CLIs installed; missing CLIs are reported as SKIP.
# Always exits 0; writes bridge-smoke-report.md at the repo root — failures are the data.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="$ROOT/bridge-smoke-report.md"
BRIDGE="$ROOT/scripts/role-bridge.sh"
WORK="$(mktemp -d)"
TIMEOUT_SECS=240
TCMD=()
if command -v timeout >/dev/null 2>&1; then TCMD=(timeout "$TIMEOUT_SECS")
elif command -v gtimeout >/dev/null 2>&1; then TCMD=(gtimeout "$TIMEOUT_SECS"); fi

{
  echo "# superagent bridge smoke report"
  echo
  echo "- date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "- host: $(uname -a)"
  echo "- repo: $ROOT ($(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo 'no git'))"
  for b in claude codex agent pi; do
    if command -v "$b" >/dev/null 2>&1; then echo "- $b: $("$b" --version 2>&1 | head -1)"; else echo "- $b: NOT FOUND"; fi
  done
  echo
} >"$REPORT"

PASS=0; FAIL=0; SKIP=0
# run_test <name> <required-binary-or-empty> <expected-substring> <cmd...>
run_test() {
  local name="$1" need="$2" expect="$3"; shift 3
  echo "## $name" >>"$REPORT"
  if [ -n "$need" ] && ! command -v "$need" >/dev/null 2>&1; then
    echo "SKIP (no $need on PATH)" >>"$REPORT"; echo >>"$REPORT"; SKIP=$((SKIP+1)); return
  fi
  local out rc
  out="$("${TCMD[@]+"${TCMD[@]}"}" "$@" 2>&1)"; rc=$?
  { echo; echo '```'; printf '$ %q ' "$@"; echo; echo "$out" | tail -40; echo "exit=$rc"; echo '```'; } >>"$REPORT"
  if [ "$rc" -eq 0 ] && [[ "$out" == *"$expect"* ]]; then echo "PASS" >>"$REPORT"; PASS=$((PASS+1))
  else echo "FAIL (expected substring: $expect)" >>"$REPORT"; FAIL=$((FAIL+1)); fi
  echo >>"$REPORT"
}

# T5 — nested claude: can `claude -p` run while CLAUDECODE is set (as it is inside a Claude Code
# session's Bash tool)? Both variants are recorded; the bridge unsets CLAUDECODE iff plain fails.
printf 'Reply with exactly: NESTED-OK\n' >"$WORK/nested.txt"
run_test "T5a nested claude -p (CLAUDECODE=1, plain)" claude "NESTED-OK" \
  env CLAUDECODE=1 claude -p --model haiku "$(cat "$WORK/nested.txt")"
run_test "T5b nested claude -p (CLAUDECODE unset)" claude "NESTED-OK" \
  env -u CLAUDECODE claude -p --model haiku "$(cat "$WORK/nested.txt")"

{ echo "---"; echo "PASS=$PASS FAIL=$FAIL SKIP=$SKIP"; } >>"$REPORT"
echo "bridge-smoke: PASS=$PASS FAIL=$FAIL SKIP=$SKIP — report: $REPORT"

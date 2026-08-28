#!/usr/bin/env bash
# bridge-smoke.sh — live probes for scripts/role-bridge.sh against real CLIs.
# Run on a machine with the CLIs installed; missing CLIs are reported as SKIP.
# Always exits 0; writes bridge-smoke-report.md at the repo root — failures are the data.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="$ROOT/bridge-smoke-report.md"
BRIDGE="$ROOT/scripts/role-bridge.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
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
  { echo; echo '```'; printf '$ '; printf '%q ' "$@"; echo; echo "$out" | tail -40; echo "exit=$rc"; echo '```'; } >>"$REPORT"
  if [[ "$out" == *"SKIP-OTHER-CLI-MISSING"* ]]; then echo "SKIP (other CLI not on PATH)" >>"$REPORT"; SKIP=$((SKIP+1))
  elif [[ "$out" == *"SKIP-LONG-NOT-REQUESTED"* ]]; then echo "SKIP (long probe not requested — set BRIDGE_SMOKE_LONG=1)" >>"$REPORT"; SKIP=$((SKIP+1))
  elif [ "$rc" -eq 0 ] && [[ "$out" == *"$expect"* ]]; then echo "PASS" >>"$REPORT"; PASS=$((PASS+1))
  else echo "FAIL (expected substring: $expect)" >>"$REPORT"; FAIL=$((FAIL+1)); fi
  echo >>"$REPORT"
}

# T1–T4 — role-bridge.sh per-harness echo probes: bridge to each harness with a trivial prompt
# and expect the sentinel back verbatim.
printf 'Reply with exactly: BRIDGE-ECHO-OK\n' >"$WORK/echo.txt"
run_test "T1 bridge → claude"  claude "BRIDGE-ECHO-OK" "$BRIDGE" --harness claude --model haiku        --effort low     --cwd "$WORK" --prompt-file "$WORK/echo.txt" --role smoke
run_test "T2 bridge → codex"   codex  "BRIDGE-ECHO-OK" "$BRIDGE" --harness codex  --model inherit      --effort low     --cwd "$WORK" --prompt-file "$WORK/echo.txt" --role smoke
run_test "T3 bridge → cursor"  agent  "BRIDGE-ECHO-OK" "$BRIDGE" --harness cursor --model inherit      --effort inherit --cwd "$WORK" --prompt-file "$WORK/echo.txt" --role smoke
run_test "T4 bridge → pi"      pi     "BRIDGE-ECHO-OK" "$BRIDGE" --harness pi     --model "${PI_SMOKE_MODEL:-openai/gpt-5}" --effort low --cwd "$WORK" --prompt-file "$WORK/echo.txt" --role smoke

# T5 — nested claude: can `claude -p` run while CLAUDECODE is set (as it is inside a Claude Code
# session's Bash tool)? Both variants are recorded; the bridge unsets CLAUDECODE iff plain fails.
printf 'Reply with exactly: NESTED-OK\n' >"$WORK/nested.txt"
run_test "T5a nested claude -p (CLAUDECODE=1, plain)" claude "NESTED-OK" \
  env CLAUDECODE=1 claude -p --model haiku "$(cat "$WORK/nested.txt")"
run_test "T5b nested claude -p (CLAUDECODE unset)" claude "NESTED-OK" \
  env -u CLAUDECODE claude -p --model haiku "$(cat "$WORK/nested.txt")"

# T6 — relay definition round trip under Claude Code: a throwaway repo with a generated
# super-implementer.md bridged to codex; the session must return the sentinel. The generated
# agent definition lives under $R/.claude/agents/, so `claude -p` must run with $R as cwd.
# Models: the outer session stands in for the SDD controller/loop tick, which runs on opus or
# sonnet in production — `--model sonnet` here, not haiku. <relay-model> tracks
# SUPER_BRIDGE_RELAY_MODEL in templates/superenv.default (sonnet); a haiku relay was measured to
# skip Bash entirely and answer the task prompt itself, which is what RELAY-PROVEN catches.
# Proof-of-dispatch: TMPDIR is pinned to a private dir for the child so role-bridge.sh (which
# derives its log dir from ${TMPDIR:-/tmp}) writes its implementer-*.log there; RELAY-PROVEN is
# only emitted when that log file exists AND the sentinel is in the session's own output — so a
# session that never actually dispatched the relay can't fake a pass. The other CLI's presence is
# checked inside the wrapped command (not an outer `if`) so a missing one shows as SKIP in the
# report instead of making the whole probe disappear.
R="$WORK/t6"; mkdir -p "$R/.claude/agents"; (cd "$R" && git init -q)
sed -e 's/<role>/implementer/g' -e 's/<KEY>/SUPER_MODEL_IMPLEMENTER/g' -e 's/<harness>/codex/g' \
    -e 's/<model>/inherit/g' -e 's/<effort>/low/g' -e 's/<relay-model>/sonnet/g' \
    -e "s#<bridge-path>#$BRIDGE#g" "$ROOT/templates/super-role-bridge-agent.md" >"$R/.claude/agents/super-implementer.md"
# NB: claude's --allowedTools takes a variadic arg list, so it greedily swallows any
# positional prompt that follows it; `--` stops that consumption at the prompt.
run_test "T6 relay definition round trip (claude→codex)" claude "RELAY-PROVEN" \
  bash -c 'command -v codex >/dev/null 2>&1 || { echo SKIP-OTHER-CLI-MISSING; exit 0; }
    mkdir -p "$1"
    out="$(cd "$2" && SUPERAGENT_BRIDGE="$3" TMPDIR="$1" claude -p --model sonnet --allowedTools "Bash,Agent,Task" -- "$4" 2>&1)"
    echo "$out"
    ls "$1"/superagent-bridge/implementer-*.log >/dev/null 2>&1 && [[ "$out" == *RELAY-OK* ]] && echo RELAY-PROVEN' \
    _ "$WORK/tmp6" "$R" "$BRIDGE" \
    "Dispatch ONE subagent with subagent_type: super-implementer and the prompt 'Reply with exactly: RELAY-OK'. Output its reply verbatim."

# T7 — spawn_agent relay round trip under Codex (codex→claude). Same proof-of-dispatch and
# other-CLI-missing handling as T6; --role implementer in the relay preamble yields
# implementer-*.log under the pinned TMPDIR.
pre="$(sed -e 's/<role>/implementer/g' -e 's/<harness>/claude/g' -e 's/<model>/haiku/g' -e 's/<effort>/low/g' -e "s#<bridge-path>#$BRIDGE#g" "$ROOT/templates/relay-preamble.md")"
run_test "T7 spawn_agent relay round trip (codex→claude)" codex "RELAY-PROVEN" \
  bash -c 'command -v claude >/dev/null 2>&1 || { echo SKIP-OTHER-CLI-MISSING; exit 0; }
    mkdir -p "$1"
    out="$(TMPDIR="$1" codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox -C "$2" "$3" </dev/null 2>&1)"
    echo "$out"
    ls "$1"/superagent-bridge/implementer-*.log >/dev/null 2>&1 && [[ "$out" == *RELAY-OK* ]] && echo RELAY-PROVEN' \
    _ "$WORK/tmp7" "$WORK" \
    "Spawn ONE agent (spawn_agent) with this exact message, then output its reply verbatim: $(printf '%s\nReply with exactly: RELAY-OK' "$pre")"

# T8 — long-running bridge call (opt-in: BRIDGE_SMOKE_LONG=1; otherwise SKIP). Same shape as T6,
# but the dispatched task sleeps past Claude Code's 120s default Bash-tool timeout, so a relay
# that does not pass an explicit long `timeout` — or an outer session with no
# BASH_DEFAULT_TIMEOUT_MS / BASH_MAX_TIMEOUT_MS in its env — is killed mid-bridge and
# RELAY-PROVEN never appears. Those two vars are forwarded to the child `claude -p` explicitly,
# which is exactly what superagent-tick.sh exports for a real tick. The outer per-probe cap is
# raised for this one probe (the default 240s is shorter than the probe itself).
R8="$WORK/t8"; mkdir -p "$R8/.claude/agents"; ( cd "$R8" && git init -q )
sed -e 's/<role>/implementer/g' -e 's/<KEY>/SUPER_MODEL_IMPLEMENTER/g' -e 's/<harness>/codex/g' \
    -e 's/<model>/inherit/g' -e 's/<effort>/low/g' -e 's/<relay-model>/sonnet/g' \
    -e "s#<bridge-path>#$BRIDGE#g" "$ROOT/templates/super-role-bridge-agent.md" >"$R8/.claude/agents/super-implementer.md"
if command -v timeout >/dev/null 2>&1; then TCMD=(timeout 1200)
elif command -v gtimeout >/dev/null 2>&1; then TCMD=(gtimeout 1200); fi
run_test "T8 long bridge call (claude→codex, >120s)" claude "RELAY-PROVEN" \
  bash -c '[ "${BRIDGE_SMOKE_LONG:-0}" = 1 ] || { echo SKIP-LONG-NOT-REQUESTED; exit 0; }
    command -v codex >/dev/null 2>&1 || { echo SKIP-OTHER-CLI-MISSING; exit 0; }
    mkdir -p "$1"
    out="$(cd "$2" && SUPERAGENT_BRIDGE="$3" TMPDIR="$1" \
      BASH_DEFAULT_TIMEOUT_MS="${BASH_DEFAULT_TIMEOUT_MS:-3600000}" \
      BASH_MAX_TIMEOUT_MS="${BASH_MAX_TIMEOUT_MS:-7200000}" \
      claude -p --model sonnet --allowedTools "Bash,Agent,Task" -- "$4" 2>&1)"
    echo "$out"
    ls "$1"/superagent-bridge/implementer-*.log >/dev/null 2>&1 && [[ "$out" == *RELAY-OK* ]] && echo RELAY-PROVEN' \
    _ "$WORK/tmp8" "$R8" "$BRIDGE" \
    "Dispatch ONE subagent with subagent_type: super-implementer and the prompt 'Run the shell command \`sleep 200\` and then reply with exactly: RELAY-OK'. Output its reply verbatim."

{ echo "---"; echo "PASS=$PASS FAIL=$FAIL SKIP=$SKIP"; } >>"$REPORT"
echo "bridge-smoke: PASS=$PASS FAIL=$FAIL SKIP=$SKIP — report: $REPORT"

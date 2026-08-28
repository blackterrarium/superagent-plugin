#!/usr/bin/env bash
# bridge-test.sh — offline tests for scripts/role-bridge.sh (PATH shims) and the
# _common.sh role parser. No network, no real CLIs. Exit 1 on any failure.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRIDGE="$ROOT/scripts/role-bridge.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
SHIM="$T/bin"; mkdir -p "$SHIM" "$T/cwd"
export PATH="$SHIM:$PATH"
export TMPDIR="$T/tmp"; mkdir -p "$TMPDIR"
FAILS=0
ok()   { echo "ok   - $1"; }
fail() { echo "FAIL - $1"; FAILS=$((FAILS+1)); }
check() { local name="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$name"; else fail "$name"; fi; }

# Each shim records argv (one per line) to $T/<name>.argv, stdin to $T/<name>.stdin, then
# behaves per $SHIM_MODE: ok (print/write result) | fail (exit 9) | empty (exit 0, nothing).
mkshim() {
  local name="$1"
  cat >"$SHIM/$name" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" >"$T/$name.argv"
cat >"$T/$name.stdin"
case "\${SHIM_MODE:-ok}" in
  fail) echo "boom" >&2; exit 9 ;;
  empty) exit 0 ;;
esac
# codex writes -o <file>; everything else prints to stdout
out=""; prev=""
for a in "\$@"; do [ "\$prev" = "-o" ] && out="\$a"; prev="\$a"; done
if [ -n "\$out" ]; then echo "RESULT-$name" >"\$out"; echo "progress chatter" ; else echo "RESULT-$name"; fi
EOF
  chmod +x "$SHIM/$name"
}
for b in claude codex agent pi; do mkshim "$b"; done
printf 'hello prompt\nline two\n' >"$T/prompt.txt"
argv() { cat "$T/$1.argv" | tr '\n' ' '; }

# ── claude ──
out="$(SUPER_CODEX_SANDBOX= "$BRIDGE" --harness claude --model sonnet --effort high --cwd "$T/cwd" --prompt-file "$T/prompt.txt" --role implementer 2>"$T/err")"; rc=$?
check "claude: exit 0"            [ "$rc" -eq 0 ]
check "claude: stdout is result"  [ "$out" = "RESULT-claude" ]
check "claude: argv"              [ "$(argv claude)" = "-p --model sonnet --effort high --allowedTools Read,Edit,Write,Bash,Grep,Glob " ]
check "claude: prompt on stdin"   cmp -s "$T/claude.stdin" "$T/prompt.txt"
check "claude: log path on stderr" grep -q '^role-bridge: log=' "$T/err"
"$BRIDGE" --harness claude --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "claude: inherit omits flags" [ "$(argv claude)" = "-p --allowedTools Read,Edit,Write,Bash,Grep,Glob " ]

# ── codex ──
out="$("$BRIDGE" --harness codex --model gpt-5.6-terra --effort medium --cwd "$T/cwd" --prompt-file "$T/prompt.txt" 2>/dev/null)"
check "codex: stdout is -o file content" [ "$out" = "RESULT-codex" ]
check "codex: default sandbox flag" grep -q -- '--dangerously-bypass-approvals-and-sandbox' "$T/codex.argv"
check "codex: model/effort/cwd flags" bash -c "a=\"\$(cat '$T/codex.argv' | tr '\n' ' ')\"; [[ \"\$a\" == *'-m gpt-5.6-terra '* && \"\$a\" == *'-c model_reasoning_effort=medium '* && \"\$a\" == *'-C $T/cwd '* && \"\$a\" == *'--skip-git-repo-check '* ]]"
check "codex: prompt via stdin (-)" bash -c "tail -1 '$T/codex.argv' | grep -qx -- '-' && cmp -s '$T/codex.stdin' '$T/prompt.txt'"
SUPER_CODEX_SANDBOX=workspace-write "$BRIDGE" --harness codex --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "codex: workspace-write flags" bash -c "a=\"\$(cat '$T/codex.argv' | tr '\n' ' ')\"; [[ \"\$a\" == *'--sandbox workspace-write -c sandbox_workspace_write.network_access=true '* && \"\$a\" != *' -m '* ]]"

# ── cursor ──
out="$("$BRIDGE" --harness cursor --model auto --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" 2>/dev/null)"
check "cursor: stdout"  [ "$out" = "RESULT-agent" ]
check "cursor: argv"    bash -c "a=\"\$(cat '$T/agent.argv' | tr '\n' ' ')\"; [[ \"\$a\" == '-p hello prompt'* && \"\$a\" == *'--trust --force --model auto --output-format text '* ]]"

# ── pi ──
out="$("$BRIDGE" --harness pi --model openai/gpt-5 --effort high --cwd "$T/cwd" --prompt-file "$T/prompt.txt" 2>/dev/null)"
check "pi: stdout"  [ "$out" = "RESULT-pi" ]
check "pi: model with level suffix" [ "$(argv pi)" = "-p --model openai/gpt-5:high " ]
"$BRIDGE" --harness pi --model openai/gpt-5 --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "pi: no suffix when effort inherit" [ "$(argv pi)" = "-p --model openai/gpt-5 " ]

# ── exit codes ──
SHIM_MODE=fail "$BRIDGE" --harness claude --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "exit 3 when CLI fails" [ "$rc" -eq 3 ]
SHIM_MODE=empty "$BRIDGE" --harness claude --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "exit 4 on empty result" [ "$rc" -eq 4 ]
PATH="/usr/bin:/bin" "$BRIDGE" --harness pi --model x/y --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "exit 2 when binary missing" [ "$rc" -eq 2 ]
"$BRIDGE" --harness nope --model x --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "usage error on bad harness" [ "$rc" -eq 64 ]
# Recognized flag with no following value must exit 64, not hang (bash 3.2's `shift 2` with
# $#=1 shifts nothing and returns nonzero, so a naive parse loop spins forever). Bound the run
# with perl's alarm so a regression fails the test instead of hanging the suite.
perl -e 'alarm 5; exec @ARGV' "$BRIDGE" --harness claude --model >/dev/null 2>&1; rc=$?
check "usage error on trailing flag with no value" [ "$rc" -eq 64 ]

echo "bridge-test: $FAILS failure(s)"
[ "$FAILS" -eq 0 ]

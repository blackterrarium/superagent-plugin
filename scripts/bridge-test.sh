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
check() {  # on failure, show the command's last output lines — otherwise a FAIL is unexplainable
  local name="$1"; shift; local out
  if out="$("$@" 2>&1)"; then ok "$name"; else fail "$name"; printf '%s\n' "$out" | tail -5 | sed 's/^/       | /'; fi
}

# Each shim records argv (one per line) to $T/<name>.argv, stdin to $T/<name>.stdin, then
# behaves per $SHIM_MODE: ok (print/write result) | fail (exit 9) | empty (exit 0, nothing).
mkshim() {
  local name="$1"
  cat >"$SHIM/$name" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" >"$T/$name.argv"
cat >"$T/$name.stdin"
printf '%s\n' "\${CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS:-unset}" >"$T/$name.env"
case "\${SHIM_MODE:-ok}" in
  fail) echo "boom" >&2; exit 9 ;;
  empty) exit 0 ;;
  slow) sleep 30; echo "RESULT-$name"; exit 0 ;;
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
check "claude: bg-wait ceiling lifted (0) when unset" bash -c "env -u CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS '$BRIDGE' --harness claude --model inherit --effort inherit --cwd '$T/cwd' --prompt-file '$T/prompt.txt' >/dev/null 2>&1; [ \"\$(cat '$T/claude.env')\" = 0 ]"
CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=5000 "$BRIDGE" --harness claude --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "claude: operator bg-wait ceiling respected" [ "$(cat "$T/claude.env")" = 5000 ]
# --tools: the executor role (superrun, issue #25) runs as its own top-level `claude -p` process and
# needs the tick's Task/Skill allowlist so SDD's subagents dispatch at depth 1 inside it.
"$BRIDGE" --harness claude --model opus --effort medium --tools executor --cwd "$T/cwd" --prompt-file "$T/prompt.txt" --role executor >/dev/null 2>&1
check "claude: --tools executor allowlist" [ "$(argv claude)" = "-p --model opus --effort medium --allowedTools Read,Edit,Write,Bash,Grep,Glob,Task,Skill " ]
"$BRIDGE" --harness claude --model opus --effort high --tools planner --cwd "$T/cwd" --prompt-file "$T/prompt.txt" --role planner >/dev/null 2>&1
check "claude: --tools planner allowlist" [ "$(argv claude)" = "-p --model opus --effort high --allowedTools Read,Edit,Write,Bash,Grep,Glob,Task,Skill " ]
"$BRIDGE" --harness claude --model inherit --effort inherit --tools "Read,Bash" --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "claude: --tools explicit list" [ "$(argv claude)" = "-p --allowedTools Read,Bash " ]
"$BRIDGE" --harness claude --model inherit --effort inherit --tools role --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "claude: --tools role = default" [ "$(argv claude)" = "-p --allowedTools Read,Edit,Write,Bash,Grep,Glob " ]
"$BRIDGE" --harness codex --model inherit --effort inherit --tools executor --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "codex: --tools accepted and ignored" bash -c "[ $rc -eq 0 ] && ! grep -q -- '--allowedTools' '$T/codex.argv'"
"$BRIDGE" --harness claude --model inherit --effort inherit --tools "" --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "usage error on empty --tools" [ "$rc" -eq 64 ]

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
check "pi: model with level suffix + role tools" [ "$(argv pi)" = "-p --approve --no-session --model openai/gpt-5:high --tools read,edit,write,bash,grep,find,ls " ]
check "pi: prompt on stdin" cmp -s "$T/pi.stdin" "$T/prompt.txt"
"$BRIDGE" --harness pi --model openai/gpt-5 --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "pi: no suffix when effort inherit" [ "$(argv pi)" = "-p --approve --no-session --model openai/gpt-5 --tools read,edit,write,bash,grep,find,ls " ]
"$BRIDGE" --harness pi --model inherit --effort inherit --tools planner --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "pi: --tools planner = role set" [ "$(argv pi)" = "-p --approve --no-session --tools read,edit,write,bash,grep,find,ls " ]
"$BRIDGE" --harness pi --model inherit --effort inherit --tools executor --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "pi: --tools executor = no --tools flag" [ "$(argv pi)" = "-p --approve --no-session " ]
"$BRIDGE" --harness pi --model inherit --effort inherit --tools "read,bash" --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "pi: --tools explicit list" [ "$(argv pi)" = "-p --approve --no-session --tools read,bash " ]
SUPERAGENT_PI_SKILLS="$T/skills" "$BRIDGE" --harness pi --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "pi: SUPERAGENT_PI_SKILLS → --skill" [ "$(argv pi)" = "-p --approve --no-session --skill $T/skills --tools read,edit,write,bash,grep,find,ls " ]

# ── exit codes ──
SHIM_MODE=fail "$BRIDGE" --harness claude --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "exit 3 when CLI fails" [ "$rc" -eq 3 ]
SHIM_MODE=empty "$BRIDGE" --harness claude --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "exit 4 on empty result" [ "$rc" -eq 4 ]
PATH="/usr/bin:/bin" "$BRIDGE" --harness pi --model x/y --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>"$T/err2"; rc=$?
check "exit 2 when binary missing" [ "$rc" -eq 2 ]
# The log line is printed only after the binary check, so an exit-2 run must not advertise
# a log path that was never written.
if grep -q 'log=' "$T/err2"; then fail "exit 2: no log= on stderr"; else ok "exit 2: no log= on stderr"; fi
"$BRIDGE" --harness nope --model x --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "usage error on bad harness" [ "$rc" -eq 64 ]
# Recognized flag with no following value must exit 64, not hang (bash 3.2's `shift 2` with
# $#=1 shifts nothing and returns nonzero, so a naive parse loop spins forever). Bound the run
# with perl's alarm so a regression fails the test instead of hanging the suite.
perl -e 'alarm 5; exec @ARGV' "$BRIDGE" --harness claude --model >/dev/null 2>&1; rc=$?
check "usage error on trailing flag with no value" [ "$rc" -eq 64 ]

# ── SUPER_CODEX_SANDBOX domain (read for ANY codex-bridged role, on any harness) ──
SUPER_CODEX_SANDBOX=read-only "$BRIDGE" --harness codex --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>"$T/errsb"; rc=$?
check "exit 64 on bad SUPER_CODEX_SANDBOX" [ "$rc" -eq 64 ]
check "bad sandbox message" grep -q 'SUPER_CODEX_SANDBOX must be danger-full-access|workspace-write' "$T/errsb"

# ── --role sanitising (the role reaches the log path) ──
rm -f "$TMPDIR"/superagent-bridge/*.log 2>/dev/null || true
"$BRIDGE" --harness claude --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" --role '../x' >/dev/null 2>"$T/errrole"
logpath="$(sed -n 's/^role-bridge: log=//p' "$T/errrole")"
check "role sanitised: log stays in logdir" bash -c "[ \"\$(dirname '$logpath')\" = '$TMPDIR/superagent-bridge' ]"
check "role sanitised: no path chars in name" bash -c "b=\"\$(basename '$logpath')\"; [[ \"\$b\" == ___x-* ]]"
check "role sanitised: log file exists" [ -f "$logpath" ]

# ── pi effort edge cases ──
"$BRIDGE" --harness pi --model inherit --effort high --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>"$T/errpi1"
check "pi: --thinking when model inherit" [ "$(argv pi)" = "-p --approve --no-session --thinking high --tools read,edit,write,bash,grep,find,ls " ]
if grep -q "dropped" "$T/errpi1"; then fail "pi: no 'dropped' warning any more"; else ok "pi: no 'dropped' warning any more"; fi
"$BRIDGE" --harness pi --model openai/gpt-5:high --effort low --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>"$T/errpi2"
check "pi: no double suffix" [ "$(argv pi)" = "-p --approve --no-session --model openai/gpt-5:high --tools read,edit,write,bash,grep,find,ls " ]
check "pi: WARN on already-pinned level" grep -q "already pins a level" "$T/errpi2"

# ── bridge-fanout ──
FANOUT="$ROOT/scripts/bridge-fanout.sh"
printf 'panel prompt one\n' >"$T/p1.txt"; printf 'panel prompt two\n' >"$T/p2.txt"; printf 'panel prompt three\n' >"$T/p3.txt"
out="$("$FANOUT" --harness pi --model openai/gpt-5 --effort high --cwd "$T/cwd" --prompt-file "$T/p1.txt" --prompt-file "$T/p2.txt" --prompt-file "$T/p3.txt" 2>"$T/fanerr")"; rc=$?
check "fanout: exit 0 when all ok" [ "$rc" -eq 0 ]
check "fanout: three framed results in order" bash -c "printf '%s\n' \"\$1\" | grep -n -E '^=== (PANELIST [123] exit=0|END [123]) ===$' | tr '\n' ' ' | grep -q '^1:=== PANELIST 1 exit=0 === 3:=== END 1 === 4:=== PANELIST 2 exit=0 === 6:=== END 2 === 7:=== PANELIST 3 exit=0 === 9:=== END 3 === $'" _ "$out"
check "fanout: each block carries the bridge stdout" [ "$(printf '%s\n' "$out" | grep -c '^RESULT-pi$')" -eq 3 ]
# Watchdog reaping: on a happy path the watchdog's own `sleep --timeout` must not survive the run
# (it is a forked child of $wd, not killed by `kill "$wd"` alone). Use a distinctive timeout value
# so a stray sleep from elsewhere can't collide with the check, and confirm none is already running.
pgrep -f '^sleep 600$' >/dev/null && fail "fanout: pre-existing sleep 600 would poison the reap check" || true
out="$("$FANOUT" --harness pi --model inherit --effort inherit --cwd "$T/cwd" --timeout 600 --prompt-file "$T/p1.txt" --prompt-file "$T/p2.txt" --prompt-file "$T/p3.txt" 2>/dev/null)"; rc=$?
check "fanout: exit 0 with --timeout 600" [ "$rc" -eq 0 ]
check "fanout: watchdog sleep reaped on success" bash -c '! pgrep -f "^sleep 600$" >/dev/null'
out="$(SHIM_MODE=slow "$FANOUT" --harness pi --model inherit --effort inherit --cwd "$T/cwd" --timeout 2 --prompt-file "$T/p1.txt" --prompt-file "$T/p2.txt" 2>/dev/null)"; rc=$?
check "fanout: exit 3 on timeout" [ "$rc" -eq 3 ]
check "fanout: timed-out panelist is BRIDGE-FAILED" bash -c "printf '%s\n' \"\$1\" | grep -q '^BRIDGE-FAILED exit=[0-9]* harness=pi role=panelist-1 log='" _ "$out"
out="$(SHIM_MODE=fail "$FANOUT" --harness pi --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/p1.txt" 2>/dev/null)"; rc=$?
check "fanout: exit 3 when a bridge fails" [ "$rc" -eq 3 ]
check "fanout: failed panelist framed with exit=3" bash -c "printf '%s\n' \"\$1\" | grep -q '^=== PANELIST 1 exit=3 ===$'" _ "$out"
"$FANOUT" --harness pi --model inherit --effort inherit --cwd "$T/cwd" >/dev/null 2>&1; rc=$?
check "fanout: usage error without prompt files" [ "$rc" -eq 64 ]
"$FANOUT" --harness nope --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/p1.txt" >/dev/null 2>&1; rc=$?
check "fanout: usage error on bad harness" [ "$rc" -eq 64 ]

# ── _common.sh role parser ──
. "$ROOT/scripts/_common.sh"
ph() { [ "$(superagent_role_harness "$1")" = "$2" ]; }
check "parse: tier → claude"          ph sonnet claude
check "parse: claude- id → claude"    ph claude-fable-5 claude
check "parse: gpt- → codex"           ph gpt-5.6-terra codex
check "parse: o-series → codex"       ph o4-mini codex
check "parse: codex- → codex"         ph codex-mini codex
check "parse: slash → pi"             ph openai/gpt-5 pi
check "parse: prefix wins"            ph pi:sonnet pi
check "parse: cursor prefix"          ph cursor:auto cursor
check "parse: inherit"                ph inherit inherit
check "parse: unknown"                ph sonet unknown
check "parse: model strip"            [ "$(superagent_role_model codex:gpt-5.6-sol)" = gpt-5.6-sol ]
check "parse: model no prefix"        [ "$(superagent_role_model opus)" = opus ]
check "effort: claude max ok"         superagent_effort_valid claude max
if superagent_effort_valid codex max; then fail "effort: codex max rejected"; else ok "effort: codex max rejected"; fi
check "effort: pi off ok"             superagent_effort_valid pi off
if superagent_effort_valid cursor high; then fail "effort: cursor high rejected"; else ok "effort: cursor high rejected"; fi
check "effort: inherit always ok"     superagent_effort_valid cursor inherit
check "effort: pi xhigh ok"           superagent_effort_valid pi xhigh
check "effort: pi max ok"             superagent_effort_valid pi max
if superagent_effort_valid pi ultra; then fail "effort: pi ultra rejected"; else ok "effort: pi ultra rejected"; fi
check "harness: pi accepted"          bash -c "SUPER_HARNESS=pi; . '$ROOT/scripts/_common.sh'; [ \"\$(superagent_harness)\" = pi ]"
check "harness: bad value rejected"   bash -c "SUPER_HARNESS=hermes; . '$ROOT/scripts/_common.sh'; ! superagent_harness 2>/dev/null"
check "ensure_cli_bin: pi resolves"   bash -c "SUPER_HARNESS=pi; . '$ROOT/scripts/_common.sh'; ensure_cli_bin"
check "ensure_pi_bin: missing → hint" bash -c "PATH=/usr/bin:/bin; . '$ROOT/scripts/_common.sh'; ensure_pi_bin 2>&1 | grep -q 'npm install -g @earendil-works/pi-coding-agent'"

# --- scheduler PATH: CLIs under a Node version manager (nvm/fnm/volta) live outside the dirs
# _superagent_augment_path hard-codes, so install-timer.sh records their dirs at install time
# (SUPERAGENT_CLI_PATH in the per-goal env file) and the augment prepends them under the scheduler.
NVMBIN="$T/nvm/versions/node/v0.0.0/bin"; mkdir -p "$NVMBIN"; cp "$SHIM/pi" "$NVMBIN/pi"
check "cli_path: SUPERAGENT_CLI_PATH dir searched under a minimal PATH" \
  bash -c "PATH=/usr/bin:/bin SUPERAGENT_CLI_PATH='$NVMBIN'; . '$ROOT/scripts/_common.sh'; ensure_pi_bin"
check "cli_path: minimal PATH without it still fails (control)" \
  bash -c "PATH=/usr/bin:/bin; unset SUPERAGENT_CLI_PATH; . '$ROOT/scripts/_common.sh'; ! ensure_pi_bin 2>/dev/null"
check "cli_path: augment is idempotent (dir appears once)" \
  bash -c "PATH=/usr/bin:/bin SUPERAGENT_CLI_PATH='$NVMBIN'; . '$ROOT/scripts/_common.sh'; _superagent_augment_path; _superagent_augment_path; [ \"\$(tr ':' '\\n' <<<\"\$PATH\" | grep -cx '$NVMBIN')\" = 1 ]"
check "cli_path_dirs: reports the dir of every resolvable CLI, deduped, standard dirs omitted" \
  bash -c ". '$ROOT/scripts/_common.sh'; [ \"\$(superagent_cli_path_dirs)\" = '$SHIM' ]"
check "ensure_pi_bin: missing → names SUPERAGENT_CLI_PATH" \
  bash -c "PATH=/usr/bin:/bin; . '$ROOT/scripts/_common.sh'; ensure_pi_bin 2>&1 | grep -q SUPERAGENT_CLI_PATH"

# --- pi-e2e.sh helpers (sourced as a library with PI_E2E_LIB=1; no phases run) ---
E2E="$ROOT/scripts/pi-e2e.sh"
E2E_JSON='[{"slug":"other","status":"DONE","iteration":"9","timer_active":"inactive","tick_running":"inactive","lock_held":false,"pending_input":0,"answer_recorded":false,"done":1,"loop_file":"/x","loop_file_exists":true,"next_fire":"","gh_auth":"ok"},{"slug":"pi-e2e-1","status":"WAITING FOR RUN","iteration":"2","timer_active":"active","tick_running":"inactive","lock_held":false,"pending_input":0,"answer_recorded":false,"done":0,"loop_file":"/y","loop_file_exists":true,"next_fire":"soon","gh_auth":"ok"}]'
check "e2e: sources as a library"                 bash -c "PI_E2E_LIB=1; . '$E2E'"
check "e2e: status_field picks the right slug"    bash -c "PI_E2E_LIB=1; . '$E2E'; [ \"\$(e2e_status_field '$E2E_JSON' pi-e2e-1 status)\" = 'WAITING FOR RUN' ]"
check "e2e: status_field numeric field"           bash -c "PI_E2E_LIB=1; . '$E2E'; [ \"\$(e2e_status_field '$E2E_JSON' other done)\" = 1 ]"
check "e2e: status_field absent slug → empty"     bash -c "PI_E2E_LIB=1; . '$E2E'; [ -z \"\$(e2e_status_field '$E2E_JSON' nope status)\" ]"
check "e2e: status_field empty array → empty"     bash -c "PI_E2E_LIB=1; . '$E2E'; [ -z \"\$(e2e_status_field '[]' x status)\" ]"
check "e2e: superenv has harness, interval, single-quoted notify" bash -c "PI_E2E_LIB=1; . '$E2E'; out=\$(e2e_render_superenv 2m /tmp/ev.log); grep -qx 'SUPER_HARNESS=pi' <<<\"\$out\" && grep -qx 'SUPER_TICK_INTERVAL=2m' <<<\"\$out\" && grep -q \"^SUPER_NOTIFY_CMD='.*SUPERAGENT_EVENT.*/tmp/ev.log.*'\$\" <<<\"\$out\""
check "e2e: superenv appends extra lines"         bash -c "PI_E2E_LIB=1; . '$E2E'; e2e_render_superenv 2m /tmp/ev.log 'SUPER_MODEL_TASK_REVIEWER=codex:gpt-5.6-sol' | grep -qx 'SUPER_MODEL_TASK_REVIEWER=codex:gpt-5.6-sol'"
check "e2e: superenv sources under set -u and notify appends the event" bash -c "PI_E2E_LIB=1; . '$E2E'; e2e_render_superenv 2m '$T/ev.log' >'$T/se'; bash -uc 'set -a; . \"$T/se\"; set +a; [ \"\$SUPER_HARNESS\" = pi ] && SUPERAGENT_EVENT=done bash -c \"\$SUPER_NOTIFY_CMD\"' && grep -qx done '$T/ev.log'"
printf '=== t superagent-tick harness=pi model=x ===\nblah\n=== t superagent-tick exit=0 ===\n=== t superagent-tick harness=pi model=x ===\n=== t superagent-tick exit=10 ===\n' >"$T/tick.log"
check "e2e: count_ticks counts session headers"   bash -c "PI_E2E_LIB=1; . '$E2E'; [ \"\$(e2e_count_ticks '$T/tick.log')\" = 2 ]"
check "e2e: count_ticks missing log → 0"          bash -c "PI_E2E_LIB=1; . '$E2E'; [ \"\$(e2e_count_ticks '$T/nope.log')\" = 0 ]"
check "e2e: transition sets E2E_LINE only on change (no subshell)" bash -c "PI_E2E_LIB=1; . '$E2E'; e2e_transition PLANNING 1; a=\$E2E_LINE; e2e_transition PLANNING 1; b=\$E2E_LINE; e2e_transition RUNNING 1; c=\$E2E_LINE; e2e_transition RUNNING 2; d=\$E2E_LINE; [ -n \"\$a\" ] && [ -z \"\$b\" ] && [[ \"\$c\" == *'RUNNING iter=1' ]] && [[ \"\$d\" == *'RUNNING iter=2' ]]"
mkdir -p "$T/deliv/scripts"; printf '#!/bin/sh\necho "hello, world"\n' >"$T/deliv/scripts/hello.sh"; printf '#!/bin/sh\n[ "$(sh "$(dirname "$0")/hello.sh")" = "hello, world" ]\n' >"$T/deliv/scripts/test.sh"; chmod +x "$T/deliv/scripts/"*.sh
check "e2e: deliverables pass"                    bash -c "PI_E2E_LIB=1; . '$E2E'; e2e_assert_deliverables '$T/deliv'"
check "e2e: deliverables fail when hello.sh is wrong" bash -c "PI_E2E_LIB=1; . '$E2E'; rm -rf '$T/deliv2'; cp -R '$T/deliv' '$T/deliv2'; echo 'echo nope' >'$T/deliv2/scripts/hello.sh'; ! e2e_assert_deliverables '$T/deliv2'"
mkshim gh; mkshim launchctl; mkshim systemctl
check "e2e: --dry-run exits 0 and prints the plan" bash -c "cd '$T/cwd' && PI_E2E_REPO=o/r '$E2E' --dry-run 2>&1 | grep -q 'nothing created or armed'"
check "e2e: --dry-run writes no report"           bash -c "cd '$T/cwd' && PI_E2E_REPO=o/r PI_E2E_REPORT='$T/dry-report.md' '$E2E' --dry-run >/dev/null 2>&1; [ ! -f '$T/dry-report.md' ]"
check "e2e: bad flag → exit 2"                    bash -c "'$E2E' --bogus >/dev/null 2>&1; [ \$? = 2 ]"
check "e2e: kill_tree kills a child and its grandchild" bash -c "PI_E2E_LIB=1; . '$E2E'; bash -c 'sleep 57; true' & p=\$!; sleep 0.3; c=\$(pgrep -P \$p | head -1); e2e_kill_tree \$p; sleep 0.3; ! kill -0 \$p 2>/dev/null && ! kill -0 \$c 2>/dev/null"
# gh shim that hangs only on `repo view` — everything else answers instantly (preflight must pass)
cat >"$SHIM/gh" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = repo ] && [ "$2" = view ]; then sleep 31; fi
echo RESULT-gh
EOF
chmod +x "$SHIM/gh"
check "e2e: SIGTERM mid-phase → cleanup, exit 143, within 10s" bash -c "cd '$T/cwd'; PI_E2E_REPO=o/r PI_E2E_REPORT='$T/e2e-term-report.md' '$E2E' >'$T/e2e-term.out' 2>&1 & p=\$!; for i in \$(seq 1 40); do grep -q Provision '$T/e2e-term.out' && break; sleep 0.5; done; t0=\$(date +%s); kill -TERM \$p; wait \$p; rc=\$?; el=\$(( \$(date +%s) - t0 )); [ \$rc = 143 ] && [ \$el -lt 10 ] && grep -q 'interrupted' '$T/e2e-term.out' && ! pgrep -f '^sleep 31\$' >/dev/null"

# --- launch.sh: a repo reached through a symlinked path (macOS /var → /private/var, /tmp → /private/tmp)
# must still accept its plan: REPO comes from git (physical) while the plan path must not be logical.
mkdir -p "$T/real/vault/g/master-plans" "$T/real/vault/g/loop-status"; ( cd "$T/real" && git init -q && printf '# plan\n' >vault/g/master-plans/p.md && git add -A && git -c user.email=t@t -c user.name=t commit -qm init )
ln -s "$T/real" "$T/link"
check "launch: plan under a symlinked repo path accepted (--dry-run)" bash -c "cd '$T/link' && SUPER_HARNESS=pi '$ROOT/scripts/launch.sh' '$T/link/vault/g/master-plans/p.md' --harness pi --dry-run 2>&1 | grep -q 'nothing created or armed'"

# --- load_superenv: the harness build's own template layers over the Claude default. A Pi-harness repo
# whose .superenv sets only SUPER_HARNESS=pi must get the Pi template's supervisor model (inherit), not
# the Claude template's claude:opus — which the pi tick refuses with exit 11 (found by pi-e2e.sh run 4).
mkdir -p "$T/se-pi" "$T/se-none"; printf 'SUPER_HARNESS=pi\n' >"$T/se-pi/.superenv"
check "superenv: harness=pi in .superenv → Pi template defaults" bash -c ". '$ROOT/scripts/_common.sh'; load_superenv '$T/se-pi'; [ \"\$SUPER_MODEL_SUPERVISOR\" = inherit ] && [ \"\$SUPER_HARNESS\" = pi ]"
check "superenv: no .superenv → Claude template defaults"       bash -c "unset SUPER_HARNESS; . '$ROOT/scripts/_common.sh'; load_superenv '$T/se-none'; [ \"\$SUPER_MODEL_SUPERVISOR\" = claude:opus ]"
check "superenv: process env SUPER_HARNESS=pi wins and layers"  bash -c "export SUPER_HARNESS=pi; . '$ROOT/scripts/_common.sh'; load_superenv '$T/se-none'; [ \"\$SUPER_MODEL_SUPERVISOR\" = inherit ]"
check "superenv: repo .superenv still overrides the harness template" bash -c "printf 'SUPER_HARNESS=pi\nSUPER_MODEL_SUPERVISOR=pi:openai-codex/gpt-5.6-sol\n' >'$T/se-pi/.superenv'; . '$ROOT/scripts/_common.sh'; load_superenv '$T/se-pi'; [ \"\$SUPER_MODEL_SUPERVISOR\" = pi:openai-codex/gpt-5.6-sol ]"

# --- role-bridge: --harness inherit (a SUPER_MODEL_* of `inherit` resolves to harness `inherit` via
# superagent_role_harness) must run on SUPER_HARNESS, not be rejected (exit 64). Found by pi-e2e.sh run 5:
# the supervisor passed the literal through and superplan's dispatch failed on both attempts.
check "bridge: --harness inherit runs SUPER_HARNESS (pi)"     bash -c "rm -f '$T/pi.argv'; SUPER_HARNESS=pi '$BRIDGE' --harness inherit --model inherit --effort inherit --cwd '$T/cwd' --prompt-file '$T/prompt.txt' >/dev/null 2>&1 && [ -f '$T/pi.argv' ]"
check "bridge: --harness inherit defaults to claude when SUPER_HARNESS unset" bash -c "rm -f '$T/claude.argv'; unset SUPER_HARNESS; '$BRIDGE' --harness inherit --model inherit --effort inherit --cwd '$T/cwd' --prompt-file '$T/prompt.txt' >/dev/null 2>&1 && [ -f '$T/claude.argv' ]"

# --- role-bridge: header + trailer lines in its own log (the evidence mix-e2e.sh asserts on). A bridged
# pi/claude role used to leave a 0-byte log (only the CLI's stderr was captured), so nothing proved which
# harness ran which role. stdout must stay exactly the CLI's final message.
"$BRIDGE" --harness codex --model gpt-5.6-terra --effort medium --cwd "$T/cwd" --prompt-file "$T/prompt.txt" --role implementer >"$T/hdr.out" 2>"$T/hdr.err"
hlog="$(sed -n 's/^role-bridge: log=//p' "$T/hdr.err")"
check "bridge log: header is the first line"   bash -c "head -1 '$hlog' | grep -Eq '^role-bridge: start=[0-9]{8}T[0-9]{6}Z harness=codex model=gpt-5.6-terra effort=medium tools=role role=implementer cwd=$T/cwd\$'"
check "bridge log: trailer is the last line"   bash -c "tail -1 '$hlog' | grep -Eq '^role-bridge: end=[0-9]{8}T[0-9]{6}Z exit=0 secs=[0-9]+ result_bytes=12\$'"
check "bridge log: CLI chatter kept in between" grep -q 'progress chatter' "$hlog"
check "bridge log: stdout unchanged"           [ "$(cat "$T/hdr.out")" = "RESULT-codex" ]
"$BRIDGE" --harness pi --model openai-codex/gpt-5.6-sol --effort high --cwd "$T/cwd" --prompt-file "$T/prompt.txt" --role task-reviewer >/dev/null 2>"$T/hdr.err"
hlog="$(sed -n 's/^role-bridge: log=//p' "$T/hdr.err")"
check "bridge log (pi): header records the pin as given, effort separate" bash -c "head -1 '$hlog' | grep -q ' harness=pi model=openai-codex/gpt-5.6-sol effort=high tools=role role=task-reviewer '"
check "bridge log (pi): exactly header + trailer when the CLI is silent" [ "$(wc -l <"$hlog" | tr -d ' ')" = 2 ]
"$BRIDGE" --harness claude --model opus --effort medium --tools executor --cwd "$T/cwd" --prompt-file "$T/prompt.txt" --role executor >/dev/null 2>"$T/hdr.err"
hlog="$(sed -n 's/^role-bridge: log=//p' "$T/hdr.err")"
check "bridge log (claude): tools=executor recorded" bash -c "head -1 '$hlog' | grep -q ' harness=claude model=opus effort=medium tools=executor role=executor '"
SHIM_MODE=fail "$BRIDGE" --harness claude --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>"$T/hdr.err"
hlog="$(sed -n 's/^role-bridge: log=//p' "$T/hdr.err")"
check "bridge log: trailer exit=3 when the CLI fails"  bash -c "tail -1 '$hlog' | grep -Eq '^role-bridge: end=.* exit=3 secs=[0-9]+ result_bytes=0\$'"
SHIM_MODE=empty "$BRIDGE" --harness claude --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>"$T/hdr.err"
hlog="$(sed -n 's/^role-bridge: log=//p' "$T/hdr.err")"
check "bridge log: trailer exit=4 on an empty result" bash -c "tail -1 '$hlog' | grep -Eq '^role-bridge: end=.* exit=4 '"
check "bridge log: inherit model/effort recorded literally" bash -c "head -1 '$hlog' | grep -q ' model=inherit effort=inherit '"
# A bridge killed mid-run leaves the header and no trailer — mix-e2e reports that row as exit=killed.
SHIM_MODE=slow "$BRIDGE" --harness pi --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" --role panelist >/dev/null 2>"$T/hdr.err" & bp=$!
for i in $(seq 1 20); do grep -q 'log=' "$T/hdr.err" 2>/dev/null && break; sleep 0.1; done
sleep 0.3
kill_tree() { local c; for c in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$c"; done; kill -TERM "$1" 2>/dev/null || true; }   # children first: the shim's `sleep 30` holds the bridge's $(…) pipe open
kill_tree "$bp"; wait "$bp" 2>/dev/null
hlog="$(sed -n 's/^role-bridge: log=//p' "$T/hdr.err")"
check "bridge log: killed mid-run → header, no trailer" bash -c "[ \"\$(wc -l <'$hlog' | tr -d ' ')\" = 1 ] && head -1 '$hlog' | grep -q '^role-bridge: start='"

# --- mix-e2e.sh helpers (sourced as a library with MIX_E2E_LIB=1; no phases run) ---
MIX="$ROOT/scripts/mix-e2e.sh"
check "mix: sources as a library (pulls in pi-e2e helpers + _common)" bash -c "MIX_E2E_LIB=1; . '$MIX'; type e2e_status_field >/dev/null && type superagent_role_model >/dev/null"
check "mix: superenv pins claude supervisor, both pairs, single-quoted notify, extra last" bash -c "MIX_E2E_LIB=1; . '$MIX'; out=\$(mix_render_superenv 2m /tmp/ev.log codex:gpt-5.6-terra pi:openai-codex/gpt-5.6-sol 'SUPER_MODEL_PANEL=pi:openai-codex/gpt-5.6-sol'); grep -qx 'SUPER_HARNESS=claude' <<<\"\$out\" && grep -qx 'SUPER_MODEL_IMPLEMENTER=codex:gpt-5.6-terra' <<<\"\$out\" && grep -qx 'SUPER_MODEL_FIX_APPLIER=codex:gpt-5.6-terra' <<<\"\$out\" && grep -qx 'SUPER_MODEL_TASK_REVIEWER=pi:openai-codex/gpt-5.6-sol' <<<\"\$out\" && grep -qx 'SUPER_MODEL_RE_REVIEWER=pi:openai-codex/gpt-5.6-sol' <<<\"\$out\" && grep -q \"^SUPER_NOTIFY_CMD='.*SUPERAGENT_EVENT.*/tmp/ev.log.*'\$\" <<<\"\$out\" && [ \"\$(tail -1 <<<\"\$out\")\" = 'SUPER_MODEL_PANEL=pi:openai-codex/gpt-5.6-sol' ]"
check "mix: superenv sources under set -u and notify appends the event" bash -c "MIX_E2E_LIB=1; . '$MIX'; mix_render_superenv 2m '$T/mev.log' codex:x pi:p/m >'$T/mse'; bash -uc 'set -a; . \"$T/mse\"; set +a; [ \"\$SUPER_HARNESS\" = claude ] && SUPERAGENT_EVENT=done bash -c \"\$SUPER_NOTIFY_CMD\"' && grep -qx done '$T/mev.log'"
# A reference kv.sh that meets the default goal's contract → the deliverable check passes; break it → fails.
mkdir -p "$T/kv/scripts"
cat >"$T/kv/scripts/kv.sh" <<'EOF'
#!/bin/sh
f="${KV_FILE:-.kv}"; [ -f "$f" ] || : >"$f"
case "$1" in
  set) grep -v "^$2=" "$f" >"$f.tmp"; printf '%s=%s\n' "$2" "$3" >>"$f.tmp"; mv "$f.tmp" "$f" ;;
  get) v=$(grep "^$2=" "$f" | cut -d= -f2-); [ -n "$v" ] || exit 1; printf '%s\n' "$v" ;;
  del) grep -v "^$2=" "$f" >"$f.tmp"; mv "$f.tmp" "$f" ;;
  list) sort "$f" ;;
  *) exit 2 ;;
esac
EOF
printf '#!/bin/sh\nexit 0\n' >"$T/kv/scripts/test.sh"
check "mix: deliverables pass on a conforming kv.sh" bash -c "MIX_E2E_LIB=1; . '$MIX'; mix_assert_deliverables '$T/kv'"
check "mix: deliverables leave no KV_FILE in the caller's env" bash -c "MIX_E2E_LIB=1; . '$MIX'; mix_assert_deliverables '$T/kv' >/dev/null; [ -z \"\${KV_FILE:-}\" ]"
rm -rf "$T/kv2"; cp -R "$T/kv" "$T/kv2"; sed -i.bak 's/exit 1;/:;/' "$T/kv2/scripts/kv.sh"   # missing key no longer exits 1 (prints an empty line, exit 0)
check "mix: deliverables fail when a missing key exits 0" bash -c "MIX_E2E_LIB=1; . '$MIX'; ! mix_assert_deliverables '$T/kv2' && mix_assert_deliverables '$T/kv2' | grep -q 'missing key'"
rm -rf "$T/kv3"; cp -R "$T/kv" "$T/kv3"; printf '#!/bin/sh\nexit 1\n' >"$T/kv3/scripts/test.sh"
check "mix: deliverables fail when test.sh fails" bash -c "MIX_E2E_LIB=1; . '$MIX'; mix_assert_deliverables '$T/kv3' | grep -q 'test.sh'"
# Evidence table from a fixture bridge-log dir: three harnesses, one row older than `since`, one killed (no trailer).
mkdir -p "$T/blog"
printf 'role-bridge: start=20260901T120000Z harness=codex model=gpt-5.6-terra effort=medium tools=role role=implementer cwd=/w\nOpenAI Codex v0.152.0\nrole-bridge: end=20260901T120500Z exit=0 secs=300 result_bytes=40\n' >"$T/blog/implementer-a.log"
printf 'role-bridge: start=20260901T120600Z harness=pi model=openai-codex/gpt-5.6-sol effort=high tools=role role=task-reviewer cwd=/w\nrole-bridge: end=20260901T120900Z exit=0 secs=180 result_bytes=90\n' >"$T/blog/task-reviewer-a.log"
printf 'role-bridge: start=20260901T115900Z harness=claude model=opus effort=medium tools=executor role=executor cwd=/w\nrole-bridge: end=20260901T121000Z exit=0 secs=660 result_bytes=500\n' >"$T/blog/executor-a.log"
printf 'role-bridge: start=20260901T110000Z harness=codex model=gpt-5.6-terra effort=medium tools=role role=implementer cwd=/w\nrole-bridge: end=20260901T110100Z exit=0 secs=60 result_bytes=1\n' >"$T/blog/implementer-old.log"
printf 'role-bridge: start=20260901T121100Z harness=pi model=openai-codex/gpt-5.6-sol effort=high tools=role role=re-reviewer cwd=/w\n' >"$T/blog/re-reviewer-killed.log"
printf 'role-bridge: start=20260901T121200Z harness=codex model=gpt-5.6-terra effort=medium tools=role role=fix-applier cwd=/w\nboom\nrole-bridge: end=20260901T121300Z exit=3 secs=60 result_bytes=0\n' >"$T/blog/fix-applier-fail.log"
: >"$T/blog/empty-legacy.log"; printf 'not a bridge log\n' >"$T/blog/junk.log"
check "mix: evidence rows sorted by start, older-than-since and non-bridge logs excluded" bash -c "MIX_E2E_LIB=1; . '$MIX'; r=\$(mix_bridge_evidence 20260901T115900Z '$T/blog' '$T/nonexistent'); [ \"\$(wc -l <<<\"\$r\" | tr -d ' ')\" = 5 ] && [ \"\$(awk 'NR==1{print \$1}' <<<\"\$r\")\" = executor ] && ! grep -q implementer-old <<<\"\$r\""
check "mix: evidence row fields role harness model effort exit secs" bash -c "MIX_E2E_LIB=1; . '$MIX'; mix_bridge_evidence 20260901T115900Z '$T/blog' | grep -q '^implementer codex gpt-5.6-terra medium 0 300 20260901T120000Z $T/blog/implementer-a.log\$'"
check "mix: evidence killed row → exit=killed secs=-"    bash -c "MIX_E2E_LIB=1; . '$MIX'; mix_bridge_evidence 20260901T115900Z '$T/blog' | grep -q '^re-reviewer pi openai-codex/gpt-5.6-sol high killed - '"
check "mix: evidence_has matches role+harness+model with exit 0" bash -c "MIX_E2E_LIB=1; . '$MIX'; r=\$(mix_bridge_evidence 20260901T115900Z '$T/blog'); mix_evidence_has \"\$r\" implementer codex gpt-5.6-terra && mix_evidence_has \"\$r\" task-reviewer pi && mix_evidence_has \"\$r\" executor claude"
check "mix: evidence_has rejects wrong harness/model and non-zero exit" bash -c "MIX_E2E_LIB=1; . '$MIX'; r=\$(mix_bridge_evidence 20260901T115900Z '$T/blog'); ! mix_evidence_has \"\$r\" implementer pi && ! mix_evidence_has \"\$r\" implementer codex gpt-5.6-sol && ! mix_evidence_has \"\$r\" fix-applier codex && ! mix_evidence_has \"\$r\" re-reviewer pi"
check "mix: evidence_count by role regex and harness" bash -c "MIX_E2E_LIB=1; . '$MIX'; r=\$(mix_bridge_evidence 20260901T115900Z '$T/blog'); [ \"\$(mix_evidence_count \"\$r\" 'implementer|fix-applier')\" = 2 ] && [ \"\$(mix_evidence_count \"\$r\" '.*' pi)\" = 2 ] && [ \"\$(mix_evidence_count \"\$r\" 'panelist.*')\" = 0 ] && [ \"\$(mix_evidence_count '' '.*')\" = 0 ]"
# Header-less logs (a pre-0.6.5 bridge): role + start from the file name, harness "legacy" — or "legacy-codex"
# with the model from codex's banner — never counted as proof (found by mix-e2e.sh run 1: the relays ran the
# INSTALLED plugin's bridge, not the checkout's).
printf 'OpenAI Codex v0.152.0\n--------\nworkdir: /w\nmodel: gpt-5.6-terra\nprovider: openai\n' >"$T/blog/implementer-20260901T121400Z-1.log"
: >"$T/blog/task-reviewer-20260901T121500Z-2.log"
: >"$T/blog/task-reviewer-20260901T100000Z-3.log"   # older than since
check "mix: legacy codex log → legacy-codex row with banner model" bash -c "MIX_E2E_LIB=1; . '$MIX'; mix_bridge_evidence 20260901T115900Z '$T/blog' | grep -q '^implementer legacy-codex gpt-5.6-terra - - - 20260901T121400Z '"
check "mix: legacy empty log → legacy row; older-than-since excluded" bash -c "MIX_E2E_LIB=1; . '$MIX'; r=\$(mix_bridge_evidence 20260901T115900Z '$T/blog'); grep -q '^task-reviewer legacy - - - - 20260901T121500Z ' <<<\"\$r\" && ! grep -q 20260901T100000Z <<<\"\$r\""
check "mix: legacy rows are never proof"  bash -c "MIX_E2E_LIB=1; . '$MIX'; r=\$(mix_bridge_evidence 20260901T115900Z '$T/blog'); ! mix_evidence_has \"\$r\" implementer legacy-codex && [ \"\$(mix_evidence_count \"\$r\" '.*' legacy)\" = 1 ]"
rm -f "$T/blog/implementer-20260901T121400Z-1.log" "$T/blog/task-reviewer-20260901T121500Z-2.log" "$T/blog/task-reviewer-20260901T100000Z-3.log"
printf 'x\n{"text":"A Final Report that begins `BRIDGE-FAILED` is a failed dispatch"}\n{"text":"BRIDGE-FAILED exit=3 harness=pi role=task-reviewer log=/x"}\n' >"$T/ticklog"
check "mix: bridge_failed_count matches reports, not prose" bash -c "MIX_E2E_LIB=1; . '$MIX'; [ \"\$(mix_bridge_failed_count '$T/ticklog')\" = 1 ] && [ \"\$(mix_bridge_failed_count '$T/nope')\" = 0 ]"
printf 'prose mentions BRIDGE-FAILED but no result\n' >"$T/ticklog0"
check "mix: bridge_failed_count = single 0 on a match-free file (grep -c prints 0 AND exits 1)" bash -c "MIX_E2E_LIB=1; . '$MIX'; [ \"\$(mix_bridge_failed_count '$T/ticklog0')\" = 0 ]"
PL=$'Installed plugins:\n\n  ❯ other@m\n    Version: 1.0.0\n    Scope: user\n    Status: ✘ disabled\n\n  ❯ superagent@superagent-marketplace\n    Version: 0.6.4\n    Scope: user\n    Status: ✔ enabled\n\n  ❯ zzz@m\n    Version: 9\n'
check "mix: plugin_field reads the superagent block only" bash -c "MIX_E2E_LIB=1; . '$MIX'; [ \"\$(mix_plugin_field \"\$1\" Version)\" = 0.6.4 ] && mix_plugin_field \"\$1\" Status | grep -q enabled" _ "$PL"
check "mix: plugin_field empty when the plugin is absent" bash -c "MIX_E2E_LIB=1; . '$MIX'; [ -z \"\$(mix_plugin_field 'Installed plugins:' Version)\" ]"
check "mix: plugin_marketplace + installed_bridge path" bash -c "MIX_E2E_LIB=1; . '$MIX'; [ \"\$(mix_plugin_marketplace \"\$1\")\" = superagent-marketplace ] && [ \"\$(MIX_E2E_PLUGIN_CACHE=/c mix_installed_bridge \"\$1\")\" = /c/superagent-marketplace/superagent/0.6.4/scripts/role-bridge.sh ]" _ "$PL"
# The shimmed dry-runs below need an "installed" bridge with the evidence header.
mkdir -p "$T/cache/superagent-marketplace/superagent/0.6.4/scripts"; cp "$BRIDGE" "$T/cache/superagent-marketplace/superagent/0.6.4/scripts/role-bridge.sh"
export MIX_E2E_PLUGIN_CACHE="$T/cache"
# --dry-run under shims: claude must list the plugin, pi must list the reviewer's provider.
cat >"$SHIM/claude" <<EOF
#!/usr/bin/env bash
case "\$1 \$2" in "plugin list") printf '%s\n' "\$MIX_PLUGIN_LIST" ;; *) echo "2.1.252 (Claude Code)" ;; esac
EOF
cat >"$SHIM/pi" <<'EOF'
#!/usr/bin/env bash
case "$1" in --list-models) printf 'openai-codex  gpt-5.6-sol  272K\n' ;; *) echo 0.84.4 ;; esac
EOF
cat >"$SHIM/codex" <<'EOF'
#!/usr/bin/env bash
echo ok
EOF
chmod +x "$SHIM/claude" "$SHIM/pi" "$SHIM/codex"
export MIX_PLUGIN_LIST="$PL"
check "mix: --dry-run exits 0 and prints the mix" bash -c "cd '$T/cwd' && MIX_E2E_REPO=o/r '$MIX' --dry-run 2>&1 | tee '$T/mix-dry.out' | grep -q 'nothing created or armed' && grep -q 'implementer+fix-applier=codex:gpt-5.6-terra' '$T/mix-dry.out'"
check "mix: --dry-run writes no report"          bash -c "cd '$T/cwd' && MIX_E2E_REPO=o/r MIX_E2E_REPORT='$T/mix-dry-report.md' '$MIX' --dry-run >/dev/null 2>&1; [ ! -f '$T/mix-dry-report.md' ]"
check "mix: preflight refuses a pin outside claude+codex+pi" bash -c "cd '$T/cwd' && MIX_E2E_REPO=o/r MIX_E2E_REVIEWER=codex:gpt-5.6-sol '$MIX' --dry-run >/dev/null 2>'$T/mix-err'; [ \$? = 2 ] && grep -q 'must name pi' '$T/mix-err'"
check "mix: preflight refuses when pi lacks the reviewer's provider" bash -c "cd '$T/cwd' && MIX_E2E_REPO=o/r MIX_E2E_REVIEWER=pi:openai/gpt-5 '$MIX' --dry-run >/dev/null 2>'$T/mix-err'; [ \$? = 2 ] && grep -q \"provider 'openai'\" '$T/mix-err'"
check "mix: preflight refuses when the plugin is disabled" bash -c "cd '$T/cwd' && MIX_PLUGIN_LIST=\"\$(printf '%s' \"\$MIX_PLUGIN_LIST\" | sed 's/✔ enabled/✘ disabled/')\" MIX_E2E_REPO=o/r '$MIX' --dry-run >/dev/null 2>'$T/mix-err'; [ \$? = 2 ] && grep -q 'not enabled' '$T/mix-err'"
mkdir -p "$T/cache/superagent-marketplace/superagent/0.1.0/scripts"; cp "$BRIDGE" "$T/cache/superagent-marketplace/superagent/0.1.0/scripts/role-bridge.sh"   # the mismatching version still ships a header-carrying bridge
check "mix: preflight WARNs (not fails) on a plugin version mismatch" bash -c "cd '$T/cwd' && MIX_PLUGIN_LIST=\"\$(printf '%s' \"\$MIX_PLUGIN_LIST\" | sed 's/0.6.4/0.1.0/')\" MIX_E2E_REPO=o/r '$MIX' --dry-run >/dev/null 2>'$T/mix-err'; [ \$? = 0 ] && grep -q 'WARN installed claude plugin is 0.1.0' '$T/mix-err'"
check "mix: preflight refuses an installed bridge without the evidence header" bash -c "mkdir -p '$T/cache-old/superagent-marketplace/superagent/0.6.4/scripts'; printf '#!/bin/sh\necho old\n' >'$T/cache-old/superagent-marketplace/superagent/0.6.4/scripts/role-bridge.sh'; cd '$T/cwd' && MIX_E2E_PLUGIN_CACHE='$T/cache-old' MIX_E2E_REPO=o/r '$MIX' --dry-run >/dev/null 2>'$T/mix-err'; [ \$? = 2 ] && grep -q 'predates the evidence header' '$T/mix-err'"
check "mix: preflight refuses when the installed bridge is missing" bash -c "cd '$T/cwd' && MIX_E2E_PLUGIN_CACHE='$T/cache-none' MIX_E2E_REPO=o/r '$MIX' --dry-run >/dev/null 2>'$T/mix-err'; [ \$? = 2 ] && grep -q 'installed bridge not found' '$T/mix-err'"
check "mix: bad flag → exit 2"                   bash -c "'$MIX' --bogus >/dev/null 2>&1; [ \$? = 2 ]"

echo "bridge-test: $FAILS failure(s)"
[ "$FAILS" -eq 0 ]

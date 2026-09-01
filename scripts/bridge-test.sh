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
check "e2e: transition prints only on change"     bash -c "PI_E2E_LIB=1; . '$E2E'; a=\$(e2e_transition PLANNING 1); e2e_transition PLANNING 1 >/dev/null; b=\$(e2e_transition PLANNING 1); c=\$(e2e_transition RUNNING 1); [ -n \"\$a\" ] && [ -z \"\$b\" ] && [[ \"\$c\" == *'RUNNING iter=1' ]]"
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
check "e2e: SIGTERM mid-phase → cleanup, exit 143, within 10s" bash -c "cd '$T/cwd'; PI_E2E_REPO=o/r PI_E2E_REPORT='$T/e2e-term-report.md' '$E2E' >'$T/e2e-term.out' 2>&1 & p=\$!; sleep 3; t0=\$(date +%s); kill -TERM \$p; wait \$p; rc=\$?; el=\$(( \$(date +%s) - t0 )); [ \$rc = 143 ] && [ \$el -lt 10 ] && grep -q 'interrupted' '$T/e2e-term.out' && ! pgrep -f '^sleep 31\$' >/dev/null"

# --- launch.sh: a repo reached through a symlinked path (macOS /var → /private/var, /tmp → /private/tmp)
# must still accept its plan: REPO comes from git (physical) while the plan path must not be logical.
mkdir -p "$T/real/vault/g/master-plans" "$T/real/vault/g/loop-status"; ( cd "$T/real" && git init -q && printf '# plan\n' >vault/g/master-plans/p.md && git add -A && git -c user.email=t@t -c user.name=t commit -qm init )
ln -s "$T/real" "$T/link"
check "launch: plan under a symlinked repo path accepted (--dry-run)" bash -c "cd '$T/link' && SUPER_HARNESS=pi '$ROOT/scripts/launch.sh' '$T/link/vault/g/master-plans/p.md' --harness pi --dry-run 2>&1 | grep -q 'nothing created or armed'"

echo "bridge-test: $FAILS failure(s)"
[ "$FAILS" -eq 0 ]

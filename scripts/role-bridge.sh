#!/usr/bin/env bash
# role-bridge.sh — run ONE agent role on a foreign harness CLI, headless.
#
#   role-bridge.sh --harness claude|codex|cursor|pi --model <m|inherit> --effort <e|inherit>
#                  --cwd <dir> --prompt-file <file> [--role <name>] [--tools role|planner|executor|<list>]
#
# --tools picks the child's tool allowlist (claude: --allowedTools; pi: --tools; codex/cursor: ignored):
#   role     (default) claude Read,Edit,Write,Bash,Grep,Glob · pi read,edit,write,bash,grep,find,ls —
#            a leaf role (implementer/reviewer/panelist)
#   planner  a superplan dispatch: claude adds Task,Skill (it invokes skills); pi = the role set
#   executor a controller role (superrun) that must dispatch subagents and invoke skills itself:
#            claude Read,Edit,Write,Bash,Grep,Glob,Task,Skill; pi = NO --tools flag (built-ins plus
#            extension tools such as pi-subagents' `subagent`). This is how superagent runs superrun
#            as the TOP-LEVEL agent of its own CLI process (issue #25): a subagent cannot
#            foreground-wait on its own children, so the SDD controller has to be depth 0 in some process.
#   <list>   an explicit comma-separated allowlist in the harness's own tool names.
# Pi children always run with --approve (project trust for one run; the operator chose the repo)
# and --no-session (a bridged run is ephemeral; the log file is its record). When
# SUPERAGENT_PI_SKILLS is set (exported by superagent-tick.sh on the pi harness) it is passed as
# --skill so the child sees the plugin's skills.
# For --harness claude the print-mode background-wait ceiling is lifted (CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS
# defaults to 0 = wait indefinitely, mirroring superagent-tick.sh; an operator-set value is kept),
# so a nested controller's subagents are never guillotined mid-flight (issue #15).
#
# Reads the prompt from <file>, runs the harness CLI in <dir>, prints the CLI's final message on
# stdout and NOTHING else. CLI chatter/stderr goes to $TMPDIR/superagent-bridge/<role>-<stamp>.log
# (path printed on stderr as "role-bridge: log=<path>").
# Exit: 0 ok · 2 CLI binary not found · 3 CLI exited non-zero · 4 CLI exited 0 with empty result ·
#       64 usage. "inherit" omits the corresponding flag.
# Env: SUPER_CODEX_SANDBOX (danger-full-access default | workspace-write) for --harness codex;
#      an out-of-domain value is a usage error (exit 64).
# BRIDGE_UNSET_CLAUDECODE is a bake-time constant set just below, NOT an environment knob:
# Task 1's T5 probe (claude CLI 2.1.250) found a plain nested `claude -p` succeeds under
# CLAUDECODE=1, so it stays false (CLAUDECODE is left set) unless a future probe says otherwise.
set -uo pipefail

BRIDGE_UNSET_CLAUDECODE=false   # T5 probe passed under CLAUDECODE=1; no need to unset it

harness=""; model="inherit"; effort="inherit"; cwd=""; prompt_file=""; role="role"; tools="role"
TOOLS_ROLE="Read,Edit,Write,Bash,Grep,Glob"
TOOLS_EXECUTOR="Read,Edit,Write,Bash,Grep,Glob,Task,Skill"
TOOLS_PI_ROLE="read,edit,write,bash,grep,find,ls"
while [ $# -gt 0 ]; do
  case "$1" in
    --harness)     [ $# -ge 2 ] || { echo "role-bridge: --harness requires a value" >&2; exit 64; }; harness="$2"; shift 2 ;;
    --model)       [ $# -ge 2 ] || { echo "role-bridge: --model requires a value" >&2; exit 64; }; model="$2"; shift 2 ;;
    --effort)      [ $# -ge 2 ] || { echo "role-bridge: --effort requires a value" >&2; exit 64; }; effort="$2"; shift 2 ;;
    --cwd)         [ $# -ge 2 ] || { echo "role-bridge: --cwd requires a value" >&2; exit 64; }; cwd="$2"; shift 2 ;;
    --prompt-file) [ $# -ge 2 ] || { echo "role-bridge: --prompt-file requires a value" >&2; exit 64; }; prompt_file="$2"; shift 2 ;;
    --role)        [ $# -ge 2 ] || { echo "role-bridge: --role requires a value" >&2; exit 64; }; role="$2"; shift 2 ;;
    --tools)       [ $# -ge 2 ] || { echo "role-bridge: --tools requires a value" >&2; exit 64; }; tools="$2"; shift 2 ;;
    *) echo "role-bridge: unknown argument '$1'" >&2; exit 64 ;;
  esac
done
case "$harness" in claude|codex|cursor|pi) ;; *) echo "role-bridge: --harness must be claude|codex|cursor|pi (got '$harness')" >&2; exit 64 ;; esac
[ -d "$cwd" ] || { echo "role-bridge: --cwd '$cwd' is not a directory" >&2; exit 64; }
[ -f "$prompt_file" ] || { echo "role-bridge: --prompt-file '$prompt_file' not found" >&2; exit 64; }
case "$tools" in
  role)     allowed="$TOOLS_ROLE";     pi_allowed="$TOOLS_PI_ROLE" ;;
  planner)  allowed="$TOOLS_EXECUTOR"; pi_allowed="$TOOLS_PI_ROLE" ;;
  executor) allowed="$TOOLS_EXECUTOR"; pi_allowed="" ;;
  "")       echo "role-bridge: --tools must be role|planner|executor|<comma-separated list> (got '')" >&2; exit 64 ;;
  *)        allowed="$tools";          pi_allowed="$tools" ;;
esac

# SUPER_CODEX_SANDBOX is read below for --harness codex; reject an out-of-domain value here
# rather than silently falling through to the danger-full-access branch.
case "${SUPER_CODEX_SANDBOX:-}" in
  ""|danger-full-access|workspace-write) ;;
  *) echo "role-bridge: SUPER_CODEX_SANDBOX must be danger-full-access|workspace-write (got '$SUPER_CODEX_SANDBOX')" >&2; exit 64 ;;
esac

# --role reaches the log path, so keep it to a safe basename charset: anything outside
# [A-Za-z0-9_-] becomes "_" (a "../x" role can never escape $logdir).
role_safe="$(printf '%s' "$role" | tr -c 'A-Za-z0-9_-' '_')"
[ -n "$role_safe" ] || role_safe=role
logdir="${TMPDIR:-/tmp}/superagent-bridge"; mkdir -p "$logdir"; chmod 700 "$logdir" 2>/dev/null || true
stamp="$(date -u '+%Y%m%dT%H%M%SZ')-$$"
log="$logdir/${role_safe}-${stamp}.log"

bin=""; case "$harness" in claude) bin=claude ;; codex) bin=codex ;; cursor) bin=agent ;; pi) bin=pi ;; esac
command -v "$bin" >/dev/null 2>&1 || { echo "role-bridge: '$bin' not found on PATH (harness=$harness)" >&2; exit 2; }
# Announced only once the binary exists, so an exit-2 run never advertises a log nobody wrote.
echo "role-bridge: log=$log" >&2

result=""; rc=0
case "$harness" in
  claude)
    args=(-p)
    [ "$model"  != inherit ] && args+=(--model "$model")
    [ "$effort" != inherit ] && args+=(--effort "$effort")
    args+=(--allowedTools "$allowed")
    envargs=(-u CLAUDE_CODE_EFFORT_LEVEL "CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=${CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS:-0}")
    [ "$BRIDGE_UNSET_CLAUDECODE" = true ] && envargs+=(-u CLAUDECODE)
    result="$(cd "$cwd" && env "${envargs[@]}" claude "${args[@]}" <"$prompt_file" 2>>"$log")" || rc=$?
    ;;
  codex)
    args=(exec)
    if [ "${SUPER_CODEX_SANDBOX:-danger-full-access}" = workspace-write ]; then
      args+=(--sandbox workspace-write -c sandbox_workspace_write.network_access=true)
    else
      args+=(--dangerously-bypass-approvals-and-sandbox)
    fi
    out="$logdir/${role_safe}-${stamp}.last"
    args+=(--skip-git-repo-check -C "$cwd")
    [ "$model"  != inherit ] && args+=(-m "$model")
    [ "$effort" != inherit ] && args+=(-c "model_reasoning_effort=$effort")
    args+=(-o "$out" -)
    (cd "$cwd" && codex "${args[@]}" <"$prompt_file" >>"$log" 2>&1) || rc=$?
    [ -f "$out" ] && result="$(cat "$out")"
    ;;
  cursor)
    args=(-p "$(cat "$prompt_file")" --trust --force)
    [ "$model" != inherit ] && args+=(--model "$model")
    args+=(--output-format text)
    result="$(cd "$cwd" && agent "${args[@]}" 2>>"$log")" || rc=$?
    ;;
  pi)
    args=(-p --approve --no-session)
    [ -n "${SUPERAGENT_PI_SKILLS:-}" ] && args+=(--skill "$SUPERAGENT_PI_SKILLS")
    # pi carries the thinking level as a ":<level>" suffix on the model string. With no model
    # the CLI's --thinking flag carries it instead. An explicit level already on the model
    # ("openai/gpt-5:high") wins — never suffix twice.
    m="$model"
    if [ "$effort" != inherit ]; then
      if [ "$model" = inherit ]; then
        args+=(--thinking "$effort")
      elif printf '%s' "$m" | grep -q ':[A-Za-z0-9_-]*$'; then
        echo "role-bridge: warning — --model '$m' already pins a level; ignoring --effort '$effort'" >&2
      else
        m="${m}:${effort}"
      fi
    fi
    [ "$model" != inherit ] && args+=(--model "$m")
    [ -n "$pi_allowed" ] && args+=(--tools "$pi_allowed")
    result="$(cd "$cwd" && pi "${args[@]}" <"$prompt_file" 2>>"$log")" || rc=$?
    ;;
esac

if [ "$rc" -ne 0 ]; then echo "role-bridge: $bin exited $rc (see $log)" >&2; exit 3; fi
if [ -z "$result" ]; then echo "role-bridge: $bin returned an empty result (see $log)" >&2; exit 4; fi
printf '%s\n' "$result"

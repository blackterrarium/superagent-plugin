#!/usr/bin/env bash
# role-bridge.sh — run ONE agent role on a foreign harness CLI, headless.
#
#   role-bridge.sh --harness claude|codex|cursor|pi --model <m|inherit> --effort <e|inherit>
#                  --cwd <dir> --prompt-file <file> [--role <name>]
#
# Reads the prompt from <file>, runs the harness CLI in <dir>, prints the CLI's final message on
# stdout and NOTHING else. CLI chatter/stderr goes to $TMPDIR/superagent-bridge/<role>-<stamp>.log
# (path printed on stderr as "role-bridge: log=<path>").
# Exit: 0 ok · 2 CLI binary not found · 3 CLI exited non-zero · 4 CLI exited 0 with empty result ·
#       64 usage. "inherit" omits the corresponding flag.
# Env: SUPER_CODEX_SANDBOX (danger-full-access default | workspace-write) for --harness codex.
# BRIDGE_UNSET_CLAUDECODE=<true|false> — Task 1's T5 probe (claude CLI 2.1.250) found a plain
# nested `claude -p` succeeds under CLAUDECODE=1, so this stays false (CLAUDECODE is left set).
set -uo pipefail

BRIDGE_UNSET_CLAUDECODE=false   # T5 probe passed under CLAUDECODE=1; no need to unset it

harness=""; model="inherit"; effort="inherit"; cwd=""; prompt_file=""; role="role"
while [ $# -gt 0 ]; do
  case "$1" in
    --harness)     [ $# -ge 2 ] || { echo "role-bridge: --harness requires a value" >&2; exit 64; }; harness="$2"; shift 2 ;;
    --model)       [ $# -ge 2 ] || { echo "role-bridge: --model requires a value" >&2; exit 64; }; model="$2"; shift 2 ;;
    --effort)      [ $# -ge 2 ] || { echo "role-bridge: --effort requires a value" >&2; exit 64; }; effort="$2"; shift 2 ;;
    --cwd)         [ $# -ge 2 ] || { echo "role-bridge: --cwd requires a value" >&2; exit 64; }; cwd="$2"; shift 2 ;;
    --prompt-file) [ $# -ge 2 ] || { echo "role-bridge: --prompt-file requires a value" >&2; exit 64; }; prompt_file="$2"; shift 2 ;;
    --role)        [ $# -ge 2 ] || { echo "role-bridge: --role requires a value" >&2; exit 64; }; role="$2"; shift 2 ;;
    *) echo "role-bridge: unknown argument '$1'" >&2; exit 64 ;;
  esac
done
case "$harness" in claude|codex|cursor|pi) ;; *) echo "role-bridge: --harness must be claude|codex|cursor|pi (got '$harness')" >&2; exit 64 ;; esac
[ -d "$cwd" ] || { echo "role-bridge: --cwd '$cwd' is not a directory" >&2; exit 64; }
[ -f "$prompt_file" ] || { echo "role-bridge: --prompt-file '$prompt_file' not found" >&2; exit 64; }

logdir="${TMPDIR:-/tmp}/superagent-bridge"; mkdir -p "$logdir"
stamp="$(date -u '+%Y%m%dT%H%M%SZ')-$$"
log="$logdir/${role}-${stamp}.log"
echo "role-bridge: log=$log" >&2

bin=""; case "$harness" in claude) bin=claude ;; codex) bin=codex ;; cursor) bin=agent ;; pi) bin=pi ;; esac
command -v "$bin" >/dev/null 2>&1 || { echo "role-bridge: '$bin' not found on PATH (harness=$harness)" >&2; exit 2; }

result=""; rc=0
case "$harness" in
  claude)
    args=(-p)
    [ "$model"  != inherit ] && args+=(--model "$model")
    [ "$effort" != inherit ] && args+=(--effort "$effort")
    args+=(--allowedTools "Read,Edit,Write,Bash,Grep,Glob")
    envargs=(-u CLAUDE_CODE_EFFORT_LEVEL)
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
    out="$logdir/${role}-${stamp}.last"
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
    args=(-p)
    m="$model"; [ "$effort" != inherit ] && m="${m}:${effort}"
    [ "$model" != inherit ] && args+=(--model "$m")
    result="$(cd "$cwd" && pi "${args[@]}" <"$prompt_file" 2>>"$log")" || rc=$?
    ;;
esac

if [ "$rc" -ne 0 ]; then echo "role-bridge: $bin exited $rc (see $log)" >&2; exit 3; fi
if [ -z "$result" ]; then echo "role-bridge: $bin returned an empty result (see $log)" >&2; exit 4; fi
printf '%s\n' "$result"

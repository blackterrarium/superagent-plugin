#!/usr/bin/env bash
# bridge-fanout.sh — run N role-bridge.sh invocations CONCURRENTLY and block until all finish.
#
#   bridge-fanout.sh --harness <h> --model <m|inherit> --effort <e|inherit> --cwd <dir>
#                    [--tools role|planner|executor|<list>] [--role <name>] [--timeout <sec>]
#                    --prompt-file <f> [--prompt-file <f> ...]
#
# The L7 panel primitive for harnesses with no blocking parallel subagent tool (pi): the supervisor
# makes ONE blocking shell call and gets every panelist's verdict back — "wait, never poll".
# Each prompt file becomes one role-bridge.sh child (--role <name>-<n>). stdout, in prompt-file
# order:
#   === PANELIST <n> exit=<rc> ===
#   <the bridge's stdout>            (or: BRIDGE-FAILED exit=<rc> harness=<h> role=<name>-<n> log=<path>)
#   === END <n> ===
# --timeout (default 1800 s): after it elapses, still-running children are killed (with their
# CLI grandchildren) and reported as failed. Exit: 0 every child ok · 3 any child failed or timed
# out · 64 usage. Env: SUPERAGENT_BRIDGE overrides the bridge path (default: sibling role-bridge.sh).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE="${SUPERAGENT_BRIDGE:-$SCRIPT_DIR/role-bridge.sh}"

harness=""; model="inherit"; effort="inherit"; cwd=""; tools="role"; role="panelist"; timeout=1800
files=()
usage() { echo "bridge-fanout: $1" >&2; exit 64; }
while [ $# -gt 0 ]; do
  case "$1" in
    --harness)     [ $# -ge 2 ] || usage "--harness requires a value"; harness="$2"; shift 2 ;;
    --model)       [ $# -ge 2 ] || usage "--model requires a value"; model="$2"; shift 2 ;;
    --effort)      [ $# -ge 2 ] || usage "--effort requires a value"; effort="$2"; shift 2 ;;
    --cwd)         [ $# -ge 2 ] || usage "--cwd requires a value"; cwd="$2"; shift 2 ;;
    --tools)       [ $# -ge 2 ] || usage "--tools requires a value"; tools="$2"; shift 2 ;;
    --role)        [ $# -ge 2 ] || usage "--role requires a value"; role="$2"; shift 2 ;;
    --timeout)     [ $# -ge 2 ] || usage "--timeout requires a value"; timeout="$2"; shift 2 ;;
    --prompt-file) [ $# -ge 2 ] || usage "--prompt-file requires a value"; files+=("$2"); shift 2 ;;
    *) usage "unknown argument '$1'" ;;
  esac
done
[ -n "$harness" ] || usage "--harness is required"
[ -d "$cwd" ] || usage "--cwd '$cwd' is not a directory"
[ "${#files[@]}" -ge 1 ] || usage "at least one --prompt-file is required"
[[ "$timeout" =~ ^[1-9][0-9]*$ ]] || usage "--timeout must be a positive integer (seconds)"
for f in "${files[@]}"; do [ -f "$f" ] || usage "--prompt-file '$f' not found"; done
[ -x "$BRIDGE" ] || usage "bridge not executable: $BRIDGE"

work="$(mktemp -d "${TMPDIR:-/tmp}/superagent-fanout.XXXXXX")"
trap 'rm -rf "$work"' EXIT

pids=(); n=0
for f in "${files[@]}"; do
  n=$((n + 1))
  "$BRIDGE" --harness "$harness" --model "$model" --effort "$effort" --tools "$tools" \
            --cwd "$cwd" --prompt-file "$f" --role "${role}-${n}" \
            >"$work/$n.out" 2>"$work/$n.err" &
  pids+=($!)
done

# Watchdog: after --timeout seconds kill every child still running, grandchildren first so a
# hung CLI does not outlive its bridge. Stdout/stderr are closed here (not just left inherited):
# a caller capturing our output via command substitution keeps its pipe open until every process
# holding the write end exits, and killing $wd does not touch its already-forked `sleep` child —
# an orphaned, still-sleeping `sleep "$timeout"` holding that fd would hang the caller for the
# full --timeout even after every real child has finished.
(
  sleep "$timeout"
  for p in "${pids[@]}"; do
    pkill -P "$p" 2>/dev/null || true
    kill "$p" 2>/dev/null || true
  done
) >/dev/null 2>&1 &
wd=$!

failed=0; i=0
for p in "${pids[@]}"; do
  i=$((i + 1))
  wait "$p"; rc=$?
  echo "$rc" >"$work/$i.rc"
  [ "$rc" -eq 0 ] || failed=$((failed + 1))
done
# Reap the watchdog's own `sleep "$timeout"` too: on the happy path (every child already
# finished) $wd is still asleep, and killing only the $wd subshell wrapper leaves that `sleep`
# reparented to init, lingering for the rest of --timeout (up to 1800s default).
pkill -P "$wd" 2>/dev/null || true
kill "$wd" 2>/dev/null || true
wait "$wd" 2>/dev/null || true

i=0
for _ in "${pids[@]}"; do
  i=$((i + 1))
  rc="$(cat "$work/$i.rc")"
  echo "=== PANELIST $i exit=$rc ==="
  if [ "$rc" -eq 0 ]; then
    cat "$work/$i.out"
  else
    logpath="$(sed -n 's/^role-bridge: log=//p' "$work/$i.err" | head -1)"
    echo "BRIDGE-FAILED exit=$rc harness=$harness role=${role}-${i} log=${logpath:-none}"
    tail -n 40 "$work/$i.err" 2>/dev/null || true
  fi
  echo "=== END $i ==="
done

[ "$failed" -eq 0 ] && exit 0 || exit 3

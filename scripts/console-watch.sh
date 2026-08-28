#!/usr/bin/env bash
# console-watch.sh — the monitor half of the console plane. Polls a loop-status
# file and alerts when the loop parks on WAITING FOR INPUT (a decision the L7
# panel could not resolve) so a human can attach an interactive console and
# answer. Exits when the loop reaches DONE.
#
# This is deliberately read-only: it never writes the loop file, so it can be
# started and stopped independently of the driver with zero effect on loop
# progress. It emits an `AGENT_LOOP_WAKE_superagent {...}` sentinel line so a
# watcher can wake an interactive agent by matching
# `^AGENT_LOOP_WAKE_superagent`; it also fires notify-send when available.
#
#   console-watch.sh <LOOP_FILE> [interval_secs]     (default interval: 60)
#
# To ANSWER a parked decision: answer.sh [--no-kick] [--replace] <slug> "<option>"
# (records the answer under the lock and kicks a tick now; --no-kick records only,
# --replace overwrites an answer already recorded — both accepted in any
# position); or run one attended --tick; or hand-edit `answer: <option>` under
# ## Pending decision (next scheduled tick resumes).
set -euo pipefail

LOOP_FILE="${LOOP_FILE:-${1:-}}"
INTERVAL="${2:-60}"
[[ -z "$LOOP_FILE" ]] && { echo "usage: console-watch.sh <LOOP_FILE> [interval_secs]" >&2; exit 2; }

echo "Watching $LOOP_FILE every ${INTERVAL}s for 'WAITING FOR INPUT' / 'DONE' (Ctrl-C to stop)."
last=""
while true; do
  if [[ -f "$LOOP_FILE" ]]; then
    status="$(sed -n 's/^status:[[:space:]]*//p' "$LOOP_FILE" | head -1)"
    if [[ "$status" != "$last" ]]; then
      echo "$(date -u +%H:%M:%SZ) status: ${status:-<none>}"
      last="$status"
    fi
    case "$status" in
      "WAITING FOR INPUT")
        echo "AGENT_LOOP_WAKE_superagent {\"loop\":\"$LOOP_FILE\",\"status\":\"WAITING FOR INPUT\"}"
        command -v notify-send >/dev/null 2>&1 && \
          notify-send "superagent" "WAITING FOR INPUT: $LOOP_FILE" || true
        ;;
      "DONE")
        echo "AGENT_LOOP_WAKE_superagent {\"loop\":\"$LOOP_FILE\",\"status\":\"DONE\"}"
        echo "Loop reached DONE — stopping watch."
        exit 0
        ;;
    esac
  else
    echo "$(date -u +%H:%M:%SZ) loop file not found yet: $LOOP_FILE"
  fi
  sleep "$INTERVAL"
done

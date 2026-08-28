#!/usr/bin/env bash
# answer.sh — answer a loop parked on WAITING FOR INPUT and resume it NOW.
#
#   answer.sh [--no-kick] <slug> <answer text…>
#
# Writes `answer: <text>` directly under `## Pending decision` in the loop file
# (the line the skill's WAITING FOR INPUT branch consumes), holding the L3 lock
# so it never races a tick, then kicks one tick through the registered scheduler
# entry so the loop resumes in seconds instead of after the next interval
# (superagent-tick.sh's SUPER_INPUT_GATE skips sessions until this line exists).
# --no-kick records the answer only; the next scheduled tick resumes.
#
# Exit codes: 2 usage · 1 no registered loop / loop file missing · 3 loop is not
# WAITING FOR INPUT · 4 a tick holds the lock (retry) · 5 no ## Pending decision
# heading · 0 recorded (kick failure is a warning, not an error).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"

KICK=true
if [[ "${1:-}" == "--no-kick" ]]; then KICK=false; shift; fi
SLUG="${1:-}"; [[ $# -gt 0 ]] && shift
ANSWER="${*:-}"
if [[ -z "$SLUG" || -z "$ANSWER" ]]; then
  echo "usage: answer.sh [--no-kick] <slug> <answer text…>" >&2
  exit 2
fi

CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/superagent"
ENV_FILE="$CONF_DIR/$SLUG.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "answer: no registered loop '$SLUG' ($ENV_FILE missing) — see status.sh for registered slugs" >&2
  exit 1
fi
LOOP_FILE="$(sed -n 's/^LOOP_FILE=//p' "$ENV_FILE" | head -1)"
if [[ -z "$LOOP_FILE" || ! -f "$LOOP_FILE" ]]; then
  echo "answer: loop file missing for '$SLUG': ${LOOP_FILE:-<unset>}" >&2
  exit 1
fi

status="$(superagent_loop_status "$LOOP_FILE")"
if [[ "$status" != "WAITING FOR INPUT" ]]; then
  echo "answer: loop '$SLUG' is '${status:-<none>}', not WAITING FOR INPUT — nothing to answer" >&2
  exit 3
fi

LOCK_DIR="$(dirname "$LOOP_FILE")/.$(basename "$LOOP_FILE").lockd"
if existing="$(superagent_pending_answer "$LOOP_FILE")"; then
  echo "answer: an answer is already recorded ('$existing') — not overwriting; kicking a tick to consume it" >&2
else
  # Check the heading BEFORE touching the lock/file — wc -l can't tell "no
  # heading matched" from "no trailing newline" (awk's print always appends
  # one), so a heading-less file would otherwise be silently rewritten.
  grep -q '^## Pending decision' "$LOOP_FILE" || {
    echo "answer: no '## Pending decision' heading in $LOOP_FILE — cannot place the answer" >&2
    exit 5
  }
  # Same lock discipline as a tick (superloop L3): mkdir is the atomic acquire.
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "answer: a tick holds the lock ($LOCK_DIR) — retry when it finishes (status.sh $SLUG)" >&2
    exit 4
  fi
  echo $$ >"$LOCK_DIR/owner"
  trap 'rm -rf "$LOCK_DIR"' EXIT
  # A signal received mid-write must still run the EXIT trap and release the lock.
  trap 'exit 143' TERM
  trap 'exit 130' INT
  tmp="$(mktemp)"
  # Pass the answer via the environment, not `awk -v` — -v runs escape
  # processing on its value, so a literal backslash (e.g. `C:\new\table`)
  # would be mangled into control characters/newlines.
  ANS="$ANSWER" awk '{ print } /^## Pending decision/ && !done { print "answer: " ENVIRON["ANS"]; done=1 }' \
    "$LOOP_FILE" >"$tmp"
  cat "$tmp" >"$LOOP_FILE"   # in place: keep the file's inode/permissions
  rm -f "$tmp"
  rm -rf "$LOCK_DIR"; trap - EXIT TERM INT
  echo "answer: recorded 'answer: $ANSWER' in $LOOP_FILE"
fi

if [[ "$KICK" != true ]]; then
  echo "answer: --no-kick — the next scheduled tick resumes the loop"
  exit 0
fi
if superagent_kick_tick "$SLUG" 2>/dev/null; then
  echo "answer: kicked tick for '$SLUG' — follow it: tail -f /tmp/superagent-$(basename "$LOOP_FILE" .md).log"
else
  echo "answer: could not kick '$SLUG' (scheduler entry not loaded?) — the next scheduled tick resumes; if the loop is disarmed, re-arm: $SCRIPT_DIR/install-timer.sh $SLUG $LOOP_FILE" >&2
fi
exit 0

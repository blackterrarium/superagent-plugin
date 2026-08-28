#!/usr/bin/env bash
# answer.sh — answer a loop parked on WAITING FOR INPUT and resume it NOW.
#
#   answer.sh [--no-kick] [--replace] <slug> <answer text…>
#
# Writes `answer: <text>` directly under `## Pending decision` in the loop file
# (the line the skill's WAITING FOR INPUT branch consumes), holding the L3 lock
# so it never races a tick, then kicks one tick through the registered scheduler
# entry so the loop resumes in seconds instead of after the next interval
# (superagent-tick.sh's SUPER_INPUT_GATE skips sessions until this line exists).
# The flags are accepted in any position (before or after the slug/answer):
#   --no-kick   record the answer only; the next scheduled tick resumes.
#   --replace   overwrite an answer: line already recorded in the block
#               (without it, an existing answer is kept and only kicked).
#
# Exit codes: 2 usage · 1 no registered loop / loop file missing · 3 loop is not
# WAITING FOR INPUT · 4 a tick holds the lock (retry) · 5 no ## Pending decision
# heading · 0 recorded (kick failure is a warning, not an error).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"

usage() {
  echo "usage: answer.sh [--no-kick] [--replace] <slug> <answer text…>" >&2
  exit 2
}

KICK=true
REPLACE=false
# Flags anywhere BEFORE the slug/answer, so `answer.sh g "Option A" --no-kick`
# is not silently recorded as part of the answer text. Parsing stops at the
# first non-flag word: everything from there on is slug + answer, so an answer
# that itself starts with `-` still needs to follow the slug (it does).
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-kick) KICK=false; shift ;;
    --replace) REPLACE=true; shift ;;
    --)        shift; break ;;
    --*)       echo "answer: unknown option '$1'" >&2; usage ;;
    *)         break ;;
  esac
done
SLUG="${1:-}"; [[ $# -gt 0 ]] && shift
# A trailing flag is a flag, not answer text (`answer.sh g "Option A" --no-kick`).
ARGS=()
for a in "$@"; do
  case "$a" in
    --no-kick) KICK=false ;;
    --replace) REPLACE=true ;;
    *)         ARGS+=("$a") ;;
  esac
done
ANSWER="${ARGS[*]:-}"
[[ -n "$SLUG" && -n "$ANSWER" ]] || usage

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

not_parked() {
  echo "answer: loop '$SLUG' is '${1:-<none>}', not WAITING FOR INPUT — nothing to answer" >&2
  exit 3
}
status="$(superagent_loop_status "$LOOP_FILE")"
[[ "$status" == "WAITING FOR INPUT" ]] || not_parked "$status"

LOCK_DIR="$(dirname "$LOOP_FILE")/.$(basename "$LOOP_FILE").lockd"
skip_write=false
if existing="$(superagent_pending_answer "$LOOP_FILE")" && [[ "$REPLACE" != true ]]; then
  echo "answer: an answer is already recorded ('$existing') — not overwriting (use --replace); kicking a tick to consume it" >&2
  skip_write=true
fi
if [[ "$skip_write" != true ]]; then
  # Check the heading BEFORE touching the lock/file — wc -l can't tell "no
  # heading matched" from "no trailing newline" (awk's print always appends
  # one), so a heading-less file would otherwise be silently rewritten.
  grep -q '^## Pending decision' "$LOOP_FILE" || {
    echo "answer: no '## Pending decision' heading in $LOOP_FILE — cannot place the answer" >&2
    exit 5
  }
  # Same lock discipline as a tick (superloop L3): mkdir is the atomic acquire.
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    # superloop L3: a lock whose recorded owner PID is dead belongs to a crashed
    # tick — reap it and retry once. A live owner, no owner file at all, or a
    # malformed owner (not a bare PID — only age-stealable, which is a tick's
    # job), is a real in-flight lock: refuse.
    lock_owner="$(cat "$LOCK_DIR/owner" 2>/dev/null || true)"
    if [[ "$lock_owner" =~ ^[0-9]+$ ]] && ! kill -0 "$lock_owner" 2>/dev/null; then
      echo "answer: reaped stale lock (owner pid $lock_owner is dead)" >&2
      rm -rf "$LOCK_DIR"
    fi
    if ! mkdir "$LOCK_DIR" 2>/dev/null; then
      echo "answer: a tick holds the lock ($LOCK_DIR) — retry when it finishes (status.sh $SLUG); if no tick is running and the lock is old, force-stop.sh --slug $SLUG reaps it" >&2
      exit 4
    fi
  fi
  # Arm the release traps BEFORE writing `owner`: a kill landing between the
  # mkdir and that write would otherwise strand an ownerless lock that superloop
  # only steals after the 90-minute staleness window.
  trap 'rm -rf "$LOCK_DIR"; rm -f "${tmp:-}"' EXIT
  # A signal received mid-write must still run the EXIT trap and release the lock.
  trap 'exit 143' TERM
  trap 'exit 130' INT
  echo $$ >"$LOCK_DIR/owner"
  # Re-read under the lock: between the pre-lock checks above and the acquire, a
  # tick could have finished and moved the loop on (or recorded its own answer).
  status="$(superagent_loop_status "$LOOP_FILE")"
  [[ "$status" == "WAITING FOR INPUT" ]] || not_parked "$status"
  if existing="$(superagent_pending_answer "$LOOP_FILE")" && [[ "$REPLACE" != true ]]; then
    echo "answer: an answer is already recorded ('$existing') — not overwriting (use --replace); kicking a tick to consume it" >&2
    skip_write=true
  fi
  if [[ "$skip_write" == true ]]; then
    rm -rf "$LOCK_DIR"; trap - EXIT TERM INT   # nothing to write — never kick while holding the lock
  fi
fi
if [[ "$skip_write" != true ]]; then
  tmp="$(mktemp)"
  # Pass the answer via the environment, not `awk -v` — -v runs escape
  # processing on its value, so a literal backslash (e.g. `C:\new\table`)
  # would be mangled into control characters/newlines.
  # With --replace, drop any existing answer: line inside ## Pending decision
  # (never one under another heading) before inserting the new one.
  ANS="$ANSWER" REPL="$REPLACE" awk '
    /^## Pending decision/ { print; if (!ins) { print "answer: " ENVIRON["ANS"]; ins=1 } ; inblk=1; next }
    /^## / { inblk=0 }
    inblk && ENVIRON["REPL"] == "true" && /^[[:space:]]*answer:[[:space:]]*/ { next }
    { print }
  ' "$LOOP_FILE" >"$tmp"
  cat "$tmp" >"$LOOP_FILE"   # in place: keep the file's inode/permissions
  rm -f "$tmp"; tmp=
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

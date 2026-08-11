#!/usr/bin/env bash
# status.sh — enumerate every superagent external loop installed on this host and
# report its live state. Multi-instance aware: the registry is the set of per-goal
# env files under ~/.config/superagent/*.env (written by install-timer.sh), so one
# invocation covers all concurrent loops.
#
#   status.sh                 human table across all loops
#   status.sh --json          machine-readable JSON array (one object per loop)
#   status.sh <slug>          drill into one loop (status, pending decision, tail)
#   status.sh --json <slug>   single-loop JSON object
#
# Fields per loop: slug, status, iteration, timer (active?), tick (running
# now?), lock (held?), input (parked on WAITING FOR INPUT?), done?, next fire.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"

CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/superagent"
JSON=0
ONE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) JSON=1; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    -*) echo "unknown flag: $1" >&2; exit 2 ;;
    *) ONE="$1"; shift ;;
  esac
done

_field() { # <loop-file> <key>  -> first "key: value" match
  sed -n "s/^$2:[[:space:]]*//p" "$1" | head -1
}

_json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

# Populate globals for one slug.
REPO=""; LOOP_FILE=""; TICK_TIMEOUT=""
_collect() {
  local slug="$1" envf="$CONF_DIR/$1.env"
  REPO=""; LOOP_FILE=""; TICK_TIMEOUT=""
  if [[ -f "$envf" ]]; then
    set -a; # shellcheck disable=SC1090
    . "$envf"; set +a
  fi
  status=""; iteration=""; pending=0; done_=0; exists=0
  if [[ -n "$LOOP_FILE" && -f "$LOOP_FILE" ]]; then
    exists=1
    status="$(_field "$LOOP_FILE" status)"
    iteration="$(_field "$LOOP_FILE" iteration)"
    [[ "$status" == "WAITING FOR INPUT" ]] && pending=1
    [[ "$status" == "DONE" ]] && done_=1
  fi
  if [[ "$(superagent_scheduler)" == launchd ]]; then
    # One launchd job is both timer and service: loaded (any state) ~ timer
    # active; state == running ~ tick in flight.
    local ld_state; ld_state="$(superagent_launchd_state "$slug")"
    timer_active="$([[ -n "$ld_state" ]] && echo active || echo inactive)"
    tick_running="$([[ "$ld_state" == running ]] && echo active || echo inactive)"
    # launchd exposes no next-fire timestamp; report the configured interval.
    next_fire="$({ launchctl print "$(superagent_launchd_domain)/$(superagent_launchd_label "$slug")" 2>/dev/null || true; } \
      | sed -n 's/.*run interval = \([0-9]*\) seconds.*/every \1s/p' | head -1)"
    [[ -z "$next_fire" ]] && next_fire="-"
  else
    timer_active="$(systemctl --user is-active "superagent-tick@$slug.timer" 2>/dev/null || true)"
    tick_running="$(systemctl --user is-active "superagent-tick@$slug.service" 2>/dev/null || true)"
    next_fire="$(systemctl --user show -p NextElapseUSecRealtime --value "superagent-tick@$slug.timer" 2>/dev/null || true)"
    [[ -z "$next_fire" || "$next_fire" == "0" ]] && next_fire="-"
  fi
  lock_held=0
  if [[ -n "$LOOP_FILE" ]]; then
    local d b; d="$(dirname "$LOOP_FILE")"; b="$(basename "$LOOP_FILE")"
    [[ -d "$d/.$b.lockd" ]] && lock_held=1
  fi
  # Explicit success: under set -e a trailing `[[ ... ]] && ...` guard that
  # evaluates false would otherwise become the function's (failing) return value
  # and silently kill the whole script.
  return 0
}

# Slug list.
shopt -s nullglob
slugs=()
if [[ -n "$ONE" ]]; then
  [[ -f "$CONF_DIR/$ONE.env" ]] || { echo "no such loop: $ONE (looked in $CONF_DIR/$ONE.env)" >&2; exit 1; }
  slugs=("$ONE")
else
  for envf in "$CONF_DIR"/*.env; do slugs+=("$(basename "$envf" .env)"); done
fi

if [[ ${#slugs[@]} -eq 0 ]]; then
  if [[ "$JSON" == 1 ]]; then echo "[]"; else echo "No superagent loops registered ($CONF_DIR is empty)."; fi
  exit 0
fi

# Host-wide gh auth state (superrun's CI/PR steps depend on it).
GH_STATE="$(gh_auth_state)"

# ---- JSON output ----
if [[ "$JSON" == 1 ]]; then
  out="["; first=1
  for slug in "${slugs[@]}"; do
    _collect "$slug"
    [[ $first == 1 ]] && first=0 || out+=","
    out+=$(printf '{"slug":"%s","status":"%s","iteration":"%s","timer_active":"%s","tick_running":"%s","lock_held":%s,"pending_input":%s,"done":%s,"loop_file":"%s","loop_file_exists":%s,"next_fire":"%s","gh_auth":"%s"}' \
      "$(_json_escape "$slug")" "$(_json_escape "$status")" "$(_json_escape "$iteration")" \
      "$(_json_escape "$timer_active")" "$(_json_escape "$tick_running")" "$lock_held" "$pending" "$done_" \
      "$(_json_escape "$LOOP_FILE")" "$exists" "$(_json_escape "$next_fire")" "$(_json_escape "$GH_STATE")")
  done
  out+="]"
  echo "$out"
  exit 0
fi

# ---- Single-slug drill-in ----
if [[ -n "$ONE" ]]; then
  _collect "$ONE"
  echo "Loop:        $ONE"
  echo "Repo:        ${REPO:-?}"
  echo "Loop file:   ${LOOP_FILE:-?}  (exists=$([[ $exists == 1 ]] && echo yes || echo no))"
  echo "Status:      ${status:-<none>}   iteration=${iteration:-?}"
  echo "Timer:       ${timer_active:-unknown}   next-fire=${next_fire}"
  echo "Tick now:    ${tick_running:-unknown}   lock-held=$([[ $lock_held == 1 ]] && echo yes || echo no)"
  echo "gh auth:     $GH_STATE"
  if [[ $pending == 1 && $exists == 1 ]]; then
    echo
    echo "=== ## Pending decision ==="
    awk '/^## Decisions/{exit} /^## Pending decision/{f=1} f{print}' "$LOOP_FILE"
  fi
  if [[ $exists == 1 ]]; then
    echo
    echo "=== last iteration-log lines ==="
    awk '/^## Iteration log/{f=1;next} f' "$LOOP_FILE" | grep -v '^[[:space:]]*$' | tail -5 || true
  fi
  log="/tmp/superagent-$(basename "${LOOP_FILE:-x}" .md).log"
  if [[ -f "$log" ]]; then
    echo
    echo "=== tail $log ==="
    tail -8 "$log"
  fi
  exit 0
fi

# ---- Multi-loop table ----
printf 'gh auth: %s\n\n' "$GH_STATE"
printf '%-24s %-18s %-5s %-8s %-6s %-6s %-6s\n' SLUG STATUS ITER TIMER TICK LOCK INPUT
printf '%-24s %-18s %-5s %-8s %-6s %-6s %-6s\n' ------------------------ ------------------ ----- -------- ------ ------ -----
for slug in "${slugs[@]}"; do
  _collect "$slug"
  printf '%-24s %-18s %-5s %-8s %-6s %-6s %-6s\n' \
    "$slug" "${status:-<none>}" "${iteration:-?}" \
    "${timer_active:-?}" "$([[ "$tick_running" == active ]] && echo yes || echo no)" \
    "$([[ $lock_held == 1 ]] && echo yes || echo no)" \
    "$([[ $pending == 1 ]] && echo YES || echo -)"
done
echo
echo "Drill in: $SCRIPT_DIR/status.sh <slug>   |   JSON: $SCRIPT_DIR/status.sh --json"

#!/usr/bin/env bash
# uninstall-timer.sh — the external-mode stop_driver(): stop and disable a goal's
# superagent scheduler entry (systemd user timer on Linux, launchd LaunchAgent on
# macOS). Use on DONE, or to pause the loop. The loop-status file and the per-goal
# <slug>.env are left in place so the loop can be resumed later with
# install-timer.sh (or a manual tick); pass --purge to also remove them.
#
# --from-tick is for the self-disarm path (superagent-tick.sh on a DONE loop):
# the caller IS the running tick, so the launchd drain-wait below would deadlock
# waiting on itself, and `launchctl bootout` kills the caller's own process group
# (the plist ships AbandonProcessGroup=false). In that mode the plist is removed
# FIRST (so no re-bootstrap at next login even if the bootout kills this script
# mid-flight) and the bootout is the final act.
#
#   uninstall-timer.sh <goal-slug> [--purge] [--from-tick]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"

usage() { echo "usage: uninstall-timer.sh <goal-slug> [--purge] [--from-tick]" >&2; exit 2; }

SLUG="${1:-}"
[[ -z "$SLUG" || "$SLUG" == -* ]] && usage
shift
PURGE=""; FROM_TICK=0
for a in "$@"; do
  case "$a" in
    --purge)     PURGE="--purge" ;;
    --from-tick) FROM_TICK=1 ;;
    *) echo "unknown arg: $a" >&2; usage ;;
  esac
done

CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/superagent"

if [[ "$(superagent_scheduler)" == launchd ]]; then
  LABEL="$(superagent_launchd_label "$SLUG")"
  DOMAIN="$(superagent_launchd_domain)"
  PLIST="$(superagent_launchd_plist "$SLUG")"
  if [[ "$FROM_TICK" == 1 ]]; then
    # Self-disarm from inside the running tick (see header): no drain-wait (the
    # "in-flight tick" is the caller), plist removed before the bootout, and the
    # bootout last — launchd reaps this script's own process group with it, so
    # nothing after that line is guaranteed to run.
    echo "Disarming $LABEL from inside the running tick; bootout is the final act (this process dies with the job)."
    rm -f "$PLIST"
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  else
    # GRACEFUL DRAIN: launchd's bootout kills the job's processes (one job is both
    # timer and service), so a tick in flight must finish BEFORE unloading — unlike
    # systemd, where disabling the .timer leaves the running .service alone. Wait
    # it out (ticks run uncapped; Ctrl-C is safe — nothing has been changed yet,
    # re-run later, or use stop.sh --hard / force-stop.sh to halt the tick first).
    if [[ "$(superagent_launchd_state "$SLUG")" == running ]]; then
      echo "A tick for '$SLUG' is in flight; waiting for it to finish before unloading (Ctrl-C is safe: nothing changed yet — re-run later, or halt it with stop.sh --hard)…"
      while [[ "$(superagent_launchd_state "$SLUG")" == running ]]; do sleep 15; done
    fi
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
  fi
  STOPPED_DESC="$LABEL"
else
  systemctl --user disable --now "superagent-tick@$SLUG.timer" 2>/dev/null || true
  UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  rm -rf "$UNIT_DIR/superagent-tick@$SLUG.timer.d"
  systemctl --user daemon-reload 2>/dev/null || true
  STOPPED_DESC="superagent-tick@$SLUG.timer"
fi

if [[ "$PURGE" == "--purge" ]]; then
  rm -f "$CONF_DIR/$SLUG.env"
  echo "Stopped $STOPPED_DESC and purged $CONF_DIR/$SLUG.env."
else
  echo "Stopped $STOPPED_DESC. Left $CONF_DIR/$SLUG.env (pass --purge to remove)."
fi

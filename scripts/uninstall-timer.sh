#!/usr/bin/env bash
# uninstall-timer.sh — the external-mode stop_driver(): stop and disable a goal's
# superagent timer. Use on DONE, or to pause the loop. The loop-status file and
# the per-goal <slug>.env are left in place so the loop can be resumed later with
# install-timer.sh (or a manual tick); pass --purge to also remove them.
#
#   uninstall-timer.sh <goal-slug> [--purge]
set -euo pipefail

SLUG="${1:-}"
[[ -z "$SLUG" ]] && { echo "usage: uninstall-timer.sh <goal-slug> [--purge]" >&2; exit 2; }
PURGE="${2:-}"

systemctl --user disable --now "superagent-tick@$SLUG.timer" 2>/dev/null || true

UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/superagent"
rm -rf "$UNIT_DIR/superagent-tick@$SLUG.timer.d"
systemctl --user daemon-reload 2>/dev/null || true

if [[ "$PURGE" == "--purge" ]]; then
  rm -f "$CONF_DIR/$SLUG.env"
  echo "Stopped superagent-tick@$SLUG.timer and purged $CONF_DIR/$SLUG.env."
else
  echo "Stopped superagent-tick@$SLUG.timer. Left $CONF_DIR/$SLUG.env (pass --purge to remove)."
fi

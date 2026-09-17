#!/usr/bin/env bash
# stop.sh — stop the superagent EXTERNAL loop for a goal, identified by its root
# master plan. Complements launch.sh.
#
#   stop.sh <PLAN.md> [--hard] [--purge] [--slug <goal-slug>] [--dry-run]
#
# Only <PLAN.md> is required. Default is a GRACEFUL DRAIN: disable + stop the timer
# so no new ticks fire; a tick already running finishes on its own (it is not
# killed). Options:
#   --hard      also stop an in-flight tick immediately (SIGTERM the service).
#   --purge     also remove the per-goal env file (~/.config/superagent/<slug>.env).
#   --slug S    override the goal-slug (skip auto-detection).
#   --dry-run   report what would be stopped, change nothing.
#
# The loop-status file is ALWAYS preserved, so the loop can be relaunched/resumed
# later with launch.sh. Progress lives in the vault plan tree, not the loop file.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/superagent"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"

usage() { echo "usage: stop.sh (<PLAN.md> | <project-dir> | --slug <slug>) [--hard] [--purge] [--slug <goal-slug>] [--dry-run]" >&2; exit 2; }

PLAN=""; HARD=0; PURGE=0; DRY=0; SLUG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --hard) HARD=1; shift ;;
    --purge) PURGE=1; shift ;;
    --dry-run) DRY=1; shift ;;
    --slug) SLUG="${2:?--slug needs a value}"; shift 2 ;;
    -*) usage ;;
    *) [[ -z "$PLAN" ]] || usage; PLAN="$1"; shift ;;
  esac
done
[[ -n "$PLAN" || -n "$SLUG" ]] || usage
superagent_control_target "$PLAN" "$SLUG"
PLAN_REL="$TARGET_LOCATOR"

have_env=0; [[ -f "$CONF_DIR/$SLUG.env" ]] && have_env=1
SCHEDULER="$(superagent_scheduler)"
if [[ "$SCHEDULER" == launchd ]]; then
  # One launchd job is both timer and service: an installed plist ~ enabled,
  # loaded (any state) ~ timer active, state == running ~ tick in flight. These
  # MUST be probed for real here — treating a missing scheduler as "not installed"
  # is exactly the false-negative that lets a loop keep firing after a "stop".
  ld_state="$(superagent_launchd_state "$SLUG")"
  timer_enabled="$([[ -f "$(superagent_launchd_plist "$SLUG")" ]] && echo enabled || true)"
  timer_active="$([[ -n "$ld_state" ]] && echo active || true)"
  tick_active="$([[ "$ld_state" == running ]] && echo active || true)"
else
  timer_enabled="$(systemctl --user is-enabled "superagent-tick@$SLUG.timer" 2>/dev/null || true)"
  timer_active="$(systemctl --user is-active "superagent-tick@$SLUG.timer" 2>/dev/null || true)"
  tick_active="$(systemctl --user is-active "superagent-tick@$SLUG.service" 2>/dev/null || true)"
fi

if [[ $have_env -eq 0 && "$timer_active" != "active" && "$timer_enabled" != "enabled" ]]; then
  echo "No superagent loop found for slug '$SLUG' (plan: $PLAN_REL). Nothing to stop."
  exit 0
fi

if [[ "$DRY" == 1 ]]; then
  echo "[dry-run] would stop superagent external loop:"
  echo "  goal slug:   $SLUG"
  echo "  plan:        $PLAN_REL"
  echo "  timer:       enabled=$timer_enabled active=$timer_active"
  echo "  tick now:    $tick_active"
  echo "  mode:        $([[ $HARD == 1 ]] && echo 'hard (would halt in-flight tick)' || echo 'graceful drain (running tick would finish)')"
  echo "  env file:    $([[ $PURGE == 1 ]] && echo 'would purge' || echo 'would keep')"
  superagent_remaining_child
  echo "[dry-run] nothing changed."
  exit 0
fi

if [[ "$HARD" == 1 && "$tick_active" == "active" ]]; then
  if [[ "$SCHEDULER" == launchd ]]; then
    # SIGTERM the job's main process; launchd then reaps the remaining process
    # group (claude child included) — the analog of systemd's cgroup stop. Like
    # the systemd path, this can orphan the L3 lock; force-stop.sh is the
    # lock-reaping recovery if a relaunch shouldn't wait out the steal window.
    echo "Hard stop: halting in-flight tick ($(superagent_launchd_label "$SLUG"))…"
    launchctl kill SIGTERM "$(superagent_launchd_domain)/$(superagent_launchd_label "$SLUG")" 2>/dev/null || true
  else
    echo "Hard stop: halting in-flight tick (superagent-tick@$SLUG.service)…"
    systemctl --user stop "superagent-tick@$SLUG.service" 2>/dev/null || true
  fi
fi

if [[ "$PURGE" == 1 ]]; then
  "$SCRIPT_DIR/uninstall-timer.sh" "$SLUG" --purge
else
  "$SCRIPT_DIR/uninstall-timer.sh" "$SLUG"
fi

echo
echo "Stopped superagent external loop:"
echo "  goal slug:  $SLUG"
echo "  plan:       $PLAN_REL"
echo "  mode:       $([[ $HARD == 1 ]] && echo 'hard (in-flight tick halted)' || echo 'graceful drain (running tick finishes)')"
echo "  env file:   $([[ $PURGE == 1 ]] && echo 'purged' || echo "kept ($CONF_DIR/$SLUG.env)")"
echo "  loop file:  preserved — relaunch with: $SCRIPT_DIR/launch.sh $PLAN_REL"

superagent_remaining_child

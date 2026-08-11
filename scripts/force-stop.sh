#!/usr/bin/env bash
# force-stop.sh — recover a HUNG superagent tick. Unlike stop.sh (which disarms the
# scheduler), this targets a single wedged/orphaned tick: it halts the in-flight
# tick service (reaping its claude child via the systemd cgroup) and removes the
# stale overlap lock (L3 `.lockd`) so the loop self-heals IMMEDIATELY instead of
# waiting out the 90-min lock-steal window. By default the timer stays armed and a
# fresh recovery tick is kicked — that tick's crash-recovery resets the persisted
# `RUNNING`/`PLANNING` state (superloop L2), so this script never hand-edits the
# loop file.
#
#   force-stop.sh (<PLAN.md> | --slug <goal-slug>) [--apply] [--drain] [--no-kick]
#
# Identify the loop by its root master plan (like stop.sh) OR by --slug. DRY-RUN by
# default (prints what it would do, changes nothing); pass --apply to act.
#   --apply     perform the cleanup (halt tick + remove stale lock).
#   --drain     after cleanup, also disable the timer (stop the loop). Default keeps
#               the timer armed so the loop resumes.
#   --no-kick   do not immediately start a recovery tick after cleanup (default kicks
#               one when the timer stays armed, for immediate self-heal).
#
# The loop-status file is ALWAYS preserved. Progress lives in the vault plan tree.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
[[ -n "$REPO" ]] || { echo "superagent: set REPO or run from inside the target repo" >&2; exit 1; }
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/superagent"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"

usage() { echo "usage: force-stop.sh (<PLAN.md> | --slug <goal-slug>) [--apply] [--drain] [--no-kick]" >&2; exit 2; }

PLAN=""; SLUG=""; APPLY=0; DRAIN=0; KICK=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug)    SLUG="${2:?--slug needs a value}"; shift 2 ;;
    --apply)   APPLY=1; shift ;;
    --drain)   DRAIN=1; shift ;;
    --no-kick) KICK=0; shift ;;
    -h|--help) usage ;;
    -*) echo "unknown arg: $1" >&2; usage ;;
    *) [[ -z "$PLAN" ]] && PLAN="$1" || { echo "unexpected extra arg: $1" >&2; usage; }; shift ;;
  esac
done
[[ -z "$PLAN" && -z "$SLUG" ]] && usage

# Resolve the slug: prefer an explicit --slug; else match the plan against the
# registered env files (like stop.sh — robust to a custom --slug used at launch).
find_slug_by_plan() {
  local plan_abs plan_rel envf lf mp
  [[ -f "$PLAN" ]] || { echo "plan file not found: $PLAN" >&2; return 2; }
  plan_abs="$(cd "$(dirname "$PLAN")" && pwd)/$(basename "$PLAN")"
  case "$plan_abs" in "$REPO"/*) plan_rel="${plan_abs#"$REPO"/}" ;; *) plan_rel="$plan_abs" ;; esac
  shopt -s nullglob
  for envf in "$CONF_DIR"/*.env; do
    lf="$(sed -n 's/^LOOP_FILE=//p' "$envf" | head -1)"
    [[ -n "$lf" && -f "$lf" ]] || continue
    mp="$(sed -n 's/^master_plan:[[:space:]]*//p' "$lf" | head -1)"
    if [[ "$mp" == "$plan_rel" ]]; then basename "$envf" .env; return 0; fi
  done
  return 1
}

if [[ -z "$SLUG" ]]; then
  SLUG="$(find_slug_by_plan || true)"
  [[ -z "$SLUG" ]] && { echo "no registered superagent loop matches plan: $PLAN" >&2; exit 1; }
fi

ENVF="$CONF_DIR/$SLUG.env"
[[ -f "$ENVF" ]] || { echo "no such loop: $SLUG (looked in $ENVF)" >&2; exit 1; }
LOOP_FILE="$(sed -n 's/^LOOP_FILE=//p' "$ENVF" | head -1)"
[[ -n "$LOOP_FILE" ]] || { echo "env file $ENVF has no LOOP_FILE" >&2; exit 1; }

# Observe current state.
status=""; iteration=""
if [[ -f "$LOOP_FILE" ]]; then
  status="$(sed -n 's/^status:[[:space:]]*//p' "$LOOP_FILE" | head -1)"
  iteration="$(sed -n 's/^iteration:[[:space:]]*//p' "$LOOP_FILE" | head -1)"
fi
SCHEDULER="$(superagent_scheduler)"
if [[ "$SCHEDULER" == launchd ]]; then
  # One launchd job is both timer and service: loaded (any state) ~ timer active,
  # state == running ~ tick in flight.
  ld_state="$(superagent_launchd_state "$SLUG")"
  tick_active="$([[ "$ld_state" == running ]] && echo active || true)"
  timer_active="$([[ -n "$ld_state" ]] && echo active || true)"
else
  tick_active="$(systemctl --user is-active "superagent-tick@$SLUG.service" 2>/dev/null || true)"
  timer_active="$(systemctl --user is-active "superagent-tick@$SLUG.timer" 2>/dev/null || true)"
fi

LOCK_DIR="$(dirname "$LOOP_FILE")/.$(basename "$LOOP_FILE").lockd"
lock_held=0; lock_age="-"
if [[ -d "$LOCK_DIR" ]]; then
  lock_held=1
  if [[ -f "$LOCK_DIR/acquired" ]]; then
    acq="$(cat "$LOCK_DIR/acquired" 2>/dev/null || echo)"
    if [[ "$acq" =~ ^[0-9]+$ ]]; then lock_age="$(( ( $(date +%s) - acq ) / 60 )) min"; fi
  fi
fi

# Any orphaned worktrees (reported only — never auto-removed; they may hold
# uncommitted work and superrun reconciles/recreates its own on re-dispatch).
orphan_wts="$(git -C "$REPO" worktree list 2>/dev/null | awk 'NR>1{print $1}' || true)"

if [[ "$DRAIN" == 1 ]]; then
  post_desc="DRAIN — disable timer (loop stopped)"
elif [[ "$KICK" == 1 ]]; then
  post_desc="keep timer armed + kick a recovery tick"
else
  post_desc="keep timer armed (no kick)"
fi

if [[ $lock_held == 1 ]]; then lock_desc="held (age ${lock_age})"; else lock_desc="not held"; fi

echo "Hung-tick recovery target:"
echo "  goal slug:   $SLUG"
echo "  loop file:   $LOOP_FILE"
echo "  status:      ${status:-<none>}   iteration=${iteration:-?}"
echo "  tick now:    ${tick_active:-inactive}"
echo "  timer:       ${timer_active:-inactive}"
echo "  lock:        $lock_desc"
echo "  post-action: $post_desc"
if [[ -n "$orphan_wts" ]]; then
  echo "  worktrees (review manually; not touched):"
  echo "$orphan_wts" | sed 's/^/    - /'
fi

if [[ "$APPLY" != 1 ]]; then
  echo
  echo "[dry-run] nothing changed. Re-run with --apply to perform the recovery."
  exit 0
fi

echo
# 1) Halt the in-flight tick. systemd: systemctl stop reaps the whole service
#    cgroup, including the wrapped claude child — precise, no blind pkill.
#    launchd: SIGTERM the job's main process; launchd then reaps the remaining
#    process group (claude child included; AbandonProcessGroup is unset/false in
#    the shipped plist).
if [[ "$tick_active" == "active" || "$tick_active" == "activating" ]]; then
  if [[ "$SCHEDULER" == launchd ]]; then
    echo "Halting in-flight tick ($(superagent_launchd_label "$SLUG"))…"
    launchctl kill SIGTERM "$(superagent_launchd_domain)/$(superagent_launchd_label "$SLUG")" 2>/dev/null || true
    # Give launchd a moment to reap the group before the lock is removed, so a
    # dying tick can't recreate/hold it.
    for _ in 1 2 3 4 5 6; do
      [[ "$(superagent_launchd_state "$SLUG")" == running ]] || break
      sleep 5
    done
  else
    echo "Halting in-flight tick (superagent-tick@$SLUG.service)…"
    systemctl --user stop "superagent-tick@$SLUG.service" 2>/dev/null || true
  fi
else
  echo "No active tick service (already exited / orphaned lock case)."
fi

# 2) Remove the stale overlap lock so the next tick acquires immediately (no 90-min wait).
if [[ -d "$LOCK_DIR" ]]; then
  echo "Removing stale overlap lock: $LOCK_DIR"
  rm -rf "$LOCK_DIR"
else
  echo "No overlap lock to remove."
fi

# 3) Timer disposition.
if [[ "$DRAIN" == 1 ]]; then
  echo "Draining: disabling the timer (loop stopped; relaunch with launch.sh)…"
  "$SCRIPT_DIR/uninstall-timer.sh" "$SLUG"
elif [[ "$KICK" == 1 ]]; then
  echo "Kicking a fresh recovery tick (crash-recovery resets ${status:-RUNNING} → WAITING FOR RUN)…"
  if [[ "$SCHEDULER" == launchd ]]; then
    launchctl kickstart "$(superagent_launchd_domain)/$(superagent_launchd_label "$SLUG")" 2>/dev/null || true
  else
    systemctl --user start --no-block "superagent-tick@$SLUG.service" 2>/dev/null || true
  fi
fi

echo
echo "Force-stop complete:"
echo "  goal slug:  $SLUG"
echo "  halted:     $([[ "$tick_active" == active || "$tick_active" == activating ]] && echo 'in-flight tick' || echo 'none (was inactive)')"
echo "  lock:       removed if present"
echo "  next:       $([[ $DRAIN == 1 ]] && echo "loop drained — relaunch with $SCRIPT_DIR/launch.sh <PLAN.md>" || echo 'loop armed — next/kicked tick crash-recovers and re-dispatches (status persists as-is; the tick resets it)')"
echo "  loop file:  preserved (not edited)"
if [[ -n "$orphan_wts" ]]; then
  echo "  note:       review the worktrees listed above; superrun recreates/reconciles its own on re-dispatch."
fi

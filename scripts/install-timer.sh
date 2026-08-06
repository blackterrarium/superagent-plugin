#!/usr/bin/env bash
# install-timer.sh — install and start a per-goal systemd USER timer that drives
# a superagent external loop, one fresh tick per interval.
#
#   install-timer.sh <goal-slug> <LOOP_FILE> [--interval 30m] [--timeout <secs>]
#
# --timeout is an OPTIONAL per-tick cap; omit it (the default) for no cap so long
# CI-push ticks are never killed. Writes ~/.config/superagent/<goal-slug>.env
# (REPO, LOOP_FILE, and TICK_TIMEOUT only when a cap is given), installs
# the template units, enables user lingering (so ticks
# fire without an active login session), and starts the timer.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
[[ -n "$REPO" ]] || { echo "superagent: set REPO or run from inside the target repo" >&2; exit 1; }
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
load_superenv "$REPO"

usage() {
  echo "usage: install-timer.sh <goal-slug> <LOOP_FILE> [--interval 30m] [--timeout <secs>] [--output stream|text] [--model <slug>]" >&2
  exit 2
}

SLUG="${1:-}"; LOOP_FILE_IN="${2:-}"
[[ -z "$SLUG" || -z "$LOOP_FILE_IN" ]] && usage
shift 2

INTERVAL="${SUPER_TICK_INTERVAL:-30m}"; TICK_TIMEOUT=""; OUTPUT_FORMAT="stream"; MODEL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --interval) INTERVAL="${2:?--interval needs a value}"; shift 2 ;;
    --timeout)  TICK_TIMEOUT="${2:?--timeout needs a value}"; shift 2 ;;
    --output)   OUTPUT_FORMAT="${2:?--output needs a value}"; shift 2 ;;
    --model)    MODEL="${2:?--model needs a value}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; usage ;;
  esac
done

case "$OUTPUT_FORMAT" in stream|text) ;; *) echo "bad --output '$OUTPUT_FORMAT' (want stream|text)" >&2; exit 2 ;; esac

# Resolve LOOP_FILE to an absolute path (its dir must already exist).
if [[ ! -d "$(dirname "$LOOP_FILE_IN")" ]]; then
  echo "loop-file directory does not exist: $(dirname "$LOOP_FILE_IN") (run bootstrap.sh first)" >&2
  exit 2
fi
LOOP_FILE="$(cd "$(dirname "$LOOP_FILE_IN")" && pwd)/$(basename "$LOOP_FILE_IN")"

CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/superagent"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$CONF_DIR" "$UNIT_DIR"

{
  echo "REPO=$REPO"
  # The plugin's own scripts/ dir — recorded at install time because the systemd
  # unit runs detached from any Claude Code session (no $CLAUDE_PLUGIN_ROOT in its
  # environment), and superagent-tick.sh lives in the plugin, not in $REPO.
  echo "SUPERAGENT_SCRIPT_DIR=$SCRIPT_DIR"
  echo "LOOP_FILE=$LOOP_FILE"
  # Only pin TICK_TIMEOUT when a cap is explicitly given; otherwise omit it so the
  # wrapper runs uncapped (no systemd/script wall-clock ceiling).
  [[ -n "$TICK_TIMEOUT" ]] && echo "TICK_TIMEOUT=$TICK_TIMEOUT"
  echo "TICK_OUTPUT_FORMAT=$OUTPUT_FORMAT"
  # Only pin TICK_MODEL when explicitly given; otherwise the wrapper's default
  # (opus) applies.
  [[ -n "$MODEL" ]] && echo "TICK_MODEL=$MODEL"
} >"$CONF_DIR/$SLUG.env"

install -m 0644 "$SCRIPT_DIR/systemd/superagent-tick@.service" "$UNIT_DIR/superagent-tick@.service"
install -m 0644 "$SCRIPT_DIR/systemd/superagent-tick@.timer"   "$UNIT_DIR/superagent-tick@.timer"

# Per-instance interval override.
DROPIN_DIR="$UNIT_DIR/superagent-tick@$SLUG.timer.d"
mkdir -p "$DROPIN_DIR"
cat >"$DROPIN_DIR/interval.conf" <<EOF
[Timer]
OnUnitActiveSec=$INTERVAL
EOF

# Let user services run without an active login session (headless servers).
loginctl enable-linger "$USER" 2>/dev/null || \
  echo "warning: could not enable-linger for $USER; ticks may pause when you log out" >&2

systemctl --user daemon-reload
systemctl --user enable --now "superagent-tick@$SLUG.timer"

echo "Installed superagent-tick@$SLUG.timer (interval=$INTERVAL timeout=${TICK_TIMEOUT:-none} output=$OUTPUT_FORMAT model=${MODEL:-default})."
echo "  config:  $CONF_DIR/$SLUG.env"
echo "  status:  systemctl --user list-timers 'superagent-tick@$SLUG.timer'"
echo "  logs:    journalctl --user -u superagent-tick@$SLUG.service -f   (or /tmp/superagent-*.log)"
echo "  stop:    $SCRIPT_DIR/uninstall-timer.sh $SLUG"

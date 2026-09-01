#!/usr/bin/env bash
# pi-e2e.sh — scripted END-TO-END testbench for the superagent framework on the Pi harness.
#
# From an empty repository it drives a tiny real goal through
#   init → supergoal → external loop (the OS scheduler fires EVERY tick) → DONE
# and asserts the observable results. The script never runs superagent-tick.sh itself: it arms
# the loop with launch.sh and only watches status.sh --json — that is the point (the 2026-08-31
# loop-to-DONE run was driven by hand; nothing had ever proven a scheduler-fired Pi tick).
#
#   scripts/pi-e2e.sh [--dry-run] [--keep]
#     PI_E2E_REPO=<owner>/<name>   remote to (re)use; NEVER deleted, reset to an orphan commit per
#                                  run (default: <gh user>/superagent-pi-e2e)
#     PI_E2E_INTERVAL=2m           scheduler interval (launchd StartInterval / systemd timer)
#     PI_E2E_MAX_MIN=90            wall-clock ceiling for the loop phase
#     PI_E2E_GOAL="…"              goal text (default: the hello-world shell goal below)
#     PI_E2E_SUPERENV_EXTRA="…"    extra .superenv lines (e.g. SUPER_MODEL_TASK_REVIEWER=codex:…)
#
# Needs: pi (authenticated), gh (authenticated), git, python3, launchctl (Darwin) or
# systemctl --user. Cost ≈ 6 Pi sessions (init, supergoal, ~4 ticks); ~20–40 min.
# Report: pi-e2e-report.md at the repo root (gitignored); run artifacts (tick log copy, event
# log, status transitions) under $TMPDIR/pi-e2e-<stamp>/.
# Exit 0 only when every phase passes. Set PI_E2E_LIB=1 and source this file to get the pure
# helpers (e2e_*) without running anything — bridge-test.sh does that.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$ROOT/scripts"

# ---------------------------------------------------------------------------
# Pure helpers (no side effects; unit-tested offline in bridge-test.sh)
# ---------------------------------------------------------------------------

# e2e_status_field <status.sh --json output> <slug> <field>
# Prints the field of the row whose slug matches (booleans as true/false); "" if absent.
e2e_status_field() {
  printf '%s' "$1" | python3 -c '
import json, sys
slug, field = sys.argv[1], sys.argv[2]
try:
    rows = json.load(sys.stdin)
except Exception:
    rows = []
for r in rows if isinstance(rows, list) else []:
    if r.get("slug") == slug:
        v = r.get(field, "")
        print(str(v).lower() if isinstance(v, bool) else v)
        break
' "$2" "$3" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
[[ "${PI_E2E_LIB:-}" == 1 ]] && return 0

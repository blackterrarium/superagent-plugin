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

# e2e_render_superenv <interval> <events_log> [extra-lines]
# The throwaway repo's .superenv. SUPER_NOTIFY_CMD is SINGLE-quoted on purpose: .superenv is
# sourced under `set -u`, and an expanded $SUPERAGENT_EVENT would abort every tick (0.4.10).
e2e_render_superenv() {
  printf 'SUPER_HARNESS=pi\nSUPER_TICK_INTERVAL=%s\n' "$1"
  printf "SUPER_NOTIFY_CMD='printf \"%%s\\\\n\" \"\$SUPERAGENT_EVENT\" >>\"%s\"'\n" "$2"
  [[ -n "${3:-}" ]] && printf '%s\n' "$3"
  return 0
}

# e2e_count_ticks <tick_log> — sessions the tick wrapper actually started (its header line).
e2e_count_ticks() {
  if [[ -f "$1" ]]; then grep -c '^=== .* superagent-tick harness=' "$1" || true; else echo 0; fi
}

# e2e_transition <status> <iteration> — prints "<utc-time> <status> iter=<n>" only when the
# pair changed since the previous call (state kept in _E2E_LAST).
_E2E_LAST=""
e2e_transition() {
  local key="$1|$2"
  [[ "$key" == "$_E2E_LAST" ]] && return 0
  _E2E_LAST="$key"
  printf '%s %s iter=%s\n' "$(date -u +%H:%M:%S)" "$1" "$2"
}

# e2e_assert_deliverables <repo_dir> — the default goal's contract: scripts/hello.sh prints
# exactly "hello, world" and scripts/test.sh exits 0. Prints the reason on failure.
e2e_assert_deliverables() {
  local d="$1"
  [[ -f "$d/scripts/hello.sh" && -f "$d/scripts/test.sh" ]] || { echo "missing scripts/hello.sh or scripts/test.sh"; return 1; }
  [[ "$(cd "$d" && sh scripts/hello.sh 2>&1)" == "hello, world" ]] || { echo "scripts/hello.sh output != 'hello, world'"; return 1; }
  (cd "$d" && sh scripts/test.sh >/dev/null 2>&1) || { echo "scripts/test.sh exited non-zero"; return 1; }
  return 0
}

# ---------------------------------------------------------------------------
[[ "${PI_E2E_LIB:-}" == 1 ]] && return 0

# ---------------------------------------------------------------------------
# Arguments and run identity
# ---------------------------------------------------------------------------
usage() { echo "usage: scripts/pi-e2e.sh [--dry-run] [--keep]   (env: PI_E2E_REPO PI_E2E_INTERVAL PI_E2E_MAX_MIN PI_E2E_GOAL PI_E2E_SUPERENV_EXTRA)" >&2; exit 2; }
DRY=0; KEEP=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --keep)    KEEP=1; shift ;;
    *) echo "pi-e2e: unknown arg: $1" >&2; usage ;;
  esac
done

STAMP="$(date -u +%Y%m%d-%H%M%S)"
SLUG="pi-e2e-$STAMP"
INTERVAL="${PI_E2E_INTERVAL:-2m}"
MAX_MIN="${PI_E2E_MAX_MIN:-90}"
GOAL="${PI_E2E_GOAL:-Add scripts/hello.sh (POSIX sh) that prints exactly: hello, world — and scripts/test.sh (POSIX sh) that runs it and exits non-zero unless the output matches exactly. Keep it to ONE implementation plan; no other files beyond the two scripts and the plan-tree bookkeeping.}"
RUN_DIR="${TMPDIR:-/tmp}"; RUN_DIR="${RUN_DIR%/}/pi-e2e-$STAMP"
REPORT="$ROOT/pi-e2e-report.md"
CLONE="$RUN_DIR/repo"
REPO_SLUG="${PI_E2E_REPO:-}"
PLAN=""; LOOP_FILE=""; ENV_FILE=""; TICK_LOG=""; PR_BASE=0
T0=$(date +%s)

# ---------------------------------------------------------------------------
# Report framing (same shape as pi-smoke.sh: sections, fenced output, a Result line)
# ---------------------------------------------------------------------------
PASS=0; FAIL=0; REPORT_OPEN=0
report_open() {
  [[ "$REPORT_OPEN" == 1 ]] && return 0
  REPORT_OPEN=1; mkdir -p "$RUN_DIR"
  {
    echo "# superagent Pi e2e report"
    echo
    echo "- date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "- host: $(uname -a)"
    echo "- plugin repo: $ROOT ($(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo 'no git'))"
    echo "- pi: $(pi --version 2>&1 | head -1)   pi-subagents: ${SUBAGENTS_VERSION:-absent}"
    echo "- remote: $REPO_SLUG   slug: $SLUG   interval: $INTERVAL   ceiling: ${MAX_MIN}m"
    echo "- run dir: $RUN_DIR"
    echo
  } >"$REPORT"
}
report_section() { report_open; { echo "## $1"; echo; } >>"$REPORT"; echo "pi-e2e: == $1"; }
report_note()    { report_open; echo "$1" >>"$REPORT"; }
report_pass()    { PASS=$((PASS+1)); { echo; echo "**Result: PASS** — $1"; echo; } >>"$REPORT"; echo "pi-e2e: PASS — $1"; }
report_fail()    { FAIL=$((FAIL+1)); { echo; echo "**Result: FAIL** — $1"; echo; } >>"$REPORT"; echo "pi-e2e: FAIL — $1" >&2; }
# report_cmd <expected-substring-or-empty> <cmd...> — runs, records, returns non-zero on failure.
report_cmd() {
  local expect="$1"; shift
  local out rc
  { echo '```'; printf '$ %s\n' "$*"; echo '```'; } >>"$REPORT"
  out="$("$@" 2>&1)"; rc=$?
  if [[ "${#out}" -gt 6000 ]]; then out="${out:0:3000}
  [... truncated ...]
${out: -2500}"; fi
  { echo; echo '```'; printf '%s\n' "$out"; echo '```'; echo; } >>"$REPORT"
  [[ $rc -ne 0 ]] && { report_fail "exit $rc: $*"; return 1; }
  if [[ -n "$expect" ]] && ! printf '%s' "$out" | grep -qi -- "$expect"; then report_fail "expected output containing: $expect"; return 1; fi
  return 0
}

# ---------------------------------------------------------------------------
# Phase 0 — preflight (nothing created)
# ---------------------------------------------------------------------------
SUBAGENTS_VERSION=""
phase_preflight() {
  local missing=() c
  for c in pi gh git python3; do command -v "$c" >/dev/null 2>&1 || missing+=("$c"); done
  if [[ "$(uname -s)" == Darwin ]]; then command -v launchctl >/dev/null 2>&1 || missing+=(launchctl)
  else command -v systemctl >/dev/null 2>&1 || missing+=(systemctl); fi
  [[ ${#missing[@]} -eq 0 ]] || { echo "pi-e2e: missing prerequisite(s): ${missing[*]}" >&2; return 2; }
  gh auth status >/dev/null 2>&1 || { echo "pi-e2e: gh is not authenticated (gh auth login)" >&2; return 2; }
  "$SCRIPTS/build-pi-skills.sh" --check >/dev/null 2>&1 || { echo "pi-e2e: pi/ build is stale — run scripts/build-pi-skills.sh" >&2; return 2; }
  if [[ -z "$REPO_SLUG" ]]; then
    local owner; owner="$(gh api user -q .login 2>/dev/null || true)"
    [[ -n "$owner" ]] || { echo "pi-e2e: cannot resolve the gh user for the default PI_E2E_REPO" >&2; return 2; }
    REPO_SLUG="$owner/superagent-pi-e2e"
  fi
  [[ "$REPO_SLUG" == */* ]] || { echo "pi-e2e: PI_E2E_REPO must be <owner>/<name> (got '$REPO_SLUG')" >&2; return 2; }
  SUBAGENTS_VERSION="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$HOME/.pi/agent/npm/node_modules/pi-subagents/package.json" 2>/dev/null | head -1)"
  [[ -n "$SUBAGENTS_VERSION" ]] || echo "pi-e2e: WARN pi-subagents not installed — SDD children run sequentially without pins (SUPER_PI_SUBAGENTS=recommended)" >&2
  local js; js="$("$SCRIPTS/status.sh" --json 2>/dev/null || echo '[]')"
  [[ -z "$(e2e_status_field "$js" "$SLUG" status)" ]] || { echo "pi-e2e: a loop is already registered under $SLUG" >&2; return 2; }
  return 0
}

print_plan() {
  echo "pi-e2e: would run:"
  echo "  remote:    $REPO_SLUG  (reset to an orphan commit; never deleted)"
  echo "  slug:      $SLUG"
  echo "  interval:  $INTERVAL   ceiling: ${MAX_MIN}m   keep clone: $KEEP"
  echo "  run dir:   $RUN_DIR"
  echo "  goal:      $GOAL"
  echo "  phases:    provision → init → supergoal → launch.sh (arm) → watch status.sh until DONE → assert → cleanup"
}

# ---------------------------------------------------------------------------
# Phase 1 — provision the throwaway repo (reused remote, reset to an orphan commit)
# ---------------------------------------------------------------------------
phase_provision() {
  report_section "1. Provision $REPO_SLUG"
  if ! gh repo view "$REPO_SLUG" >/dev/null 2>&1; then
    report_cmd "" gh repo create "$REPO_SLUG" --private --description "superagent Pi e2e testbench (reset per run by scripts/pi-e2e.sh)" || return 1
  fi
  mkdir -p "$RUN_DIR"
  report_cmd "" git clone -q "https://github.com/$REPO_SLUG.git" "$CLONE" || return 1
  report_cmd "" bash -c "
    cd '$CLONE' &&
    git checkout -q --orphan e2e-reset &&
    { git rm -rfq --cached . >/dev/null 2>&1 || true; } &&
    find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + &&
    printf '# superagent Pi e2e\n\nReset %s by scripts/pi-e2e.sh — every commit after this one was made by the superagent loop on the Pi harness.\n' '$STAMP' >README.md &&
    cat >.superenv <<'SUPERENV'
$(e2e_render_superenv "$INTERVAL" "$RUN_DIR/events.log" "${PI_E2E_SUPERENV_EXTRA:-}")
SUPERENV
    git add -A && git commit -qm 'e2e: reset $STAMP' && git branch -M main && git push -q --force -u origin main && echo reset-ok" || return 1
  local b n
  for b in $(gh api "repos/$REPO_SLUG/branches" -q '.[].name' 2>/dev/null | grep -vx main || true); do
    gh api -X DELETE "repos/$REPO_SLUG/git/refs/heads/$b" >/dev/null 2>&1 && report_note "- deleted stale branch \`$b\`" || true
  done
  for n in $(gh pr list -R "$REPO_SLUG" --state open --json number -q '.[].number' 2>/dev/null || true); do
    gh pr close -R "$REPO_SLUG" "$n" >/dev/null 2>&1 && report_note "- closed stale PR #$n" || true
  done
  PR_BASE="$(gh pr list -R "$REPO_SLUG" --state merged --json number -q 'length' 2>/dev/null || echo 0)"
  report_note "- merged PRs before this run: $PR_BASE"
  report_pass "clean main at orphan commit; .superenv: SUPER_HARNESS=pi, interval $INTERVAL, notify → events.log"
}

# ---------------------------------------------------------------------------
# Phase 2 — init (headless Pi, the plugin's Pi build delivered with --skill)
# ---------------------------------------------------------------------------
pi_run() {  # pi_run <prompt> — one headless Pi session in the clone
  ( cd "$CLONE" && pi -p --approve --no-session --skill "$ROOT/pi/skills" "$1" </dev/null )
}
phase_init() {
  report_section "2. init"
  report_cmd "" pi_run "Read $ROOT/pi/skills/init/SKILL.md and run it." || return 1
  grep -qx 'SUPER_HARNESS=pi' "$CLONE/.superenv" || { report_fail "init overwrote .superenv (SUPER_HARNESS=pi gone)"; return 1; }
  [[ -f "$CLONE/.pi/agents/super-implementer.md" ]] || { report_fail "no .pi/agents/super-implementer.md after init"; return 1; }
  [[ -d "$CLONE/vault" ]] || { report_fail "no vault/ after init"; return 1; }
  ( cd "$CLONE" && git checkout -q main 2>/dev/null; git add -A && git commit -qm "e2e: init leftovers" >/dev/null 2>&1; git push -q origin main >/dev/null 2>&1 ) || true
  report_pass ".superenv intact, .pi/agents/super-implementer.md present, vault/ present"
}

# ---------------------------------------------------------------------------
# Phase 3 — supergoal (creates the goal vault + root PLAN.md, merges its own PR)
# ---------------------------------------------------------------------------
phase_goal() {
  report_section "3. supergoal"
  report_cmd "" pi_run "Read $ROOT/pi/skills/supergoal/SKILL.md and run it with this goal: $GOAL" || return 1
  ( cd "$CLONE" && git checkout -q main && git pull -q --ff-only origin main ) || { report_fail "git pull main after supergoal"; return 1; }
  local plans; plans="$(ls "$CLONE"/vault/*/PLAN.md 2>/dev/null || true)"
  [[ -n "$plans" && "$(printf '%s\n' "$plans" | wc -l | tr -d ' ')" == 1 ]] || { report_fail "expected exactly one vault/*/PLAN.md on main, found: ${plans:-none}"; return 1; }
  PLAN="$plans"
  local merged; merged="$(gh pr list -R "$REPO_SLUG" --state merged --json number -q 'length')"
  [[ "$merged" -gt "$PR_BASE" ]] || { report_fail "supergoal merged no PR (merged=$merged base=$PR_BASE)"; return 1; }
  report_pass "root plan ${PLAN#$CLONE/}; merged PRs so far: $((merged - PR_BASE))"
}

# ---------------------------------------------------------------------------
# Phase 4 — arm the real scheduler with launch.sh (kickstarts the first tick)
# ---------------------------------------------------------------------------
phase_arm() {
  report_section "4. launch.sh (arm the scheduler)"
  report_cmd "Launched superagent external loop" bash -c "cd '$CLONE' && '$SCRIPTS/launch.sh' '$PLAN' --harness pi --interval '$INTERVAL' --slug '$SLUG'" || return 1
  local js; js="$("$SCRIPTS/status.sh" --json)"
  [[ "$(e2e_status_field "$js" "$SLUG" timer_active)" == active ]] || { report_fail "status.sh: timer not active for $SLUG"; return 1; }
  LOOP_FILE="$(e2e_status_field "$js" "$SLUG" loop_file)"
  [[ -f "$LOOP_FILE" ]] || { report_fail "loop file missing: $LOOP_FILE"; return 1; }
  ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/superagent/$SLUG.env"
  grep -qx 'SUPER_HARNESS=pi' "$ENV_FILE" || { report_fail "$ENV_FILE lacks SUPER_HARNESS=pi"; return 1; }
  grep -q '^SUPERAGENT_CLI_PATH=' "$ENV_FILE" || { report_fail "$ENV_FILE lacks SUPERAGENT_CLI_PATH (0.6.3 not in effect)"; return 1; }
  TICK_LOG="/tmp/superagent-$(basename "$LOOP_FILE" .md).log"
  report_note "- loop file: \`$LOOP_FILE\`"
  report_note "- env file: \`$ENV_FILE\` ($(grep '^SUPERAGENT_CLI_PATH=' "$ENV_FILE"))"
  report_note "- tick log: \`$TICK_LOG\`"
  report_pass "timer active, loop file at $(sed -n 's/^status:[[:space:]]*//p' "$LOOP_FILE" | head -1), env file pins harness + CLI path"
}

# ---------------------------------------------------------------------------
# Phase 5 — drive: WATCH ONLY. The scheduler fires every tick; we poll status.sh.
# ---------------------------------------------------------------------------
phase_drive() {
  report_section "5. Drive (watch only — ticks are scheduler-fired every $INTERVAL, ceiling ${MAX_MIN}m)"
  report_note '```'
  local deadline=$(( $(date +%s) + MAX_MIN * 60 )) js st it line
  while :; do
    js="$("$SCRIPTS/status.sh" --json 2>/dev/null || echo '[]')"
    st="$(e2e_status_field "$js" "$SLUG" status)"; it="$(e2e_status_field "$js" "$SLUG" iteration)"
    line="$(e2e_transition "$st" "$it")"
    if [[ -n "$line" ]]; then
      line="$line ticks=$(e2e_count_ticks "$TICK_LOG")"
      printf '%s\n' "$line" | tee -a "$RUN_DIR/transitions.log" >>"$REPORT"; echo "pi-e2e:   $line"
    fi
    if [[ "$(e2e_status_field "$js" "$SLUG" done)" == 1 ]]; then
      report_note '```'; report_pass "DONE after $(e2e_count_ticks "$TICK_LOG") tick(s), $(( ($(date +%s) - T0) / 60 )) min since start"; return 0
    fi
    if [[ "$(e2e_status_field "$js" "$SLUG" pending_input)" == 1 ]]; then
      report_note '```'; report_fail "parked WAITING FOR INPUT — $(sed -n '/## Pending decision/,$p' "$LOOP_FILE" | head -15 | tr '\n' ' ')"; return 1
    fi
    [[ -n "$st" ]] || { report_note '```'; report_fail "loop vanished from status.sh"; return 1; }
    if (( $(date +%s) > deadline )); then report_note '```'; report_fail "ceiling ${MAX_MIN}m reached at status '$st' iter=$it"; return 1; fi
    sleep 30
  done
}

# ---------------------------------------------------------------------------
# Phase 6 — assert the outcome on main
# ---------------------------------------------------------------------------
phase_assert() {
  report_section "6. Assert outcome"
  local ticks merged open why
  ticks="$(e2e_count_ticks "$TICK_LOG")"
  [[ "$ticks" -ge 2 ]] || { report_fail "only $ticks tick(s) in $TICK_LOG — the scheduler never fired on its own"; return 1; }
  ( cd "$CLONE" && git checkout -q main && git pull -q --ff-only origin main ) || { report_fail "git pull main"; return 1; }
  why="$(e2e_assert_deliverables "$CLONE")" || { report_fail "deliverables: $why"; ( cd "$CLONE" && ls -R scripts 2>/dev/null | head -20 ) >>"$REPORT"; return 1; }
  merged="$(gh pr list -R "$REPO_SLUG" --state merged --json number -q 'length')"
  open="$(gh pr list -R "$REPO_SLUG" --state open --json number -q 'length')"
  [[ $(( merged - PR_BASE )) -ge 3 && "$open" == 0 ]] || { report_fail "PRs this run: merged=$(( merged - PR_BASE )) open=$open (want ≥3 merged, 0 open)"; return 1; }
  [[ "$(e2e_status_field "$("$SCRIPTS/status.sh" --json)" "$SLUG" timer_active)" != active ]] || { report_fail "timer still active after DONE (SUPER_AUTO_DISARM_ON_DONE)"; return 1; }
  grep -qx done "$RUN_DIR/events.log" 2>/dev/null || { report_fail "no 'done' event in $RUN_DIR/events.log (SUPER_NOTIFY_CMD)"; return 1; }
  gh pr list -R "$REPO_SLUG" --state merged --json number,title -q '.[] | "- #\(.number) \(.title)"' | head -n $(( merged - PR_BASE )) >>"$REPORT"
  report_pass "ticks=$ticks merged=$(( merged - PR_BASE )) open=0 deliverables ok, timer disarmed, notify=done"
}

# ---------------------------------------------------------------------------
# Phase 7 — cleanup (trap: always). Only place that touches the scheduler on the way out.
# ---------------------------------------------------------------------------
CLEANED=0
phase_cleanup() {
  [[ "$CLEANED" == 1 ]] && return 0; CLEANED=1
  local js; js="$("$SCRIPTS/status.sh" --json 2>/dev/null || echo '[]')"
  if [[ -n "$(e2e_status_field "$js" "$SLUG" status)" ]]; then
    if [[ "$(e2e_status_field "$js" "$SLUG" tick_running)" == active && -n "$PLAN" ]]; then
      "$SCRIPTS/stop.sh" "$PLAN" --hard --slug "$SLUG" >/dev/null 2>&1 || true
    fi
    "$SCRIPTS/uninstall-timer.sh" "$SLUG" --purge >/dev/null 2>&1 || true
    echo "pi-e2e: cleanup — scheduler entry + env file for $SLUG removed"
  fi
  [[ -n "$TICK_LOG" && -f "$TICK_LOG" ]] && cp "$TICK_LOG" "$RUN_DIR/tick.log" 2>/dev/null
  if [[ "$KEEP" == 1 ]]; then echo "pi-e2e: clone kept at $CLONE"; else rm -rf "$CLONE"; fi
  return 0
}

# ---------------------------------------------------------------------------
main() {
  phase_preflight || exit $?
  print_plan
  if [[ "$DRY" == 1 ]]; then echo "[dry-run] nothing created or armed."; exit 0; fi
  trap phase_cleanup EXIT INT TERM
  report_open
  local rc=0
  phase_provision && phase_init && phase_goal && phase_arm && phase_drive && phase_assert || rc=1
  phase_cleanup
  {
    echo "## Summary"; echo
    echo "- PASS: $PASS   FAIL: $FAIL   elapsed: $(( ($(date +%s) - T0) / 60 )) min"
    echo "- verdict: $([[ $rc == 0 ]] && echo PASS || echo FAIL)"
    echo "- artifacts: $RUN_DIR (tick.log, events.log, transitions.log)"
  } >>"$REPORT"
  echo; echo "pi-e2e: $([[ $rc == 0 ]] && echo PASS || echo FAIL) — $PASS pass, $FAIL fail, $(( ($(date +%s) - T0) / 60 )) min"
  echo "pi-e2e: report: $REPORT   artifacts: $RUN_DIR"
  exit $rc
}
main

#!/usr/bin/env bash
# mix-e2e.sh — scripted END-TO-END testbench for MULTI-HARNESS ROLE MIXING.
#
# From an empty repository it drives a small but real goal through
#   init → supergoal → external loop (the OS scheduler fires EVERY tick) → DONE
# with the roles split across THREE harness CLIs — supervisor / planner / executor on Claude,
# implementer + fix-applier bridged to Codex, task-reviewer + re-reviewer bridged to Pi — and then
# proves, from role-bridge.sh's own log header/trailer lines (not from any agent's prose), that
# every pinned role ran on its pinned harness with its pinned model. A final report-only phase
# summarises the run (ticks, minutes, PRs, bridge calls per harness, fix rounds, escalations) so the
# operator can evaluate the framework on an actual goal.
#
#   scripts/mix-e2e.sh [--dry-run] [--keep]
#     MIX_E2E_REPO=<owner>/<name>   remote to (re)use; NEVER deleted, reset to an orphan commit per
#                                   run (default: <gh user>/superagent-mix-e2e)
#     MIX_E2E_INTERVAL=2m           scheduler interval (launchd StartInterval / systemd timer)
#     MIX_E2E_MAX_MIN=150           wall-clock ceiling for the loop phase
#     MIX_E2E_GOAL="…"              goal text (default: the POSIX-sh key-value store below)
#     MIX_E2E_IMPLEMENTER=codex:gpt-5.6-terra           pin for implementer + fix-applier
#     MIX_E2E_REVIEWER=pi:openai-codex/gpt-5.6-sol      pin for task-reviewer + re-reviewer
#     MIX_E2E_SUPERENV_EXTRA="…"    extra .superenv lines, appended last (override anything)
#
# Needs: claude (with the superagent plugin installed + enabled), codex (logged in), pi (with the
# reviewer pin's provider authenticated), gh (authenticated), git, python3, launchctl (Darwin) or
# systemctl --user. Cost ≈ 2 Claude sessions (init, supergoal) + one Claude tick per interval fired
# + inside the ticks: a Claude executor process, one Codex session per implementer/fix-applier
# dispatch and one Pi session per review; ~60–120 min.
# Report: mix-e2e-report.md at the repo root (gitignored); run artifacts (tick log copy, event log,
# status transitions, the run's bridge logs) under $TMPDIR/mix-e2e-<stamp>/.
# Exit 0 only when every phase passes. Set MIX_E2E_LIB=1 and source this file to get the pure
# helpers (mix_*) without running anything — bridge-test.sh does that.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$ROOT/scripts"
# Shared e2e helpers (e2e_status_field, e2e_count_ticks, e2e_transition, e2e_kill_tree, e2e_run)
# and the role grammar (superagent_role_harness / superagent_role_model).
PI_E2E_LIB=1; . "$SCRIPTS/pi-e2e.sh"
. "$SCRIPTS/_common.sh"

# ---------------------------------------------------------------------------
# Pure helpers (no side effects; unit-tested offline in bridge-test.sh)
# ---------------------------------------------------------------------------

# mix_render_superenv <interval> <events_log> <implementer-pin> <reviewer-pin> [extra-lines]
# The throwaway repo's .superenv. Claude supervises; the two SDD pairs are bridged. SUPER_NOTIFY_CMD
# is SINGLE-quoted on purpose (.superenv is sourced under `set -u`; see pi-e2e.sh).
mix_render_superenv() {
  printf 'SUPER_HARNESS=claude\nSUPER_TICK_INTERVAL=%s\n' "$1"
  printf 'SUPER_MODEL_IMPLEMENTER=%s\nSUPER_MODEL_FIX_APPLIER=%s\n' "$3" "$3"
  printf 'SUPER_MODEL_TASK_REVIEWER=%s\nSUPER_MODEL_RE_REVIEWER=%s\n' "$4" "$4"
  printf "SUPER_NOTIFY_CMD='printf \"%%s\\\\n\" \"\$SUPERAGENT_EVENT\" >>\"%s\"'\n" "$2"
  [[ -n "${5:-}" ]] && printf '%s\n' "$5"
  return 0
}

# mix_assert_deliverables <repo_dir> — the default goal's contract: scripts/kv.sh (POSIX sh, store at
# $KV_FILE) supports set/get/del/list with replace-on-set, sorted list, and exit 1 + empty stdout on a
# missing key; scripts/test.sh exits 0. Prints the reason on failure.
mix_assert_deliverables() {
  local d="$1" kv="$1/scripts/kv.sh" store out
  [[ -f "$kv" && -f "$d/scripts/test.sh" ]] || { echo "missing scripts/kv.sh or scripts/test.sh"; return 1; }
  store="$(mktemp -d)/store"
  _kv() { KV_FILE="$store" command sh "$kv" "$@" 2>/dev/null; }   # kv.sh against the temp store; $store/$kv are this function's locals (dynamic scoping)
  _kv set a 1 >/dev/null || { echo "set a 1 failed"; return 1; }
  _kv set b two >/dev/null || { echo "set b two failed"; return 1; }
  _kv set a 3 >/dev/null || { echo "set a 3 (replace) failed"; return 1; }
  out="$(_kv get a)"; [[ "$out" == 3 ]] || { echo "get a after replace: '$out' != '3'"; return 1; }
  out="$(_kv get b)"; [[ "$out" == two ]] || { echo "get b: '$out' != 'two'"; return 1; }
  if out="$(_kv get nope)"; then echo "get of a missing key exited 0"; return 1; fi
  [[ -z "$out" ]] || { echo "get of a missing key printed '$out' on stdout"; return 1; }
  _kv del a >/dev/null || { echo "del a failed"; return 1; }
  if _kv get a >/dev/null; then echo "get a after del exited 0"; return 1; fi
  _kv set z 26 >/dev/null || { echo "set z 26 failed"; return 1; }
  out="$(_kv list)"; [[ "$out" == "$(printf 'b=two\nz=26')" ]] || { echo "list: '$out' != 'b=two\\nz=26'"; return 1; }
  (cd "$d" && command sh scripts/test.sh >/dev/null 2>&1) || { echo "scripts/test.sh exited non-zero"; return 1; }
  rm -rf "$(dirname "$store")"
  return 0
}

# mix_bridge_evidence <since-stamp> <log_dir>... — one row per bridge log whose header start= is at or
# after <since-stamp> (compact UTC, e.g. 20260901T120000Z; string order == time order), sorted by start:
#   <role> <harness> <model> <effort> <exit> <secs> <start> <file>
# exit is the trailer's exit code, or "killed" when the log has a header but no trailer (secs "-").
# A header-less log (a bridge older than 0.6.5) becomes a row with harness "legacy" (or "legacy-codex"
# + the model from codex's banner) and "-" elsewhere — visible in the table, never counted as proof.
mix_bridge_evidence() {
  local since="$1"; shift
  python3 - "$since" "$@" <<'PY'
import os, re, sys
since, dirs = sys.argv[1], sys.argv[2:]
hdr = re.compile(r'^role-bridge: start=(\S+) harness=(\S+) model=(\S+) effort=(\S+) tools=(\S+) role=(\S+) cwd=')
tr  = re.compile(r'^role-bridge: end=(\S+) exit=(\d+) secs=(\d+)')
fn  = re.compile(r'^(.+)-(\d{8}T\d{6}Z)-\d+\.log$')
rows = []
for d in dirs:
    if not os.path.isdir(d): continue
    for name in os.listdir(d):
        if not name.endswith('.log'): continue
        p = os.path.join(d, name)
        try:
            with open(p, errors='replace') as f: lines = f.read().splitlines()
        except OSError: continue
        m = hdr.match(lines[0]) if lines else None
        if m:
            if m.group(1) < since: continue
            t = tr.match(lines[-1]) if len(lines) > 1 else None
            ex, secs = (t.group(2), t.group(3)) if t else ('killed', '-')
            rows.append((m.group(1), m.group(6), m.group(2), m.group(3), m.group(4), ex, secs, p))
            continue
        # No header: a log written by a bridge that predates the evidence lines (< 0.6.5). Its role and
        # start come from the file name; codex's own banner still tells the harness and model, any other
        # harness is unprovable ("legacy").
        f = fn.match(name)
        if not f or f.group(2) < since: continue
        h, model = 'legacy', '-'
        if lines and lines[0].startswith('OpenAI Codex'):
            h = 'legacy-codex'
            for l in lines[1:12]:
                if l.startswith('model: '): model = l[7:].strip(); break
        rows.append((f.group(2), f.group(1), h, model, '-', '-', '-', p))
for start, role, h, model, eff, ex, secs, p in sorted(rows):
    print(role, h, model, eff, ex, secs, start, p)
PY
}

# mix_evidence_has <rows> <role> <harness> [model] — 0 iff some row matches with exit=0.
mix_evidence_has() {
  printf '%s\n' "$1" | awk -v r="$2" -v h="$3" -v m="${4:-}" '$1==r && $2==h && (m=="" || $3==m) && $5=="0" {found=1} END {exit found?0:1}'
}
# mix_evidence_count <rows> <role-regex> [harness] — number of matching rows (any exit).
mix_evidence_count() {
  printf '%s\n' "$1" | awk -v r="$2" -v h="${3:-}" 'NF && $1 ~ ("^(" r ")$") && (h=="" || $2==h) {n++} END {print n+0}'
}

# mix_plugin_field <claude plugin list output> <Version|Status> — the field of the superagent@… block.
mix_plugin_field() {
  printf '%s\n' "$1" | awk -v f="$2" '/^[[:space:]]*(❯[[:space:]]*)?superagent@/ {inb=1; next} inb && $1==f":" {sub(/^[[:space:]]*[A-Za-z]+:[[:space:]]*/, ""); print; exit} inb && /^[[:space:]]*(❯[[:space:]]*)?[a-z0-9-]+@/ {exit}'
}

# mix_plugin_marketplace <claude plugin list output> — the marketplace half of "superagent@<marketplace>".
mix_plugin_marketplace() {
  printf '%s\n' "$1" | sed -n 's/^[[:space:]]*\(❯[[:space:]]*\)\{0,1\}superagent@\([A-Za-z0-9_.-]*\).*/\2/p' | head -1
}
# mix_installed_bridge <claude plugin list output> — the role-bridge.sh the RELAYS actually run. The relay
# definitions superagent:init renders bake the installed plugin's bridge path (measured: the relay inlines
# the "${SUPERAGENT_BRIDGE:-<path>}" fallback literally), so the evidence lines must exist THERE.
mix_installed_bridge() {
  local mkt ver; mkt="$(mix_plugin_marketplace "$1")"; ver="$(mix_plugin_field "$1" Version)"
  [[ -n "$mkt" && -n "$ver" ]] || return 1
  echo "${MIX_E2E_PLUGIN_CACHE:-$HOME/.claude/plugins/cache}/$mkt/superagent/$ver/scripts/role-bridge.sh"
}
# mix_bridge_failed_count <tick_log> — relay failures reported as results (the prose in SKILL.md also
# contains the word, so match the report's shape, not the word). NB `grep -c` PRINTS 0 and exits 1 on
# zero matches, so `|| echo 0` would print "0" twice (found by run 2: the doubled value failed the
# comparison and aborted the evidence phase of an otherwise-clean run).
mix_bridge_failed_count() {
  if [[ -f "$1" ]]; then grep -c 'BRIDGE-FAILED exit=[0-9]' "$1" || true; else echo 0; fi
}

# ---------------------------------------------------------------------------
[[ "${MIX_E2E_LIB:-}" == 1 ]] && return 0

# ---------------------------------------------------------------------------
# Arguments and run identity
# ---------------------------------------------------------------------------
usage() { echo "usage: scripts/mix-e2e.sh [--dry-run] [--keep]   (env: MIX_E2E_REPO MIX_E2E_INTERVAL MIX_E2E_MAX_MIN MIX_E2E_GOAL MIX_E2E_IMPLEMENTER MIX_E2E_REVIEWER MIX_E2E_SUPERENV_EXTRA)" >&2; exit 2; }
DRY=0; KEEP=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --keep)    KEEP=1; shift ;;
    *) echo "mix-e2e: unknown arg: $1" >&2; usage ;;
  esac
done

STAMP="$(date -u +%Y%m%d-%H%M%S)"
T0_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"          # bridge logs with start= ≥ this belong to the run
SLUG="mix-e2e-$STAMP"
INTERVAL="${MIX_E2E_INTERVAL:-2m}"
MAX_MIN="${MIX_E2E_MAX_MIN:-150}"
IMPL_PIN="${MIX_E2E_IMPLEMENTER:-codex:gpt-5.6-terra}"
REV_PIN="${MIX_E2E_REVIEWER:-pi:openai-codex/gpt-5.6-sol}"
IMPL_H="$(superagent_role_harness "$IMPL_PIN")"; IMPL_M="$(superagent_role_model "$IMPL_PIN")"
REV_H="$(superagent_role_harness "$REV_PIN")";   REV_M="$(superagent_role_model "$REV_PIN")"
GOAL="${MIX_E2E_GOAL:-Add scripts/kv.sh, a POSIX-sh file-backed key-value store: \`kv.sh set <key> <value>\`, \`kv.sh get <key>\` (prints the value; exit 1 and NOTHING on stdout when the key is absent), \`kv.sh del <key>\`, \`kv.sh list\` (every key=value, sorted by key, one per line). The store file is \$KV_FILE (default: .kv in the current directory); keys match [A-Za-z0-9_-]+; values are single lines; setting an existing key replaces its value. Also add scripts/test.sh (POSIX sh) that exercises all four commands against a temporary store and exits non-zero on any mismatch. Keep it to ONE implementation plan of two or three tasks; no files beyond the two scripts and the plan-tree bookkeeping.}"
RUN_DIR="${TMPDIR:-/tmp}"; RUN_DIR="${RUN_DIR%/}/mix-e2e-$STAMP"
REPORT="${MIX_E2E_REPORT:-$ROOT/mix-e2e-report.md}"
CLONE="$RUN_DIR/repo"
REPO_SLUG="${MIX_E2E_REPO:-}"
BRIDGE_DIRS=("${TMPDIR:-/tmp}/superagent-bridge" /tmp/superagent-bridge)   # where role-bridge.sh logs (per-user TMPDIR under launchd too; /tmp as fallback)
PLAN=""; LOOP_FILE=""; ENV_FILE=""; TICK_LOG=""; PR_BASE=0; ROWS=""
INSTALLED_BRIDGE=""; PLUGIN_INSTALLED=""; PLUGIN_REPO="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$ROOT/.claude-plugin/plugin.json" | head -1)"
T0=$(date +%s)

# ---------------------------------------------------------------------------
# Report framing (same shape as pi-e2e.sh)
# ---------------------------------------------------------------------------
PASS=0; FAIL=0; REPORT_OPEN=0
report_open() {
  [[ "$REPORT_OPEN" == 1 ]] && return 0
  REPORT_OPEN=1; mkdir -p "$RUN_DIR"
  {
    echo "# superagent multi-harness mixing e2e report"
    echo
    echo "- date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "- host: $(uname -a)"
    echo "- plugin repo: $ROOT ($(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo 'no git')) version $PLUGIN_REPO; installed claude plugin: ${PLUGIN_INSTALLED:-?} (relays run \`$INSTALLED_BRIDGE\`)"
    echo "- claude: $(claude --version 2>&1 | head -1)   codex: $(codex --version 2>&1 | head -1)   pi: $(pi --version 2>&1 | head -1)"
    echo "- mix: supervisor/planner/executor=claude · implementer+fix-applier=$IMPL_PIN · task-reviewer+re-reviewer=$REV_PIN"
    echo "- remote: $REPO_SLUG   slug: $SLUG   interval: $INTERVAL   ceiling: ${MAX_MIN}m"
    echo "- run dir: $RUN_DIR"
    echo
  } >"$REPORT"
}
report_section() { report_open; { echo "## $1"; echo; } >>"$REPORT"; echo "mix-e2e: == $1"; }
report_note()    { report_open; echo "$1" >>"$REPORT"; }
report_pass()    { PASS=$((PASS+1)); { echo; echo "**Result: PASS** — $1"; echo; } >>"$REPORT"; echo "mix-e2e: PASS — $1"; }
report_fail()    { FAIL=$((FAIL+1)); { echo; echo "**Result: FAIL** — $1"; echo; } >>"$REPORT"; echo "mix-e2e: FAIL — $1" >&2; }
report_cmd() {   # report_cmd <expected-substring-or-empty> <cmd...>
  local expect="$1"; shift
  local out rc
  { echo '```'; printf '$ %s\n' "$*"; echo '```'; } >>"$REPORT"
  local tmp; tmp="$(mktemp)"
  e2e_run "$@" >"$tmp" 2>&1; rc=$?
  out="$(cat "$tmp")"; rm -f "$tmp"
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
phase_preflight() {
  local missing=() c
  for c in claude codex pi gh git python3; do command -v "$c" >/dev/null 2>&1 || missing+=("$c"); done
  if [[ "$(uname -s)" == Darwin ]]; then command -v launchctl >/dev/null 2>&1 || missing+=(launchctl)
  else command -v systemctl >/dev/null 2>&1 || missing+=(systemctl); fi
  [[ ${#missing[@]} -eq 0 ]] || { echo "mix-e2e: missing prerequisite(s): ${missing[*]}" >&2; return 2; }
  gh auth status >/dev/null 2>&1 || { echo "mix-e2e: gh is not authenticated (gh auth login)" >&2; return 2; }
  [[ "$IMPL_H" == codex && "$REV_H" == pi ]] || { echo "mix-e2e: MIX_E2E_IMPLEMENTER must name codex and MIX_E2E_REVIEWER must name pi (got $IMPL_H / $REV_H) — this testbench is the claude+codex+pi mix" >&2; return 2; }
  # Pi must be able to run the reviewer pin's provider (the host's Pi may hold only one login).
  local prov="${REV_M%%/*}"
  pi --list-models 2>/dev/null | awk '{print $1}' | grep -qx -- "$prov" || { echo "mix-e2e: pi lists no models for provider '$prov' (pi --list-models) — authenticate it or change MIX_E2E_REVIEWER" >&2; return 2; }
  codex login status >/dev/null 2>&1 || echo "mix-e2e: WARN codex login status is not ok — codex-bridged roles may fail" >&2
  # The claude tick reads skills/superagent/SKILL.md from this checkout but its in-session
  # superagent:superplan / superrun dispatches resolve through the INSTALLED plugin.
  local pl; pl="$(claude plugin list 2>/dev/null || true)"
  PLUGIN_INSTALLED="$(mix_plugin_field "$pl" Version)"
  [[ -n "$PLUGIN_INSTALLED" ]] || { echo "mix-e2e: the superagent plugin is not installed in claude (claude plugin list)" >&2; return 2; }
  mix_plugin_field "$pl" Status | grep -q enabled || { echo "mix-e2e: the superagent plugin is installed but not enabled in claude" >&2; return 2; }
  [[ "$PLUGIN_INSTALLED" == "$PLUGIN_REPO" ]] || echo "mix-e2e: WARN installed claude plugin is $PLUGIN_INSTALLED, this checkout is $PLUGIN_REPO — skills run from the installed version, scripts from the checkout (claude plugin update superagent@superagent-marketplace)" >&2
  INSTALLED_BRIDGE="$(mix_installed_bridge "$pl")" || { echo "mix-e2e: cannot derive the installed plugin's cache path from 'claude plugin list'" >&2; return 2; }
  [[ -f "$INSTALLED_BRIDGE" ]] || { echo "mix-e2e: installed bridge not found at $INSTALLED_BRIDGE" >&2; return 2; }
  grep -q 'role-bridge: start=' "$INSTALLED_BRIDGE" || { echo "mix-e2e: the INSTALLED plugin's $INSTALLED_BRIDGE predates the evidence header (0.6.5) — the relays run that copy, so the harness-evidence phase cannot pass. Update the plugin (claude plugin update superagent@superagent-marketplace) or, for a pre-merge run, copy this checkout's scripts/role-bridge.sh over it." >&2; return 2; }
  for c in pi codex cursor; do
    "$SCRIPTS/build-$c-skills.sh" --check >/dev/null 2>&1 || { echo "mix-e2e: $c/ build is stale — run scripts/build-$c-skills.sh" >&2; return 2; }
  done
  if [[ -z "$REPO_SLUG" ]]; then
    local owner; owner="$(gh api user -q .login 2>/dev/null || true)"
    [[ -n "$owner" ]] || { echo "mix-e2e: cannot resolve the gh user for the default MIX_E2E_REPO" >&2; return 2; }
    REPO_SLUG="$owner/superagent-mix-e2e"
  fi
  [[ "$REPO_SLUG" == */* ]] || { echo "mix-e2e: MIX_E2E_REPO must be <owner>/<name> (got '$REPO_SLUG')" >&2; return 2; }
  local js; js="$("$SCRIPTS/status.sh" --json 2>/dev/null || echo '[]')"
  [[ -z "$(e2e_status_field "$js" "$SLUG" status)" ]] || { echo "mix-e2e: a loop is already registered under $SLUG" >&2; return 2; }
  return 0
}

print_plan() {
  echo "mix-e2e: would run:"
  echo "  remote:    $REPO_SLUG  (reset to an orphan commit; never deleted)"
  echo "  slug:      $SLUG"
  echo "  mix:       supervisor/planner/executor=claude  implementer+fix-applier=$IMPL_PIN  task-reviewer+re-reviewer=$REV_PIN"
  echo "  plugin:    checkout $PLUGIN_REPO, installed in claude $PLUGIN_INSTALLED (relays run $INSTALLED_BRIDGE)"
  echo "  interval:  $INTERVAL   ceiling: ${MAX_MIN}m   keep clone: $KEEP"
  echo "  run dir:   $RUN_DIR"
  echo "  goal:      $GOAL"
  echo "  phases:    provision → init → supergoal → launch.sh (arm) → watch status.sh until DONE → assert (+ harness evidence) → evaluate → cleanup"
}

# ---------------------------------------------------------------------------
# Phase 1 — provision the throwaway repo (reused remote, reset to an orphan commit)
# ---------------------------------------------------------------------------
phase_provision() {
  report_section "1. Provision $REPO_SLUG"
  if ! e2e_run gh repo view "$REPO_SLUG" >/dev/null 2>&1; then
    report_cmd "" gh repo create "$REPO_SLUG" --private --description "superagent multi-harness mixing e2e testbench (reset per run by scripts/mix-e2e.sh)" || return 1
  fi
  mkdir -p "$RUN_DIR"
  report_cmd "" git clone -q "https://github.com/$REPO_SLUG.git" "$CLONE" || return 1
  report_cmd "" bash -c "
    cd '$CLONE' &&
    git checkout -q --orphan e2e-reset &&
    { git rm -rfq --cached . >/dev/null 2>&1 || true; } &&
    find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + &&
    printf '# superagent mix e2e\n\nReset %s by scripts/mix-e2e.sh — every commit after this one was made by the superagent loop: Claude supervising, Codex implementing, Pi reviewing.\n' '$STAMP' >README.md &&
    cat >.superenv <<'SUPERENV'
$(mix_render_superenv "$INTERVAL" "$RUN_DIR/events.log" "$IMPL_PIN" "$REV_PIN" "${MIX_E2E_SUPERENV_EXTRA:-}")
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
  report_pass "clean main at orphan commit; .superenv: claude supervisor, $IMPL_PIN implementer, $REV_PIN reviewer, notify → events.log"
}

# ---------------------------------------------------------------------------
# Phase 2 — init (headless claude; the installed plugin's skills via the Skill tool)
# ---------------------------------------------------------------------------
CLAUDE_TOOLS="Read,Edit,Write,Bash,Grep,Glob,Skill,Task"
# Prompts go on STDIN: --allowedTools is variadic and would swallow a positional prompt.
claude_run()  { ( cd "$CLONE" && printf '%s' "$1" | claude -p --model opus --allowedTools "$CLAUDE_TOOLS" ); }
claude_turn() {  # claude_turn new|resume <session-uuid> <prompt> — a turn in one PERSISTENT session
  local flag=--resume; [[ "$1" == new ]] && flag=--session-id
  ( cd "$CLONE" && printf '%s' "$3" | claude -p --model opus "$flag" "$2" --allowedTools "$CLAUDE_TOOLS" )
}
UNATTENDED="You are running unattended and headless: never ask a question, never end with a question, make every routine judgment call yourself."
phase_init() {
  report_section "2. init"
  report_cmd "" claude_run "Use the Skill tool to invoke superagent:init and follow it to completion in this repository. $UNATTENDED" || return 1
  grep -qx 'SUPER_HARNESS=claude' "$CLONE/.superenv" || { report_fail "init overwrote .superenv (SUPER_HARNESS=claude gone)"; return 1; }
  grep -qx "SUPER_MODEL_TASK_REVIEWER=$REV_PIN" "$CLONE/.superenv" || { report_fail "init overwrote .superenv (reviewer pin gone)"; return 1; }
  local f r
  for r in implementer fix-applier; do
    f="$CLONE/.claude/agents/super-$r.md"
    [[ -f "$f" ]] || { report_fail "no $f after init"; return 1; }
    grep -q 'generated-by: superagent:init' "$f" || { report_fail "$f lacks the generated-by marker"; return 1; }
    grep -q -- "--harness codex" "$f" || { report_fail "$f is not a codex relay (no --harness codex)"; return 1; }
    grep -q -- "--model \"$IMPL_M\"" "$f" || { report_fail "$f does not pin --model \"$IMPL_M\""; return 1; }
  done
  for r in task-reviewer re-reviewer; do
    f="$CLONE/.claude/agents/super-$r.md"
    [[ -f "$f" ]] || { report_fail "no $f after init"; return 1; }
    grep -q -- "--harness pi" "$f" || { report_fail "$f is not a pi relay (no --harness pi)"; return 1; }
    grep -q -- "--model \"$REV_M\"" "$f" || { report_fail "$f does not pin --model \"$REV_M\""; return 1; }
  done
  [[ -d "$CLONE/vault" ]] || { report_fail "no vault/ after init"; return 1; }
  ( cd "$CLONE" && git checkout -q main 2>/dev/null; git add -A && git commit -qm "e2e: init leftovers" >/dev/null 2>&1; git push -q origin main >/dev/null 2>&1 ) || true
  report_note "- relay definitions: $(cd "$CLONE" && ls .claude/agents/ | tr '\n' ' ')"
  report_pass ".superenv intact; super-implementer/fix-applier are codex relays, super-task-reviewer/re-reviewer are pi relays; vault/ present"
}

# ---------------------------------------------------------------------------
# Phase 3 — supergoal (two turns in one session: draft, then the operator's "yes" at its gate)
# ---------------------------------------------------------------------------
phase_goal() {
  local sid; sid="$(python3 -c 'import uuid; print(uuid.uuid4())')"
  report_section "3. supergoal (turn 1: draft — stops at its confirmation gate)"
  report_cmd "" claude_turn new "$sid" "Use the Skill tool to invoke superagent:supergoal with this goal: $GOAL
$UNATTENDED Stop at the skill's confirmation gate as it prescribes." || return 1
  report_section "3b. supergoal (turn 2: the operator's \"yes\" at the confirmation gate)"
  report_cmd "" claude_turn resume "$sid" "Yes — confirmed. Write the goal folder and root plan to the vault exactly as drafted, commit them, open the PR and merge it now, then print the Final Report. $UNATTENDED" || return 1
  ( cd "$CLONE" && git checkout -q main && git pull -q --ff-only origin main ) || { report_fail "git pull main after supergoal"; return 1; }
  local plans; plans="$(ls "$CLONE"/vault/*/master-plans/*.md 2>/dev/null || true)"
  [[ -n "$plans" && "$(printf '%s\n' "$plans" | wc -l | tr -d ' ')" == 1 ]] || { report_fail "expected exactly one vault/*/master-plans/*.md on main, found: ${plans:-none}"; return 1; }
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
  report_cmd "Launched superagent external loop" bash -c "cd '$CLONE' && '$SCRIPTS/launch.sh' '$PLAN' --harness claude --interval '$INTERVAL' --slug '$SLUG'" || return 1
  local js; js="$("$SCRIPTS/status.sh" --json)"
  [[ "$(e2e_status_field "$js" "$SLUG" timer_active)" == active ]] || { report_fail "status.sh: timer not active for $SLUG"; return 1; }
  LOOP_FILE="$(e2e_status_field "$js" "$SLUG" loop_file)"
  [[ -f "$LOOP_FILE" ]] || { report_fail "loop file missing: $LOOP_FILE"; return 1; }
  ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/superagent/$SLUG.env"
  grep -qx 'SUPER_HARNESS=claude' "$ENV_FILE" || { report_fail "$ENV_FILE lacks SUPER_HARNESS=claude"; return 1; }
  grep -q '^SUPERAGENT_CLI_PATH=' "$ENV_FILE" || { report_fail "$ENV_FILE lacks SUPERAGENT_CLI_PATH (the codex/pi bridges from a scheduler tick depend on it)"; return 1; }
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
    e2e_transition "$st" "$it"; line="$E2E_LINE"
    if [[ -n "$line" ]]; then
      line="$line ticks=$(e2e_count_ticks "$TICK_LOG") bridges=$(mix_bridge_evidence "$T0_STAMP" "${BRIDGE_DIRS[@]}" | awk 'NF{n++} END{print n+0}')"
      printf '%s\n' "$line" | tee -a "$RUN_DIR/transitions.log" >>"$REPORT"; echo "mix-e2e:   $line"
    fi
    if [[ "$(e2e_status_field "$js" "$SLUG" done)" == 1 ]]; then
      local i
      for i in $(seq 1 24); do   # the self-disarm is the tick's last act; let it settle
        js="$("$SCRIPTS/status.sh" --json 2>/dev/null || echo '[]')"
        [[ "$(e2e_status_field "$js" "$SLUG" tick_running)" == active ]] || break
        e2e_run sleep 5
      done
      report_note '```'; report_pass "DONE after $(e2e_count_ticks "$TICK_LOG") tick(s), $(( ($(date +%s) - T0) / 60 )) min since start (tick settled after $(( (i - 1) * 5 ))s)"; return 0
    fi
    if [[ "$(e2e_status_field "$js" "$SLUG" pending_input)" == 1 ]]; then
      report_note '```'; report_fail "parked WAITING FOR INPUT — $(sed -n '/## Pending decision/,$p' "$LOOP_FILE" | head -15 | tr '\n' ' ')"; return 1
    fi
    [[ -n "$st" ]] || { report_note '```'; report_fail "loop vanished from status.sh"; return 1; }
    if (( $(date +%s) > deadline )); then report_note '```'; report_fail "ceiling ${MAX_MIN}m reached at status '$st' iter=$it"; return 1; fi
    e2e_run sleep 30
  done
}

# ---------------------------------------------------------------------------
# Phase 6 — assert the outcome on main AND the per-role harness evidence
# ---------------------------------------------------------------------------
evidence_table() {  # evidence_table <rows> — markdown
  echo "| role | harness | model | effort | exit | secs | start (UTC) |"
  echo "|---|---|---|---|---|---|---|"
  printf '%s\n' "$1" | awk 'NF {printf "| %s | %s | %s | %s | %s | %s | %s |\n", $1, $2, $3, $4, $5, $6, $7}'
}
phase_assert() {
  report_section "6. Assert outcome"
  local ticks merged open why
  ticks="$(e2e_count_ticks "$TICK_LOG")"
  [[ "$ticks" -ge 2 ]] || { report_fail "only $ticks tick(s) in $TICK_LOG — the scheduler never fired on its own"; return 1; }
  ( cd "$CLONE" && git checkout -q main && git pull -q --ff-only origin main ) || { report_fail "git pull main"; return 1; }
  why="$(mix_assert_deliverables "$CLONE")" || { report_fail "deliverables: $why"; ( cd "$CLONE" && ls -R scripts 2>/dev/null | head -20 ) >>"$REPORT"; return 1; }
  merged="$(gh pr list -R "$REPO_SLUG" --state merged --json number -q 'length')"
  open="$(gh pr list -R "$REPO_SLUG" --state open --json number -q 'length')"
  [[ $(( merged - PR_BASE )) -ge 3 && "$open" == 0 ]] || { report_fail "PRs this run: merged=$(( merged - PR_BASE )) open=$open (want ≥3 merged, 0 open)"; return 1; }
  local i timer=active
  for i in $(seq 1 24); do
    timer="$(e2e_status_field "$("$SCRIPTS/status.sh" --json 2>/dev/null || echo '[]')" "$SLUG" timer_active)"
    [[ "$timer" == active ]] || break
    e2e_run sleep 5
  done
  [[ "$timer" != active ]] || { report_fail "timer still active 2 min after DONE (SUPER_AUTO_DISARM_ON_DONE)"; return 1; }
  grep -qx done "$RUN_DIR/events.log" 2>/dev/null || { report_fail "no 'done' event in $RUN_DIR/events.log (SUPER_NOTIFY_CMD)"; return 1; }
  gh pr list -R "$REPO_SLUG" --state merged --json number,title -q '.[] | "- #\(.number) \(.title)"' | head -n $(( merged - PR_BASE )) >>"$REPORT"
  report_pass "ticks=$ticks merged=$(( merged - PR_BASE )) open=0 deliverables ok, timer disarmed, notify=done"

  report_section "6b. Harness evidence (role-bridge.sh log headers/trailers since $T0_STAMP)"
  ROWS="$(mix_bridge_evidence "$T0_STAMP" "${BRIDGE_DIRS[@]}")"
  { echo; evidence_table "$ROWS"; echo; } >>"$REPORT"
  [[ -n "$ROWS" ]] || { report_fail "no bridge logs since $T0_STAMP in ${BRIDGE_DIRS[*]}"; return 1; }
  local legacy; legacy=$(( $(mix_evidence_count "$ROWS" '.*' legacy) + $(mix_evidence_count "$ROWS" '.*' legacy-codex) ))
  [[ "$legacy" == 0 ]] || report_note "- $legacy header-less (pre-0.6.5) bridge log(s): the relays ran a bridge without the evidence lines — see preflight's installed-bridge check"
  mix_evidence_has "$ROWS" implementer codex "$IMPL_M" || { report_fail "no successful implementer run on codex/$IMPL_M"; return 1; }
  mix_evidence_has "$ROWS" task-reviewer pi "$REV_M"   || { report_fail "no successful task-reviewer run on pi/$REV_M"; return 1; }
  mix_evidence_has "$ROWS" executor claude             || { report_fail "no successful executor (superrun) process on claude"; return 1; }
  local stray; stray="$(printf '%s\n' "$ROWS" | awk -v ih="$IMPL_H" -v rh="$REV_H" 'NF && $2 !~ /^legacy/ && ((($1=="implementer"||$1=="fix-applier") && $2!=ih) || (($1=="task-reviewer"||$1=="re-reviewer") && $2!=rh)) {print $1"→"$2}' | sort -u | tr '\n' ' ')"
  [[ -z "$stray" ]] || { report_fail "pinned role(s) ran on the wrong harness: $stray"; return 1; }
  local bf; bf="$(mix_bridge_failed_count "$TICK_LOG")"
  [[ "$bf" == 0 ]] || { report_fail "$bf BRIDGE-FAILED result(s) in the tick log"; return 1; }
  local wrong; wrong="$(printf '%s\n' "$ROWS" | awk 'NF && $5!="0" {print $1"("$2")exit="$5}' | tr '\n' ' ')"
  [[ -z "$wrong" ]] && report_note "- every bridge call exited 0" || report_note "- non-zero bridge calls (not asserted — the loop recovered): $wrong"
  report_pass "codex ran implementer, pi ran task-reviewer, claude ran the executor; no pinned role strayed; no BRIDGE-FAILED"
}

# ---------------------------------------------------------------------------
# Phase 7 — evaluate (report-only; never fails)
# ---------------------------------------------------------------------------
phase_evaluate() {
  report_section "7. Evaluation (report-only)"
  local h rows; rows="${ROWS:-$(mix_bridge_evidence "$T0_STAMP" "${BRIDGE_DIRS[@]}")}"
  {
    echo "- elapsed: $(( ($(date +%s) - T0) / 60 )) min end to end; loop phase ticks: $(e2e_count_ticks "$TICK_LOG"); loop iterations: $(sed -n 's/^iteration:[[:space:]]*//p' "$LOOP_FILE" 2>/dev/null | head -1)"
    echo "- merged PRs this run: $(( $(gh pr list -R "$REPO_SLUG" --state merged --json number -q 'length' 2>/dev/null || echo 0) - PR_BASE ))"
    echo "- bridge calls per harness (count / total secs / longest):"
    for h in claude codex pi; do
      printf '%s\n' "$rows" | awk -v h="$h" 'NF && $2==h {n++; if ($6!="-") {s+=$6; if ($6+0>mx) mx=$6+0}} END {printf "  - %s: %d calls, %d s total, %d s longest\n", h, n, s, mx}'
    done
    echo "- roles: implementer=$(mix_evidence_count "$rows" implementer) fix-applier=$(mix_evidence_count "$rows" fix-applier) task-reviewer=$(mix_evidence_count "$rows" task-reviewer) re-reviewer=$(mix_evidence_count "$rows" re-reviewer) executor=$(mix_evidence_count "$rows" executor) planner=$(mix_evidence_count "$rows" planner) panelists=$(mix_evidence_count "$rows" 'panelist.*')"
    echo "- fix rounds (fix-applier calls): $(mix_evidence_count "$rows" fix-applier); L7 escalations (panelist calls / 3): $(( $(mix_evidence_count "$rows" 'panelist.*') / 3 ))"
    echo "- bridge calls that did not exit 0: $(printf '%s\n' "$rows" | awk 'NF && $5!="0" && $5!="-"' | wc -l | tr -d ' ')   header-less (legacy) rows: $(printf '%s\n' "$rows" | awk 'NF && $2 ~ /^legacy/' | wc -l | tr -d ' ')"
    echo "- tick log: $(grep -c 'superagent-tick ERROR' "$TICK_LOG" 2>/dev/null || echo 0) tick ERROR line(s); $(mix_bridge_failed_count "$TICK_LOG") BRIDGE-FAILED result(s)"
    echo
    echo "Loop log tail:"; echo; echo '```'
    sed -n '/^## Iteration log/,$p' "$LOOP_FILE" 2>/dev/null | tail -25
    echo '```'
  } >>"$REPORT"
  echo "mix-e2e: evaluation written"
  return 0
}

# ---------------------------------------------------------------------------
# Phase 8 — cleanup (trap: always). Only place that touches the scheduler on the way out.
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
    echo "mix-e2e: cleanup — scheduler entry + env file for $SLUG removed" >&3
  fi
  [[ -n "$TICK_LOG" && -f "$TICK_LOG" ]] && cp "$TICK_LOG" "$RUN_DIR/tick.log" 2>/dev/null
  # Keep the run's bridge logs (the evidence) with the other artifacts.
  local f; mkdir -p "$RUN_DIR/bridge" 2>/dev/null
  mix_bridge_evidence "$T0_STAMP" "${BRIDGE_DIRS[@]}" | awk 'NF {print $8}' | while IFS= read -r f; do cp "$f" "${f%.log}.last" "$RUN_DIR/bridge/" 2>/dev/null; done
  if [[ "$KEEP" == 1 ]]; then echo "mix-e2e: clone kept at $CLONE" >&3; else rm -rf "$CLONE"; fi
  return 0
}

on_signal() {  # on_signal <name> <exit-code>
  trap - INT TERM
  echo "mix-e2e: interrupted by SIG$1 — stopping the running child and cleaning up" >&3
  [[ -n "$CHILD_PID" ]] && e2e_kill_tree "$CHILD_PID"
  [[ "$REPORT_OPEN" == 1 ]] && report_fail "interrupted by SIG$1"
  phase_cleanup
  exit "$2"
}

# ---------------------------------------------------------------------------
main() {
  phase_preflight || exit $?
  print_plan
  if [[ "$DRY" == 1 ]]; then echo "[dry-run] nothing created or armed."; exit 0; fi
  exec 3>&2
  trap 'on_signal INT 130' INT
  trap 'on_signal TERM 143' TERM
  trap phase_cleanup EXIT
  report_open
  local rc=0
  phase_provision && phase_init && phase_goal && phase_arm && phase_drive && phase_assert || rc=1
  [[ -n "$LOOP_FILE" ]] && phase_evaluate
  phase_cleanup
  {
    echo "## Summary"; echo
    echo "- PASS: $PASS   FAIL: $FAIL   elapsed: $(( ($(date +%s) - T0) / 60 )) min"
    echo "- verdict: $([[ $rc == 0 ]] && echo PASS || echo FAIL)"
    echo "- artifacts: $RUN_DIR (tick.log, events.log, transitions.log, bridge/)"
  } >>"$REPORT"
  echo; echo "mix-e2e: $([[ $rc == 0 ]] && echo PASS || echo FAIL) — $PASS pass, $FAIL fail, $(( ($(date +%s) - T0) / 60 )) min"
  echo "mix-e2e: report: $REPORT   artifacts: $RUN_DIR"
  exit $rc
}
main

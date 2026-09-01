# Pi e2e testbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One script, `scripts/pi-e2e.sh`, that drives a tiny real goal from an empty repo through `init → supergoal → scheduler-fired external loop → DONE` on the Pi harness, asserts the outcome, cleans up, and writes a report.

**Architecture:** A bash script in the style of `pi-smoke.sh` (report sections, PASS/FAIL per phase) whose pure helpers are sourceable as a library (`PI_E2E_LIB=1`) so `bridge-test.sh` can unit-test them offline with shimmed CLIs. The script never invokes `superagent-tick.sh`; it arms the loop with `launch.sh` and only watches `status.sh --json`. Cleanup is a trap.

**Tech Stack:** bash 3.2+ (macOS), `python3` (JSON), `gh`, `git`, `pi`, launchd/systemd via the plugin's own scripts.

**Spec:** `docs/superpowers/specs/2026-09-01-pi-e2e-testbench-design.md`

## Global Constraints

- Never delete the remote repo (`PI_E2E_REPO`, default `<gh user>/superagent-pi-e2e`); reset it per run.
- The script never runs a tick itself; ticks are scheduler-fired (`ticks ≥ 2` asserted).
- `.superenv` values with `$` are single-quoted (`SUPER_NOTIFY_CMD`); `.superenv` is sourced under `set -u`.
- Report file `pi-e2e-report.md` is gitignored; run artifacts under `$TMPDIR/pi-e2e-<stamp>/`.
- Defaults: `PI_E2E_INTERVAL=2m`, `PI_E2E_MAX_MIN=90`, slug `pi-e2e-<YYYYmmdd-HHMMSS>`.
- Version bump to 0.6.4 with a CHANGELOG entry; `pi/README.md` is generated — edit `scripts/build-pi-skills.sh` and rebuild.

---

## File structure

- Create `scripts/pi-e2e.sh` — the testbench. Top: helpers (pure, no side effects). Middle: phase functions `phase_preflight … phase_cleanup`. Bottom: `main` guarded by `[[ "${PI_E2E_LIB:-}" == 1 ]] && return 0`.
- Modify `scripts/bridge-test.sh` — append the offline cases (it already has shims for `pi`, and a `check` helper).
- Modify `.gitignore` — `pi-e2e-report.md`.
- Modify `scripts/README.md` — a "Pi e2e testbench" subsection next to the smoke description.
- Modify `scripts/build-pi-skills.sh` — the `pi/README.md` heredoc: a "Testbench" paragraph + the live result.
- Modify `CHANGELOG.md`, `.claude-plugin/plugin.json` (0.6.4); rebuild pi/codex/cursor trees.

Helper interfaces (all in `scripts/pi-e2e.sh`, used by later tasks):

```
e2e_status_field <json> <slug> <field>   # prints the field of the object whose slug matches; "" if absent
e2e_render_superenv <interval> <events_log> [extra]   # prints .superenv content
e2e_count_ticks <tick_log>               # number of "superagent-tick harness=" headers
e2e_assert_deliverables <repo_dir>       # 0 if scripts/hello.sh prints "hello, world" and scripts/test.sh exits 0
e2e_transition <status> <iteration>      # prints "<ts> <status> iter=<n>" only when (status,iteration) changed since last call
```

---

### Task 1: Library skeleton + `e2e_status_field`

**Files:** Create `scripts/pi-e2e.sh`; Modify `scripts/bridge-test.sh` (append before `echo "bridge-test: …"`).

- [ ] **Step 1: Failing tests** — append to `bridge-test.sh`:

```bash
# --- pi-e2e.sh helpers (sourced as a library; no phases run) ---
E2E="$ROOT/scripts/pi-e2e.sh"
E2E_JSON='[{"slug":"other","status":"DONE","iteration":"9","timer_active":"inactive","tick_running":"inactive","lock_held":false,"pending_input":0,"answer_recorded":false,"done":1,"loop_file":"/x","loop_file_exists":true,"next_fire":"","gh_auth":"ok"},{"slug":"pi-e2e-1","status":"WAITING FOR RUN","iteration":"2","timer_active":"active","tick_running":"inactive","lock_held":false,"pending_input":0,"answer_recorded":false,"done":0,"loop_file":"/y","loop_file_exists":true,"next_fire":"soon","gh_auth":"ok"}]'
check "e2e: sources as a library" bash -c "PI_E2E_LIB=1; . '$E2E'"
check "e2e: status_field picks the right slug" bash -c "PI_E2E_LIB=1; . '$E2E'; [ \"\$(e2e_status_field '$E2E_JSON' pi-e2e-1 status)\" = 'WAITING FOR RUN' ]"
check "e2e: status_field numeric field" bash -c "PI_E2E_LIB=1; . '$E2E'; [ \"\$(e2e_status_field '$E2E_JSON' other done)\" = 1 ]"
check "e2e: status_field absent slug → empty" bash -c "PI_E2E_LIB=1; . '$E2E'; [ -z \"\$(e2e_status_field '$E2E_JSON' nope status)\" ]"
check "e2e: status_field empty array → empty" bash -c "PI_E2E_LIB=1; . '$E2E'; [ -z \"\$(e2e_status_field '[]' x status)\" ]"
```

- [ ] **Step 2: Run** `bash scripts/bridge-test.sh </dev/null | grep e2e` → 5 FAIL.
- [ ] **Step 3: Implement** the skeleton with the helper:

```bash
#!/usr/bin/env bash
# pi-e2e.sh — (header per spec) …
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$ROOT/scripts"

e2e_status_field() {  # <json> <slug> <field>
  python3 - "$2" "$3" <<<"$1" <<'EOF' 2>/dev/null || true
import json,sys
slug,field=sys.argv[1],sys.argv[2]
try: rows=json.load(sys.stdin)
except Exception: rows=[]
for r in rows:
    if r.get("slug")==slug:
        v=r.get(field,""); print(v if not isinstance(v,bool) else str(v).lower()); break
EOF
}
```
  (Two here-docs on one python invocation is invalid — feed JSON via `printf '%s' "$1" | python3 -c '…' "$2" "$3"` instead; the test pins behaviour, not the form.)

- [ ] **Step 4: Run** → 5 ok. **Step 5: Commit** `feat(pi-e2e): library skeleton + status JSON helper`.

### Task 2: Pure helpers — superenv rendering, tick counting, transitions, deliverables

**Files:** Modify `scripts/pi-e2e.sh`, `scripts/bridge-test.sh`.

- [ ] **Step 1: Failing tests**

```bash
check "e2e: superenv has harness, interval, single-quoted notify" bash -c "PI_E2E_LIB=1; . '$E2E'; out=\$(e2e_render_superenv 2m /tmp/ev.log); grep -qx 'SUPER_HARNESS=pi' <<<\"\$out\" && grep -qx 'SUPER_TICK_INTERVAL=2m' <<<\"\$out\" && grep -q \"^SUPER_NOTIFY_CMD='.*\\\$SUPERAGENT_EVENT.*/tmp/ev.log.*'\$\" <<<\"\$out\""
check "e2e: superenv appends extra lines" bash -c "PI_E2E_LIB=1; . '$E2E'; e2e_render_superenv 2m /tmp/ev.log 'SUPER_MODEL_TASK_REVIEWER=codex:gpt-5.6-sol' | grep -qx 'SUPER_MODEL_TASK_REVIEWER=codex:gpt-5.6-sol'"
check "e2e: superenv sources under set -u" bash -c "PI_E2E_LIB=1; . '$E2E'; e2e_render_superenv 2m /tmp/ev.log >'$T/se'; bash -uc 'set -a; . \"$T/se\"; [ \"\$SUPER_HARNESS\" = pi ]'"
printf '=== t superagent-tick harness=pi model=x ===\nblah\n=== t superagent-tick exit=0 ===\n=== t superagent-tick harness=pi model=x ===\n=== t superagent-tick exit=10 ===\n' >"$T/tick.log"
check "e2e: count_ticks counts session headers" bash -c "PI_E2E_LIB=1; . '$E2E'; [ \"\$(e2e_count_ticks '$T/tick.log')\" = 2 ]"
check "e2e: count_ticks missing log → 0" bash -c "PI_E2E_LIB=1; . '$E2E'; [ \"\$(e2e_count_ticks '$T/nope.log')\" = 0 ]"
check "e2e: transition prints only on change" bash -c "PI_E2E_LIB=1; . '$E2E'; a=\$(e2e_transition PLANNING 1); b=\$(e2e_transition PLANNING 1); c=\$(e2e_transition RUNNING 1); [ -n \"\$a\" ] && [ -z \"\$b\" ] && [[ \"\$c\" == *'RUNNING iter=1' ]]"
mkdir -p "$T/deliv/scripts"; printf '#!/bin/sh\necho "hello, world"\n' >"$T/deliv/scripts/hello.sh"; printf '#!/bin/sh\n[ "$(sh "$(dirname "$0")/hello.sh")" = "hello, world" ]\n' >"$T/deliv/scripts/test.sh"; chmod +x "$T/deliv/scripts/"*.sh
check "e2e: deliverables pass" bash -c "PI_E2E_LIB=1; . '$E2E'; e2e_assert_deliverables '$T/deliv'"
check "e2e: deliverables fail when hello.sh is wrong" bash -c "PI_E2E_LIB=1; . '$E2E'; cp -R '$T/deliv' '$T/deliv2'; echo 'echo nope' >'$T/deliv2/scripts/hello.sh'; ! e2e_assert_deliverables '$T/deliv2'"
```

- [ ] **Step 2: Run** → 9 FAIL. **Step 3: Implement:**

```bash
e2e_render_superenv() {  # <interval> <events_log> [extra-lines]
  printf 'SUPER_HARNESS=pi\nSUPER_TICK_INTERVAL=%s\n' "$1"
  printf "SUPER_NOTIFY_CMD='printf \"%%s\\\\n\" \"\$SUPERAGENT_EVENT\" >>\"%s\"'\n" "$2"
  [[ -n "${3:-}" ]] && printf '%s\n' "$3"
  return 0
}
e2e_count_ticks() { [[ -f "$1" ]] && grep -c '^=== .* superagent-tick harness=' "$1" || echo 0; }
_E2E_LAST=""
e2e_transition() {  # <status> <iteration>
  local key="$1|$2"; [[ "$key" == "$_E2E_LAST" ]] && return 0
  _E2E_LAST="$key"; printf '%s %s iter=%s\n' "$(date -u +%H:%M:%S)" "$1" "$2"
}
e2e_assert_deliverables() {  # <repo_dir>
  local d="$1"
  [[ -f "$d/scripts/hello.sh" && -f "$d/scripts/test.sh" ]] || { echo "missing scripts/hello.sh or scripts/test.sh"; return 1; }
  [[ "$(cd "$d" && sh scripts/hello.sh 2>&1)" == "hello, world" ]] || { echo "hello.sh output != 'hello, world'"; return 1; }
  (cd "$d" && sh scripts/test.sh >/dev/null 2>&1) || { echo "scripts/test.sh failed"; return 1; }
}
```

- [ ] **Step 4: Run** → all ok. **Step 5: Commit** `feat(pi-e2e): pure helpers`.

### Task 3: Report framing, preflight, `--dry-run`

**Files:** Modify `scripts/pi-e2e.sh`, `scripts/bridge-test.sh`, `.gitignore`.

- [ ] **Step 1: Failing test** — under the bridge-test shims (`pi` exists; add `gh` and `launchctl`/`systemctl` shims that exit 0; `git`/`python3` are real):

```bash
mkshim gh; mkshim launchctl; mkshim systemctl
check "e2e: --dry-run exits 0 and prints the plan" bash -c "cd '$T/cwd' && PI_E2E_REPO=o/r '$E2E' --dry-run 2>&1 | grep -q 'dry-run.*nothing created'"
check "e2e: --dry-run writes no report" bash -c "cd '$T/cwd' && PI_E2E_REPO=o/r '$E2E' --dry-run >/dev/null 2>&1; [ ! -f '$ROOT/pi-e2e-report.md' ]"
check "e2e: bad flag → exit 2" bash -c "'$E2E' --bogus >/dev/null 2>&1; [ \$? = 2 ]"
```
  Note: preflight runs `build-pi-skills.sh --check` (real, offline) and `status.sh --json` (real; reads `~/.config/superagent`, harmless). The `gh` shim must answer `gh auth status` (exit 0) and `gh api user -q .login` (prints `RESULT-gh` — accept any non-empty login).

- [ ] **Step 2: Run** → 3 FAIL. **Step 3: Implement** — arg parsing (`--dry-run`, `--keep`, else usage exit 2), `report_section <title>`, `report_cmd <expect-substring> <cmd…>` (same head+tail truncation as `pi-smoke.sh` `run_test`, but returns the verdict so a phase can abort), `phase_preflight` checking: `pi gh git python3`, scheduler binary (`launchctl` on Darwin else `systemctl`), `gh auth status`, `"$SCRIPTS/build-pi-skills.sh" --check`, `pi-subagents` (WARN), slug not in `status.sh --json`. `--dry-run`: after preflight print repo/slug/interval/ceiling/run dir and `[dry-run] nothing created or armed.`; exit 0; no report file is written in dry-run (report is opened lazily by the first non-dry section). Add `pi-e2e-report.md` to `.gitignore`.
- [ ] **Step 4: Run** → ok. **Step 5: Commit** `feat(pi-e2e): report framing, preflight, --dry-run`.

### Task 4: Phases 1–4 (provision, init, goal, arm)

**Files:** Modify `scripts/pi-e2e.sh`.

- [ ] **Step 1: Implement** (no offline test — these are network/CLI phases; the live run is their test; the phase functions are small and read top-to-bottom):

```bash
phase_provision() {
  report_section "1. Provision $REPO_SLUG"
  gh repo view "$REPO_SLUG" >/dev/null 2>&1 || report_cmd "" gh repo create "$REPO_SLUG" --private --description "superagent Pi e2e testbench (reset per run)" || return 1
  report_cmd "" git clone -q "https://github.com/$REPO_SLUG.git" "$CLONE" || return 1
  ( cd "$CLONE" && git checkout -q --orphan e2e-reset && git rm -rfq --cached . >/dev/null 2>&1; rm -rf ./* .pi .superenv vault 2>/dev/null
    printf '# superagent Pi e2e\n\nReset %s by scripts/pi-e2e.sh.\n' "$STAMP" >README.md
    e2e_render_superenv "$INTERVAL" "$RUN_DIR/events.log" "${PI_E2E_SUPERENV_EXTRA:-}" >.superenv
    git add -A && git commit -qm "e2e: reset $STAMP" && git branch -M main && git push -q --force origin main ) || return 1
  # stale branches + open PRs from earlier runs
  for b in $(gh api "repos/$REPO_SLUG/branches" -q '.[].name' | grep -vx main); do gh api -X DELETE "repos/$REPO_SLUG/git/refs/heads/$b" >/dev/null 2>&1 || true; done
  for n in $(gh pr list -R "$REPO_SLUG" --state open -q '.[].number' --json number); do gh pr close -R "$REPO_SLUG" "$n" >/dev/null 2>&1 || true; done
  PR_BASE="$(gh pr list -R "$REPO_SLUG" --state merged --json number -q 'length')"
}
phase_init() {
  report_section "2. init"
  report_cmd "" bash -c "cd '$CLONE' && pi -p --approve --no-session --skill '$ROOT/pi/skills' 'Read $ROOT/pi/skills/init/SKILL.md and run it.'" || return 1
  grep -qx 'SUPER_HARNESS=pi' "$CLONE/.superenv" || { report_fail "init overwrote SUPER_HARNESS"; return 1; }
  [[ -f "$CLONE/.pi/agents/super-implementer.md" ]] || { report_fail "no .pi/agents/super-implementer.md"; return 1; }
  [[ -d "$CLONE/vault" ]] || { report_fail "no vault/"; return 1; }
  ( cd "$CLONE" && git add -A && git commit -qm "e2e: init" 2>/dev/null; git push -q origin main ) || true
}
phase_goal() {
  report_section "3. supergoal"
  report_cmd "" bash -c "cd '$CLONE' && pi -p --approve --no-session --skill '$ROOT/pi/skills' 'Read $ROOT/pi/skills/supergoal/SKILL.md and run it with this goal: $GOAL'" || return 1
  ( cd "$CLONE" && git checkout -q main && git pull -q ) || true
  PLAN="$(ls "$CLONE"/vault/*/PLAN.md 2>/dev/null | head -1)"
  [[ -n "$PLAN" && "$(ls "$CLONE"/vault/*/PLAN.md | wc -l | tr -d ' ')" == 1 ]] || { report_fail "expected exactly one vault/*/PLAN.md"; return 1; }
  [[ "$(gh pr list -R "$REPO_SLUG" --state merged --json number -q 'length')" -gt "$PR_BASE" ]] || { report_fail "supergoal merged no PR"; return 1; }
}
phase_arm() {
  report_section "4. launch.sh (arm the scheduler)"
  report_cmd "Launched superagent external loop" bash -c "cd '$CLONE' && REPO='$CLONE' '$SCRIPTS/launch.sh' '$PLAN' --harness pi --interval '$INTERVAL' --slug '$SLUG'" || return 1
  local js; js="$("$SCRIPTS/status.sh" --json)"
  [[ "$(e2e_status_field "$js" "$SLUG" timer_active)" == active ]] || { report_fail "timer not active"; return 1; }
  LOOP_FILE="$(e2e_status_field "$js" "$SLUG" loop_file)"; [[ -f "$LOOP_FILE" ]] || { report_fail "loop file missing"; return 1; }
  ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/superagent/$SLUG.env"
  grep -qx 'SUPER_HARNESS=pi' "$ENV_FILE" && grep -q '^SUPERAGENT_CLI_PATH=' "$ENV_FILE" || { report_fail "env file lacks SUPER_HARNESS=pi / SUPERAGENT_CLI_PATH"; return 1; }
  TICK_LOG="/tmp/superagent-$(basename "$LOOP_FILE" .md).log"
}
```
- [ ] **Step 2: Syntax** `bash -n scripts/pi-e2e.sh`; rerun bridge-test (dry-run still ok). **Step 3: Commit** `feat(pi-e2e): provision/init/goal/arm phases`.

### Task 5: Phases 5–7 (drive, assert, cleanup) + main

**Files:** Modify `scripts/pi-e2e.sh`.

- [ ] **Step 1: Implement**

```bash
phase_drive() {
  report_section "5. Drive (watch only; ticks are scheduler-fired every $INTERVAL)"
  local deadline=$(( $(date +%s) + MAX_MIN*60 )) js st it
  while :; do
    js="$("$SCRIPTS/status.sh" --json)"; st="$(e2e_status_field "$js" "$SLUG" status)"; it="$(e2e_status_field "$js" "$SLUG" iteration)"
    e2e_transition "$st" "$it" | tee -a "$RUN_DIR/transitions.log" | sed 's/^/  /' >>"$REPORT"
    [[ "$(e2e_status_field "$js" "$SLUG" done)" == 1 ]] && { report_pass "DONE after $(e2e_count_ticks "$TICK_LOG") ticks"; return 0; }
    [[ "$(e2e_status_field "$js" "$SLUG" pending_input)" == 1 ]] && { report_fail "parked WAITING FOR INPUT: $(sed -n '/## Pending decision/,$p' "$LOOP_FILE" | head -20)"; return 1; }
    [[ -z "$st" ]] && { report_fail "loop vanished from status.sh"; return 1; }
    (( $(date +%s) > deadline )) && { report_fail "ceiling ${MAX_MIN}m reached at status '$st' iter=$it"; return 1; }
    sleep 30
  done
}
phase_assert() {
  report_section "6. Assert outcome"
  local ticks merged open; ticks="$(e2e_count_ticks "$TICK_LOG")"
  [[ "$ticks" -ge 2 ]] || { report_fail "only $ticks tick(s) — scheduler never fired"; return 1; }
  ( cd "$CLONE" && git checkout -q main && git pull -q ) || { report_fail "git pull"; return 1; }
  e2e_assert_deliverables "$CLONE" || { report_fail "deliverables"; return 1; }
  merged="$(gh pr list -R "$REPO_SLUG" --state merged --json number -q 'length')"; open="$(gh pr list -R "$REPO_SLUG" --state open --json number -q 'length')"
  [[ $(( merged - PR_BASE )) -ge 3 && "$open" == 0 ]] || { report_fail "PRs: merged=$((merged-PR_BASE)) open=$open (want ≥3 / 0)"; return 1; }
  [[ "$(e2e_status_field "$("$SCRIPTS/status.sh" --json)" "$SLUG" timer_active)" != active ]] || { report_fail "timer still active after DONE (SUPER_AUTO_DISARM_ON_DONE)"; return 1; }
  grep -qx done "$RUN_DIR/events.log" 2>/dev/null || { report_fail "no 'done' event in events.log (SUPER_NOTIFY_CMD)"; return 1; }
  report_pass "ticks=$ticks merged=$((merged-PR_BASE)) open=0 timer=disarmed notify=done"
}
phase_cleanup() {  # trap EXIT
  local js; js="$("$SCRIPTS/status.sh" --json 2>/dev/null)"
  if [[ -n "$(e2e_status_field "$js" "$SLUG" status)" ]]; then
    [[ "$(e2e_status_field "$js" "$SLUG" tick_running)" == active ]] && "$SCRIPTS/stop.sh" --slug "$SLUG" --hard "$PLAN" >/dev/null 2>&1
    "$SCRIPTS/uninstall-timer.sh" "$SLUG" --purge >/dev/null 2>&1 || true
  fi
  [[ -f "$TICK_LOG" ]] && cp "$TICK_LOG" "$RUN_DIR/tick.log"
  [[ "$KEEP" == 1 ]] || rm -rf "$CLONE"
}
```
  `main`: preflight → (dry-run exit) → `trap phase_cleanup EXIT INT TERM` → phases 1..6 in order, stop at first failure → summary (`PASS`/`FAIL`, phases, run dir) → exit 0/1.
- [ ] **Step 2:** `bash -n`; bridge-test still green. **Step 3: Commit** `feat(pi-e2e): drive/assert/cleanup + main`.

### Task 6: Docs, version, live run, record

**Files:** Modify `scripts/README.md`, `scripts/build-pi-skills.sh` (README heredoc), `CHANGELOG.md`, `.claude-plugin/plugin.json`; rebuild trees.

- [ ] **Step 1:** `scripts/README.md` — subsection "Pi e2e testbench (`pi-e2e.sh`)": what it does, env knobs, cost note, remote policy, `--dry-run`/`--keep`.
- [ ] **Step 2:** `scripts/build-pi-skills.sh` README heredoc — "Testbench" paragraph after the smoke entries and a line in Known gaps replacing "A live scheduler-fired loop remains unexercised" with the recorded result (filled after Step 4).
- [ ] **Step 3:** CHANGELOG `## 0.6.4 — 2026-09-01`; bump; rebuild `build-{pi,codex,cursor}-skills.sh`; `--check` ×3; bridge-test green.
- [ ] **Step 4: Live run** `bash scripts/pi-e2e.sh` (background, ~20–40 min). Record ticks/PRs/duration from `pi-e2e-report.md` into the Step 2 paragraph; rebuild; `--check`.
- [ ] **Step 5: Commit** `feat: pi-e2e.sh — scripted Pi end-to-end testbench (scheduler-fired loop to DONE); bump to 0.6.4`, push, PR.

## Self-review

- Spec coverage: command/knobs → T3/T5 main; phases 0–7 → T3 (0), T4 (1–4), T5 (5–7); default goal + `.superenv` → T2/T4; slug → T3; testing → T1–T3; decisions 1–6 encoded (1: `gh repo view || create`, never delete; 2: drive only watches; 3: extra env opt-in; 4: python3 in preflight; 5: defaults; 6: pending_input = FAIL).
- Placeholders: none; the one fenced "invalid" note in T1 tells the implementer the right form.
- Names: `e2e_status_field / e2e_render_superenv / e2e_count_ticks / e2e_transition / e2e_assert_deliverables` consistent across T1–T5; report helpers `report_section / report_cmd / report_pass / report_fail`; globals `REPO_SLUG CLONE RUN_DIR STAMP SLUG INTERVAL MAX_MIN GOAL PLAN LOOP_FILE ENV_FILE TICK_LOG PR_BASE KEEP REPORT`.

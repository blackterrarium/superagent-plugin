# WAITING FOR CI Gate + Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a `WAITING FOR CI` park free (bash pre-check of the recorded run ids, no session while any run is still running) and land the four small correctness items parked by the #22 review.

**Architecture:** One more pre-session gate in `scripts/superagent-tick.sh`, placed after the gh preflight, backed by a new `_common.sh` parser `superagent_ci_runs`; fail-open on any doubt. `answer.sh` releases the lock before kicking on its skip path and steals a dead-owner lock. `status.sh` derives the INPUT column from `superagent_pending_answer`. Docs, builds, CHANGELOG, 0.4.9.

**Tech Stack:** Bash (`set -euo pipefail`), awk/grep, `gh`; throwaway stub harness in the scratchpad (same as #22 — `$SCRATCH/harness/setup.sh` already exists with `write_loop`, `tick`, `pass`, `fail`, stub `claude`/`gh`, `XDG_CONFIG_HOME` env for slug `g`).

**Spec:** `docs/superpowers/specs/2026-08-28-ci-gate-and-hardening-design.md`

## Global Constraints

- Branch `ci-gate-and-hardening` off `main` (31e7fe4); commit per task; PR at the end; never commit to `main`.
- `set -euo pipefail` in executables; `_common.sh` helpers must be set-e-safe and must NOT use `${N:?}` (empty arg → empty output / non-fatal rc).
- `cursor/` and `codex/` are generated; edit `skills/`, run both build scripts, both `--check` must pass.
- New `.superenv` key exact: `SUPER_CI_GATE=true`. No new tick exit codes; the gate exits 0.
- The CI gate goes AFTER `ensure_gh_auth || exit 4` and BEFORE the `if [[ "$HARNESS" == claude ]]; then PROMPT=` block; it never runs when `status != WAITING FOR CI`.
- Fail-open: no ids / `gh` error → log + fall through to the session.
- `$SCRATCH` = `/private/tmp/claude-501/-Users-eugene-src-superagent-plugin/506813a2-f910-4cad-adea-baa8834a5d16/scratchpad`; harness files are never committed. The harness keeps `$HOME/.local/bin` in PATH so `_superagent_augment_path` doesn't shadow the stubs.
- Test-rc idiom in the harness: `rc=0; cmd || rc=$?` (never `cmd; rc=$?` under `set -e`).

---

### Task 1: `superagent_ci_runs` + the CI gate

**Files:**
- Modify: `scripts/_common.sh` (append after `superagent_pending_answer`)
- Modify: `scripts/superagent-tick.sh` (insert after `ensure_gh_auth || exit 4`)
- Modify: `templates/superenv.default` (after `SUPER_INPUT_GATE`)
- Modify: `$SCRATCH/harness/setup.sh` (extend stub `gh`, add `write_ci_loop`) — throwaway
- Create: `$SCRATCH/harness/t5_ci_gate.sh` — throwaway

**Interfaces:**
- Produces: `superagent_ci_runs <loop-file>` → space-separated run ids (digit runs of ≥5 chars) found under `ci_wait:` → `runs:` in the frontmatter, in either `runs: [123456, 234567]` or `runs:\n    - 123456` form; empty output, rc 0 when none / missing file / empty arg.
- Gate log lines (exact prefixes): `superagent-tick: WAITING FOR CI — <n>/<m> run(s) still running — skipping the session (SUPER_CI_GATE)`; `superagent-tick: WAITING FOR CI — all <m> run(s) terminal — running the resume session`; `superagent-tick: WAITING FOR CI — no run ids in ci_wait — letting the session handle it`; `superagent-tick: WAITING FOR CI — gh query failed for run <id> — letting the session handle it`.

- [ ] **Step 1: Extend the stub harness**

Append to `$SCRATCH/harness/setup.sh` (before the final `tick()`/`pass`/`fail` lines is fine — it is sourced whole):

```bash
# stub gh: add `run view <id> --json status --jq .status` → contents of $H/ghstatus/<id>, exit 1 if absent
mkdir -p "$H/ghstatus"
cat >"$H/bin/gh" <<'S'
#!/usr/bin/env bash
case "$1 ${2:-}" in
  "auth status") exit 0 ;;
  "auth token")  echo stub-token ;;
  "run view")    echo "STUB_GH_RUN_VIEW $3" >>"$STUB_LOG"
                 [[ -f "$H/ghstatus/$3" ]] || { echo "run not found" >&2; exit 1; }
                 cat "$H/ghstatus/$3" ;;
  *) exit 0 ;;
esac
S
chmod +x "$H/bin/gh"
export H
# write_ci_loop <runs-yaml…>  — WAITING FOR CI fixture; pass the runs: line(s) verbatim
write_ci_loop() {
  {
    cat <<L
---
master_plan: vault/g/master-plans/PLAN.md
status: WAITING FOR CI
plan_exhausted: false
prior_status:
driver: external
cron_id:
created: 2026-08-28
iteration: 4
session_skill_count: 0
ci_wait:
  branch: feat-x
  pr: 7
L
    printf '%s\n' "$@"
    cat <<L
  since: 2026-08-28T00:00:00Z
---

## Pending decision

## Decisions

## Iteration log
- 4: superrun → CI-PENDING (runs 123456 234567)
L
  } >"$LOOP_FILE"
}
ghstatus() { echo "$2" >"$H/ghstatus/$1"; }   # ghstatus <id> <status>
```

- [ ] **Step 2: Write the failing test**

```bash
cat >"$SCRATCH/harness/t5_ci_gate.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/setup.sh"
. "$PLUGIN/scripts/_common.sh"
rm -f "$H/ghstatus"/*

# helper: inline list, list form, none, missing file, empty arg
write_ci_loop "  runs: [123456, 234567]"
[[ "$(superagent_ci_runs "$LOOP_FILE")" == "123456 234567" ]] || fail "inline runs: $(superagent_ci_runs "$LOOP_FILE")"
pass "ci_runs parses inline list"
write_ci_loop "  runs:" "    - 123456" "    - 234567"
[[ "$(superagent_ci_runs "$LOOP_FILE")" == "123456 234567" ]] || fail "list runs"
pass "ci_runs parses list form"
write_ci_loop "  runs: []"
[[ -z "$(superagent_ci_runs "$LOOP_FILE")" ]] || fail "empty runs"
[[ -z "$(superagent_ci_runs /nonexistent)" && -z "$(superagent_ci_runs "")" ]] || fail "missing/empty arg"
pass "ci_runs empty cases safe"
# the pr: 7 / iteration: 4 numbers must NOT be picked up as run ids
write_ci_loop "  runs: [123456]"
[[ "$(superagent_ci_runs "$LOOP_FILE")" == "123456" ]] || fail "leaked non-run digits"
pass "ci_runs ignores other numbers"

# 1. one run still in progress → no session, exit 0
write_ci_loop "  runs: [123456, 234567]"; ghstatus 123456 completed; ghstatus 234567 in_progress
: >"$STUB_LOG"; rc=0; tick || rc=$?
[[ $rc -eq 0 ]] || fail "gate rc=$rc"
grep -q STUB_CLAUDE_CALLED "$STUB_LOG" && fail "session launched while CI running"
grep -q "1/2 run(s) still running — skipping the session (SUPER_CI_GATE)" "$LOG_FILE" || fail "gate log line"
pass "running CI → session skipped"

# 2. all terminal (mixed conclusions are still 'completed') → session runs
ghstatus 234567 completed
: >"$STUB_LOG"; STUB_SET_STATUS="WAITING FOR RUN" tick
grep -q STUB_CLAUDE_CALLED "$STUB_LOG" || fail "no session when all terminal"
grep -q "all 2 run(s) terminal — running the resume session" "$LOG_FILE" || fail "terminal log line"
pass "all terminal → session runs"

# 3. gh failure → fail-open (session runs), logged
write_ci_loop "  runs: [999999]"
: >"$STUB_LOG"; STUB_SET_STATUS="WAITING FOR RUN" tick
grep -q STUB_CLAUDE_CALLED "$STUB_LOG" || fail "gh failure did not fall through"
grep -q "gh query failed for run 999999" "$LOG_FILE" || fail "gh failure log"
pass "gh failure → fail-open"

# 4. no ids → fail-open
write_ci_loop "  runs: []"
: >"$STUB_LOG"; STUB_SET_STATUS="WAITING FOR RUN" tick
grep -q STUB_CLAUDE_CALLED "$STUB_LOG" || fail "no-ids did not fall through"
grep -q "no run ids in ci_wait" "$LOG_FILE" || fail "no-ids log"
pass "no ids → fail-open"

# 5. gate off → session runs even while CI running
write_ci_loop "  runs: [123456]"; ghstatus 123456 queued
: >"$STUB_LOG"; SUPER_CI_GATE=false STUB_SET_STATUS="WAITING FOR RUN" tick
grep -q STUB_CLAUDE_CALLED "$STUB_LOG" || fail "SUPER_CI_GATE=false did not run"
pass "SUPER_CI_GATE=false runs the session"

# 6. gate is inert for other statuses (no gh run view calls)
write_loop "WAITING FOR RUN"
: >"$STUB_LOG"; STUB_SET_STATUS="WAITING FOR PLAN" tick
grep -q STUB_GH_RUN_VIEW "$STUB_LOG" && fail "queried runs outside WAITING FOR CI"
pass "gate inert outside WAITING FOR CI"
EOF
chmod +x "$SCRATCH/harness/t5_ci_gate.sh"
```

- [ ] **Step 3: Run it to verify it fails**

Run: `bash "$SCRATCH/harness/t5_ci_gate.sh"`
Expected: `superagent_ci_runs: command not found`.

- [ ] **Step 4: Append `superagent_ci_runs` to `scripts/_common.sh`** (after `superagent_pending_answer`)

```bash

# superagent_ci_runs <loop-file> — the GitHub Actions run ids recorded under the
# frontmatter's `ci_wait:` → `runs:` while the loop is WAITING FOR CI, as a
# space-separated list. Accepts the canonical inline form `runs: [1, 2]` and a
# `- id` list. Only the frontmatter is read; only the runs: entry inside the
# ci_wait: block is scanned (pr:/iteration: numbers never leak in). Empty
# output, rc 0 when there are none, the file is unreadable, or the arg is empty.
superagent_ci_runs() {
  local f="${1:-}"
  [[ -n "$f" ]] || return 0
  { awk '
      NR==1 && /^---/ { fm=1; next }
      fm && /^---/ { exit }
      !fm { next }
      /^ci_wait:/ { blk=1; next }
      blk && /^[^[:space:]]/ { blk=0 }
      !blk { next }
      /^[[:space:]]+runs:/ { inruns=1; sub(/^[[:space:]]+runs:/, ""); print; next }
      inruns && /^[[:space:]]+-/ { print; next }
      inruns { inruns=0 }
    ' "$f" 2>/dev/null | grep -oE '[0-9]{5,}' | tr '\n' ' ' | sed 's/ $//'; } || true
}
```

- [ ] **Step 5: Insert the CI gate in `scripts/superagent-tick.sh`**

Immediately after `ensure_gh_auth || exit 4` (before any `if [[ "$HARNESS" == cursor ]]` / `SKILLS_ROOT` resolution is fine — place it right after the preflight line):

```bash
# --- WAITING FOR CI gate ------------------------------------------------------
# A loop parked on CI resumes only when every run in ci_wait.runs is terminal.
# The skill's external branch does exactly one status query and exits otherwise
# — but that query used to cost a full CLI session per interval for the whole
# 60–120 min lane. Do the same query here in bash (gh is authenticated by the
# preflight above): any run not `completed` → one log line, exit 0, no session.
# Fail-OPEN on doubt (no parseable ids, gh error): fall through to the session,
# which is exactly today's behaviour — the gate must never strand a loop.
# Opt out with SUPER_CI_GATE=false.
if [[ "${SUPER_CI_GATE:-true}" == true && \
      "$(superagent_loop_status "$LOOP_FILE")" == "WAITING FOR CI" ]]; then
  ci_runs="$(superagent_ci_runs "$LOOP_FILE")"
  if [[ -z "$ci_runs" ]]; then
    echo "=== $(ts) superagent-tick: WAITING FOR CI — no run ids in ci_wait — letting the session handle it ===" >>"$LOG_FILE"
  else
    ci_total=0; ci_running=0; ci_failed=""
    for ci_id in $ci_runs; do
      ci_total=$((ci_total + 1))
      ci_state="$( (cd "$REPO" && gh run view "$ci_id" --json status --jq .status) 2>>"$LOG_FILE" )" || { ci_failed="$ci_id"; break; }
      [[ "$ci_state" == completed ]] || ci_running=$((ci_running + 1))
    done
    if [[ -n "$ci_failed" ]]; then
      echo "=== $(ts) superagent-tick: WAITING FOR CI — gh query failed for run ${ci_failed} — letting the session handle it ===" >>"$LOG_FILE"
    elif [[ "$ci_running" -gt 0 ]]; then
      echo "=== $(ts) superagent-tick: WAITING FOR CI — ${ci_running}/${ci_total} run(s) still running — skipping the session (SUPER_CI_GATE) ===" >>"$LOG_FILE"
      exit 0
    else
      echo "=== $(ts) superagent-tick: WAITING FOR CI — all ${ci_total} run(s) terminal — running the resume session ===" >>"$LOG_FILE"
    fi
  fi
fi
```

- [ ] **Step 6: `templates/superenv.default`** — after the `SUPER_INPUT_GATE` line:

```bash
SUPER_CI_GATE=true                      # external driver: a tick that finds WAITING FOR CI checks ci_wait.runs with `gh run view` in bash and exits without a session while any run is still running; false = launch the session every interval as before
```

- [ ] **Step 7: Run to green + regressions**

Run: `bash "$SCRATCH/harness/t5_ci_gate.sh" && bash "$SCRATCH/harness/t2_gate.sh" && bash "$SCRATCH/harness/t3_notify.sh" && bash -n scripts/superagent-tick.sh scripts/_common.sh`
Expected: 10 + 5 + 10 `PASS:` lines (t3 currently has 10 checks), exit 0.

- [ ] **Step 8: Commit**

```bash
git add scripts/_common.sh scripts/superagent-tick.sh templates/superenv.default
git commit -m "feat(tick): bash CI gate — no session while ci_wait.runs are still running (SUPER_CI_GATE)"
```

---

### Task 2: `answer.sh` lock hardening + `status.sh` INPUT column + README facts

**Files:**
- Modify: `scripts/answer.sh` (header comment; mkdir-failure branch; under-lock skip path)
- Modify: `scripts/status.sh` (`_collect`, JSON, drill-in, table)
- Modify: `scripts/README.md:98-107` (`.superenv` layer paragraph)
- Modify: `$SCRATCH/harness/setup.sh` (stub `launchctl`) — throwaway
- Modify: `$SCRATCH/harness/t4_answer.sh` (append 3 checks); Create: `$SCRATCH/harness/t6_status.sh` — throwaway

**Interfaces:**
- `answer.sh`: on the under-lock "already recorded" path the lock is released before `superagent_kick_tick`; a held lock whose `owner` PID is dead is reaped (log line `answer: reaped stale lock (owner pid <pid> is dead)`) and acquisition retried once; a live owner or an ownerless lock still exits 4.
- `status.sh`: `pending` ∈ {0,1,2} (2 = answer recorded); table INPUT prints `YES` / `ans` / `-`; JSON adds `"answer_recorded":true|false`; drill-in prints `Answer recorded: <text>` when set.

- [ ] **Step 1: Stub `launchctl` + failing tests**

Append to `$SCRATCH/harness/setup.sh`:

```bash
# stub launchctl: `kickstart` records whether the loop's lock dir exists at kick time; `print` = not loaded
cat >"$H/bin/launchctl" <<'S'
#!/usr/bin/env bash
case "$1" in
  kickstart) d="$(dirname "$LOOP_FILE")/.$(basename "$LOOP_FILE").lockd"
             echo "KICK lock_present=$([[ -d "$d" ]] && echo yes || echo no)" >>"$STUB_LOG"; exit 0 ;;
  print)     exit 113 ;;
  *)         exit 0 ;;
esac
S
chmod +x "$H/bin/launchctl"
```

Append to `$SCRATCH/harness/t4_answer.sh`:

```bash
# 10. under-lock skip path releases the lock BEFORE the kick
write_loop "WAITING FOR INPUT" "postgres"
: >"$STUB_LOG"; rc=0; "$A" g sqlite >/dev/null 2>&1 || rc=$?
[[ $rc -eq 0 ]] || fail "skip-path rc=$rc"
grep -q "KICK lock_present=no" "$STUB_LOG" || fail "lock still held at kick: $(cat "$STUB_LOG")"
pass "skip path kicks with the lock released"

# 11. dead-owner lock is reaped and the answer recorded
write_loop "WAITING FOR INPUT"
L="$(dirname "$LOOP_FILE")/.$(basename "$LOOP_FILE").lockd"; mkdir "$L"; echo 2147483000 >"$L/owner"
rc=0; out="$("$A" --no-kick g postgres 2>&1)" || rc=$?
[[ $rc -eq 0 ]] || fail "dead-owner rc=$rc: $out"
grep -q "reaped stale lock (owner pid 2147483000 is dead)" <<<"$out" || fail "no reap message: $out"
grep -q '^answer: postgres$' "$LOOP_FILE" || fail "answer not written after reap"
[[ ! -d "$L" ]] || fail "lock leaked after reap"
pass "dead-owner lock reaped"

# 12. live-owner lock still refused (rc 4), ownerless lock refused (rc 4)
write_loop "WAITING FOR INPUT"
mkdir "$L"; echo $$ >"$L/owner"; rc=0; "$A" --no-kick g postgres >/dev/null 2>&1 || rc=$?
[[ $rc -eq 4 ]] || fail "live owner rc=$rc"; rm -rf "$L"
mkdir "$L"; rc=0; "$A" --no-kick g postgres >/dev/null 2>&1 || rc=$?
[[ $rc -eq 4 ]] || fail "ownerless rc=$rc"; rm -rf "$L"
pass "live/ownerless lock → rc 4"
```

Create `$SCRATCH/harness/t6_status.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/setup.sh"
S="$PLUGIN/scripts/status.sh"
write_loop "WAITING FOR INPUT"
"$S" | grep -E '^g +WAITING FOR INPUT' | grep -q ' YES *$' || fail "unanswered INPUT column: $("$S" | grep '^g ')"
"$S" --json | grep -q '"pending_input":1' && "$S" --json | grep -q '"answer_recorded":false' || fail "json unanswered"
pass "unanswered → YES / answer_recorded=false"
write_loop "WAITING FOR INPUT" "postgres"
"$S" | grep -E '^g +WAITING FOR INPUT' | grep -q ' ans *$' || fail "answered INPUT column: $("$S" | grep '^g ')"
"$S" --json | grep -q '"answer_recorded":true' || fail "json answered"
"$S" g | grep -q 'Answer recorded: postgres' || fail "drill-in answer line"
pass "answered → ans / answer_recorded=true / drill-in shows it"
write_loop "WAITING FOR RUN"
"$S" | grep -E '^g +WAITING FOR RUN' | grep -q ' - *$' || fail "ready INPUT column"
pass "ready → -"
```
`chmod +x "$SCRATCH/harness/t6_status.sh"`

- [ ] **Step 2: Run to verify failure**

Run: `bash "$SCRATCH/harness/t4_answer.sh"; bash "$SCRATCH/harness/t6_status.sh"`
Expected: t4 fails at check 10 (`lock still held at kick`); t6 fails at `answered INPUT column`.

- [ ] **Step 3: `scripts/answer.sh`**

(a) Header comment: replace `# The flags are accepted in any position before the answer text:` with `# The flags are accepted in any position (before or after the slug/answer):`.

(b) Replace the mkdir-failure block:

```bash
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "answer: a tick holds the lock ($LOCK_DIR) — retry when it finishes (status.sh $SLUG); if no tick is running, the lock is stale — force-stop.sh --slug $SLUG reaps it" >&2
    exit 4
  fi
```
with:

```bash
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    # superloop L3: a lock whose recorded owner PID is dead belongs to a crashed
    # tick — reap it and retry once. A live owner, or no owner file at all (an
    # older/hand-made lock — only age-stealable, which is a tick's job), is a
    # real in-flight tick: refuse.
    lock_owner="$(cat "$LOCK_DIR/owner" 2>/dev/null || true)"
    if [[ -n "$lock_owner" ]] && ! kill -0 "$lock_owner" 2>/dev/null; then
      echo "answer: reaped stale lock (owner pid $lock_owner is dead)" >&2
      rm -rf "$LOCK_DIR"
    fi
    if ! mkdir "$LOCK_DIR" 2>/dev/null; then
      echo "answer: a tick holds the lock ($LOCK_DIR) — retry when it finishes (status.sh $SLUG); if no tick is running and the lock is old, force-stop.sh --slug $SLUG reaps it" >&2
      exit 4
    fi
  fi
```

(c) Under-lock skip path: after the second `if existing=… && [[ "$REPLACE" != true ]]; then … skip_write=true; fi` inside the lock section, add so the lock never outlives the decision not to write:

```bash
  if [[ "$skip_write" == true ]]; then
    rm -rf "$LOCK_DIR"; trap - EXIT TERM INT   # nothing to write — never kick while holding the lock
  fi
```

- [ ] **Step 4: `scripts/status.sh`**

In `_collect`, replace `[[ "$status" == "WAITING FOR INPUT" ]] && pending=1` with:

```bash
    answer_recorded=false
    if [[ "$status" == "WAITING FOR INPUT" ]]; then
      if superagent_pending_answer "$LOOP_FILE" >/dev/null; then pending=2; answer_recorded=true; else pending=1; fi
    fi
```
Also initialise `answer_recorded=false` on the `status=""; iteration=""; pending=0; …` line.

JSON: change `"pending_input":%s,"done":%s` to `"pending_input":%s,"answer_recorded":%s,"done":%s` and add `"$answer_recorded"` after `"$pending"` in the argument list.

Drill-in: after the `if [[ $pending == 1 && $exists == 1 ]]; then … fi` pending-decision block, change its guard to `$pending != 0` and append inside, after the awk:

```bash
    if [[ $pending == 2 ]]; then
      echo "Answer recorded: $(superagent_pending_answer "$LOOP_FILE")  (next fire resumes; kick now: $SCRIPT_DIR/answer.sh $ONE --replace \"<option>\" or wait)"
    fi
```

Table: replace `"$([[ $pending == 1 ]] && echo YES || echo -)"` with `"$(case $pending in 1) echo YES;; 2) echo ans;; *) echo -;; esac)"`. Update the header comment's `input (parked on WAITING FOR INPUT?)` to `input (YES = parked, needs you; ans = answer recorded, next fire resumes)`.

- [ ] **Step 5: `scripts/README.md` `.superenv` paragraph**

Replace `(the plugin's shipped defaults, 28 \`SUPER_*\` keys covering models, paths, loop tuning, CI policy, and review protocol)` with `(the plugin's shipped defaults — every \`SUPER_*\` key with its default and a one-line description lives there; it is the reference)`, and replace `so \`SUPER_TICK_INTERVAL\` (default \`30m\`) and \`SUPER_MODEL_SUPERVISOR\` (default \`inherit\`, which the tick treats as \`opus\`) are available` with `so \`SUPER_TICK_INTERVAL\` and \`SUPER_MODEL_SUPERVISOR\` (defaults in the template) are available`.

- [ ] **Step 6: Run to green**

Run: `bash "$SCRATCH/harness/t4_answer.sh" && bash "$SCRATCH/harness/t6_status.sh" && bash -n scripts/answer.sh scripts/status.sh`
Expected: 12 + 3 `PASS:` lines, exit 0.

- [ ] **Step 7: Commit**

```bash
git add scripts/answer.sh scripts/status.sh scripts/README.md
git commit -m "fix(scripts): answer.sh releases the lock before kicking and reaps dead-owner locks; status.sh INPUT shows ans when answered; README cites the superenv template"
```

---

### Task 3: Skills, docs, builds, CHANGELOG, 0.4.9

**Files:**
- Modify: `skills/superagent/SKILL.md` (Parking step 1 ~line 232; `### WAITING FOR CI` external bullet ~line 358)
- Modify: `skills/superagent-monitor/SKILL.md` (`STATUS=WAITING FOR CI` bullet ~line 69; `INPUT=YES` bullet ~line 63)
- Modify: `scripts/README.md` (answering section end ~line 322: add the CI-gate sentence)
- Modify: `README.md` (~line 203 `WAITING FOR CI` is a durable parked state…)
- Modify: `CHANGELOG.md`, `.claude-plugin/plugin.json`; regenerate `cursor/`, `codex/`

- [ ] **Step 1: `skills/superagent/SKILL.md`**

Parking step 1: after `— \`runs:\` (all run ids),` insert `written as an inline list of GitHub Actions run ids, e.g. \`runs: [123456, 234567]\` (the shipped wrapper's CI gate parses this block),`.

`### WAITING FOR CI` external bullet: after `this is the only network call this tick).` insert a new sub-bullet before `- Any run still not …`:

```markdown
  - (Loops driven by the shipped `scripts/` wrapper normally never reach this branch while a run is
    still in progress: `superagent-tick.sh` performs the same `gh run view` check in bash before
    launching the session and exits 0 while any run is not `completed` — `SUPER_CI_GATE`, default
    on. A session that does land here with runs still running means the gate was off or `gh`
    failed in the wrapper; do the single query as written.)
```

- [ ] **Step 2: `skills/superagent-monitor/SKILL.md`**

`STATUS=WAITING FOR CI` bullet: replace `external ticks do one cheap status check each and no-op until the runs are terminal.` with `the wrapper checks the runs with \`gh run view\` in bash each interval and launches no session until every run is terminal (\`SUPER_CI_GATE\`).`

`INPUT=YES` bullet: append: `\`INPUT=ans\` means an answer is already recorded and the next fire (or \`answer.sh\`'s kick) resumes — nothing to do.`

- [ ] **Step 3: READMEs**

`scripts/README.md`: after the paragraph beginning `While a loop waits, scheduled fires cost nothing:` add:

```markdown
The same holds for `WAITING FOR CI`: the wrapper queries each run in the loop file's `ci_wait.runs`
with `gh run view --json status` and launches no session until all are `completed`
(`SUPER_CI_GATE=true`). If the ids cannot be parsed or `gh` fails, it falls through to the session
(the pre-0.4.9 behaviour) rather than stalling.
```

`README.md`: after `\`WAITING FOR CI\` is a durable **parked** state:` sentence region (line ~203-205), append one sentence: `On the shipped external driver, parked fires are free — the wrapper checks the recorded run ids in bash and starts no session until they are terminal.`

- [ ] **Step 4: CHANGELOG + version + builds**

Insert above `## 0.4.8`:

```markdown
## 0.4.9 — 2026-08-28

- **`WAITING FOR CI` is now a free park (`SUPER_CI_GATE=true`).** The other parked state still
  launched a full CLI session per interval whose only job was one status query. `superagent-tick.sh`
  now parses `ci_wait.runs` from the loop-file frontmatter (`superagent_ci_runs`; inline
  `runs: [id, id]` or a `- id` list) and runs `gh run view <id> --json status` for each after the gh
  preflight; any run not `completed` → one log line, exit 0, no session. Fail-open: unparseable ids
  or a `gh` error fall through to the session (the old behaviour) — the gate can never strand a loop.
  The skill now prescribes the inline-list form as canonical.
- **`answer.sh`:** releases the lock *before* kicking on the "answer already recorded" path (the
  kicked tick used to find the lock held and exit, costing an interval); reaps a lock whose `owner`
  PID is dead (superloop L3) instead of refusing forever.
- **`status.sh`:** `INPUT` column is `YES` (parked, needs you) / `ans` (answer recorded, next fire
  resumes) / `-`; JSON gains `answer_recorded`; drill-in prints the recorded answer.
- `scripts/README.md`: the `.superenv` paragraph cites `templates/superenv.default` instead of stale
  key-count/default values.
```

Then:
```bash
sed -i '' 's/"version": "0.4.8"/"version": "0.4.9"/' .claude-plugin/plugin.json
scripts/build-cursor-skills.sh && scripts/build-codex-skills.sh && scripts/build-cursor-skills.sh --check && scripts/build-codex-skills.sh --check
grep -n '"version"' .claude-plugin/plugin.json cursor/.cursor-plugin/plugin.json codex/plugins/superagent/.codex-plugin/plugin.json
```
Expected: both checks clean; all three `0.4.9`.

- [ ] **Step 5: Full re-verify**

```bash
bash -n scripts/_common.sh scripts/superagent-tick.sh scripts/answer.sh scripts/status.sh
for t in t1_helpers t2_gate t3_notify t4_answer t5_ci_gate t6_status; do bash "$SCRATCH/harness/$t.sh" || exit 1; done
```
Expected: 8+5+10+12+10+3 = 48 `PASS:` lines, no `FAIL:`.

- [ ] **Step 6: Commit**

```bash
git add README.md scripts/README.md skills/ cursor/ codex/ CHANGELOG.md .claude-plugin/plugin.json
git commit -m "docs: CI gate + status/answer hardening across skills and runbooks; bump to 0.4.9"
```

## Self-review
- Spec 1 → Task 1 (+ skill canonical form, Task 3); Spec 2 → Task 2 (a,b,c); Spec 3 → Task 2 Step 4; Spec 4 → Task 2 Step 5; docs/changelog/version → Task 3.
- Names: `superagent_ci_runs`, `SUPER_CI_GATE`, log-line texts, `pending`∈{0,1,2}, `answer_recorded`, reap message — consistent between code, tests, docs, changelog.
- No placeholders; every code step complete.

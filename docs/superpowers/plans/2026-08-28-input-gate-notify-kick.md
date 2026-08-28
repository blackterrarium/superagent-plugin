# WAITING FOR INPUT Gate / Notify / Kick Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the external driver from burning a full LLM session per interval while a loop is parked on `WAITING FOR INPUT`; notify the operator once when it parks (or finishes); let the operator answer and resume the loop immediately with one command.

**Architecture:** Three additive changes to the shipped Bash driver, no skill-logic change. (1) `superagent-tick.sh` gains a pre-session gate that exits 0 when the loop file is `WAITING FOR INPUT` with no `answer:` under `## Pending decision`. (2) The wrapper snapshots `status` before the session and fires `superagent_notify` on a transition into `WAITING FOR INPUT` / `DONE` (`SUPER_NOTIFY_CMD`, else `osascript`/`notify-send`). (3) New `scripts/answer.sh <slug> <answer…>` writes the answer under the L3 lock and kicks a tick via a new `superagent_kick_tick` helper shared with `launch.sh`. Docs, skills, generated builds, CHANGELOG, and version follow.

**Tech Stack:** Bash (`set -euo pipefail`), awk/sed, launchd/systemd, markdown skills with build markers; no test framework — verification is a throwaway stub-CLI harness in the scratchpad (same approach as PRs #16/#19/#20), plus `scripts/build-*-skills.sh --check`.

**Spec:** `docs/superpowers/specs/2026-08-28-input-gate-notify-kick-design.md` (read it first).

## Global Constraints

- Work on a feature branch off `main` (`input-gate-notify-kick`); commit per task; PR to `main` at the end. Never commit directly to `main`.
- `set -euo pipefail` in every executable script; `_common.sh` is SOURCED and must stay `set`-clean — every helper must be safe under a caller's `set -e`/`pipefail` (a `$(pipeline)` that can legitimately produce no output must end in `|| true`).
- `cursor/` and `codex/` are GENERATED — never hand-edit; edit canonical skills, run `scripts/build-cursor-skills.sh` and `scripts/build-codex-skills.sh`, commit the regenerated trees. Both `--check` modes must pass after any skill edit.
- The version lives only in `.claude-plugin/plugin.json` + `CHANGELOG.md`; the build scripts copy it into the two generated `plugin.json` files.
- New `.superenv` keys (exact): `SUPER_INPUT_GATE=true`, `SUPER_NOTIFY_CMD=` (empty). No new tick exit codes — the gate exits `0`.
- Scratchpad for all throwaway files: `/private/tmp/claude-501/-Users-eugene-src-superagent-plugin/506813a2-f910-4cad-adea-baa8834a5d16/scratchpad` (referred to as `$SCRATCH` below).
- The stub harness must keep `$HOME/.local/bin` in `PATH` so `_superagent_augment_path` does not prepend `/opt/homebrew/bin` ahead of the stub `claude`/`gh` (it only augments when `~/.local/bin` is absent).
- The harness must set `XDG_CONFIG_HOME=$SCRATCH/harness/xdg` so no test touches the real `~/.config/superagent/`.
- Loop-file `answer:` detection is scoped to the `## Pending decision` section only (an `answer:` line under `## Decisions` must NOT count).

---

### Task 1: Stub harness + loop-status helpers in `_common.sh`

**Files:**
- Create: `$SCRATCH/harness/setup.sh` (throwaway, not committed)
- Create: `$SCRATCH/harness/t1_helpers.sh` (throwaway, not committed)
- Modify: `scripts/_common.sh` (append a new section after `load_superenv`)

**Interfaces:**
- Produces (in `_common.sh`):
  - `superagent_loop_status <loop-file>` → echoes the trimmed frontmatter `status:` value, empty if unreadable; always rc 0.
  - `superagent_pending_section <loop-file>` → echoes the body lines of `## Pending decision` (heading excluded, up to the next `## ` heading); always rc 0.
  - `superagent_pending_answer <loop-file>` → echoes the first non-empty `answer: <x>` value found INSIDE `## Pending decision`; rc 1 (no output) if none.
- Consumed by Tasks 2, 3, 4.

- [ ] **Step 1: Create the shared stub harness**

```bash
SCRATCH=/private/tmp/claude-501/-Users-eugene-src-superagent-plugin/506813a2-f910-4cad-adea-baa8834a5d16/scratchpad
mkdir -p "$SCRATCH/harness/bin" "$SCRATCH/harness/xdg/superagent"
cat >"$SCRATCH/harness/setup.sh" <<'EOF'
# source me. Builds a fresh fixture repo + stub CLIs for one test run.
SCRATCH=/private/tmp/claude-501/-Users-eugene-src-superagent-plugin/506813a2-f910-4cad-adea-baa8834a5d16/scratchpad
H="$SCRATCH/harness"
PLUGIN=/Users/eugene/src/superagent-plugin
export XDG_CONFIG_HOME="$H/xdg"
export PATH="$H/bin:$HOME/.local/bin:$PATH"
export STUB_LOG="$H/stub.log"; : >"$STUB_LOG"
rm -rf "$H/repo"; mkdir -p "$H/repo/vault/g/loop-status"
( cd "$H/repo" && git init -q && git commit -q --allow-empty -m init )
export REPO="$H/repo"
export LOOP_FILE="$H/repo/vault/g/loop-status/2026-08-28-g.md"
export LOG_FILE="$H/tick.log"; : >"$LOG_FILE"
export SUPERAGENT_SLUG=g
printf 'REPO=%s\nSUPERAGENT_SCRIPT_DIR=%s/scripts\nLOOP_FILE=%s\nSUPERAGENT_SLUG=g\nSUPER_HARNESS=claude\n' \
  "$REPO" "$PLUGIN" "$LOOP_FILE" >"$XDG_CONFIG_HOME/superagent/g.env"
# stub claude: logs argv; optionally rewrites status; exits STUB_RC
cat >"$H/bin/claude" <<'S'
#!/usr/bin/env bash
echo "STUB_CLAUDE_CALLED $*" >>"$STUB_LOG"
if [[ -n "${STUB_SET_STATUS:-}" ]]; then
  t="$(mktemp)"; sed "s/^status:.*/status: ${STUB_SET_STATUS}/" "$LOOP_FILE" >"$t" && cat "$t" >"$LOOP_FILE" && rm -f "$t"
fi
exit "${STUB_RC:-0}"
S
cat >"$H/bin/gh" <<'S'
#!/usr/bin/env bash
case "$1 ${2:-}" in
  "auth status") exit 0 ;;
  "auth token")  echo stub-token ;;
  *) exit 0 ;;
esac
S
chmod +x "$H/bin/claude" "$H/bin/gh"
# write_loop <status> [with_answer]   — fixture loop file
write_loop() {
  local st="$1" ans="${2:-}"
  {
    cat <<L
---
master_plan: vault/g/master-plans/PLAN.md
status: $st
plan_exhausted: false
prior_status: WAITING FOR RUN
driver: external
cron_id:
created: 2026-08-28
iteration: 3
session_skill_count: 0
---

## Pending decision
Question: which datastore? Options: (a) postgres (b) sqlite.
Write your choice as \`answer: <option>\` under this block.
L
    [[ -n "$ans" ]] && echo "answer: $ans"
    cat <<L

## Decisions
answer: stale-decoy-must-not-count
- 2026-08-27 user-resolved: keep flat branches

## Iteration log
- 3: superrun → PR #1 merged
L
  } >"$LOOP_FILE"
}
tick() { "$PLUGIN/scripts/superagent-tick.sh"; }
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }
EOF
echo written
```

- [ ] **Step 2: Write the failing helper test**

```bash
cat >"$SCRATCH/harness/t1_helpers.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/setup.sh"
. "$PLUGIN/scripts/_common.sh"
write_loop "WAITING FOR INPUT"
[[ "$(superagent_loop_status "$LOOP_FILE")" == "WAITING FOR INPUT" ]] || fail "loop_status"
pass "loop_status reads frontmatter"
superagent_pending_section "$LOOP_FILE" | grep -q "which datastore" || fail "pending_section body"
superagent_pending_section "$LOOP_FILE" | grep -q "stale-decoy" && fail "pending_section leaked ## Decisions"
pass "pending_section is scoped"
if superagent_pending_answer "$LOOP_FILE" >/dev/null; then fail "answer found when none (decoy counted)"; fi
pass "no answer → rc 1 (decoy ignored)"
write_loop "WAITING FOR INPUT" "postgres"
[[ "$(superagent_pending_answer "$LOOP_FILE")" == "postgres" ]] || fail "answer text"
pass "answer text extracted"
[[ -z "$(superagent_loop_status /nonexistent)" ]] || fail "missing file should be empty"
pass "missing file safe under set -e"
EOF
chmod +x "$SCRATCH/harness/t1_helpers.sh"
```

- [ ] **Step 3: Run it to verify it fails**

Run: `bash "$SCRATCH/harness/t1_helpers.sh"`
Expected: `superagent_loop_status: command not found` (exit non-zero).

- [ ] **Step 4: Append the helpers to `scripts/_common.sh`**

Append after the `load_superenv` function (end of file):

```bash

# ---------------------------------------------------------------------------
# Loop-status file readers — shared by the tick wrapper, answer.sh, status.sh.
# All are safe under a caller's `set -euo pipefail`: a missing/unreadable file
# or an absent field yields empty output, never a fatal rc (except where the
# rc IS the answer — superagent_pending_answer).
# ---------------------------------------------------------------------------

# superagent_loop_status <loop-file> — trimmed frontmatter `status:` value.
superagent_loop_status() {
  { sed -n 's/^status:[[:space:]]*//p' "${1:?loop-file}" 2>/dev/null | head -1 | sed 's/[[:space:]]*$//'; } || true
}

# superagent_pending_section <loop-file> — body of `## Pending decision`
# (heading excluded, up to the next `## ` heading).
superagent_pending_section() {
  awk '/^## Pending decision/{f=1; next} /^## /{f=0} f' "${1:?loop-file}" 2>/dev/null || true
}

# superagent_pending_answer <loop-file> — the first non-empty `answer: <x>` value
# INSIDE ## Pending decision (an answer: line elsewhere, e.g. under ## Decisions,
# never counts). Echoes the value and returns 0; returns 1 with no output if none.
superagent_pending_answer() {
  local a
  a="$({ superagent_pending_section "${1:?loop-file}" \
        | sed -n 's/^[[:space:]]*answer:[[:space:]]*//p' | sed 's/[[:space:]]*$//' \
        | grep -v '^$' | head -1; } || true)"
  [[ -n "$a" ]] || return 1
  echo "$a"
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `bash "$SCRATCH/harness/t1_helpers.sh"`
Expected: five `PASS:` lines, exit 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/_common.sh
git commit -m "feat(_common): loop-status readers (status, pending section, pending answer)"
```

---

### Task 2: Pre-session `WAITING FOR INPUT` gate in `superagent-tick.sh`

**Files:**
- Modify: `scripts/superagent-tick.sh` (move `ts()` near the top; insert the gate right after `load_superenv "$REPO"`, before `HARNESS=`)
- Modify: `templates/superenv.default` (add `SUPER_INPUT_GATE`)
- Create: `$SCRATCH/harness/t2_gate.sh` (throwaway)

**Interfaces:**
- Consumes: `superagent_loop_status`, `superagent_pending_answer` (Task 1).
- Produces: gate behavior — `WAITING FOR INPUT` + no answer → single log line `superagent-tick: loop is WAITING FOR INPUT with no answer — skipping the session (SUPER_INPUT_GATE)` and `exit 0`, **no CLI launched**. `SUPER_INPUT_GATE=false` restores today's behavior. Referenced by docs in Task 5.

- [ ] **Step 1: Write the failing gate test**

```bash
cat >"$SCRATCH/harness/t2_gate.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/setup.sh"

# 1. parked, no answer → no session, exit 0, log line
write_loop "WAITING FOR INPUT"
tick; rc=$?
[[ $rc -eq 0 ]] || fail "gate rc=$rc"
grep -q STUB_CLAUDE_CALLED "$STUB_LOG" && fail "gate launched a session"
grep -q "skipping the session (SUPER_INPUT_GATE)" "$LOG_FILE" || fail "gate log line missing"
pass "parked+unanswered → session skipped"

# 2. parked, answer present → session runs
: >"$STUB_LOG"; write_loop "WAITING FOR INPUT" "postgres"
STUB_SET_STATUS="WAITING FOR RUN" tick
grep -q STUB_CLAUDE_CALLED "$STUB_LOG" || fail "answered loop did not run a session"
pass "parked+answered → session runs"

# 3. decoy answer under ## Decisions only → still skipped
: >"$STUB_LOG"; write_loop "WAITING FOR INPUT"
tick
grep -q STUB_CLAUDE_CALLED "$STUB_LOG" && fail "decoy answer counted"
pass "decoy under ## Decisions ignored"

# 4. gate disabled → session runs even unanswered
: >"$STUB_LOG"; write_loop "WAITING FOR INPUT"
SUPER_INPUT_GATE=false tick
grep -q STUB_CLAUDE_CALLED "$STUB_LOG" || fail "SUPER_INPUT_GATE=false did not run"
pass "SUPER_INPUT_GATE=false runs the session"

# 5. ready state untouched
: >"$STUB_LOG"; write_loop "WAITING FOR RUN"
STUB_SET_STATUS="WAITING FOR PLAN" tick
grep -q STUB_CLAUDE_CALLED "$STUB_LOG" || fail "ready state gated"
pass "ready state runs the session"
EOF
chmod +x "$SCRATCH/harness/t2_gate.sh"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash "$SCRATCH/harness/t2_gate.sh"`
Expected: `FAIL: gate launched a session` (today every fire launches the stub).

- [ ] **Step 3: Move `ts()` to the top of the wrapper**

Delete the line `ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }` (currently just after the `PROMPT=` block) and insert it immediately after `set -euo pipefail` near line 17:

```bash
set -euo pipefail
ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
```

- [ ] **Step 4: Insert the gate**

Immediately after `load_superenv "$REPO"` and BEFORE `HARNESS="$(superagent_harness)" || exit 6` (so a parked loop skips the gh/CLI preflight too — `gh auth status` is a network call):

```bash
# --- WAITING FOR INPUT gate ---------------------------------------------------
# A loop parked on WAITING FOR INPUT resumes only when a human writes
# `answer: <option>` under ## Pending decision. Until then every scheduler fire
# used to launch a full paid CLI session that read the file, found no answer, and
# exited — the same no-op-per-interval waste #18 fixed for DONE. Poll the file in
# bash instead: no answer → log one line, exit 0 (a legal clean no-op under the
# L2 teardown invariant), no session. The moment an answer appears the next fire
# runs the session as before (or answer.sh kicks one immediately). Runs BEFORE
# the gh/CLI preflight so a parked loop costs nothing at all. Opt out with
# SUPER_INPUT_GATE=false.
if [[ "${SUPER_INPUT_GATE:-true}" == true && \
      "$(superagent_loop_status "$LOOP_FILE")" == "WAITING FOR INPUT" ]] && \
   ! superagent_pending_answer "$LOOP_FILE" >/dev/null; then
  echo "=== $(ts) superagent-tick: loop is WAITING FOR INPUT with no answer — skipping the session (SUPER_INPUT_GATE). Answer + resume now: $SCRIPT_DIR/answer.sh ${SUPERAGENT_SLUG:-<slug>} \"<option>\" ===" >>"$LOG_FILE"
  exit 0
fi
```

- [ ] **Step 5: Add the knob to `templates/superenv.default`**

Under `# ── Loop tuning`, after the `SUPER_AUTO_DISARM_ON_DONE` line:

```bash
SUPER_INPUT_GATE=true                   # external driver: a tick that finds WAITING FOR INPUT with no `answer:` exits without launching a session (bash-only poll); false = launch the session every interval as before
```

- [ ] **Step 6: Run the gate test to verify it passes**

Run: `bash "$SCRATCH/harness/t2_gate.sh"`
Expected: five `PASS:` lines, exit 0.

- [ ] **Step 7: Commit**

```bash
git add scripts/superagent-tick.sh templates/superenv.default
git commit -m "feat(tick): bash gate skips the session while WAITING FOR INPUT is unanswered (SUPER_INPUT_GATE)"
```

---

### Task 3: Transition notifications (`superagent_notify` + wrapper hook)

**Files:**
- Modify: `scripts/_common.sh` (append `superagent_notify`)
- Modify: `scripts/superagent-tick.sh` (snapshot `status_before` before the session; notify block after the stranded-transient block, before the DONE self-disarm)
- Modify: `templates/superenv.default` (add `SUPER_NOTIFY_CMD`)
- Create: `$SCRATCH/harness/t3_notify.sh` (throwaway)

**Interfaces:**
- Consumes: `superagent_loop_status`, `superagent_pending_section` (Task 1).
- Produces: `superagent_notify <event> <slug> <loop-file>`; `event` ∈ `waiting-for-input | done`. Runs `SUPER_NOTIFY_CMD` via `bash -c` with `SUPERAGENT_EVENT`, `SUPERAGENT_SLUG`, `LOOP_FILE`, `SUPERAGENT_TITLE`, `SUPERAGENT_BODY` in its environment; else `osascript` (Darwin) / `notify-send`; always returns 0; echoes `superagent: notified event=<event> slug=<slug>`. Wrapper fires it only when `status_before != status_after` and `status_after` is one of the two events.

- [ ] **Step 1: Write the failing notify test**

```bash
cat >"$SCRATCH/harness/t3_notify.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/setup.sh"
NOTE="$H/notify.out"
export SUPER_NOTIFY_CMD='printf "%s|%s|%s|%s\n" "$SUPERAGENT_EVENT" "$SUPERAGENT_SLUG" "$SUPERAGENT_TITLE" "$SUPERAGENT_BODY" >>'"$NOTE"
export SUPER_AUTO_DISARM_ON_DONE=false   # keep the DONE test from calling uninstall-timer on this host

# 1. RUNNING→WAITING FOR INPUT transition fires exactly once with the question in the body
: >"$NOTE"; write_loop "WAITING FOR RUN"
STUB_SET_STATUS="WAITING FOR INPUT" tick
[[ "$(wc -l <"$NOTE")" -eq 1 ]] || fail "expected 1 notification, got $(wc -l <"$NOTE")"
grep -q '^waiting-for-input|g|' "$NOTE" || fail "event/slug wrong: $(cat "$NOTE")"
grep -q 'which datastore' "$NOTE" || fail "body lacks the pending question"
pass "transition → one waiting-for-input notification"

# 2. a later fire on the already-parked loop (gate path) does NOT re-notify
: >"$NOTE"; tick
[[ ! -s "$NOTE" ]] || fail "re-notified on a gated fire"
pass "gated fire is silent"

# 3. gate off, still parked, session runs, status unchanged → still no notification
: >"$NOTE"; SUPER_INPUT_GATE=false tick
[[ ! -s "$NOTE" ]] || fail "re-notified without a transition"
pass "no transition → silent"

# 4. →DONE fires the done event
: >"$NOTE"; write_loop "WAITING FOR RUN"
STUB_SET_STATUS="DONE" tick
grep -q '^done|g|' "$NOTE" || fail "done event missing: $(cat "$NOTE")"
pass "transition → done notification"

# 5. a failing SUPER_NOTIFY_CMD never fails the tick
write_loop "WAITING FOR RUN"
SUPER_NOTIFY_CMD='exit 7' STUB_SET_STATUS="WAITING FOR INPUT" tick; rc=$?
[[ $rc -eq 0 ]] || fail "notify failure leaked into tick rc=$rc"
grep -q "SUPER_NOTIFY_CMD failed" "$LOG_FILE" || fail "notify failure not logged"
pass "notify failure is logged, tick rc preserved"

# 6. empty SUPER_NOTIFY_CMD → built-in path → still logs 'notified' and exits 0
write_loop "WAITING FOR RUN"
SUPER_NOTIFY_CMD= STUB_SET_STATUS="WAITING FOR INPUT" tick
grep -q "notified event=waiting-for-input" "$LOG_FILE" || fail "built-in notifier did not log"
pass "built-in notifier path is safe"
EOF
chmod +x "$SCRATCH/harness/t3_notify.sh"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash "$SCRATCH/harness/t3_notify.sh"`
Expected: `FAIL: expected 1 notification, got 0`.

- [ ] **Step 3: Append `superagent_notify` to `scripts/_common.sh`**

```bash

# ---------------------------------------------------------------------------
# Operator notification — fired by the tick wrapper on a loop-status transition
# into WAITING FOR INPUT (a decision needs a human) or DONE. Unattended mode
# guarantees nobody is tailing the tick log, so this is the one signal the
# operator actually receives.
#   SUPER_NOTIFY_CMD  a shell snippet run via `bash -c` (e.g. a curl to ntfy.sh /
#                     Slack / Pushover) with SUPERAGENT_EVENT, SUPERAGENT_SLUG,
#                     LOOP_FILE, SUPERAGENT_TITLE, SUPERAGENT_BODY exported;
#   (unset/empty)     a desktop notification: osascript on macOS, notify-send on
#                     Linux, when available; otherwise log only.
# Never fails the caller (a broken notifier must not fail a healthy tick).
# ---------------------------------------------------------------------------
superagent_notify() {
  local event="${1:?event}" slug="${2:?slug}" loop="${3:?loop-file}" title body
  case "$event" in
    waiting-for-input)
      title="superagent: $slug needs a decision"
      body="$({ superagent_pending_section "$loop" | grep -v '^[[:space:]]*$' | head -3 \
                | tr '\n' ' ' | cut -c1-200; } || true)"
      [[ -n "$body" ]] || body="WAITING FOR INPUT: $loop"
      ;;
    done)
      title="superagent: $slug is DONE"; body="Loop reached DONE: $loop"
      ;;
    *)
      title="superagent: $slug $event"; body="$loop"
      ;;
  esac
  if [[ -n "${SUPER_NOTIFY_CMD:-}" ]]; then
    SUPERAGENT_EVENT="$event" SUPERAGENT_SLUG="$slug" LOOP_FILE="$loop" \
    SUPERAGENT_TITLE="$title" SUPERAGENT_BODY="$body" \
      bash -c "$SUPER_NOTIFY_CMD" || echo "superagent: SUPER_NOTIFY_CMD failed (rc=$?) for event=$event" >&2
  elif [[ "$(uname -s)" == Darwin ]] && command -v osascript >/dev/null 2>&1; then
    local t="${title//\"/}" b="${body//\"/}"; t="${t//\\/}"; b="${b//\\/}"
    osascript -e "display notification \"$b\" with title \"$t\"" >/dev/null 2>&1 || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "$title" "$body" >/dev/null 2>&1 || true
  fi
  echo "superagent: notified event=$event slug=$slug"
  return 0
}
```

- [ ] **Step 4: Snapshot the status before the session in `superagent-tick.sh`**

Immediately before the line `log_bytes_before="$(wc -c <"$LOG_FILE" 2>/dev/null || echo 0)"`:

```bash
# Status on entry, so post-run hooks can detect a TRANSITION (notify once on
# parking/finishing, never on every subsequent fire).
status_before="$(superagent_loop_status "$LOOP_FILE")"
```

- [ ] **Step 5: Add the notify block**

Immediately after `echo "=== $(ts) superagent-tick exit=${rc} ===" >>"$LOG_FILE"` and BEFORE the `# --- DONE self-disarm (issue #18)` block (on launchd the disarm's bootout kills this process, so notify must precede it):

```bash
# --- transition notifications -----------------------------------------------
# Tell the operator ONCE when this tick parked the loop on WAITING FOR INPUT or
# finished it (DONE) — the transition (entry status != exit status) is the
# once-only guard, so no sidecar state is needed and a gated/unchanged fire is
# silent. SUPER_NOTIFY_CMD or the desktop notifier; see superagent_notify.
status_after="$(superagent_loop_status "$LOOP_FILE")"
if [[ "$status_before" != "$status_after" ]]; then
  case "$status_after" in
    "WAITING FOR INPUT") superagent_notify waiting-for-input "${SUPERAGENT_SLUG:-$(basename "$LOOP_FILE" .md)}" "$LOOP_FILE" >>"$LOG_FILE" 2>&1 || true ;;
    DONE)                superagent_notify done              "${SUPERAGENT_SLUG:-$(basename "$LOOP_FILE" .md)}" "$LOOP_FILE" >>"$LOG_FILE" 2>&1 || true ;;
  esac
fi
```

- [ ] **Step 6: Add the knob to `templates/superenv.default`**

Under `# ── Loop tuning`, after the `SUPER_INPUT_GATE` line:

```bash
SUPER_NOTIFY_CMD=                       # external driver: shell snippet run when a loop parks on WAITING FOR INPUT or reaches DONE (env: SUPERAGENT_EVENT SUPERAGENT_SLUG LOOP_FILE SUPERAGENT_TITLE SUPERAGENT_BODY), e.g. curl -d "$SUPERAGENT_BODY" -H "Title: $SUPERAGENT_TITLE" ntfy.sh/<topic>; empty = desktop notification (osascript / notify-send) when available
```

- [ ] **Step 7: Run the notify test, then re-run the gate test**

Run: `bash "$SCRATCH/harness/t3_notify.sh" && bash "$SCRATCH/harness/t2_gate.sh"`
Expected: six `PASS:` lines then five `PASS:` lines, exit 0. (On this macOS host test 6 also pops a real desktop notification — that is correct.)

- [ ] **Step 8: Commit**

```bash
git add scripts/_common.sh scripts/superagent-tick.sh templates/superenv.default
git commit -m "feat(tick): notify the operator once on WAITING FOR INPUT / DONE transitions (SUPER_NOTIFY_CMD)"
```

---

### Task 4: `superagent_kick_tick` + `scripts/answer.sh` (answer under the lock, resume now)

**Files:**
- Modify: `scripts/_common.sh` (append `superagent_kick_tick`)
- Modify: `scripts/launch.sh:148-154` (use the helper)
- Create: `scripts/answer.sh`
- Create: `$SCRATCH/harness/t4_answer.sh` (throwaway)

**Interfaces:**
- Consumes: `superagent_loop_status`, `superagent_pending_answer` (Task 1); `superagent_scheduler`, `superagent_launchd_domain`, `superagent_launchd_label` (existing).
- Produces: `superagent_kick_tick <slug>` → `launchctl kickstart gui/<uid>/com.superagent.tick.<slug>` on Darwin, `systemctl --user start --no-block superagent-tick@<slug>.service` elsewhere; rc propagated. `answer.sh [--no-kick] <slug> <answer text…>`: exit 2 usage, 1 no registered loop / missing loop file, 3 status not `WAITING FOR INPUT`, 4 lock held, 5 no `## Pending decision` heading; on success prints `answer: recorded 'answer: <text>' in <loop-file>` then either `answer: kicked tick for '<slug>'` or (kick failed) a warning that the next scheduled tick resumes — exit 0 either way.

- [ ] **Step 1: Write the failing answer test**

```bash
cat >"$SCRATCH/harness/t4_answer.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/setup.sh"
A="$PLUGIN/scripts/answer.sh"

# 1. happy path: answer line lands directly under the heading; decoy untouched; kick attempted
write_loop "WAITING FOR INPUT"
out="$("$A" g postgres 2>&1)"; rc=$?
[[ $rc -eq 0 ]] || fail "answer rc=$rc: $out"
awk '/^## Pending decision/{getline; print; exit}' "$LOOP_FILE" | grep -q '^answer: postgres$' || fail "answer not under heading"
[[ "$(grep -c '^answer: ' "$LOOP_FILE")" -eq 2 ]] || fail "unexpected answer line count (decoy + new expected)"
grep -q "recorded 'answer: postgres'" <<<"$out" || fail "no recorded message: $out"
grep -Eq "kicked tick for 'g'|could not kick 'g'" <<<"$out" || fail "no kick message: $out"
[[ ! -d "$(dirname "$LOOP_FILE")/.$(basename "$LOOP_FILE").lockd" ]] || fail "lock leaked"
pass "answer recorded under heading, lock released, kick attempted"

# 2. the tick now consumes it (gate lets it through)
: >"$STUB_LOG"; STUB_SET_STATUS="WAITING FOR RUN" tick
grep -q STUB_CLAUDE_CALLED "$STUB_LOG" || fail "tick did not run after answer"
pass "answered loop runs on the next tick"

# 3. multi-word answer, --no-kick
write_loop "WAITING FOR INPUT"
out="$("$A" --no-kick g use sqlite for now 2>&1)"
grep -q '^answer: use sqlite for now$' "$LOOP_FILE" || fail "multi-word answer"
grep -q "no-kick" <<<"$out" || fail "--no-kick message: $out"
pass "multi-word + --no-kick"

# 4. refuses when a live tick holds the lock
write_loop "WAITING FOR INPUT"
L="$(dirname "$LOOP_FILE")/.$(basename "$LOOP_FILE").lockd"; mkdir "$L"; echo $$ >"$L/owner"
"$A" --no-kick g postgres >/dev/null 2>&1 && fail "wrote while lock held"
[[ $? -eq 4 ]] || true
grep -q '^answer: postgres' "$LOOP_FILE" && fail "answer written despite lock"
rm -rf "$L"; pass "lock held → refused, file untouched"

# 5. refuses when not WAITING FOR INPUT
write_loop "WAITING FOR RUN"
"$A" --no-kick g postgres >/dev/null 2>&1; rc=$?
[[ $rc -eq 3 ]] || fail "expected rc 3 for non-parked loop, got $rc"
pass "non-parked → rc 3"

# 6. unknown slug
"$A" --no-kick nope postgres >/dev/null 2>&1; rc=$?
[[ $rc -eq 1 ]] || fail "expected rc 1 for unknown slug, got $rc"
pass "unknown slug → rc 1"

# 7. usage
"$A" >/dev/null 2>&1; rc=$?
[[ $rc -eq 2 ]] || fail "expected rc 2 usage, got $rc"
pass "usage → rc 2"
EOF
chmod +x "$SCRATCH/harness/t4_answer.sh"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash "$SCRATCH/harness/t4_answer.sh"`
Expected: `FAIL: answer rc=127` (script does not exist).

- [ ] **Step 3: Append `superagent_kick_tick` to `scripts/_common.sh`**

```bash

# superagent_kick_tick <slug> — fire ONE tick now (non-blocking) through the
# registered scheduler entry, instead of waiting out the interval. Used by
# launch.sh (first tick) and answer.sh (resume right after an answer). rc is
# the scheduler's: non-zero when the entry is not loaded/armed.
superagent_kick_tick() {
  local slug="${1:?slug}"
  if [[ "$(superagent_scheduler)" == launchd ]]; then
    launchctl kickstart "$(superagent_launchd_domain)/$(superagent_launchd_label "$slug")"
  else
    systemctl --user start --no-block "superagent-tick@$slug.service"
  fi
}
```

- [ ] **Step 4: Use it in `scripts/launch.sh`**

Replace the current kick (lines ~148-154):

```bash
# Kick the first tick now (non-blocking) so the loop starts immediately instead of
# waiting for the timer's first interval.
if [[ "$SCHEDULER" == launchd ]]; then
  launchctl kickstart "$(superagent_launchd_domain)/$(superagent_launchd_label "$SLUG")" 2>/dev/null || true
else
  systemctl --user start --no-block "superagent-tick@$SLUG.service" 2>/dev/null || true
fi
```

with:

```bash
# Kick the first tick now (non-blocking) so the loop starts immediately instead of
# waiting for the timer's first interval.
superagent_kick_tick "$SLUG" 2>/dev/null || true
```

(Open the file first and match the exact existing block — the `if`/`else` shape above is from the current file; if the surrounding lines differ, keep them and replace only the scheduler branch.)

- [ ] **Step 5: Create `scripts/answer.sh`**

```bash
#!/usr/bin/env bash
# answer.sh — answer a loop parked on WAITING FOR INPUT and resume it NOW.
#
#   answer.sh [--no-kick] <slug> <answer text…>
#
# Writes `answer: <text>` directly under `## Pending decision` in the loop file
# (the line the skill's WAITING FOR INPUT branch consumes), holding the L3 lock
# so it never races a tick, then kicks one tick through the registered scheduler
# entry so the loop resumes in seconds instead of after the next interval
# (superagent-tick.sh's SUPER_INPUT_GATE skips sessions until this line exists).
# --no-kick records the answer only; the next scheduled tick resumes.
#
# Exit codes: 2 usage · 1 no registered loop / loop file missing · 3 loop is not
# WAITING FOR INPUT · 4 a tick holds the lock (retry) · 5 no ## Pending decision
# heading · 0 recorded (kick failure is a warning, not an error).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"

KICK=true
if [[ "${1:-}" == "--no-kick" ]]; then KICK=false; shift; fi
SLUG="${1:-}"; [[ $# -gt 0 ]] && shift
ANSWER="${*:-}"
if [[ -z "$SLUG" || -z "$ANSWER" ]]; then
  echo "usage: answer.sh [--no-kick] <slug> <answer text…>" >&2
  exit 2
fi

CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/superagent"
ENV_FILE="$CONF_DIR/$SLUG.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "answer: no registered loop '$SLUG' ($ENV_FILE missing) — see status.sh for registered slugs" >&2
  exit 1
fi
LOOP_FILE="$(sed -n 's/^LOOP_FILE=//p' "$ENV_FILE" | head -1)"
if [[ -z "$LOOP_FILE" || ! -f "$LOOP_FILE" ]]; then
  echo "answer: loop file missing for '$SLUG': ${LOOP_FILE:-<unset>}" >&2
  exit 1
fi

status="$(superagent_loop_status "$LOOP_FILE")"
if [[ "$status" != "WAITING FOR INPUT" ]]; then
  echo "answer: loop '$SLUG' is '${status:-<none>}', not WAITING FOR INPUT — nothing to answer" >&2
  exit 3
fi

LOCK_DIR="$(dirname "$LOOP_FILE")/.$(basename "$LOOP_FILE").lockd"
if existing="$(superagent_pending_answer "$LOOP_FILE")"; then
  echo "answer: an answer is already recorded ('$existing') — not overwriting; kicking a tick to consume it" >&2
else
  # Same lock discipline as a tick (superloop L3): mkdir is the atomic acquire.
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "answer: a tick holds the lock ($LOCK_DIR) — retry when it finishes (status.sh $SLUG)" >&2
    exit 4
  fi
  echo $$ >"$LOCK_DIR/owner"
  trap 'rm -rf "$LOCK_DIR"' EXIT
  tmp="$(mktemp)"
  awk -v ans="$ANSWER" '{ print } /^## Pending decision/ && !done { print "answer: " ans; done=1 }' \
    "$LOOP_FILE" >"$tmp"
  if [[ "$(wc -l <"$tmp")" -le "$(wc -l <"$LOOP_FILE")" ]]; then
    rm -f "$tmp"
    echo "answer: no '## Pending decision' heading in $LOOP_FILE — cannot place the answer" >&2
    exit 5
  fi
  cat "$tmp" >"$LOOP_FILE"   # in place: keep the file's inode/permissions
  rm -f "$tmp"
  rm -rf "$LOCK_DIR"; trap - EXIT
  echo "answer: recorded 'answer: $ANSWER' in $LOOP_FILE"
fi

if [[ "$KICK" != true ]]; then
  echo "answer: --no-kick — the next scheduled tick resumes the loop"
  exit 0
fi
if superagent_kick_tick "$SLUG" 2>/dev/null; then
  echo "answer: kicked tick for '$SLUG' — follow it: tail -f /tmp/superagent-$(basename "$LOOP_FILE" .md).log"
else
  echo "answer: could not kick '$SLUG' (scheduler entry not loaded?) — the next scheduled tick resumes; if the loop is disarmed, re-arm: $SCRIPT_DIR/install-timer.sh $SLUG $LOOP_FILE" >&2
fi
exit 0
```

Then: `chmod +x scripts/answer.sh`.

- [ ] **Step 6: Run the answer test, then all earlier tests**

Run: `bash "$SCRATCH/harness/t4_answer.sh" && bash "$SCRATCH/harness/t2_gate.sh" && bash "$SCRATCH/harness/t3_notify.sh" && bash -n scripts/launch.sh`
Expected: 7 + 5 + 6 `PASS:` lines, exit 0; `bash -n` silent.

- [ ] **Step 7: Commit**

```bash
git add scripts/_common.sh scripts/launch.sh scripts/answer.sh
git commit -m "feat(scripts): answer.sh — answer a parked loop under the lock and kick a tick now"
```

---

### Task 5: Docs + skills + generated builds

**Files:**
- Modify: `skills/superagent/SKILL.md` (the `### WAITING FOR INPUT` branch, non-interactive bullet ~lines 320-328; the `⚠️ Needs you:` report line ~571)
- Modify: `skills/superloop/SKILL.md` (L2 console paragraph ~lines 441-444; L7 unattended bullet ~lines 742-749)
- Modify: `skills/superagent-monitor/SKILL.md` (Step 1 `WAITING FOR INPUT` bullet ~line 63; Step 2 Paths)
- Modify: `skills/superagent-external/SKILL.md` (mention notify/gate in its "what happens next" wording, if it has one — grep `WAITING FOR INPUT`)
- Modify: `scripts/README.md` (answering section ~lines 288-310; script list ~line 244; add `answer.sh` to the usage block ~line 185)
- Modify: `README.md` (~lines 229-233)
- Modify: `scripts/console-watch.sh` (header comment: point to `answer.sh`)
- Regenerate: `cursor/`, `codex/`

**Interfaces:**
- Consumes: the exact names from Tasks 2-4: `SUPER_INPUT_GATE`, `SUPER_NOTIFY_CMD`, `answer.sh [--no-kick] <slug> <answer…>`.

- [ ] **Step 1: `skills/superagent/SKILL.md` — non-interactive bullet of `### WAITING FOR INPUT`**

Replace the sentence starting `The **scheduler keeps firing \`--tick\`**, which **polls** for the written answer and resumes the moment it appears — no driver teardown needed. A human can supply that answer from an independent interactive console (see the CLI runbook), or by editing the loop file directly.` with:

```markdown
    The scheduler keeps firing, but for loops driven by the shipped `scripts/` wrapper the fire is
    **free while unanswered**: `superagent-tick.sh` reads the loop file in bash and exits without a
    session until an `answer:` line exists under `## Pending decision` (`SUPER_INPUT_GATE`, default
    on); it also notifies the operator once on the transition (`SUPER_NOTIFY_CMD`, else a desktop
    notification). A human answers **and resumes immediately** with
    `$SUPERAGENT_SCRIPTS/answer.sh <slug> "<option>"` (writes the line under the lock, kicks a tick),
    from `superagent:superagent-monitor`, or by editing the loop file directly (next scheduled fire
    resumes).
```

And in the report template line `⚠️ **Needs you:** <only when status == WAITING FOR INPUT — the pending question + how to answer (interactive prompt, or \`answer:\` in the loop file for a scheduled loop)>` change the parenthetical to `(interactive prompt, or \`answer.sh <slug> "<option>"\` for a scheduled loop)`.

- [ ] **Step 2: `skills/superloop/SKILL.md`**

In the L2 "Interactive console" bullet, replace `or by writing \`answer: <option>\` into the loop file for the next scheduled tick to poll.` with:

```markdown
  or by writing `answer: <option>` into the loop file (`scripts/answer.sh <slug> "<option>"` does this
  under the lock and kicks a tick at once; a hand edit is picked up on the next scheduled fire).
```

In the L7 unattended bullet, after `even in a brand-new session.` insert:

```markdown
   (Shipped-wrapper loops pay nothing while waiting: `superagent-tick.sh` polls the file in bash and
   only launches a session once the answer exists — `SUPER_INPUT_GATE` — and notifies the operator
   once on parking — `SUPER_NOTIFY_CMD`.)
```

- [ ] **Step 3: `skills/superagent-monitor/SKILL.md` — Step 2**

Replace the whole of Step 2 from `**Path A — attended tick (preferred).**` through the end of the Path B code block with:

````markdown
**Path A — `answer.sh` (preferred).** Present the decision options to the user with `AskQuestion`, then
record the answer and resume the loop in one step — it takes the loop's L3 lock (refuses if a tick is
mid-flight: retry), writes `answer: <option>` under `## Pending decision`, and kicks one tick
immediately so the loop resumes now rather than after the interval (the wrapper's `SUPER_INPUT_GATE`
otherwise skips sessions until that line exists):

```
"$SUPERAGENT_SCRIPTS/answer.sh" <slug> "<option>"        # add --no-kick to record only
tail -f /tmp/superagent-<loop-basename>.log               # watch the resumed tick
```

Exit codes: 3 = not `WAITING FOR INPUT`, 4 = lock held (a tick is running — wait, then retry), 1 =
unknown slug.

**Path B — attended tick (when you want to watch it apply in-session).** Run exactly one interactive
tick, passing the chosen answer as guidance. The skill's `WAITING FOR INPUT` branch consumes it,
records it under `## Decisions`, restores `prior_status`, and continues the tick — all under the lock,
serialized against the scheduler. Derive the plugin root from `$SUPERAGENT_SCRIPTS` and read the skill
file directly (headless `claude -p` cannot run a slash command or rely on `${CLAUDE_PLUGIN_ROOT}` —
superloop L2 Driver B):

```
cd "$primary_root"
PLUGIN_ROOT="$(cd "$SUPERAGENT_SCRIPTS/.." && pwd)"
claude -p "Read ${PLUGIN_ROOT}/skills/superagent/SKILL.md and run exactly ONE --tick on loop file <LOOP_FILE>. The pending decision is answered: <ANSWER>. Apply it and continue the tick." --allowedTools "Read,Edit,Write,Bash,Task,Skill"
```
````

Keep the trailing `Never call AskUserQuestion/AskQuestion on behalf of a headless tick…` paragraph. In Step 1's `WAITING FOR INPUT` bullet, append: `The operator was notified once when it parked (SUPER_NOTIFY_CMD / desktop), and scheduled fires are free until answered (SUPER_INPUT_GATE).`

- [ ] **Step 4: `scripts/README.md`**

In the usage block (~line 185) add after the `console-watch.sh` line:

```
$SUPERAGENT_SCRIPTS/answer.sh <slug> "<option>"            # answer WAITING FOR INPUT + kick a tick now
```

In the script list (~line 244) add a bullet:

```markdown
- `answer.sh [--no-kick] <slug> <answer…>` — answer a `WAITING FOR INPUT` loop: writes `answer: <text>`
  under `## Pending decision` (holding the L3 lock) and kicks one tick so the loop resumes now.
```

Replace the answering section's item 2 (`**Answer injection.** … rm -rf "$d/.$b.lockd"  # release`) with:

````markdown
2. **`answer.sh` (one command, resumes now).** Records the answer under the lock and kicks a tick:

   ```bash
   $SUPERAGENT_SCRIPTS/answer.sh <slug> "<option>"
   ```

   A hand edit also works (add `answer: <option>` under `## Pending decision`, holding
   `.<loop>.lockd` as a tick would) — it is consumed on the next scheduled fire.

While a loop waits, scheduled fires cost nothing: `superagent-tick.sh` checks the loop file in bash and
exits before launching a session until the answer exists (`SUPER_INPUT_GATE=true`, `.superenv`). The
operator is told once when the loop parks or finishes: set `SUPER_NOTIFY_CMD` to any shell snippet
(it sees `SUPERAGENT_EVENT` = `waiting-for-input`|`done`, `SUPERAGENT_SLUG`, `LOOP_FILE`,
`SUPERAGENT_TITLE`, `SUPERAGENT_BODY`), e.g.
`curl -s -d "$SUPERAGENT_BODY" -H "Title: $SUPERAGENT_TITLE" ntfy.sh/<topic>`; unset, the wrapper falls
back to a desktop notification (`osascript` on macOS, `notify-send` on Linux) when available.
````

- [ ] **Step 5: `README.md`**

Replace `so the loop writes the pending question plus an \`answer: <option>\` instruction into the loop file and every subsequent tick polls for it — resume is automatic once a human (or a separate monitoring console) supplies it.` with:

```markdown
so the loop writes the pending question plus an `answer: <option>` instruction into the loop file,
the driver notifies the operator once (`SUPER_NOTIFY_CMD` / desktop notification), and scheduled
fires are free until an answer exists (a bash check, no session). `scripts/answer.sh <slug> "<option>"`
records the answer under the lock and kicks a tick, so resume is immediate.
```

- [ ] **Step 6: `scripts/console-watch.sh` header**

Replace the two numbered "To ANSWER" lines in the header comment with:

```bash
# To ANSWER a parked decision: answer.sh <slug> "<option>" (records the answer
# under the lock and kicks a tick now); or run one attended --tick; or hand-edit
# `answer: <option>` under ## Pending decision (next scheduled tick resumes).
```

- [ ] **Step 7: `skills/superagent-external/SKILL.md`**

Run `grep -n "WAITING FOR INPUT\|answer" skills/superagent-external/SKILL.md`. Where it tells the user what happens on a parked decision, add one sentence: `You are notified once when that happens (SUPER_NOTIFY_CMD, else a desktop notification); answer + resume with $SUPERAGENT_SCRIPTS/answer.sh <slug> "<option>".` If there is no such sentence, add it to the skill's final "what next" report guidance.

- [ ] **Step 8: Regenerate builds and check**

Run: `scripts/build-cursor-skills.sh && scripts/build-codex-skills.sh && scripts/build-cursor-skills.sh --check && scripts/build-codex-skills.sh --check`
Expected: both `--check` runs report no diff, exit 0. `git status` shows changes under `cursor/skills/…` and `codex/plugins/superagent/skills/…` mirroring the canonical edits.

- [ ] **Step 9: Commit**

```bash
git add README.md scripts/README.md scripts/console-watch.sh skills/ cursor/ codex/
git commit -m "docs: gate/notify/answer.sh across skills, runbooks, and generated builds"
```

---

### Task 6: CHANGELOG + version 0.4.8 + full re-verify

**Files:**
- Modify: `CHANGELOG.md` (new top entry)
- Modify: `.claude-plugin/plugin.json` (`"version": "0.4.8"`)
- Regenerate: `cursor/.cursor-plugin/plugin.json`, `codex/plugins/superagent/.codex-plugin/plugin.json` (via the build scripts)

- [ ] **Step 1: CHANGELOG entry** (insert above `## 0.4.7`)

```markdown
## 0.4.8 — 2026-08-28

- **A loop parked on `WAITING FOR INPUT` no longer burns a paid session per interval.** The
  wrapper had no pre-screen for the parked state, so every scheduler fire launched a full CLI session
  that read the file, found no answer, and exited — the DONE-polling waste of #18, still open for the
  parked state. Three additive driver changes (no skill-logic or scheduler change):
  - **Bash gate (`SUPER_INPUT_GATE=true`).** `superagent-tick.sh` reads the loop file before any
    preflight; `WAITING FOR INPUT` with no `answer:` under `## Pending decision` → one log line,
    exit 0, no session. Polling continues for free; resume-on-answer is unchanged.
  - **One notification on the transition (`SUPER_NOTIFY_CMD`).** The wrapper snapshots `status`
    before the session and fires `superagent_notify` when the tick parks the loop
    (`waiting-for-input`, body = the pending question) or finishes it (`done`). Your snippet runs via
    `bash -c` with `SUPERAGENT_EVENT/SLUG/TITLE/BODY` + `LOOP_FILE` in env (ntfy/Slack/Pushover…);
    unset → `osascript` (macOS) / `notify-send` (Linux) when available. A failing notifier is logged
    and never fails the tick. Transition detection = fires once, no sidecar state.
  - **`scripts/answer.sh [--no-kick] <slug> <answer…>`.** Records `answer: <text>` directly under
    `## Pending decision` holding the L3 lock (refuses with exit 4 while a tick is mid-flight, 3 if
    the loop isn't parked), then kicks one tick via the registered scheduler entry so the loop resumes
    in seconds. Kick logic lifted into `_common.sh` (`superagent_kick_tick`) and shared with
    `launch.sh`. `superagent-monitor` now recommends it as the primary answer path.
  - New `_common.sh` readers `superagent_loop_status` / `superagent_pending_section` /
    `superagent_pending_answer` (answer detection is scoped to the pending section — an `answer:`
    under `## Decisions` never counts).
  - Follow-ups (not here): a `WAITING FOR CI` bash gate; event-driven wake via launchd
    `WatchPaths` / a systemd `.path` unit.
```

- [ ] **Step 2: Bump the version and regenerate**

```bash
sed -i '' 's/"version": "0.4.7"/"version": "0.4.8"/' .claude-plugin/plugin.json
scripts/build-cursor-skills.sh && scripts/build-codex-skills.sh
grep -rn '"version"' .claude-plugin/plugin.json cursor/.cursor-plugin/plugin.json codex/plugins/superagent/.codex-plugin/plugin.json
```
Expected: all three show `0.4.8`.

- [ ] **Step 3: Full re-verify**

```bash
bash -n scripts/_common.sh scripts/superagent-tick.sh scripts/answer.sh scripts/launch.sh
bash "$SCRATCH/harness/t1_helpers.sh" && bash "$SCRATCH/harness/t2_gate.sh" && \
bash "$SCRATCH/harness/t3_notify.sh" && bash "$SCRATCH/harness/t4_answer.sh"
scripts/build-cursor-skills.sh --check && scripts/build-codex-skills.sh --check
command -v shellcheck >/dev/null && shellcheck -x scripts/answer.sh scripts/superagent-tick.sh scripts/_common.sh || true
```
Expected: 5 + 5 + 6 + 7 = 23 `PASS:` lines, both checks clean, no shellcheck errors (warnings acceptable only if pre-existing).

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md .claude-plugin/plugin.json cursor/.cursor-plugin/plugin.json codex/plugins/superagent/.codex-plugin/plugin.json
git commit -m "chore: changelog + bump to 0.4.8"
```

- [ ] **Step 5: Open the PR** (use `superpowers:finishing-a-development-branch`)

```bash
git push -u origin input-gate-notify-kick
gh pr create --title "feat: free polling while WAITING FOR INPUT, notify once, answer.sh resumes now; bump to 0.4.8" --body-file <(cat <<'EOF'
## Problem
A loop parked on `WAITING FOR INPUT` kept launching a full paid CLI session every interval just to find no answer (the #18 pathology, still open for the parked state); nobody was told it parked; and answering waited out the interval.

## Fix
- **Bash gate** `SUPER_INPUT_GATE` — no session until `answer:` exists under `## Pending decision`.
- **Notify once** `SUPER_NOTIFY_CMD` — on the transition into `WAITING FOR INPUT` / `DONE`; desktop fallback.
- **`scripts/answer.sh <slug> "<option>"`** — records the answer under the L3 lock and kicks a tick now; `superagent_kick_tick` shared with `launch.sh`; monitor skill recommends it.

## Verification
Stub-CLI harness (real `superagent-tick.sh` + `answer.sh`, stubbed `claude`/`gh`, real loop-file fixture with an `answer:` decoy under `## Decisions`): 23/23 — gate skip / answered runs / decoy ignored / gate off / ready untouched; notify once / silent on gated fire / silent without transition / done event / failing notifier logged & rc preserved / built-in path; answer under heading + lock released + kick attempted / consumed next tick / multi-word + --no-kick / lock held → 4 / not parked → 3 / unknown slug → 1 / usage → 2. Both build `--check`s clean.

Spec: `docs/superpowers/specs/2026-08-28-input-gate-notify-kick-design.md` · Plan: `docs/superpowers/plans/2026-08-28-input-gate-notify-kick.md`

## Follow-ups
`WAITING FOR CI` bash gate; launchd WatchPaths / systemd .path event-driven wake.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)
```

---

## Self-review (done at authoring time)

- **Spec coverage:** gate → Task 2; notify (cmd + desktop fallback + once-only + never-fail) → Task 3; answer + kick + lock + `launch.sh` reuse + monitor recommendation → Tasks 4-5; `.superenv` keys → Tasks 2-3; docs/builds → Task 5; changelog/version → Task 6; out-of-scope items recorded in spec + changelog.
- **Placeholders:** none — every code step is complete; the only "grep first" step (Task 5 Step 7) gives the exact sentence to add.
- **Name consistency:** `superagent_loop_status` / `superagent_pending_section` / `superagent_pending_answer` / `superagent_notify` / `superagent_kick_tick`; `SUPER_INPUT_GATE` / `SUPER_NOTIFY_CMD`; env `SUPERAGENT_EVENT|SLUG|TITLE|BODY` + `LOOP_FILE`; `answer.sh [--no-kick] <slug> <answer…>` exit codes 1/2/3/4/5 — identical across tasks, tests, docs, and changelog.

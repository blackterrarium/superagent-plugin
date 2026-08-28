---
name: superagent
description: Use when asked to drive a goal's root seed/master plan (PLAN.md) to completion unattended, or when a scheduler fires `--tick` on an existing loop-status file — the autonomy supervisor for the super* plan-tree lifecycle, driven in-session (cron) or by an external scheduler in a fresh context per tick.
argument-hint: <PLAN.md> [--driver=cron|desktop]   (or: --tick <loop-file>)
disable-model-invocation: true
license: all rights reserved
related skills: superloop, superplan, superrun, supertraverse, superfinish
---

# Superagent

The **autonomy supervisor** for the `super*` plan-tree lifecycle. Given a goal's **root** seed/master
plan, superagent drives the whole arc — `superplan` writes the next step's plan, `superrun` executes
the next ready leaf plan and closes it out — to completion **unattended**, one step per iteration,
until every step is both planned and executed.

superagent does **not** plan or execute work itself. Each iteration it dispatches **exactly one** of
`superplan` / `superrun` (never both) **in its own subagent** (see **Subagent dispatch** below), reads
that skill's Final Report, **relays it verbatim to the caller** (see **Final Report — per tick**),
advances a small state machine, and lets its **driver** fire the next iteration. Two drivers are supported (see **Drivers**): an
**in-session `cron`** job (attended; context accumulates) or an **external scheduler** — a Desktop
routine or OS cron firing `/superagent --tick` in a **fresh session per iteration (clean context)**.
All state lives in the loop file, so the two are interchangeable. The loop ends itself when the goal is
complete.

**This skill is built on the `superloop` chassis.** **Invoke the `superagent:superloop` skill via the Skill tool at
the start of the run** and apply its clauses **L1–L7** throughout: the loop-status file (L1), the
cron/external driver + guard/bootstrap/resume (L2), the overlap lock (L3), the context-handoff gate
(L4), the sync gate (L5), the PR integration discipline (L6), and the decision-escalation ladder (L7).
superloop owns the **chassis**; superagent supplies the **work model** below — the `WAITING FOR PLAN` /
`WAITING FOR RUN` status vocabulary, the one-skill-per-tick `superplan` / `superrun` dispatch (Step 1),
and the two-signal `DONE` condition. superagent's `<consumer>` value for L2's tick prompt is
`superagent`; its `<bootstrap-input>` is the root `<PLAN.md>`; its status-role mapping is ready =
`WAITING FOR PLAN` / `WAITING FOR RUN`, transient = `PLANNING` / `RUNNING`, plus `WAITING FOR INPUT`,
`DONE`, and a superagent-specific **parked** state `WAITING FOR CI` (see **CI wait — monitor-parked**);
its heavy step (L4) is one `superplan` or `superrun` invocation (dispatched in its own subagent)
with threshold (`SUPER_HEAVY_STEP_LIMIT`, default 6); its be-sure
artifacts (L5) are the `superplan` / `superrun`-reported plan / closeout files plus PR squash commits;
its escalation option-set (L7) is {retry `superrun` / re-plan / decline}.

| Thought | Reality |
|---------|---------|
| "I'll plan this step and then run it in the same tick while I'm here" | NO. **One skill per tick.** Set the next status and let the next cron tick run it. superplan and superrun contexts must never intermix. |
| "I'll just invoke `superplan`/`superrun` via the Skill tool here — it's simpler" | NO. **Every `superplan`/`superrun` invocation runs in its own `general-purpose` subagent** (see **Subagent dispatch**). superagent's own context ingests only the returned Final Report (which it then relays verbatim to the caller), never the full skill execution — that is what keeps the supervisor lean and the per-session threshold (`SUPER_HEAVY_STEP_LIMIT`, default 6) meaningful. |
| "I'll detect the next step / execute the plan myself" | NO. superagent never traverses, plans, or executes. It dispatches `superplan` / `superrun` (each in its own subagent) and reacts to their Final Reports. |
| "/superagent was run again — I'll start the loop" | NO. Check first. `cron` mode: `CronList` — a live job + non-terminal status = already looping, report and exit. `external` mode: a non-terminal loop file = the Desktop routine / cron entry is already the driver; report state and re-print setup, don't arm anything. Never start a second loop. | <!-- cc-only -->
<!-- cursor-only:start
| "/superagent was run again — I'll start the loop" | NO. Check first. A non-terminal loop file = the scheduler entry is already the driver; report state and re-print setup, don't arm anything. Never start a second loop. |
cursor-only:end -->
<!-- codex-only:start
| "/superagent was run again — I'll start the loop" | NO. Check first. A non-terminal loop file = the scheduler entry is already the driver; report state and re-print setup, don't arm anything. Never start a second loop. |
codex-only:end -->
| "A fresh/empty context means I lost the loop state" | NO. All state is in the loop file. A `--tick` works identically in a clean context (external driver) or an accumulating one (cron). Acquire the lock, read the file, run one tick. |
| "A skill raised a question — I'll just ask the user" | NO. First run the **subagent panel** (Decision-escalation ladder). Ask the user only if the panel cannot converge. |
| "The work is blocked — terminate the loop" | NO. Run the panel on the blocker first (retry / re-plan / decline / escalate). Stop the driver only when DONE or an escalation pauses the loop. |
| "superplan/superrun already did `git checkout main && pull`, so local is synced" | NO. That pull can silently fail or be skipped (worktree checkout error after a remote `--admin` merge; propagation race). Run the **Sync gate** before AND after every skill, and verify the merged artifacts are present locally — never advance on a stale tree. |
| "Context is getting low but I'll squeeze one more `superplan`/`superrun` in while I'm here" | NO. **Run the Session skill-budget gate (Step 0.5) before every iteration.** After `SUPER_HEAVY_STEP_LIMIT` heavy skills (default 6) in one cron session → persist, stop the cron driver, and hand off; tell the user to `/clear` and re-run `/superagent`. A skill that dies mid-run with the window blown leaves no clean resume. | <!-- cc-only -->
| "superrun yielded CI-PENDING — I'll poll `gh run view` / `gh run watch` in a loop until it finishes" | NO. **Park.** Record the CI packet, set `WAITING FOR CI`, arm the completion **Monitor**, release the lock, end the tick. The harness re-invokes you exactly once, when ALL runs are terminal. Per-tick / in-context polling is the context waste the parked state exists to eliminate. | <!-- cc-only -->
| "A tick fired while WAITING FOR CI — I'll check the run status while I'm here" | cron: NO — strict no-op (the Monitor owns the wait; read status, release lock, exit — no `gh`, no `curl`, no subagent). external: ONE batched `curl` over the recorded run ids, then exit if any is still running — never a heavy dispatch. | <!-- cc-only -->
<!-- cursor-only:start
| "superrun yielded CI-PENDING — I'll poll `gh run view` / `gh run watch` in a loop until it finishes" | NO. **Park.** Record the CI packet, set `WAITING FOR CI`, release the lock, end the tick. Each later scheduled tick does ONE batched `curl` over the recorded run ids and exits unless every run is terminal. Per-tick heavy polling is the context waste the parked state exists to eliminate. |
| "A tick fired while WAITING FOR CI — I'll check the run status while I'm here" | ONE batched `curl` over the recorded run ids, then exit if any is still running — never a heavy dispatch. |
cursor-only:end -->
<!-- codex-only:start
| "superrun yielded CI-PENDING — I'll poll `gh run view` / `gh run watch` in a loop until it finishes" | NO. **Park.** Record the CI packet, set `WAITING FOR CI`, release the lock, end the tick. Each later scheduled tick does ONE batched `curl` over the recorded run ids and exits unless every run is terminal. Per-tick heavy polling is the context waste the parked state exists to eliminate. |
| "A tick fired while WAITING FOR CI — I'll check the run status while I'm here" | ONE batched `curl` over the recorded run ids, then exit if any is still running — never a heavy dispatch. |
codex-only:end -->
| "The dispatched subagent will run a long time — I'll run it in the background and check on it while I wait" | NO. **Wait, never poll.** Every heavy-skill dispatch is synchronous (`run_in_background: false` on the Agent call for `superplan`; a blocking Bash call for `superrun`): the blocked call waits at zero context cost and the Final Report arrives as the tool result. A background dispatch + `TaskOutput`/`TaskList` checks spends supervisor context on "still running" snapshots the synchronous return delivers for free. |
| "I'll dispatch `superrun` as an Agent-tool subagent like `superplan`" | NO. **`superrun` runs in its own CLI process** (`role-bridge.sh --tools executor` from your Bash tool — see **Subagent dispatch**). `superrun` is the SDD controller and must dispatch its own implementer/reviewer subagents; a subagent cannot foreground-wait on its children (superloop L7's depth-1 constraint), so as an Agent-tool subagent it degrades into a `SendMessage`-nudge spiral and never converges (issue #25). |
| "My dispatch was interrupted mid-flight (API lost, host slept) — I'll ask the operator whether to resume or pause" | NO. **A tick never ends with a question — not via a tool, not as the final chat message** (in an unattended session no one can answer; the questioning turn exits 0 and strands `status: PLANNING`/`RUNNING` + the held lock). Self-heal immediately per superloop L2's tick teardown invariant: log the interruption, reset `PLANNING → WAITING FOR PLAN` / `RUNNING → WAITING FOR RUN`, `release_lock()`, end the tick with a normal report. The next scheduled tick retries the step. |

## Hard gate — `<PLAN.md>` is required

**DO NOT START A LOOP WITHOUT THE MASTER PLAN FILE.** If superagent is invoked with no `<PLAN.md>`
and no existing loop-status file can be located, respond with exactly:

    superagent requires a master plan file (PLAN.md). None provided and no loop file found. Exiting.

and **exit**. Do not guess a plan from the working directory.

`<PLAN.md>` must be the goal's **root** seed/master plan (the same file `superrun` traverses and
`superplan` descends from) — not a leaf implementation plan.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${CLAUDE_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

---

## The loop-status file

The location, format, frontmatter schema, `primary_root()`, goal-folder derivation, and gitignore facts
are **superloop L1**. superagent's `status:` values map to L1's generic roles as: ready = `WAITING FOR
PLAN` / `WAITING FOR RUN`; transient = `PLANNING` / `RUNNING`; plus `WAITING FOR INPUT` and `DONE`.
`WAITING FOR CI` is a superagent-specific **parked** role — durable like a ready state (a persisted
`WAITING FOR CI` is normal, NOT a crash), but its tick branch dispatches nothing heavy. superagent adds
the `plan_exhausted` frontmatter field (its two-signal DONE) and, while parked, a `ci_wait:` block (see
**CI wait — monitor-parked**).

### Status vocabulary

- `WAITING FOR PLAN` — ready to dispatch `superplan` (in its own subagent) for the next step.
- `PLANNING` — `superplan` is running (transient within a tick; persisted ⇒ a crash).
- `WAITING FOR RUN` — ready to dispatch `superrun` (in its own subagent) for the next ready leaf.
- `RUNNING` — `superrun` is running (transient within a tick; persisted ⇒ a crash).
- `WAITING FOR CI` — a dispatched `superrun` pushed long CI and yielded a CI-PENDING report; the loop
  is **parked** on the run(s) behind a completion Monitor (cron) or a one-curl-per-tick check
  (external). Durable, not a crash. See **CI wait — monitor-parked**.
- `WAITING FOR INPUT` — a decision the subagent panel could not resolve is awaiting the user.
- `DONE` — every step is both planned and executed (the two-signal terminal; see below).

---

## Step 0 — Parse the invocation, then guard / bootstrap / resume

Parse the invocation (form (A) internal `--tick <loop-file>`; form (B) user entry) and guard / bootstrap
/ resume per **superloop L2**, with `<consumer>` = `superagent` and the required bootstrap input = the
root `<PLAN.md>`. If form (B) is invoked with no `<PLAN.md>` and no existing loop file can be located,
print superagent's exact hard-gate message (above) and exit. L2 owns the form-(A) lock-then-read-then-
`DONE`-no-op sequence, the form-(B) driver parse / state-location / cron-and-external guard-bootstrap-
resume branching, and the read-`master_plan`/`status`/…-before-Step-1 step. After L2 hands control back
— having read the loop file and (for a continuing tick) acquired the lock — run **Step 0.5** then go to
**Step 1**.

---

## Step 0.5 — Session skill-budget gate (check BEFORE every iteration)

<!-- cc-only:start -->
Run **superloop L4** (`check_session_budget()`) before every iteration — after reading the loop file
(Step 0) and after the `DONE` no-op, but before the Step 1 dispatch. superagent's **heavy step** is one
`superplan` or `superrun` invocation (incremented in Step 2); the handoff **threshold** is `SUPER_HEAVY_STEP_LIMIT` (default 6). If L4 hands
off, this tick ends there; otherwise go to **Step 1**.
<!-- cc-only:end -->
<!-- cursor-only:start
A structural no-op in this build (superloop L4): the external driver is the only driver and every tick
runs in a fresh context. Go straight to **Step 1**.
cursor-only:end -->
<!-- codex-only:start
A structural no-op in this build (superloop L4): the external driver is the only driver and every tick
runs in a fresh context. Go straight to **Step 1**.
codex-only:end -->

---

## Sync gate — local `main` must equal `origin/main` (REQUIRED around every skill dispatch)

Run **superloop L5** (`sync_main()` + the Be-sure verification, STOP → `WAITING FOR INPUT`) around every
skill dispatch — pre, so the delegated skill reads a fresh tree, and post, so a silently-skipped local
pull never leaves the primary checkout stale. superagent's **be-sure artifacts** are the
`superplan` / `superrun` Final-Report-named plan / closeout files plus the PR squash commits (see the
per-status Sync-gate steps in **Step 1**). If L5 STOPs, the loop pauses on `WAITING FOR INPUT` — do not
advance.

---

## Subagent dispatch — `superplan`/`superrun` always run isolated

**Every heavy-skill invocation runs isolated from superagent's own context — superagent NEVER
invokes `superplan` or `superrun` inline.** The two skills are isolated differently, and the
difference is load-bearing:

- **`superplan` → an Agent-tool subagent.** `superplan` authors documents and dispatches no
  subagents of its own, so a depth-1 subagent is the right container. When Step 1 reaches the
  `WAITING FOR PLAN` branch, dispatch it with the **Agent tool** (`subagent_type: general-purpose` —
  full tool access: Bash, Edit/Write, git, `gh` — and `run_in_background: false`; see **Synchronous
  dispatch** below).
- **`superrun` → its own CLI process.** `superrun` is the `subagent-driven-development` controller:
  it dispatches implementer / reviewer / fix-applier subagents and foreground-waits on each. **A
  subagent cannot foreground-wait on its own children** (superloop L7's depth-1 constraint): run as
  an Agent-tool subagent, `superrun`'s children background and yield control back after every turn,
  and the tick decays into a `SendMessage`-nudge spiral with two writers racing on the worktree
  (issue #25). So when Step 1 reaches the `WAITING FOR RUN` branch — and for the ci-resume dispatch
  and any escalation-ladder retry — start `superrun` as the **top-level agent of a fresh headless
  CLI process** via the shipped bridge, from **your own Bash tool**, and block on it:

  1. Write the dispatch prompt (the instruction list below, with the concrete `<PLAN.md>` path and,
     for a resume, the `ci_wait` packet + conclusions) to a temp file with a quoted heredoc:
     `f="$(mktemp "${TMPDIR:-/tmp}/super-executor.XXXXXX")"; cat >"$f" <<'__SUPERAGENT_PROMPT_END__' … __SUPERAGENT_PROMPT_END__`.
  2. Resolve the executor's harness / model / effort (see **Model resolution** below), then run —
     from the **primary checkout root** (`superrun` makes its own worktree), with `timeout: 7200000`
     on the Bash call:
     `"${SUPERAGENT_BRIDGE:-${CLAUDE_PLUGIN_ROOT}/scripts/role-bridge.sh}" --harness <h> --model "<m>" --effort "<e>" --tools executor --cwd "<primary root>" --prompt-file "$f" --role executor`
     `--tools executor` gives the child the tick's own allowlist (`Read,Edit,Write,Bash,Grep,Glob,Task,Skill`),
     so inside that process `superrun`'s SDD subagents are depth 1 and the synchronous wait holds —
     exactly as it does for this tick's own dispatches. The bridge also lifts the print-mode
     background-wait ceiling (issue #15) for the child.
  3. Exit 0 → stdout **is** `superrun`'s final message (Final Report or CI-PENDING report); parse and
     relay it exactly as before. Non-zero → the bridge prints `role-bridge: log=<path>` on stderr;
     treat it as a crashed dispatch (escalation ladder, quoting the log path) — never retry blindly.

  **Preflight (once per tick, before the first `superrun` dispatch):** `superrun` runs 20–60 min and
  the Bash tool kills anything past its cap. `scripts/superagent-tick.sh` exports
  `BASH_MAX_TIMEOUT_MS=7200000` for every external tick; an attended `cron` session must be launched
  with `BASH_DEFAULT_TIMEOUT_MS=3600000 BASH_MAX_TIMEOUT_MS=7200000 claude …`. Check
  `[ "${BASH_MAX_TIMEOUT_MS:-0}" -ge 7200000 ]` in Bash; if it fails, do **not** dispatch — reset
  `RUNNING → WAITING FOR RUN`, `stop_driver()`, `release_lock()`, and report the missing env var in
  `Findings & issues` (a dispatch that gets guillotined at 600 s strands a half-done worktree).

  The child process shares this host's CLI login and plugin set, so `superagent:superrun` and
  `superpowers:*` resolve there exactly as here; the `.claude/agents/super-<role>.md` definitions
  `superagent:init` generated resolve from the `--cwd` root as usual.

Either way, instruct the executor/subagent to:

1. invoke the named skill (`superagent:superplan` or `superagent:superrun`) via its **Skill tool** with `<PLAN.md> =
   master_plan` (and the per-branch arguments below), and
2. **return that skill's complete Final Report verbatim as its final message** — the subagent's final
   message is what superagent receives as the tool result, and the verbatim report is exactly what the
   per-branch step-5 parsing consumes. (One sanctioned exception: a `superrun` process that queued
   long CI returns a **CI-PENDING report** instead and exits — that is a valid yield, not a failure;
   a fresh process resumes it later; see **CI wait — monitor-parked**.)

**Model resolution — every heavy-skill dispatch site passes a model per its `.superenv` role key**
(`SUPER_MODEL_PLANNER` for `superplan`, `SUPER_MODEL_EXECUTOR` for `superrun` — including the
ci-resume's fresh process and escalation-ladder retries).

*`superrun` (process dispatch):* the bridge takes the CLI's native model string directly, so no
agent definition is involved. In Bash, `. "${CLAUDE_PLUGIN_ROOT}/scripts/_common.sh"` and pass
`--harness "$(superagent_role_harness "$SUPER_MODEL_EXECUTOR")"` (an `inherit` harness → `SUPER_HARNESS`),
`--model "$(superagent_role_model "$SUPER_MODEL_EXECUTOR")"` (a tier, a full `claude-*` ID, or a
foreign harness's model — all pass through unchanged; `inherit` omits the flag) and
`--effort "$SUPER_EFFORT_EXECUTOR"` (`inherit` omits it). A bridged executor (harness ≠
`SUPER_HARNESS`) is the same command with the foreign `--harness`; the bridge runs that CLI. A
`.claude/agents/super-executor.md` definition, if `superagent:init` generated one, is unused by this
path.

*`superplan` (Agent-tool dispatch):*

- `inherit` → omit the `model:` parameter (the subagent runs on the session model).
- A tier name (`sonnet` | `opus` | `haiku` | `fable`) → pass it as `model:`.
- A **full model ID** (matches `^claude-`, e.g. `claude-fable-5`) → the Agent tool's `model:`
  parameter is tier-enum-only and rejects it; instead dispatch with `subagent_type: super-planner`
  — the per-role agent definition `superagent:init` generates in `.claude/agents/`,
  whose `model:` frontmatter carries the pin — and omit `model:`. If that definition is missing,
  that is a hard error: surface it (instruct a `superagent:init` re-run), never silently downgrade.
- A **bridged** value (harness prefix or inference ≠ `SUPER_HARNESS`, e.g. `codex:gpt-5.6-sol`,
  `openai/gpt-5`) → dispatch with `subagent_type: super-planner` and omit
  `model:`; the generated definition is a relay to that harness's CLI. A Final Report that begins
  `BRIDGE-FAILED` is a failed dispatch — route it through the escalation ladder like any other
  crashed subagent, quoting its `log=` path.

**Synchronous dispatch — the supervisor WAITS on the tool call; it never polls a running subagent.**
The harness runs Agent-tool subagents in the background by default, which hands back a task handle and
invites `TaskOutput`/`TaskList` status checks while the work runs — for a long `superplan`/`superrun`
that polling is pure supervisor-context waste. So every heavy-skill dispatch — the Step-1 `superplan`
Agent call passes **`run_in_background: false`**; the `superrun` bridge call (Step-1, the ci-resume's
fresh process, an escalation-ladder retry) is a plain **foreground Bash call with `timeout: 7200000`**,
never `run_in_background: true` — **blocks until the child's final message returns as the tool
result**. The blocked wait costs zero
context; there is nothing to check on and nothing to do until the report arrives. No `TaskOutput` /
`TaskList` peeks, no sleep loops, no "let me see how it's doing" reads — a poll can only report "still
running", which the synchronous return delivers for free by not having returned yet. A long dispatch
does not starve the loop (ticks fire between turns in `cron` mode and serialize on the lock in
`external` mode), and a subagent facing a genuinely open-ended wait — long CI — does not sit through it
either: it yields a **CI-PENDING report** (see **CI wait — monitor-parked**), so the synchronous call's
duration is bounded by real work. The multi-hour wait belongs to the parked state's Monitor, never to a
polling supervisor.

**Retain that verbatim report — it is relayed, not just parsed.** Parsing it to advance the state
machine (step 5) does not consume it: superagent must keep the exact returned text and reproduce it in
this tick's **Final Report — per tick** so the caller sees it on the CLI, plus surface any issue it
flags. Relaying the *small Final Report* verbatim is exactly the "ingests only the small Final Report"
contract below — it is the report, not the full execution trace.

Do **not** pass `isolation: worktree` to the `superplan` Agent call, and point the `superrun` bridge's
`--cwd` at the primary checkout root, never a worktree — `superplan`/`superrun` create and manage their
own worktrees/PRs, and forcing an outer worktree would conflict with that.

Everything around the dispatch stays in **superagent's own (parent) context, unchanged**: the pre/post
**Sync gate** + **be-sure** verification (L5) run in the parent and verify artifacts on local `main`
*after* the subagent returns; the **overlap lock** (L3) is held by the parent across the whole tick (the
subagent never touches it); and the heavy-step counter increments once in **Step 2**. Isolating the heavy
work is *why* the per-session threshold can be `SUPER_HEAVY_STEP_LIMIT` (default 6) (Step 0.5) — the parent ingests only the small Final
Report per tick (and relays it to the caller), not the full execution trace.

---

## CI wait — monitor-parked (never poll a long CI)

A `superrun` process that pushes a long CI lane does **not** block until CI finishes — per its own
Step 3a it returns a **CI-PENDING report** (leaf plan, root, worktree, branch, PR url, run ids) and
exits; a fresh process resumes the leaf later from that packet. The supervisor's job is to **park
the loop on that wait, not to poll it**:
neither the supervisor's context (a `gh run view` loop) nor the tick cadence (re-checking CI every
tick) may be spent watching a 60–120 min run. One wait = one resume signal.

**Parking (on receiving a CI-PENDING report, in the `WAITING FOR RUN` branch):**

1. Write a `ci_wait:` block into the loop-file frontmatter with these keys: `runs:` (all run ids,
   as an inline list of GitHub Actions run ids), `repo:` (the `owner/name` of the repository the
   runs live in — the PR's **base** repository, e.g. from `gh repo view --json nameWithOwner`; this is
   what lets the wrapper find the runs when the clone's remote is a fork), `branch:`, `pr:`, `leaf:`,
   `worktree:`, and `since: <ISO-8601 UTC timestamp, e.g. 2026-08-28T14:05:00Z>`. Set
   `status: WAITING FOR CI`. It must look exactly like this:

   ```yaml
   ci_wait:
     runs: [123456, 234567]      # GitHub Actions run ids — inline list; the wrapper's CI gate parses this block
     repo: <owner>/<name>        # where the runs live (PR base repo); the wrapper passes it as `gh run view --repo`
     branch: <branch>
     pr: <number>
     leaf: <plan path>
     worktree: <path>
     since: <ISO-8601 UTC timestamp>
   ```

   `ci_wait:` must be a top-level frontmatter key with `runs:` indented beneath it (not a `{…}`
   flow mapping) — that is the shape `superagent-tick.sh`'s `SUPER_CI_GATE` reads. `since:` must be
   ISO-8601 UTC: the wrapper compares it against `SUPER_CI_MAX_WAIT_MIN` (default 180) and, once a
   park is older than that with runs still not `completed`, notifies the operator once (`ci-stale`)
   and lets the session run each interval so a run stuck in `queued`/`waiting` cannot park the loop
   silently forever. A session that lands in the external branch with runs still running should
   treat that as the stale case: inspect the runs (`gh run view <id>`), and either re-park with a
   fresh `since:` if they are genuinely progressing, or cancel/re-trigger and re-park.
2. **Arm the resume signal — by driver:**
<!-- cc-only:start -->
   - **cron (in-session):** arm **one `Monitor`** (`persistent: true`) that `curl`s
     `https://api.github.com/repos/<owner>/<repo>/actions/runs/<id>` for **each** id in `ci_wait.runs`
     (auth: `TOK=$(gh auth token)` captured before arming — prefer `curl` for polling inside a Monitor:
     on hosts where `SUPER_GH_DISABLE_SANDBOX=true`, `gh` cannot run *inside* the Monitor at all (it
     needs keychain access), so `curl` to `api.github.com` is the only option there; where
     `SUPER_GH_DISABLE_SANDBOX=false`, `curl` is still preferred for consistency) and fires the
     first time **every** run is `status: completed`, emitting each `id: conclusion` pair. It MUST
     emit on **any** terminal state (success / failure / cancelled / timed_out) — a success-only
     filter is silent through a crash, and silence looks like "still running". Then **suspend the
     tick cadence for the wait**: `CronDelete cron_id`, clear `cron_id`, and log `parked on CI —
     cron driver suspended, Monitor armed`. No ticks fire while parked; the Monitor's fire is the
     only resume signal.
<!-- cc-only:end -->
   - **external:** the tick is a fresh headless session — a Monitor cannot outlive it, and the
     scheduler is user-managed (never touched). The scheduler keeps firing ticks; the `WAITING FOR
     CI` tick branch (Step 1) is the cheap check.
3. **`release_lock()` and end the tick** (report the parking in this tick's Final Report). The lock
   is NOT held across the wait — a multi-hour CI must never age the lock into L3's `SUPER_LOCK_STEAL_MIN`-minute (default 90) steal.

**Resuming (all runs terminal):**

1. Entry points: the **Monitor fired** (cron — harness re-invokes the session), or an **external
   `WAITING FOR CI` tick's one batched curl** found every run `completed`, or a **form-(B) RESUME**
   found `status: WAITING FOR CI` (see below). `acquire_lock()` if not already held this tick.
2. Verify the conclusions independently (one `gh run view <id>` per run — with the sandbox override if
   `SUPER_GH_DISABLE_SANDBOX=true` — or the same batched curl) — never advance on the Monitor's report
   alone.
3. **Resume `superagent:superrun`:** the process that yielded has exited, so there is nothing to
   message — dispatch a **fresh** `superrun` process exactly as in `WAITING FOR RUN` step 3 (bridge,
   `--tools executor`, foreground Bash, `timeout: 7200000`; model per **Model resolution** under
   **Subagent dispatch**, from `SUPER_MODEL_EXECUTOR`), with a prompt that instructs it to invoke
   `superagent:superrun` with the full `ci_wait` packet + each run's conclusion via its
   **Resume entry — post-CI**. It returns the real Final Report.
4. Continue the normal `WAITING FOR RUN` steps 4–6 on that report (sync gate post + be-sure, parse →
   next state, iteration log). Clear the `ci_wait:` block.
   **cron:** re-arm the driver (`CronCreate`, record the new `cron_id`) so ticks resume. <!-- cc-only -->
5. The heavy-skill count for this leaf was already incremented on the tick that dispatched
   `superrun` (Step 2); the park and resume ticks increment `iteration` but **not**
   `session_skill_count` again.

<!-- cc-only:start -->
**RESUME / restart while parked (form B, or a fresh cron session):** a persisted `WAITING FOR CI`
whose Monitor died with its session is recovered on the standard RESUME path — check the recorded
runs once (batched curl or `gh run view`): all terminal → run the resume flow above this tick; any
still running → re-arm the **Monitor** (cron — but do **not** `CronCreate` a driver while parked; the
Monitor is the sole resume signal, and the driver is re-armed on ci-resume) or just report the parked
state (external — the scheduler's ticks keep checking) and exit.
<!-- cc-only:end -->
<!-- cursor-only:start
**RESUME / restart while parked (form B):** a persisted `WAITING FOR CI` is recovered on the standard
RESUME path — check the recorded runs once (batched curl or `gh run view`): all terminal → run the
resume flow above this tick; any still running → report the parked state (the scheduler's ticks keep
checking) and exit.
cursor-only:end -->
<!-- codex-only:start
**RESUME / restart while parked (form B):** a persisted `WAITING FOR CI` is recovered on the standard
RESUME path — check the recorded runs once (batched curl or `gh run view`): all terminal → run the
resume flow above this tick; any still running → report the parked state (the scheduler's ticks keep
checking) and exit.
codex-only:end -->

---

## Step 1 — Dispatch on `status` (invoke AT MOST ONE skill this tick)

### `DONE`
A tick fired after completion (form A already no-ops `DONE` before Step 1; this covers the cron path).
Report it, **do not change status**, `stop_driver()`, `release_lock()`, and exit. (Script-driven
external loops: the tick wrapper self-disarms the scheduler entry after this session ends — never run
`uninstall-timer.sh` from inside the session; see superloop L2/`stop_driver()`.)

### `WAITING FOR INPUT`
A prior iteration escalated a decision the panel could not resolve. Read the `## Pending decision`
block.
- **Answer supplied** (recorded under `## Pending decision`, or given in the re-invoking
  `/superagent` prompt) → append it to `## Decisions`, clear the pending block, restore `status` from
  `prior_status`, and **fall through** to that branch this tick, applying the decision as guidance to
  the next skill invocation.
- **No answer yet** → branch on context:
  - **Interactive (a person is at the session — typically `cron`/attended):** `AskUserQuestion`. On an
    answer, proceed as above. If it genuinely can't be answered, **pause** (`stop_driver()`),
    `release_lock()` — a later `/superagent <PLAN.md>` resumes.
  - **Non-interactive scheduled tick (external Desktop/headless CLI, fresh session — no one to
    prompt):** do **not** block on `AskUserQuestion` (in a headless `claude -p` tick
    there is no TTY to answer, so it would stall the one-shot session). Ensure `## Pending decision`
    holds the question + an explicit *"write your choice as `answer: <option>` under this block"*
    instruction, `release_lock()`, and exit.
    The scheduler keeps firing, but for loops driven by the shipped `scripts/` wrapper the fire is
    **free while unanswered**: `superagent-tick.sh` reads the loop file in bash and exits without a
    session until an `answer:` line exists under `## Pending decision` (`SUPER_INPUT_GATE`, default
    on); it also notifies the operator once on the transition (`SUPER_NOTIFY_CMD`, else a desktop
    notification). A human answers **and resumes immediately** with
    `$SUPERAGENT_SCRIPTS/answer.sh <slug> "<option>"` (writes the line under the lock, kicks a tick),
    from `superagent:superagent-monitor`, or by editing the loop file directly (next scheduled fire
    resumes).

### `PLANNING` or `RUNNING` (crash recovery)
These are transient *within* a tick (superagent sets them, runs the skill synchronously, then sets the
next status — all in one turn). Ticks never overlap: in `cron` mode they fire between turns; in
`external` mode the **lock** serializes them. So a **persisted** `PLANNING`/`RUNNING` means a crashed
prior tick (which also left a stale lock that `acquire_lock()` steals immediately when its recorded
owner PID is dead, else after `SUPER_LOCK_STEAL_MIN` minutes (default 90)). **Self-heal:** log
a recovery note, reset `PLANNING → WAITING FOR PLAN` / `RUNNING → WAITING FOR RUN`, and fall through to
that branch this tick. (`WAITING FOR CI` is **not** a crash — it is the durable parked state; see its
own branch.)

The same mapping applies **in-flight**: if this tick's own dispatch is interrupted and the step cannot
be completed (superloop L2, tick teardown invariant), apply the reset **now** — log the interruption,
reset the transient status to its ready state, `release_lock()`, and end the tick with a normal
report so the next tick retries. Never end the tick asking what to do, and never leave
`PLANNING`/`RUNNING` persisted on a normal exit.

### `WAITING FOR CI` (parked — the cheap branch)
The loop is parked on the run ids in `ci_wait.runs` (see **CI wait — monitor-parked**).
<!-- cc-only:start -->
- **cron:** strict no-op — the Monitor owns the wait. Read status, `release_lock()`, exit. No `gh`,
  no `curl`, no subagent. (Normally no cron tick even fires here — the driver was suspended at
  parking; this covers a straggler tick or a manual `--tick`.)
<!-- cc-only:end -->
- **external:** run **one batched `curl`** over all ids in `ci_wait.runs` (auth `gh auth token` — with
  the sandbox override if `SUPER_GH_DISABLE_SANDBOX=true`; this is the only network call this tick).
  - (Loops driven by the shipped `scripts/` wrapper normally never reach this branch while a run is
    still in progress: `superagent-tick.sh` performs the same `gh run view` check in bash before
    launching the session and exits 0 while any run is not `completed` — `SUPER_CI_GATE`, default
    on. A session that does land here with runs still running means the gate was off, `gh`
    failed in the wrapper, or the park exceeded `SUPER_CI_MAX_WAIT_MIN` (stale wait — see
    **Parking**); do the single query as written, and in the stale case decide whether to re-park
    with a fresh `since:` or cancel/re-trigger the run.)
  - Any run still not `completed` → `release_lock()`, exit. Nothing else this tick.
  - All terminal → run the **Resuming** flow (CI wait — monitor-parked) this tick: verify, dispatch
    the resume process, then continue `WAITING FOR RUN` steps 4–6 on its Final Report.

### `WAITING FOR PLAN`
1. **Sync gate (pre).** Run `sync_main()` so `superplan` reads a fresh tree. If it STOPs, pause and end
   this tick.
2. Set `status: PLANNING`, write the loop file.
3. **Dispatch `superagent:superplan` in its own subagent** (Agent tool, `subagent_type: general-purpose`,
   `run_in_background: false` — wait on the tool result, never poll; see **Subagent dispatch**). Model
   per **Model resolution** (see **Subagent dispatch**), from `SUPER_MODEL_PLANNER`.
   Instruct the subagent to invoke the `superagent:superplan` skill (Skill tool) with
   `<PLAN.md> = master_plan`, **no `<TOPIC>`** — its `supertraverse` descent finds the next deepest
   unplanned step across all levels (including sub-masters) — and to **return superplan's complete Final
   Report verbatim as its final message** (step 5 parses that report). superagent never invokes
   `superplan` inline in its own context.
4. **Sync gate (post + be-sure).** Run `sync_main()`, then verify `superplan`'s reported plan file and
   immediate-parent/ancestor progress-row edits are present and tracked on local `main`. If a reported
   artifact is missing or the tree can't reconcile, escalate (STOP) — do not advance, and surface the
   failure in this tick's `Findings & issues` line.
5. **Retain `superplan`'s verbatim Final Report for relay** (it is reproduced in this tick's **Final
   Report — per tick**) and **note any issue it surfaces** — a CRITICAL / ⚠️ finding, a plan error, a
   seed contradiction, a `not-traversable` result — for the `Findings & issues` line, independent of
   whether it triggers escalation. Then parse the report → next state:
   - **Plan type: implementation plan** → `status: WAITING FOR RUN`, `plan_exhausted: false`.
   - **Plan type: seed/master plan** (a sub-master was written) → `status: WAITING FOR PLAN`,
     `plan_exhausted: false` (next tick descends into it and plans deeper).
   - **`No available task to plan …`** (superplan's "none") → `plan_exhausted: true`,
     `status: WAITING FOR RUN`. Do **not** conclude DONE yet — planned-but-unexecuted leaves may
     remain; let `superrun` check.
   - **`not-traversable` / `I need to know the plan file`** → ERROR: report, `stop_driver()`,
     `release_lock()`.
6. Append an iteration-log entry (skill, result, plan path, PR URL). Go to **Step 2**.

### `WAITING FOR RUN`
1. **Sync gate (pre).** Run `sync_main()` so `superrun`'s traversal reads a fresh tree. If it STOPs,
   pause and end this tick.
2. Set `status: RUNNING`, write the loop file.
3. **Dispatch `superagent:superrun` in its own CLI process** — **not** an Agent-tool subagent: run
   `role-bridge.sh --tools executor` from your Bash tool, foreground, `timeout: 7200000`, after the
   `BASH_MAX_TIMEOUT_MS` preflight (all in **Subagent dispatch**). Model per **Model resolution**
   (see **Subagent dispatch**), from `SUPER_MODEL_EXECUTOR`.
   The prompt instructs it to invoke the `superagent:superrun` skill (Skill tool) with
   `<PLAN.md> = master_plan` (the root) and to **return superrun's complete Final Report verbatim as its
   final message** (step 5 parses that report) — or, if it queues long CI, its **CI-PENDING report**
   (step 5's park case; a fresh process resumes it). superagent never invokes `superrun` inline in its
   own context, and never as a subagent (issue #25).
4. **Sync gate (post + be-sure).** If `superrun` returned a **CI-PENDING report** (see step 5),
   skip this step — nothing merged yet; it runs on the resume tick instead. Otherwise run
   `sync_main()`, then verify `superrun`'s reported merges landed
   on local `main`: the leaf's closeout report exists and is tracked, and (if the code PR merged) its
   squash commit is in `origin/main` history. A merged code PR but stale local `main` is the exact bug
   this gate exists for — reconcile (ff-pull) or escalate. Do not advance on an unverified merge, and
   surface the failure in this tick's `Findings & issues` line.
5. **Retain `superrun`'s verbatim Final Report for relay** (it is reproduced in this tick's **Final
   Report — per tick**) and **note any issue it surfaces** — a CRITICAL / ⚠️ finding, an implementation
   inconsistency, a BLOCKED task, a CI-red code PR — for the `Findings & issues` line, independent of
   whether it triggers escalation. Then parse the report → next state:
   - **CI-PENDING report** (not a Final Report — `superrun` queued long CI and yielded) → **park**:
     run the **Parking** flow (CI wait — monitor-parked): write `ci_wait:`, `status: WAITING FOR CI`,
     arm the resume signal per driver, and end the tick there (skip step 4's be-sure — nothing merged
     yet; the sync gate + be-sure run on the resume tick instead). Not a failure, not BLOCKED.
   - **Executed a leaf** (code PR merged, closeout PR merged) → `status: WAITING FOR PLAN`,
     `plan_exhausted: false` (more may remain to plan/run).
   - **`none`** (no incomplete implementation plan to execute):
     - `plan_exhausted == true` → **`status: DONE`** (nothing to plan AND nothing to run = complete).
     - else → `status: WAITING FOR PLAN` (steps remain to be planned).
   - **BLOCKED** (a task could not complete) **or code PR CI-red** → **do not terminate.** Run the
     **Decision-escalation ladder** (below) on the blocker. If the panel converges → apply it (retry
     `superagent:superrun` with guidance — per **Subagent dispatch**, model per its **Model
     resolution** from `SUPER_MODEL_EXECUTOR` — route to `WAITING FOR PLAN` for a re-plan, or mark
     the step declined),
     log the decision, continue. If the panel cannot converge → escalate via `WAITING FOR INPUT`.
     Never silently spin on a blocked plan.
6. Append an iteration-log entry (skill, result, code PR + closeout PR URLs). Go to **Step 2**.

---

## Step 2 — Persist, then let the driver continue (or stop it)

1. Increment `iteration`. **If a heavy skill (`superplan`/`superrun`) was invoked this tick, increment
   `session_skill_count`** (the Step 0.5 handoff trigger; guard / escalation / handoff ticks that ran
   no heavy skill do **not** increment it). A parked leaf counts **once**: the tick that dispatched
   `superrun` (and then parked on its CI-PENDING yield) increments; the later ci-resume tick — even
   one that dispatches a fresh resume subagent — does **not** increment again. Write the loop file (frontmatter + appended log). Plain
   Write — no commit, no PR (the file is gitignored).
2. **Terminal** (`DONE`, hard error, or `WAITING FOR INPUT` unanswered in an unattended run): print a
   final summary (plus the pending question + resume instructions for the input case) and
<!-- cc-only:start -->
   `stop_driver()` (cron → `CronDelete`; external → on `DONE` the shipped tick wrapper self-disarms
   the scheduler entry after the session; Desktop-routine or hand-rolled schedulers → instruct the
   user to disable the routine). No more
<!-- cc-only:end -->
<!-- cursor-only:start
   `stop_driver()` (on `DONE` a shipped-script-driven scheduler entry self-disarms after the session;
   otherwise instruct the user to disable the scheduler entry). No more
cursor-only:end -->
<!-- codex-only:start
   `stop_driver()` (on `DONE` a shipped-script-driven scheduler entry self-disarms after the session;
   otherwise instruct the user to disable the scheduler entry). No more
codex-only:end -->
   ticks fire.
3. **Otherwise**: do nothing to the driver — the next `--tick <loop-file>` fires on its own (the
   in-session `cron` job, or the external Desktop routine / OS-cron entry, depending on `driver`).
4. **Always `release_lock()`** before the turn ends — terminal or not.
5. **Teardown invariant (superloop L2):** the persisted `status` at end-of-turn is never a
   `PLANNING`/`RUNNING` this tick wrote (an interrupted dispatch is reset to its ready state
   in-flight, using the mapping defined in Step 1's crash-recovery branch), and the turn never ends
   with a question — a decision needing the user ends only via `WAITING FOR INPUT` + `## Pending
   decision`. The external tick wrapper enforces this: a `0`-exit session that leaves a transient
   status (with no live peer tick holding the lock) is re-flagged as a loud failed tick (exit 10).

**One-skill-per-iteration is structurally guaranteed:** a `--tick` runs Step 1 → at most one of
`superplan`/`superrun` → Step 2. Ticks never overlap — in `cron` mode they fire between turns; in
`external` mode the **lock** serializes fresh-session ticks (a long tick just makes the next fire
no-op until the lock releases). Ticks are idempotent — a tick that finds nothing to do no-ops.

---

## Drivers — attended (in-session) vs Desktop/headless (clean context)

The two drivers (Driver A `cron`, Driver B `external`), the context model, the overlap lock
(`acquire_lock()` / `release_lock()`), and `stop_driver()` are **superloop L2 + L3**. superagent arms
`/superagent --tick <loop-file>` as its tick prompt (`<consumer>` = `superagent`).

<!-- cc-only:start -->
**Running from the Claude CLI.** For `external` mode the tick fires
in a fresh headless `claude -p` session per interval; because print mode cannot run slash commands, and
Skill-tool semantics for a disable-model-invocation skill in headless print mode are unverified, the
scheduler drives it by asking the CLI to *read `skills/superagent/SKILL.md` directly (at the plugin's
installed location) and run exactly one `--tick`* (superloop L2, Driver B). The loop's own internal
`superagent:superplan` / `superagent:superrun` dispatches still go through the Skill tool once the
session is running. `${CLAUDE_PLUGIN_ROOT}/scripts/` packages the whole
thing (the tick wrapper, a per-goal scheduler entry — systemd user timer on Linux, launchd
LaunchAgent on macOS — and
bootstrap/install/uninstall/console-watch/status helpers); the runbook is
[scripts/README.md](../../scripts/README.md), which documents the `SUPERAGENT_SCRIPTS` convention
runnable examples use to locate this plugin's installed `scripts/` directory. Monitor and control
running loops (multi-instance: list state, answer `WAITING FOR INPUT`, drain/stop/uninstall/re-arm) with
the `superagent-monitor` skill. The driver must never `--resume` (fresh
context per tick — L4 is a no-op in `external` mode, so the loop runs straight to `DONE`); an
interactive monitoring/answering console is a separate plane that can be started/stopped independently.
<!-- cc-only:end -->
<!-- cursor-only:start
**Running from the Cursor CLI.** For `external` mode the tick fires in a fresh headless `agent -p`
session per interval; the scheduler drives it by asking the CLI to *read `skills/superagent/SKILL.md`
directly (at the plugin's installed location) and run exactly one `--tick`* (superloop L2, Driver B).
The loop's own internal `superagent:superplan` / `superagent:superrun` dispatches still go through the
skill mechanism once the session is running, so the plugin must be installed and enabled for headless
sessions (or passed via `--plugin-dir`). **Port status:** the shipped `scripts/` wrappers still invoke
the Claude CLI — until they are ported, schedule the Driver B `agent -p` recipe directly. The driver
must never `--resume` (fresh context per tick — L4 is a no-op in `external` mode, so the loop runs
straight to `DONE`); an interactive monitoring/answering console is a separate plane that can be
started/stopped independently.
cursor-only:end -->
<!-- codex-only:start
**Running from the Codex CLI.** For `external` mode the tick fires in a fresh headless `codex exec`
session per interval; the scheduler drives it by asking the CLI to *read the supervisor's SKILL.md
directly (at the plugin's installed location —
`<marketplace-root>/plugins/superagent/skills/superagent/SKILL.md`) and run exactly one `--tick`*
(superloop L2, Driver B). The loop's own internal `superagent:superplan` / `superagent:superrun`
dispatches still go through the skill mechanism once the session is running, so the plugin must be
installed via the Codex plugin marketplace (`codex plugin marketplace add <plugin-repo>/codex`, then
`codex plugin add superagent@superagent`) — there is no per-invocation `--plugin-dir` analog. The
shipped `scripts/` wrappers are harness-aware: `SUPER_HARNESS=codex` makes `superagent-tick.sh` fire
`codex exec` (sandbox per `SUPER_CODEX_SANDBOX`, default `danger-full-access`; auth via `OPENAI_API_KEY`
in `.env` or the CLI's stored login). The driver must never resume a prior session (fresh context per
tick — L4 is a no-op in `external` mode, so the loop runs straight to `DONE`); an interactive
monitoring/answering console is a separate plane that can be started/stopped independently.
codex-only:end -->

---

## Decision-escalation ladder — autonomy posture

Resolve raised decisions per **superloop L7** (Rung 1 = 3-subagent panel, ≥2/3 converge; Rung 2 = user
escalation via `WAITING FOR INPUT` / `AskUserQuestion` / durable `answer:` polling). superagent's
**trigger surface**: a CRITICAL / ⚠️ finding, a `not-traversable` result, or a `superrun` BLOCKED /
CI-red Final Report. superagent's **option-set**: {retry `superrun` with guidance / route to `WAITING
FOR PLAN` for a re-plan / mark the step declined}.

**Always surface the outcome to the caller.** Whenever the ladder fires — even when the Rung-1 panel
resolves it **autonomously** — name the triggering issue and how it was resolved (e.g. "panel 2/3:
re-plan") in this tick's `Findings & issues` line. Recording it under `## Decisions` in the gitignored
loop file is not enough: the caller must learn that an issue arose and what the loop did about it. (A
Rung-2 escalation additionally populates the `⚠️ Needs you` block.)

---

## Final Report — per tick

After each tick, report to the caller and end the turn. The report has two jobs beyond the tick header:
**(a) relay the delegated skill's verbatim Final Report** so the caller sees on the CLI exactly what
`superplan` / `superrun` produced — the rich output (files created/modified, findings, PRs) that would
otherwise stay buried in the subagent; and **(b) always surface issues** — every problem observed this
tick, even one the loop already resolved itself.

    ## Superagent tick <iteration>

    **Goal:** <master_plan path>
    **Loop file:** <loop-file path>
    **This tick:** <superplan | superrun | park (CI wait) | ci-resume | guard | resume | escalation> — <one-line result>
    **Status:** <new status>   (driver: <cron|external>, <scheduled / stopped / paused / parked on CI>)

    **PRs this tick:** <plan/code/closeout PR urls, or none>

    **Findings & issues:** <every problem observed this tick — CRITICAL / ⚠️ findings, plan errors,
    implementation inconsistencies, BLOCKED / CI-red outcomes, `not-traversable`, sync-gate / be-sure
    failures, and any escalation-ladder decision (including how a Rung-1 panel resolved it
    autonomously). Surface these even when the loop handled them itself. If genuinely none: none>

    ### Delegated skill report (verbatim)
    <the complete `superplan` / `superrun` Final Report exactly as the subagent returned it. A park
    tick relays the CI-PENDING report verbatim instead (with the armed Monitor / awaited run ids
    named in "This tick"). For a tick that dispatched no heavy skill — guard / resume /
    crash-recovery / escalation-only — write: none (no skill dispatched this tick)>

    ⚠️ **Needs you:** <only when status == WAITING FOR INPUT — the pending question + how to answer
    (interactive prompt, or `answer.sh <slug> "<option>"` for a scheduled loop)>

On **DONE**, replace the body with a completion summary: every step planned + executed, the PRs merged,
<!-- cc-only:start -->
and confirmation the driver was stopped — `cron` → `CronDelete`d; `external` → shipped-script loops:
note that the tick wrapper self-disarms the scheduler entry when this session ends
(`SUPER_AUTO_DISARM_ON_DONE`); Desktop-routine loops: remind the user to disable the routine. Include
the final tick's verbatim **Delegated skill
<!-- cc-only:end -->
<!-- cursor-only:start
and confirmation the driver was stopped — shipped-script loops: note that the tick wrapper
self-disarms the scheduler entry when this session ends (`SUPER_AUTO_DISARM_ON_DONE`); otherwise
remind the user to disable the scheduler entry. Include the final tick's
verbatim **Delegated skill
cursor-only:end -->
<!-- codex-only:start
and confirmation the driver was stopped — shipped-script loops: note that the tick wrapper
self-disarms the scheduler entry when this session ends (`SUPER_AUTO_DISARM_ON_DONE`); otherwise
remind the user to disable the scheduler entry. Include the final tick's
verbatim **Delegated skill
codex-only:end -->
report** and any still-open `Findings & issues`.

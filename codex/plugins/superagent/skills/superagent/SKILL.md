---
name: superagent
description: Use when asked to drive a goal's root seed/master plan (PLAN.md) to completion unattended, or when a scheduler fires `--tick` on an existing loop-status file — the autonomy supervisor for the super* plan-tree lifecycle, driven in-session (cron) or by an external scheduler in a fresh context per tick.
argument-hint: <PLAN.md> [--driver=cron|desktop]   (or: --tick <loop-file>)
disable-model-invocation: true
license: all rights reserved
related skills: superloop, superplan, superrun, supertraverse, superfinish
---

<!-- GENERATED FILE — Codex build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-codex-skills.sh. -->

> **Codex build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` and `Monitor` tools do **not** exist on Codex — treat
>   any residual mention of them as inapplicable and NEVER attempt those tool calls.
> - Tool mapping: "Agent tool" / "spawn a subagent" = the `spawn_agent` tool (multi-agent v2 —
>   wait for the child's result). Role pins from `.superenv` map to its parameters:
>   `SUPER_MODEL_<ROLE>` → `model`, `SUPER_EFFORT_<ROLE>` → `reasoning_effort`
>   (`inherit` = omit the parameter). There are NO `.claude/agents/` definition files in this
>   build — where a skill says "dispatch via subagent_type: super-<role>", pass the role's
>   resolved model/effort as spawn parameters instead. "Skill tool" = reference the skill by
>   name in the conversation. `AskUserQuestion` / `AskQuestion` = ask the user in chat (attended
>   sessions only — never in a headless tick). `EnterWorktree` = not available; use
>   `git worktree` via shell.
> - `${SUPER_PLUGIN_ROOT}` in commands and paths = this plugin's installed root (the directory
>   containing `skills/` and `templates/`, two levels above each SKILL.md — for a marketplace
>   install that is the plugin cache copy; in the source repository it is
>   `<repo>/codex/plugins/superagent`). Substitute its absolute path wherever it appears.
>   Exception: the external-driver `scripts/` helpers (`superagent-tick.sh`, `launch.sh`, …) are
>   not packaged inside the plugin — they live in the plugin source repository. Read
>   `${SUPER_PLUGIN_ROOT}/scripts/` as that repository's `scripts/` directory (the
>   `SUPERAGENT_SCRIPTS` convention in its scripts/README.md).
> - Skill lookup: this plugin installs via the Codex plugin marketplace; skills resolve by name
>   (e.g. `superplan`). The `superagent` supervisor skill is driven by reading its SKILL.md
>   directly (the external tick's file-read prompt), never invoked by name.

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
| "/superagent was run again — I'll start the loop" | NO. Check first. A non-terminal loop file = the scheduler entry is already the driver; report state and re-print setup, don't arm anything. Never start a second loop. |
| "A fresh/empty context means I lost the loop state" | NO. All state is in the loop file. A `--tick` works identically in a clean context (external driver) or an accumulating one (cron). Acquire the lock, read the file, run one tick. |
| "A skill raised a question — I'll just ask the user" | NO. First run the **subagent panel** (Decision-escalation ladder). Ask the user only if the panel cannot converge. |
| "The work is blocked — terminate the loop" | NO. Run the panel on the blocker first (retry / re-plan / decline / escalate). Stop the driver only when DONE or an escalation pauses the loop. |
| "superplan/superrun already did `git checkout main && pull`, so local is synced" | NO. That pull can silently fail or be skipped (worktree checkout error after a remote `--admin` merge; propagation race). Run the **Sync gate** before AND after every skill, and verify the merged artifacts are present locally — never advance on a stale tree. |
| "superrun yielded CI-PENDING — I'll poll `gh run view` / `gh run watch` in a loop until it finishes" | NO. **Park.** Record the CI packet, set `WAITING FOR CI`, release the lock, end the tick. Each later scheduled tick does ONE batched `curl` over the recorded run ids and exits unless every run is terminal. Per-tick heavy polling is the context waste the parked state exists to eliminate. |
| "A tick fired while WAITING FOR CI — I'll check the run status while I'm here" | ONE batched `curl` over the recorded run ids, then exit if any is still running — never a heavy dispatch. |
| "The dispatched subagent will run a long time — I'll run it in the background and check on it while I wait" | NO. **Wait, never poll.** Every heavy-skill dispatch is synchronous (`run_in_background: false`): the blocked Agent call waits at zero context cost and the Final Report arrives as the tool result. A background dispatch + `TaskOutput`/`TaskList` checks spends supervisor context on "still running" snapshots the synchronous return delivers for free. |

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
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
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

A structural no-op in this build (superloop L4): the external driver is the only driver and every tick
runs in a fresh context. Go straight to **Step 1**.

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

**Every heavy-skill invocation runs in its own subagent — superagent NEVER invokes `superplan` or
`superrun` inline in its own context.** When Step 1 reaches a `WAITING FOR PLAN` / `WAITING FOR RUN`
branch, dispatch the skill with the **Agent tool** (`subagent_type: general-purpose` — that type has the
full tool access `superplan`/`superrun` need: Bash, Edit/Write, git, `gh`, `EnterWorktree`, CI/Monitor
tools — and `run_in_background: false`; see **Synchronous dispatch** below). Instruct the subagent to:

1. invoke the named skill (`superagent:superplan` or `superagent:superrun`) via its **Skill tool** with `<PLAN.md> =
   master_plan` (and the per-branch arguments below), and
2. **return that skill's complete Final Report verbatim as its final message** — the subagent's final
   message is what superagent receives as the tool result, and the verbatim report is exactly what the
   per-branch step-5 parsing consumes. (One sanctioned exception: a `superrun` subagent that queued
   long CI returns a **CI-PENDING report** instead and stays resumable — that is a valid yield, not a
   failure; see **CI wait — monitor-parked**.)

**Model resolution — every heavy-skill dispatch site passes a model per its `.superenv` role key**
(`SUPER_MODEL_PLANNER` for `superplan`, `SUPER_MODEL_EXECUTOR` for `superrun` — including the
ci-resume's fresh subagent and escalation-ladder retries):

- `inherit` → omit the `model:` parameter (the subagent runs on the session model).
- A tier name (`sonnet` | `opus` | `haiku` | `fable`) → pass it as `model:`.
- A **full model ID** (matches `^claude-`, e.g. `claude-fable-5`) → the Agent tool's `model:`
  parameter is tier-enum-only and rejects it; instead dispatch with `subagent_type: super-planner` /
  `super-executor` — the per-role agent definition `superagent:init` generates in `.claude/agents/`,
  whose `model:` frontmatter carries the pin — and omit `model:`. If that definition is missing,
  that is a hard error: surface it (instruct a `superagent:init` re-run), never silently downgrade.

**Synchronous dispatch — the supervisor WAITS on the tool call; it never polls a running subagent.**
The harness runs Agent-tool subagents in the background by default, which hands back a task handle and
invites `TaskOutput`/`TaskList` status checks while the work runs — for a long `superplan`/`superrun`
that polling is pure supervisor-context waste. So every heavy-skill Agent call — the Step-1 dispatches,
the ci-resume's fresh subagent, an escalation-ladder retry — passes **`run_in_background: false`** and
**blocks until the subagent's final message returns as the tool result**. The blocked wait costs zero
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

Do **not** pass `isolation: worktree` to the Agent call — `superplan`/`superrun` create and manage their
own worktrees/PRs, and forcing an outer worktree would conflict with that.

Everything around the dispatch stays in **superagent's own (parent) context, unchanged**: the pre/post
**Sync gate** + **be-sure** verification (L5) run in the parent and verify artifacts on local `main`
*after* the subagent returns; the **overlap lock** (L3) is held by the parent across the whole tick (the
subagent never touches it); and the heavy-step counter increments once in **Step 2**. Isolating the heavy
work is *why* the per-session threshold can be `SUPER_HEAVY_STEP_LIMIT` (default 6) (Step 0.5) — the parent ingests only the small Final
Report per tick (and relays it to the caller), not the full execution trace.

---

## CI wait — monitor-parked (never poll a long CI)

A `superrun` subagent that pushes a long CI lane does **not** block until CI finishes — per its own
Step 3a it returns a **CI-PENDING report** (leaf plan, root, worktree, branch, PR url, run ids) and
stops, resumable later. The supervisor's job is to **park the loop on that wait, not to poll it**:
neither the supervisor's context (a `gh run view` loop) nor the tick cadence (re-checking CI every
tick) may be spent watching a 60–120 min run. One wait = one resume signal.

**Parking (on receiving a CI-PENDING report, in the `WAITING FOR RUN` branch):**

1. Write a `ci_wait:` block into the loop-file frontmatter — `runs:` (all run ids), `branch:`, `pr:`,
   `leaf:`, `worktree:`, `subagent:` (the dispatched superrun subagent's id/name, for the
   `SendMessage` resume), `since: <timestamp>`. Set `status: WAITING FOR CI`.
2. **Arm the resume signal — by driver:**
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
3. **Resume `superagent:superrun`:** if `ci_wait.subagent` is still reachable (same session — the cron/Monitor
   path), `SendMessage` it **once**: "CI run(s) <ids> terminal: <id: conclusion, …>. Finish the leaf
   now — Step 3a terminal-state branch, then closeout; return your Final Report." If it is not
   reachable (external fresh session; or `SendMessage` fails), dispatch a **fresh** general-purpose
   subagent (`run_in_background: false` — synchronous, like every heavy dispatch; model per
   **Model resolution** under **Subagent dispatch**, from `SUPER_MODEL_EXECUTOR`) instructed to invoke
   `superagent:superrun` with the full `ci_wait` packet + conclusions via its
   **Resume entry — post-CI**. Either way the subagent returns the real Final Report.
4. Continue the normal `WAITING FOR RUN` steps 4–6 on that report (sync gate post + be-sure, parse →
   next state, iteration log). Clear the `ci_wait:` block.
5. The heavy-skill count for this leaf was already incremented on the tick that dispatched
   `superrun` (Step 2); the park and resume ticks increment `iteration` but **not**
   `session_skill_count` again.

**RESUME / restart while parked (form B):** a persisted `WAITING FOR CI` is recovered on the standard
RESUME path — check the recorded runs once (batched curl or `gh run view`): all terminal → run the
resume flow above this tick; any still running → report the parked state (the scheduler's ticks keep
checking) and exit.

---

## Step 1 — Dispatch on `status` (invoke AT MOST ONE skill this tick)

### `DONE`
A tick fired after completion (form A already no-ops `DONE` before Step 1; this covers the cron path).
Report it, **do not change status**, `stop_driver()`, `release_lock()`, and exit.

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
    prompt):** do **not** block on `AskUserQuestion` (in a headless `codex exec` tick
    there is no TTY to answer, so it would stall the one-shot session). Ensure `## Pending decision`
    holds the question + an explicit *"write your choice as `answer: <option>` under this block"*
    instruction, `release_lock()`, and exit. The **scheduler keeps firing `--tick`**, which **polls**
    for the written answer and resumes the moment it appears — no driver teardown needed. A human can
    supply that answer from an independent interactive console (see the CLI runbook), or by editing the
    loop file directly.

### `PLANNING` or `RUNNING` (crash recovery)
These are transient *within* a tick (superagent sets them, runs the skill synchronously, then sets the
next status — all in one turn). Ticks never overlap: in `cron` mode they fire between turns; in
`external` mode the **lock** serializes them. So a **persisted** `PLANNING`/`RUNNING` means a crashed
prior tick (which also left a stale lock that `acquire_lock()` steals immediately when its recorded
owner PID is dead, else after `SUPER_LOCK_STEAL_MIN` minutes (default 90)). **Self-heal:** log
a recovery note, reset `PLANNING → WAITING FOR PLAN` / `RUNNING → WAITING FOR RUN`, and fall through to
that branch this tick. (`WAITING FOR CI` is **not** a crash — it is the durable parked state; see its
own branch.)

### `WAITING FOR CI` (parked — the cheap branch)
The loop is parked on the run ids in `ci_wait.runs` (see **CI wait — monitor-parked**).
- **external:** run **one batched `curl`** over all ids in `ci_wait.runs` (auth `gh auth token` — with
  the sandbox override if `SUPER_GH_DISABLE_SANDBOX=true`; this is the only network call this tick).
  - Any run still not `completed` → `release_lock()`, exit. Nothing else this tick.
  - All terminal → run the **Resuming** flow (CI wait — monitor-parked) this tick: verify, dispatch
    the resume subagent, then continue `WAITING FOR RUN` steps 4–6 on its Final Report.

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
3. **Dispatch `superagent:superrun` in its own subagent** (Agent tool, `subagent_type: general-purpose`,
   `run_in_background: false` — wait on the tool result, never poll; see **Subagent dispatch**). Model
   per **Model resolution** (see **Subagent dispatch**), from `SUPER_MODEL_EXECUTOR`.
   Instruct the subagent to invoke the `superagent:superrun` skill (Skill tool) with
   `<PLAN.md> = master_plan` (the root) and to **return superrun's complete Final Report verbatim as its
   final message** (step 5 parses that report) — or, if it queues long CI, its **CI-PENDING report**
   (step 5's park case; the subagent stays resumable). superagent never invokes `superrun` inline in its
   own context.
4. **Sync gate (post + be-sure).** If the subagent returned a **CI-PENDING report** (see step 5),
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
   `stop_driver()` (instruct the user to disable the scheduler entry). No more
   ticks fire.
3. **Otherwise**: do nothing to the driver — the next `--tick <loop-file>` fires on its own (the
   in-session `cron` job, or the external Desktop routine / OS-cron entry, depending on `driver`).
4. **Always `release_lock()`** before the turn ends — terminal or not.

**One-skill-per-iteration is structurally guaranteed:** a `--tick` runs Step 1 → at most one of
`superplan`/`superrun` → Step 2. Ticks never overlap — in `cron` mode they fire between turns; in
`external` mode the **lock** serializes fresh-session ticks (a long tick just makes the next fire
no-op until the lock releases). Ticks are idempotent — a tick that finds nothing to do no-ops.

---

## Drivers — attended (in-session) vs Desktop/headless (clean context)

The two drivers (Driver A `cron`, Driver B `external`), the context model, the overlap lock
(`acquire_lock()` / `release_lock()`), and `stop_driver()` are **superloop L2 + L3**. superagent arms
`/superagent --tick <loop-file>` as its tick prompt (`<consumer>` = `superagent`).

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
    (interactive prompt, or `answer:` in the loop file for a scheduled loop)>

On **DONE**, replace the body with a completion summary: every step planned + executed, the PRs merged,
and confirmation the user was reminded to disable the scheduler entry. Include the final tick's
verbatim **Delegated skill
report** and any still-open `Findings & issues`.

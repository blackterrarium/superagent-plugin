---
name: superloop
description: Shared autonomy-loop chassis — the gitignored loop-status state file, the cron/external driver, the overlap lock, the context-handoff (session skill-budget) gate, the sync gate, the PR-merge discipline, and the 3-subagent escalation ladder. A clause library (L1–L7) invoked via the Skill tool by autonomy-driver skills (superagent today) to avoid re-implementing the loop machinery.
license: MIT
---

<!-- GENERATED FILE — Pi build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-pi-skills.sh. -->

> **Pi build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` / `Monitor` / `AskUserQuestion` tools do **not** exist
>   on Pi — treat any residual mention as inapplicable and NEVER attempt those tool calls.
> - Tool mapping in the SUPERVISOR (`superagent`, `superloop`): "Agent tool" / "dispatch a
>   subagent" = a blocking `bash` call to `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh`
>   (`superplan`, `superrefine`, `superreplan`, `superrun`) or
>   `${SUPER_PLUGIN_ROOT}/scripts/bridge-fanout.sh` (the L7 panel),
>   per the Pi-specific guidance embedded in those skills. The supervisor never uses a subagent tool.
> - Tool mapping in `superrun` / `superbuild` (the task-loop controller): "dispatch a subagent" = the `subagent` tool
>   from the `pi-subagents` package with `async: false`, one child per call; role pins ride the
>   `.pi/agents/super-<role>.md` definitions `init` generates. `pi-subagents` ≥ 0.58.0 is required;
>   if the tool is absent, stop and report the missing prerequisite. No sequential fallback.
> - "Skill tool / invoke skill X" = `read` `${SUPER_PLUGIN_ROOT}/skills/X/SKILL.md` and follow it
>   (`/skill:` commands are interactive-only). No other skill package is required.
> - `${SUPER_PLUGIN_ROOT}` = the plugin repository's `pi/` directory (two levels above each
>   SKILL.md). It contains `skills/`, `templates/`, and `scripts/` (`role-bridge.sh`,
>   `bridge-fanout.sh`, `_common.sh`, `prd-lint.sh`, `supereval.sh`, `workspace-state.py`, `superbuild.sh`, `_evalspec.sh`). The external-driver wrappers (`superagent-tick.sh`,
>   `launch.sh`, …) live in the repository's top-level `scripts/` — one directory up.
> - `EnterWorktree` = not available; in `github` mode use `git worktree` via `bash`. In `none`
>   mode the canonical local-workspace override applies and no git command is allowed.

# Superloop

The single source of truth for the **autonomy-loop chassis** — the driver-agnostic machinery a `super*`-style
unattended supervisor needs to drive a goal to completion across many ticks: where loop state lives, how a
tick is fired and serialized, when to hand off for a fresh context, how to keep the local tree synced around
every merge, and how to resolve a raised decision without a human. It owns the **chassis**, not the **work
model**: the caller supplies *what happens each tick* and *what "done" means*.

This is the autonomy analogue of `supertraverse` (plan-tree navigation) and `superauthor` (plan authoring).
Like them, superloop is a **clause library**: the calling skill (e.g. `superagent`) invokes it via the Skill
tool and carries out the clauses **L1–L7 inline with its own file / Bash / Skill / Cron tools**. **Superloop
itself reads nothing, writes nothing, runs nothing, and commits nothing** — the **caller** owns every read,
write, Cron call, and commit. The clauses define *how* the shared machinery works; the caller supplies the
work-model-specific specifics.

## Repo configuration (.superenv)

Resolve project context before any workflow action by sourcing `${SUPER_PLUGIN_ROOT}/scripts/_common.sh` under bash (it refuses zsh and other shells — wrap the call in `bash -c '…'` when your shell is not bash) and calling `superagent_load_context "$PWD" run` (lifecycle control commands first load the registered `SUPERAGENT_PROJECT_ROOT`). Use its exported physical `REPO` and validated `SUPER_GIT_MODE`. Resolution is process environment > nearest/explicit project `.superenv` > packaged default; missing mode means `github`. In `none`, never run git, gh, GitHub API, credential discovery, worktree, commit, push, PR, merge, sync, or CI-poll operations. An existing `.git` directory does not change this rule.

## Vault root

Resolve `SUPER_GOAL_ROOT` (above). If it starts with `/` or `~`, the vault is **external**:
`<vault_root>` is that path (`~` expanded to `$HOME`, one trailing `/` stripped), resolved physically
(`cd "<path>" && pwd -P`) so it matches the paths `launch.sh` stores, and the vault is its own git
repository outside the checkout. Otherwise `<vault_root>` is `<primary_root>/<SUPER_GOAL_ROOT>`
(`primary_root` = the physical `REPO` exported by `superagent_load_context`). Every goal
folder, project folder, loop-status file and lock derives from `<vault_root>`; **never join
`SUPER_GOAL_ROOT` onto the checkout root by hand.** The same rule is `vault_root` /
`vault_is_external` in `scripts/_common.sh`.

## Subroutine contract — read before applying the clauses

When `superagent` (or any autonomy-driver skill) invokes this skill via the Skill tool, you (the calling
agent) are running superloop as **one step inside the caller's workflow**, not as a standalone task. After
you apply a clause, you **MUST return control to the calling skill and immediately continue executing the
caller's next section** — do NOT end your turn, do NOT wait for user input, do NOT print a "superloop
complete" report. **Superloop has no Final Report of its own; the caller writes the only user-facing
report** (the caller's per-tick report).

## Caller-supplied parameters (the work-model seam)

The caller supplies, once, at invocation:
- **`<consumer>`** — the caller's own slash-command name, used in the driver's tick prompt (`/<consumer> --tick <loop-file>`) — see L2. For superagent this is `superagent`; the project consumer is `supercode`.
- **`<bootstrap-input>`** — the caller's required bootstrap input, the L2 hard gate (no input + no existing loop file ⇒ print the hard-gate message and exit). Defaults to the goal's **root** seed/master plan (superagent: root `<PLAN.md>`); supercode supplies the real project directory and external driver only — see L2.
- **Status vocabulary + role→value mapping** — the caller's concrete `status:` values *and* the mapping of each onto L1's generic roles (a *ready* state, a *transient/running* state, `WAITING FOR INPUT`, `DONE`), plus any extra frontmatter fields the caller stores beyond the L1 baseline — see L1.
- **Heavy-step definition + THRESHOLD** — what increments `session_skill_count`, and the handoff THRESHOLD (this plugin's callers resolve it from `SUPER_HEAVY_STEP_LIMIT`, default 6) — see L4.
- **Be-sure artifact list** — the output file(s)/PR(s) the caller's just-completed sub-step reports, which the Be-sure verification confirms are present and tracked (L5's two-kind rule) — see L5/L6.
- **Escalation option-set + apply actions** — the concrete options and what "apply" does per trigger — see L7.
- **Per-tick body & DONE-condition** — entirely the caller's; superloop never dispatches the work.

## Clause index

- **L1** — The loop-status file (location, format, `primary_root()`, goal-folder derivation, gitignore, generic status roles).
- **L2** — Drivers & guard/bootstrap/resume (Driver A cron, Driver B external, context model, Step-0 branching, `stop_driver()`).
- **L3** — Overlap lock (`acquire_lock()` / `release_lock()`).
- **L4** — Context-handoff gate (`check_session_budget()`).
- **L5** — Sync gate (`sync_main()` + `sync_vault()` (external vault only) + Be-sure verification).
- **L6** — PR integration discipline (CI-green gate + `--admin` merge via `superauthor` A7 + post-merge sync/be-sure + CI-red escalation trigger).
- **L7** — Decision-escalation ladder (3-subagent panel → user escalation).

---

## L1 — The loop-status file

The supercode consumer instead uses its existing registered project state (default
`<project>/<SUPER_LOOP_STATUS_DIRNAME>/supercode.md`), stores `project` rather than `master_plan`,
and supplies its own operation-aware transient recovery and DONE validation. These project overrides
do not alter the following plan-tree defaults.

State lives in a single per-goal file: `<goal-folder>/<SUPER_LOOP_STATUS_DIRNAME>/<YYYY-MM-DD>-<slug>.md`.

The **goal folder** is derived from `<PLAN.md>` the same way `superplan` does it (its *Goal
Identification* step): the directory that contains the `master-plans/` / `plans/` subfolders for this
plan family — the **parent** of the `master-plans/` folder the seed sits in, **not** that
`master-plans/` folder. Goal folders live under the vault root `<vault_root>` (see **Vault root**;
worked example from the originating repo: `SUPER_GOAL_ROOT=vault/network-compose`), so the loop file lands at
`<vault_root>/<goal>/<SUPER_LOOP_STATUS_DIRNAME>/<date>-<slug>.md` — a sibling of that goal's
`master-plans/`, `plans/`, `reports/`, `findings/`.

The `<SUPER_LOOP_STATUS_DIRNAME>/` directory is **gitignored** — in an internal vault by the
code repo's `.gitignore` pattern `<SUPER_GOAL_ROOT>/**/<SUPER_LOOP_STATUS_DIRNAME>/` (worked example
from the originating repo: `vault/network-compose/**/loop-status/`); in an **external vault** by the
vault repo's own `.gitignore` pattern `**/<SUPER_LOOP_STATUS_DIRNAME>/` (written by `superagent:init`).
It is **local-only state** — never commit it, never open a PR for it, just
Write it with the Write tool. Being gitignored, it survives `superplan`/`superrun`'s `git checkout -b …
/ checkout main / pull` dance untouched and can never be swept into one of their explicit-`git add`
docs commits.

**The loop-status file always lives at the vault root, never in a worktree.** In an **external
vault** that is automatic — `<vault_root>` is the same directory from every worktree. In an
**internal vault**, because `<SUPER_LOOP_STATUS_DIRNAME>/` is gitignored, it is physical working-tree
state that exists only in the primary checkout — it is **absent from every linked git worktree**. If
the loop is launched from inside a worktree (e.g. one created by `EnterWorktree` for plan
execution), resolve the primary checkout root **first** and root the loop-status path there:

```
# primary_root(): the checkout this worktree was created from (a no-op if already primary)
primary_root="$REPO"
# In the primary checkout, --git-dir == --git-common-dir (both `.git`); in a linked worktree they
# differ (--git-dir → <primary>/.git/worktrees/<name>, --git-common-dir → <primary>/.git), so
# `dirname` of the common dir is the primary checkout root — regardless of the primary's current branch.
```

Every loop-status read/write and the overlap-lock dir derive from the **loop file's own directory**
(`<vault_root>/<goal>/<SUPER_LOOP_STATUS_DIRNAME>/` — the scripts compute the lock as
`dirname(<loop-file>)/.<basename>.lockd`); only the Sync gate's code-repo `git` commands use
`primary_root` as their base. Derive the goal folder (`<vault_root>/<goal>/`) with `<vault_root>`
resolved at `primary_root`: the loop file is
`<vault_root>/<goal>/<SUPER_LOOP_STATUS_DIRNAME>/<date>-<slug>.md` (internal vault:
`<primary_root>/<SUPER_GOAL_ROOT>/<goal>/…`; external vault: `<SUPER_GOAL_ROOT>/<goal>/…` verbatim).

Format — YAML frontmatter is the machine state; the body is an append-only human log:

```markdown
---
master_plan: <SUPER_GOAL_ROOT>/<goal>/master-plans/<seed>.md   # ROOT seed: repo-relative (internal vault) or ABSOLUTE (external vault)
git_mode: github | none                # immutable execution contract; legacy missing means github
project_root: <physical REPO>          # scheduler/control-plane root, required for new goals
status: WAITING FOR PLAN          # caller's status vocabulary (see the status roles below)
plan_exhausted: false             # CALLER-SPECIFIC: e.g. superagent's queue-exhaustion hint; other consumers add their own work-model fields here
planning_operation: none          # optional recovery hint: refine | replan | none; tracked tree/records override it
planning_target:                  # optional stage ID, legacy repair leaf, or decision record hint
planning_generation:              # optional upfront root generation hint
planning_record:                  # optional C8 record path/Decision ID hint
prior_status:                     # status to restore after a WAITING FOR INPUT escalation resolves
driver: external                  # the only driver in this build (external scheduler — fresh context per tick)
cron_id:                          # unused in this build (Claude Code in-session driver only); leave empty
created: <today>
iteration: 0
session_skill_count: 0            # heavy skills run in the CURRENT cron session; reset to 0 at each cron session start; drives the L4 handoff (cron only)
---

## Pending decision
<!-- present only while status == WAITING FOR INPUT, in L7 Rung 2's required shape: what failed,
     most likely cause, recommended option, other options, how to answer, then a reference list.
     Cleared once resolved. -->

## Decisions
<!-- append-only: each escalated decision, the panel verdict (or "user-resolved"), the chosen
     option, and one-line rationale. Every entry names what it concerned — `PR #N · <job/step>` or
     the stage and blocker — so L7's repeat check can match it. -->

## Iteration log
- (one entry appended per tick: iteration #, skill invoked, result, PR URLs, status transition)
```

**Keep the loop file small — every tick reads it.** An iteration-log entry is at most three lines:
iteration, skill, one-line result, PR/receipt links, status transition. Hashes, execution identities,
budget accounting and verbatim reports belong in the tick's own report (the tick log the driver
writes, and the delegated skill's report and ledger), never in the loop file. A tick reads the
frontmatter, `## Pending decision`, `## Decisions` and the **last five** iteration-log entries — for
example `awk` up to `## Iteration log` plus `tail` of the rest — not the whole file; older entries
are history it never needs.

The baseline fields (`master_plan`, `status`, `prior_status`, `driver`, `cron_id`, `created`,
`iteration`, `session_skill_count`) are owned by superloop. `plan_exhausted` is **caller-specific** —
it is superagent's queue-exhaustion field (not completion proof); other consumers add their own work-model fields here.

### Status vocabulary

**Generic status roles (superloop owns these semantics; the caller names the values):**
- a **ready** state — the loop is poised to run the caller's per-tick body (superagent: `WAITING FOR PLAN`, `WAITING FOR RUN`).
- a **transient/running** state — set at the start of a tick, replaced before the tick ends; **persisted ⇒ a crashed tick**, self-healed by L2's crash-recovery (superagent: `PLANNING`, `RUNNING`).
- **`WAITING FOR INPUT`** — a decision the escalation ladder (L7) could not resolve is awaiting the user.
- **`DONE`** — the caller's DONE-condition is satisfied (superagent: queue exhaustion plus verified supertraverse C9 completion audit).

The caller declares its concrete `status:` values and supplies the role→value mapping when it invokes superloop.

---

## L2 — Drivers & guard/bootstrap/resume

The caller names its own slash-command in the driver's tick prompt: every literal `/<consumer> --tick
<loop-file>` below substitutes the caller's command. `<consumer>` is the caller-supplied slash-command
name (superagent: `superagent`).

### Hard gate — the caller's required bootstrap input is required

The caller names its **required bootstrap input** (superagent: the root `<PLAN.md>`). **DO NOT START A
LOOP WITHOUT THAT INPUT.** If form (B) below is invoked with no required input and no existing
loop-status file can be located → print the caller's hard-gate message and **exit**. Do not guess the
input from the working directory. The caller supplies the exact message string (superagent: *"superagent
requires a master plan file (PLAN.md). None provided and no loop file found. Exiting."*). The required
input must be the goal's **root** seed/master plan (the same file `superrun` traverses and `superplan`
descends from) — not a leaf implementation plan.

### Context model (why a clean context per tick is fine — and better)

The per-tick logic is **driver-agnostic**: a tick reads all state from the loop file and runs one
iteration, so it behaves identically whether ticks fire in one long-lived session or in a fresh session
each time. The `driver:` field in the loop file records which mode bootstrapped the loop. Pick it in
form (B) with `--driver=` (default `cron`).

A tick keeps **no state in conversation memory** — `status`, `plan_exhausted`, `cron_id`, decisions all
live in the loop file. So a tick run in a **fresh, empty context** behaves exactly like one in an
accumulating session. Clean-context-per-tick is in fact *preferable*: it bounds context growth and
gives genuine isolation between successive ticks (they never share a context at all). The two drivers
differ only in *who fires the tick* and *whether context accumulates*.

### Step 0 — Parse the invocation, then guard / bootstrap / resume

Before any git/auth/CI action or dispatch, compare effective `SUPER_GIT_MODE` and physical `REPO`
with the loop/root markers. An unmarked legacy goal means `github`. A mismatch writes
`WAITING FOR INPUT` with the recorded/effective values and recovery choices, releases owned locks,
and exits without git, gh, GitHub API, credentials, merge claims, or dispatch. Version one never
migrates an in-flight goal automatically.

`$ARGUMENTS` arrives in one of two forms.

#### (A) Internal tick — `--tick <loop-file>`

Fired by the driver each interval — the in-session `cron` job, **or** an external Desktop routine / OS
cron, **possibly in a fresh empty context**. It **carries the loop file's full path directly** — no
goal-folder derivation, no search. This is the only form that advances the state machine.

1. **`acquire_lock()`** (see **L3**). If another tick is already in flight → **exit immediately**
   (no-op; the next fire retries). This is what keeps fresh-session external ticks from overlapping.
2. Read the named loop file. The carried path is **absolute**, rooted at `<vault_root>` (see **Vault
   root**) — in an internal vault that is under the primary checkout (`primary_root()`, not the
   worktree); in an external vault it is the vault itself — so the tick's cwd is irrelevant for
   reading/writing the file. Still resolve `primary_root()` (see **L1**) for the Sync gate's code-repo
   `git` commands — a tick can fire while cwd is a worktree; the overlap-lock dir derives from the
   **loop file's own directory** (see **L1** and **L3**), not from `primary_root`. A clean
   context is fine — **all** state (`status`, `plan_exhausted`, `driver`, `cron_id`, decisions) is in the
   file, not in conversation memory.
3. If `status` is **`DONE`** → `release_lock()`, no-op, and (in `external` mode) remind the user to
   disable the Desktop routine / scheduler entry; exit. (External loops driven by the shipped
   `scripts/` wrapper disarm themselves: after the session ends, `superagent-tick.sh` sees the
   `DONE` in the loop file and uninstalls its own scheduler entry —
   `SUPER_AUTO_DISARM_ON_DONE`, default `true` — so this branch should fire at most once there.
   Never uninstall the scheduler from **inside** the session: on launchd that kills the running
   tick's own process group. The wrapper handles it after the session.) Otherwise run the **Context-handoff gate (L4,
   `check_session_budget()`)** — if it hands off, this tick ends there — then go to the caller's per-tick
   body.

Do **not** re-bootstrap or re-arm any driver from a tick. `release_lock()` runs at the end of the tick
and on every early-exit/escalation path.

#### (B) User entry — `<bootstrap-input> [--driver=cron|desktop|headless]`, or empty

1. **Hard gate.** If no required bootstrap input and no existing loop file can be located → print the
   caller's hard-gate message (above) and exit.
3. **Locate state.** Derive the goal folder from the required input (the `superplan`
   Goal-Identification rule — parent of the `master-plans/` folder), then **root it at
   `<vault_root>`** (see **Vault root**) — so the lookup and the lazy first-write target are
   `<vault_root>/<goal-folder>/<SUPER_LOOP_STATUS_DIRNAME>/`: in an internal vault that is under
   `primary_root()`, not the worktree the loop may have been launched from, exactly as before; in an
   external vault it is the vault itself. The input `<PLAN.md>` path is repo-relative in an internal
   vault and absolute in an external one (the form `launch.sh` stores in `master_plan:`); only the
   on-disk base changes. Look in `<vault_root>/<goal-folder>/<SUPER_LOOP_STATUS_DIRNAME>/`
   for a file whose `master_plan:` matches the input. Deterministic, single-directory lookup — not a
   global scan. The `<SUPER_LOOP_STATUS_DIRNAME>/` subdir is created lazily on first write (no `mkdir`).
4. **Guard / bootstrap / resume — branch on `driver`:**

   **`external` mode** (Desktop routine / OS cron — **no `CronCreate`, no `CronList`**; the scheduler is
   user-managed):
   - **No loop file** → **FRESH START**: create the loop file (`driver: external`, the ready `status`,
     …, `cron_id:` empty, `session_skill_count: 0`), **print the exact scheduler entry to create**
     (Desktop routine or headless `pi -p` recipe from **Driver B**, with this loop file's absolute
     path), then continue to the caller's per-tick body to run the first iteration now. Subsequent ticks
     come from the external scheduler.
   - **Loop file exists, non-terminal** → report `status`/`iteration`/last log line and **re-print the
     scheduler entry** so the user can confirm the Desktop routine / cron entry is firing `--tick` on
     this loop file. (There is no in-session driver to "resume" — the external scheduler is the driver.)
     Do not run a tick here unless the user asks; the scheduler will.
   - **`status: DONE`** → report "already complete" and remind the user to disable the Desktop routine /
     scheduler entry if one is still armed (loops driven by the shipped `scripts/` wrapper normally
     disarmed themselves on the tick that reached `DONE` — `SUPER_AUTO_DISARM_ON_DONE`); exit.

After branching, read `master_plan`, `status`, `plan_exhausted`, `prior_status`, `driver`, `iteration`,
`session_skill_count` from the loop file before the per-tick body. When form (B) continues to run the
first tick, wrap it in the lock too — `acquire_lock()` first (skip if held), `release_lock()` at the
end — and run the **Context-handoff gate (L4)** before the body, exactly like a form-(A) tick.

### Crash recovery — a persisted transient/running state means a crashed tick

**Consumer recovery seam:** supercode must reconcile committed operation artifacts and full
acceptance context before any transient reset. Its mappings are META-PLANNING → WAITING FOR
META-PLAN, EVALUATING → WAITING FOR EVAL, DIAGNOSING → WAITING FOR DIAGNOSIS. Incomplete reusable
META keeps its original goal/operation. Conflicts park. The following plan-tree recovery defaults
remain unchanged; neither consumer resets a live peer's transient or lock.

The transient/running role (L1) is transient *within* a tick: the loop sets it, runs the body
synchronously, then sets the next status — all in one turn. Ticks never overlap: in `cron` mode they
fire between turns; in `external` mode the **lock (L3)** serializes them. So a **persisted** transient
state means a crashed prior tick (which also left a stale lock that `acquire_lock()` steals
immediately when its recorded owner PID is dead, or after
`SUPER_LOCK_STEAL_MIN` minutes (default 90) only when no valid owner PID was recorded). **Self-heal:** log a recovery note and reconcile the
caller-owned authoritative artifacts before retrying. A published docs operation, merged code delivery,
open/CI-pending PR, or integrated closeout may have succeeded after the response was lost; actual
tracked commits/PRs and identity-bound partial-closeout/delivery records override the stale transient hint. Then **map the
persisted transient state back to its matching ready state** (the caller supplies the
transient→ready mapping for its own status values — superagent: `PLANNING → WAITING FOR PLAN`,
`RUNNING → WAITING FOR RUN`) and fall through to that branch. Recovery reuses the existing identity;
it never duplicates publication or reruns delivered work merely because loop state lagged.

### Tick teardown invariant — never exit on a transient status, never end a tick with a question

A tick has exactly four legal terminal shapes: **advanced** (the next ready / parked / `DONE` status
written), **parked** (`WAITING FOR CI`, or `WAITING FOR INPUT` with its `## Pending decision` block
written), a clean **no-op** (held-lock exit, `DONE` guard, budget handoff), or
**interrupted-and-restored** (below). In every one of them, any transient status **this tick wrote**
is replaced before the turn ends and any lock **this tick acquired** is released. (A held-lock no-op
touches neither: the transient status and lock it observed belong to the live peer tick and stay
exactly as found.) A normal end-of-tick that leaves its own transient status persisted is a **failed
tick**, even if the session reports success (the shipped external wrapper enforces this: a `0`-exit
session that leaves a transient status with no live peer holding the lock is re-flagged as a loud
non-zero tick).

**Ending the tick by asking a question is never legal — in any form.** Not via an Ask tool (the
driver prompts already forbid those), and **not as the session's final chat message**: in an
unattended session no one can answer, the harness records the questioning turn as a successful
completion (`exit 0`, `is_error: false`), and the question strands the transient status and the held
lock until crash recovery cleans up. If a decision genuinely needs the user, the **only** channel is
L7 Rung 2's durable machinery — write `## Pending decision`, set `status: WAITING FOR INPUT`,
`release_lock()`, exit. (An **attended** interactive tick may use `AskUserQuestion` mid-tick per L7
Rung 2 — but the tick still ends in one of the four terminal shapes above.)

**Interrupted dispatch — self-heal now, don't ask.** If this tick's own heavy dispatch dies under it
(API stream lost mid-response, host slept, subagent vanished) and the step cannot be completed this
tick, do exactly what the next tick's crash recovery would do — immediately, so nothing is left
stranded: append an interruption note to `## Iteration log`, map the transient status back to its
ready state (the caller's transient→ready mapping), `release_lock()`, and end the tick with a normal
non-question report naming the interruption. The next scheduled tick retries the step from the ready
state — **retry is the standing answer to an interruption**; only a genuine decision point (an L7
trigger) parks the loop on `WAITING FOR INPUT`.

### Driver B — `external` (Desktop scheduled task, or headless OS cron) — CLEAN CONTEXT

`/<consumer> <bootstrap-input> --driver=desktop` (aliases `--driver=external` / `--driver=headless`)
bootstraps the loop file with `driver: external`, **arms NO `CronCreate` job**, and **prints the exact
scheduler entry to create**. An external scheduler then fires `/<consumer> --tick <loop-file>` on its
interval, each in a **fresh session = clean context**.
- Duplicate guard: **not** `CronList` (each fresh session's `CronList` is empty). The **lock (L3)**
  prevents overlap; "is a loop already set up?" is answered by the loop-file `status` plus the fact that
  the *Desktop routine / scheduler entry* is what the user manages.
- **Interactive console is a separate, start/stop-independent plane.** The scheduler is the *driver*;
  a human can additionally open an interactive Claude session to **monitor** (read the
  loop file, tail the driver log, `gh pr/run`) and to **answer** a `WAITING FOR INPUT` decision — either
  by running one attended `--tick` (a person is present, so the L7 Rung-2 branch uses `AskQuestion` and
  applies the answer under the L3 lock) or by writing `answer: <option>` into the loop file
  (`scripts/answer.sh <slug> "<option>"`, with the registered slug — not the loop file's basename — does this under the lock and kicks a tick at once; a hand edit is
  picked up on the next scheduled fire). Because all state is in the loop file, this console can be started and stopped
  at will without affecting driver progress (only the driver process should use `--resume`-free fresh
  ticks; an interactive console may `--resume` freely).

### `stop_driver()` — used wherever the loop completes or pauses
- **external:** the Desktop routine / scheduler entry is **user-managed** — the skill cannot delete it
  from inside the session (on launchd, unloading the job would kill the running tick's own process
  group). Leave the terminal/paused status in the loop file (further `--tick` fires no-op on `DONE`, or
  re-asks on `WAITING FOR INPUT`) and **print a clear instruction to disable the Desktop routine (or
  remove the cron/launchd entry)** for this loop file. For loops driven by the shipped `scripts/`
  wrapper, `DONE` needs no user action: after the session ends, `superagent-tick.sh` reads the `DONE`
  status and uninstalls its own scheduler entry (`uninstall-timer.sh <slug> --from-tick`), keeping the
  loop-status and per-goal env files so the loop stays re-armable — gated by
  `SUPER_AUTO_DISARM_ON_DONE` (default `true`).


---

## L3 — Overlap lock — `acquire_lock()` / `release_lock()` (REQUIRED for every tick, both drivers)

In `SUPER_GIT_MODE=none`, the project writer lock is outer to L3. The external wrapper runs the
mutating tick through `workspace-state.py run --root "$REPO"` and also `--root "$vault_root"` for
an external vault. A nested planner/executor inherits `SUPER_WORKSPACE_TOKEN` and
`SUPER_WORKSPACE_OWNER_PID`, validates the existing owner, and borrows it; it never creates a second
writer. Direct interactive mutation must either have a demonstrably live inherited session owner or
run the operation through the helper. Acquire multiple roots in physical-path lexical order, then L3.
A busy project yields without iteration/status advancement. Release only matching tokens; a live or
ambiguous owner is never age-stolen. This lock coordinates Superagent writers, not arbitrary editors.

External ticks run in **independent sessions**, so a long tick (a run with a 30-min CI gate) can
still be running when the next interval fires. Guard every tick with an atomic file lock in the
loop-status dir so two ticks never run concurrently:
- **Project consumer (`supercode`) override:** use the installed
  `scripts/_coding_loop_state.py acquire-lock LOCK_DIR --owner DRIVER_PID --steal-min MIN` for
  **every** acquire/reclaim path, including answers and force recovery. The helper serializes
  mkdir, stale re-read/removal, and owner/acquired publication under `fcntl.flock` on the persistent
  sibling `LOCK_DIR.reclaim`. Never unlink that inode, even during stop/recovery. Exit on return 1
  (busy); report return 2 as invalid/error. A live owner is never age-stolen. Release the main
  `.lockd` only if owner still names this driver PID. Do not execute the legacy rm/reacquire recipe
  below for projects. Legacy goal consumers retain the Python-free default.
- **`acquire_lock()`** — atomically `mkdir "<loop-file-dir>/.<loop-file-basename>.lockd"`. The lock
  derives from the **loop file's own directory** (`<vault_root>/<goal>/<SUPER_LOOP_STATUS_DIRNAME>/`),
  never from `primary_root` (see **L1**). `<loop-file-dir>` is an absolute path — inside the primary
  checkout for an internal vault, inside the vault repo for an external one — so the lock is
  unambiguous even when the loop is launched from a worktree. On **success**, write a unix
  timestamp to `…lockd/acquired` AND the driving process's PID —
  `${SUPERAGENT_TICK_PID:-$PPID}` (the external wrapper exports `SUPERAGENT_TICK_PID`; in-session
  ticks fall back to `$PPID`, the CLI process) — to `…lockd/owner`, then proceed. On **failure**
  (held): read `…lockd/owner`; if it names a PID that is **no longer alive** (`kill -0 <pid>`
  fails), the owning tick is dead — `rm -rf` the lock dir, re-acquire, and log a recovery note.
  If the owner PID is alive, **exit the tick immediately regardless of lock age** — another tick
  is in flight. Only when no valid owner PID was recorded (an older or interrupted lock), fall
  back to `…lockd/acquired` age: older than **`SUPER_LOCK_STEAL_MIN` minutes (default 90)** →
  `rm -rf`, re-acquire, log a recovery note; otherwise exit and let the next scheduled fire retry.
- **`release_lock()`** — `rm -rf` the lock dir on **every** exit path of a tick (normal end, early
  no-op, escalation/STOP). In `cron` mode ticks already never overlap, so the lock is a harmless no-op;
  in `external` mode it is load-bearing (it is what replaces `CronList`'s implicit single-session
  serialization).
- **Wrapper safety net** — the agent-side `release_lock()` never runs when the CLI kills the
  session mid-tick (e.g. a print-mode background-wait ceiling), which used to leak the lock for the
  full steal window. `superagent-tick.sh` therefore traps EXIT and reaps the lock **iff**
  `…lockd/owner` names its own PID — it never touches a peer's live lock. The `owner` file is what
  makes both this trap and the immediate dead-owner steal above possible; always write it.

---

## L4 — Context-handoff gate — `check_session_budget()` (check BEFORE every iteration)


---

## L5 — Sync gate — local `main` must equal `origin/main` (REQUIRED around every skill dispatch)

**Local branch (`SUPER_GIT_MODE=none`).** Do not run this section's git sync commands. Before a
dispatch, verify the recorded mode/root and owned workspace token. Capture a pre-task filesystem
snapshot/manifest outside project and vault roots. After execution and review, capture the result and
compare paths, contents, deletions, and executable bits. Reject inconsistent capture or source changes
during evidence collection. Be-sure verification reopens every reported artifact, receipt, review, and
required command result at its durable path. A status label or report alone is never proof. Preserve
unrelated user changes; snapshots are inspection evidence, never automatic rollback or overwrite.
After this branch succeeds, continue to the caller without applying the GitHub sync recipes below.

The caller's sub-steps (a selected planning operation / `superrun`, or a consumer's own fix-PR flow) merge their PRs to
`origin/main` and then try `git checkout main && git pull --ff-only`. **That local pull can silently
fail or be skipped** — most commonly when a `git checkout main` runs *inside a worktree* (where `main`
is already checked out in the primary tree and the checkout errors **after** the remote `--admin` merge
already happened), or on a brief propagation race right after `gh pr merge`. When it does, the **primary
checkout stays stale**: the loop-status file is fine (gitignored/local), but the **tracked plan tree**
the next sub-step reads (progress tables, plan files, closeout rows) is behind `origin/main`. The next
traversal then acts on stale rows — **re-planning a step whose plan row already merged** (an infinite
re-plan loop), or failing to find a leaf whose closeout already merged. The loop must never read, or
hand a sub-step, a stale tree.

Run this gate in the **primary repo checkout**. Resolve `primary_root()` (see **L1**) and run
**every** gate `git` command against it — `git -C "$primary_root" <…>` (fetch, rev-parse, rev-list,
merge --ff-only, status, checkout). This is what makes `git checkout main` correct when the loop
itself was launched in a worktree: it operates on the **primary tree**, not the worktree (which
cannot check out `main` — it is already checked out in the primary tree). In the primary checkout
`primary_root` resolves to cwd, so `git -C "$primary_root"` is a no-op there. All
`git` commands run in the Bash sandbox (no `gh`; `git fetch`/`pull` work there).

### `sync_main()` — deterministic, mechanical (no subagent panel — this is plumbing, not judgement)
1. `git rev-parse --abbrev-ref HEAD` → must be `main`. If on a `plan/…`/`finish/…`/feature branch or
   detached (a crashed skill left it there) → `git checkout main`. If `checkout` fails on dirty
   **tracked** files you did not author → **STOP and escalate** (do not stash/discard — they may be
   someone's work).
2. `git fetch origin main`.
3. Compare `main` to `origin/main` — `git rev-list --left-right --count main...origin/main`:
   - **equal** (`0  0`) → synced.
   - **behind only** (`0  N`, local is an ancestor) → `git merge --ff-only origin/main` (≡
     `git pull --ff-only`).
   - **ahead / diverged** (`M  *`, local has commits not on origin) → **STOP and escalate**:
     unexpected for the PR-only flow; surface the state, never reset or force.
4. No uncommitted **tracked** changes: `git status --porcelain --untracked-files=no` is empty (the
   ignored loop-status file and other untracked scratch are fine). If not → **STOP and escalate** (do
   not commit or discard tracked changes you did not make).

### `sync_vault()` — external vault only, run right after `sync_main()`
In internal mode the vault is part of the code repo and `sync_main()` already covered it; skip
this. In **external** mode (see **Vault root**) the plan tree lives in the vault repo, so:
1. `git -C "<vault_root>" remote get-url origin` fails → **no remote → synced** (nothing to pull).
2. `origin` exists but the vault branch has no upstream (`git -C "<vault_root>" rev-parse
   --abbrev-ref @{upstream}` fails) → `git -C "<vault_root>" push -u origin HEAD`; success → synced,
   failure → STOP and escalate.
3. Otherwise `git -C "<vault_root>" fetch origin` and compare the vault's current branch to its
   upstream — `git -C "<vault_root>" rev-list --left-right --count HEAD...@{upstream}`:
   - **equal** → synced;
   - **behind only** → `git -C "<vault_root>" merge --ff-only @{upstream}`;
   - **ahead only** → **normal here** (an earlier A7 push failed): `git -C "<vault_root>" push`;
     if the push fails → STOP and escalate;
   - **diverged** → STOP and escalate (never reset or force).
4. `git -C "<vault_root>" status --porcelain --untracked-files=no` must be empty → else STOP and
   escalate (tracked vault changes nobody committed).

### Be-sure verification (after a skill, post-`sync_main()`/`sync_vault()`)
The caller's just-completed sub-step reports the PR(s) it merged and the file(s) it wrote; confirm each
is present and tracked:
- the reported output file(s) exist and are tracked. **Internal vault:** both kinds are checked
  with the existing form, `git -C "$primary_root" ls-files --error-unmatch <repo-relative path>` —
  the paths the sub-step reports are already repo-relative. **External vault:** a vault artifact is
  reported by A8 as an absolute path plus `**Commit:** <short-sha> in <vault_root>`; strip the
  `<vault_root>/` prefix and check `git -C "<vault_root>" ls-files --error-unmatch <vault-relative
  path>`, and confirm the commit with `git -C "<vault_root>" cat-file -e <short-sha>`; code paths
  are checked on the code repo as before;
- (optional) the merge is in history — `git log --oneline origin/main | grep <pr-number>`.

For an identity-bearing operation, verify the report against its actual authoritative publication:
the recorded stage/generation/revision or Decision ID, source/preparation/delivery identity, and the
one integrated A7 transition. A filename, loop hint, unmerged docs PR, or child success message alone
does not pass Be-sure. On a lost response, one matching integrated unit is success to reuse; competing
or partial units require reconciliation before another write.

If a reported artifact is **missing** after a clean `sync_main()`, the merge did not propagate as
claimed: `git fetch` once more and re-check; if still missing → **STOP and escalate** with the
discrepancy. **Do not advance the state machine on an unverified merge** — that is how the loop drifts
onto stale state.

### When the gate STOPs
Record it in the loop file (a `## Pending decision`-style note with the exact git state), set
`prior_status` and `status: WAITING FOR INPUT`, `stop_driver()` to pause, `release_lock()`, and surface
the git state + how to resume — the same durable-resume mechanism as `WAITING FOR INPUT`. A stale or
divergent tree is a **safety stop**, not something to guess past or force.

---

## L6 — PR integration discipline

**Local branch (`SUPER_GIT_MODE=none`).** There is no integration PR, commit, push, merge, sync, or
CI poll. A leaf may become `completed-local` only after its closeout receipt is reopened and verifies:
root and active leaf identity; `git_mode: none`; before/result snapshot identities and manifest paths;
added/modified/deleted files; local commands with exit/result evidence; task and final review outcomes;
acceptance coverage; outstanding obligations; and timestamp. Commit/PR fields read
`N/A (SUPER_GIT_MODE=none)`. Only then may parent progress advance. L6 returns to the caller after
durable verification; it never invokes A7's GitHub branch.

An autonomy loop that opens and merges its own PRs MUST follow the same `SUPER_PROTECTED_MAIN`-gated
discipline the rest of the `super*` family uses (if `SUPER_PROTECTED_MAIN=true`, the shipped default,
the default branch is a protected branch and this MUST go through a feature branch and a PR; if
`SUPER_PROTECTED_MAIN=false`, a direct commit to the default branch is permitted instead). This
clause is the autonomy-loop view of it; the **canonical merge
skeleton lives in `superauthor` clause A7** (merge per `SUPER_MERGE_METHOD`, default `squash`; pass
`gh pr merge --admin` only if `SUPER_ADMIN_MERGE=true`, otherwise never — reaching for it unprompted on
a repo whose branch protection doesn't require it trips the harness security classifier). Do not
duplicate that skeleton — apply A7's.

1. **CI-green and current-authority gate before merge.** A code PR is merged only once its gating CI
   lane is green (the caller names the lane) **and** the caller revalidates the current authoritative
   work identity/barrier/disposition. A queued-before-request packet is not merge authority. If CI is
   red, an adopted barrier is pending, the active identity changed, or disposition is unresolved, do
   **not** merge — preserve the PR evidence and route to the caller's reconciliation/escalation path.
2. **Merge via A7.** Apply `superauthor` A7's merge — per `SUPER_MERGE_METHOD` (default `squash`), never
   `--admin` unless `SUPER_ADMIN_MERGE=true` permits it. If `SUPER_PROTECTED_MAIN=true` (the shipped
   default), the default branch is protected; never direct-push. If `SUPER_PROTECTED_MAIN=false`, a
   direct commit to the default branch is permitted instead.
   Commit/PR text carries no AI-attribution / `Co-Authored-By` trailers (repo policy).
3. **Post-merge sync + be-sure (L5).** Immediately run `sync_main()` (then `sync_vault()` in external
   vault mode) and the Be-sure verification so the primary checkout reflects the merge before the
   next tick reads the tree.

**superagent's subset.** superagent does **not** itself open/merge work PRs — selected planning operations / `superrun`
do that inside their own flows. superagent therefore applies only **L6.1's CI-red → L7 escalation
trigger** and **L6.3's post-merge sync+be-sure** (around each selected planning operation / `superrun` dispatch). A
consumer whose per-tick body opens its own PRs applies the full clause.

---

## L7 — Decision-escalation ladder — autonomy posture

For the project consumer, this ladder may resolve routine operation failures only. Specification
changes, agreement adoption and raised round-limit decisions require an explicit recorded author
answer; no panel vote can approve them or weaken acceptance.

The bar is **not** "never ask the user." Routine actions (commits, PR merges) never need approval, but
delegated skills legitimately surface genuine decision points. The loop resolves them itself first,
and escalates to the user only as a last resort — always leaving a durable resume path.

**Triggers** (watched in each delegated skill's Final Report — the integration point, so the
sub-skills' internals need no rewrite): a CRITICAL / ⚠️ finding, a `not-traversable` result, a
BLOCKED / CI-red outcome, or any place a skill surfaces a clarification rather than completing cleanly.
Standing posture: if a delegated skill would otherwise ask the user inline, resolve it via this ladder
instead.

**Protected surfaces.** A file matching `SUPER_PROTECTED_PATHS` (`superagent_protected_match` in
`scripts/_common.sh`), an approved acceptance row, or a value the project's own instructions pin is a
protected surface. When the best-supported fix needs one, the ladder asks the owner for **exactly that
change** — the **protected-change request** in Rung 2 — instead of asking for more evidence or more
authority around it. The panel may choose to ask; it never approves the change itself.

> **Depth-1 subagent constraint.** Subagents cannot spawn subagents (depth-1) — more precisely, a
> subagent cannot foreground-wait on children it spawns; they background and yield instead. The
> read-only 3-subagent panel fits within this limit; the supervisor that runs the panel **cannot
> itself be a subagent** — it must be the top-level loop agent. The same constraint is why
> `superagent` runs `superrun` (the task-loop controller, which must wait on its own implementer/reviewer
> subagents) as the top-level agent of a separate CLI process rather than as a subagent (issue #25;
> see superagent **Subagent dispatch**).

### Rung 1 — Subagent panel (resolve autonomously)
Dispatch **3 panelists in one blocking `bash` call** to the fan-out script — this harness has no
blocking parallel subagent tool, and the supervisor never uses a subagent tool at all. Write the
packet to three temp files (`mktemp "${TMPDIR:-/tmp}/super-panel.XXXXXX"` ×3, quoted
heredocs; the first carries the simplest-explanation brief below), resolve the panel's harness/model/effort from `SUPER_MODEL_PANEL` / `SUPER_EFFORT_PANEL`
(`. "${SUPER_PLUGIN_ROOT}/scripts/_common.sh"` under bash; `superagent_role_harness`, an `inherit` harness →
`pi`; `superagent_role_model`), then run with the largest `timeout` the `bash` tool accepts:
`"${SUPERAGENT_FANOUT:-${SUPER_PLUGIN_ROOT}/scripts/bridge-fanout.sh}" --harness <h> --model "<m>" --effort "<e>" --tools role --cwd "$PWD" --role panelist --timeout 1800 --prompt-file "$f1" --prompt-file "$f2" --prompt-file "$f3"`
stdout carries the three verdicts framed `=== PANELIST <n> exit=<rc> === … === END <n> ===`; a
block whose body begins `BRIDGE-FAILED` (bridge error or the 1800 s timeout) is that panelist
returning no verdict. `SUPER_PANEL_AGENT_TYPE` is ignored on Pi. The call blocks until
all three return — never launch panelists as background `pi-subagents` runs and poll them.
**The packet states facts and pointers, not conclusions.** Give each panelist: the blocker as the
delegated skill reported it (verbatim, including any CI triage record), the relevant plan + report
excerpt, every earlier `## Decisions` entry on the same PR, step, blocker or replan request, the
concrete options,
and pointers — PR, CI run ids, worktree, ledger, vault paths. Do not assert what the evidence has
not established: "the cause is unknown" and "the budget is spent" are claims for the panel to test,
not framing to hand it. Agreement among panelists who were told the answer measures the packet, not
the problem.

**Panelists investigate.** Each panelist may — and should — run read-only checks itself: CI logs
(`gh run view <id> --log-failed`), run artifacts and history, the diff, the ledger, the plan tree. No
writes, pushes, reruns or comments. Honour any project rule that excludes a specific sensitive source,
such as privileged service logs; the ordinary CI job log and junit output are not in that category.

**One panelist argues for the simple answer.** Append this to the first panelist's prompt only:
*"Before voting, make the strongest case for the simplest explanation consistent with the evidence
and the cheapest fix that would unblock the work. Your verdict is still your own judgment."* The
other two prompts stay identical, so the remaining diversity comes from independent reasoning.
A choice between readings the project's sources do not settle is a specification gap **when the
stage's acceptance depends on it**, and then it goes to the owner. When it does not — when a
test-scoped substitute, a narrowed case or a postponed case (superreplan's remedies 1–3) avoids it —
it is a scope question, and the cheapest scope remedy goes first. A remedy avoids the gap only if
the stage still meets its stated goal without that case.

**A repeat may not converge on an unchanged retry.** When an earlier `## Decisions` entry concerned
the same PR and failing step or blocker, say so in the packet. A retry adopted for that failure must
carry a change the earlier attempt did not have; otherwise the panel chooses another option.

Require each to return a structured verdict over the concrete options —
`{chosen_option, likely_cause, rationale, confidence}` — or
`{insufficient-info, missing_fact, cheapest_way_to_obtain, read_only: yes|no}`. An
`insufficient-info` must name the specific missing fact and the cheapest way to get it; a bare one is
malformed and counts as no verdict.
A reply that begins `BRIDGE-FAILED` is a bridged panelist whose foreign CLI never produced a
verdict: count it as no verdict (never as a vote, and never as a reason to abandon the rung), and
note the bridge failure in the `## Decisions` entry.

**Fetch, then re-run once.** If any panelist names a missing fact obtainable by a read-only action,
the supervisor obtains it itself, adds it to the packet, and re-runs the panel **once** before Rung 2.
Three verdicts with no usable content — bare `insufficient-info`, malformed or `BRIDGE-FAILED` — are a
malformed panel result, not a reason to escalate: re-run the panel once, restating that a verdict must
name an option or a missing fact. Only a second malformed result goes to Rung 2, and its block then
lists the read-only checks the supervisor and panel ran and what each returned.

**Converge.** If **≥2 of 3** agree on the same option with non-low confidence → **adopt it.** Record
it under `## Decisions` (option + one-line rationale + "panel 2/3" or "3/3"), then **apply** the
**caller-supplied option set** and its per-option apply action (superagent: retry the run with guidance
/ route back to the ready-to-plan state / mark the step declined):
- a scope/clarity question → re-invoke the same skill with the decision as guidance context (e.g. as
  `<TOPIC>` framing or an explicit directive);
- a BLOCKED execution → apply whichever option the panel chose from the caller-supplied set (superagent:
  retry `superrun` with the unblock guidance, **or** route to the ready-to-plan state for a re-plan,
  **or** mark the step declined).
- a **protected-change request** → the panel has chosen to ask, not to approve: go straight to Rung 2
  and write the yes/no protected-change block. Converging on it never applies the change.

**Re-plan guidance is bounded.** Guidance carried with an adopted re-plan is the chosen option, the
facts behind it and, where relevant, the superreplan remedy (1–5) it recommends. It may not add
deliverables, analyses, proofs or artifacts outside the stage's acceptance and scope: a verdict whose
guidance does is malformed and counts as no verdict. Any directive the guidance does give reaches the
replanner tagged `[planner]`, so the replanner may set it aside with a recorded reason.

**Replans that publish nothing converge.** The caller counts consecutive replanner `BLOCKED`
outcomes for one originating stage — each published nothing but at most a record-only checkpoint
(superagent: `replan_stalls`). A replanner that returns BLOCKED **recommending remedy 2 or 3**
(narrow or postpone the case) goes to Rung 2 as that yes/no question at once; a BLOCKED naming a
genuine specification gap with candidate values likewise goes to Rung 2 at once, as a choice among
those values. Re-planning instead needs a named material difference. From the **second** stall on, the panel may not choose re-plan
again unless the packet names what is materially different from the last attempt. An owner `yes` to
narrowing or postponing, or a test-scoped substitute the replanner has not already rejected, counts
as that difference. Otherwise the options are superreplan's scope remedies — narrowing or postponing
the case as a yes/no owner question — or decline/defer. Prefer the scope remedy: decline/defer only
when none of remedies 1–3 applies. An owner's answer — a `yes`, or a chosen candidate value — is
carried into the re-plan as `[owner]` authority for exactly that answer.

**Constraint origins.** A plan restriction tagged `[planner]` (superreplan's origin rule) binds the
panel no more than it binds the executor: an adopted option may relax one, recorded under
`## Decisions` with the reason. A `[source: …]` or `[owner: …]` restriction is never relaxed by a vote.
Exhausting a `[planner]` budget — a diagnostic attempt count, an evidence lane — is not by itself a
reason for Rung 2.

**At a cap.** When the blocker is a cap (fix rounds, final fix waves, CI-triage fixes), the packet
carries the executor's cap summary — for each open finding, what was tried, why it did not land, the
smallest change that would close it, and whether that change is in scope and protected. Choose among
one more targeted round on exactly that change (Retry, with the change as guidance — at most once per
finding per leaf), a protected-change request when the change touches a protected surface, or a
re-plan.

### Repeat check (before every Rung 2)
Before writing a pending decision, compare it with the `## Decisions` history. Earlier decisions
include owner answers **and** earlier re-plans of the same request that published nothing. When an
earlier decision concerned the same PR and the same failing CI step or blocker, or the same replan
request, the new block must:

- say so in its first line — `Repeat: same failure as <earlier Decision IDs>`;
- summarise what each earlier answer authorised and why that did not resolve it;
- lead, as its recommendation, with a **different kind** of option than last time: a concrete fix, a
  protected-change request, a scope remedy (narrow or postpone the case), or decline/defer. For a
  replan-stall repeat, lead with the replanner's recommended scope remedy; lead with decline/defer
  only when none of remedies 1–3 applies. A protected-change request for the same surface with a
  new value counts as different when the block says why the approved value did not suffice.

No option in a repeat block may ask for more evidence, more diagnostic attempts, more budget, or an
unchanged retry on the same failure.

### Rung 2 — Escalate to the user (last resort)
If the panel cannot converge (split, still without usable verdicts after the re-run, or every
verdict an `insufficient-info` whose missing fact is not obtainable read-only — typically a fact only
the owner can supply), it converged on a protected-change request, or a replanner recommended
narrowing or postponing an acceptance case or returned a genuine gap with candidate values
(*Replans that publish nothing converge*):
1. Write a `## Pending decision` block in the **required shape** below. Save the current `status`
   into `prior_status`; set `status: WAITING FOR INPUT`.
2. **Interactive session** (a person is present — typically `cron`/attended): call `AskUserQuestion`
   now (the recommended option first, then the others). On an answer → record under `## Decisions`
   ("user-resolved"), clear the pending block, restore `prior_status`, apply, and **continue this
   tick** — the driver keeps firing, so the loop never breaks.
3. **Scheduled / unattended tick** (external Desktop/headless, or a `cron` tick with no one present):
   do **not** block on `AskUserQuestion`, and do **not** end the tick with the question as the final
   chat message either (L2's tick teardown invariant — a question-terminated turn reads as a
   successful completion and strands the loop). The `## Pending decision` block (with the *"`answer: <option>`"*
   instruction) is already written and `status: WAITING FOR INPUT` is saved, so **resume is automatic**:
   the next `--tick` polls for the written answer and continues from `prior_status` once it appears —
   even in a brand-new session.
   (Shipped-wrapper loops pay nothing while waiting: `superagent-tick.sh` polls the file in bash and
   only launches a session once the answer exists — `SUPER_INPUT_GATE` — and notifies the operator
   once on parking — `SUPER_NOTIFY_CMD`.)
   In `cron` mode, if you'd rather not burn ticks re-polling, `stop_driver()`
   to pause; the next `/<consumer> <bootstrap-input>` re-arms and resumes. `release_lock()` and end the tick.

**Required shape of a pending decision.** Plain language a person outside the loop understands, in
this order; Decision IDs, hashes, run ids, budget accounting and the panel's per-option analysis go
in the trailing reference list, never in the body:

```markdown
## Pending decision
<Repeat: same failure as <IDs> — <what each earlier answer authorised; why it did not resolve it>>   ← only when the repeat check fired
**What failed:** <one sentence>
**Most likely cause:** <one sentence> — because <two or three facts>. Not checked: <what was not checked>.
**Recommended:** `<option>` — if chosen, the loop will <what it does next>.
**Other options:**
- `<option>` — <one line, with its cost>
**How to answer:** write `answer: <option>` under this block (or `answer.sh <slug> "<option>"`). The
option name alone is a complete answer.
**Reference:** <Decision ID, PR, run ids, plan/ledger paths, panel verdicts, budgets>
```

`<slug>` is the **registered slug** from the tick prompt's `Registered loop slug:` line (the name of
the loop's `~/.config/superagent/<slug>.env`). It often differs from the loop file's basename, so never
derive it from the loop file name; when the prompt says `none` (or there is no tick prompt), drop the
`answer.sh` clause and give only the `answer:` line.

A **protected-change request** is a yes/no question in the same shape. In place of the
Recommended / Other options lines it carries:

```markdown
**Approve this change?** In `<file>`: `<old value>` → `<new value>` — protected because <the glob it matches, or the project rule that pins it>.
**On yes:** <what the loop does — e.g. applies exactly this change on PR #N, pushes, waits for CI>.
**On no:** <the route it takes — decline/defer the step, or re-plan — and what that costs>.
**How to answer:** `answer: yes` approves exactly this change; `answer: yes <value>` approves the same
change with a different value; `answer: no` takes the no path.
```

`yes` approves exactly the change described and nothing wider; `yes <value>` substitutes the value.
Record the approved change verbatim under `## Decisions` (files, old → new, the answer as written);
it is authority for that change only, and the next dispatch receives it as guidance. `no` routes as
the block states.

**A specification gap needs a necessity test.** Before a block asks the owner to settle a gap the
sources leave open, it states which acceptance case depends on the gap and whether a superreplan
remedy 1–3 avoids it — that is, whether the stage still meets its stated goal without that case. When one does, the **recommended** option is that remedy as a yes/no question,
and settling the gap is listed as the alternative. When the owner must settle the gap, the block
offers named candidate values with a recommendation — never a request to author domain semantics,
policy or specification text.

A block is **invalid**, and must be rewritten before it is saved, when:

- every option asks for more authority, evidence, attempts or budget;
- it states no likely cause, unless it says which read-only checks were tried and what each returned;
- answering it requires the owner to write the disposition text — a single word or short phrase must
  always be a valid answer;
- it asks the owner to settle a specification gap without the necessity test above, or asks for
  free-text policy instead of offering named candidate values.

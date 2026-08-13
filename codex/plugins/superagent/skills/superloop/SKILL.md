---
name: superloop
description: Shared autonomy-loop chassis — the gitignored loop-status state file, the cron/external driver, the overlap lock, the context-handoff (session skill-budget) gate, the sync gate, the PR-merge discipline, and the 3-subagent escalation ladder. A clause library (L1–L7) invoked via the Skill tool by autonomy-driver skills (superagent today) to avoid re-implementing the loop machinery.
license: all rights reserved
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

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

## Subroutine contract — read before applying the clauses

When `superagent` (or any autonomy-driver skill) invokes this skill via the Skill tool, you (the calling
agent) are running superloop as **one step inside the caller's workflow**, not as a standalone task. After
you apply a clause, you **MUST return control to the calling skill and immediately continue executing the
caller's next section** — do NOT end your turn, do NOT wait for user input, do NOT print a "superloop
complete" report. **Superloop has no Final Report of its own; the caller writes the only user-facing
report** (the caller's per-tick report).

## Caller-supplied parameters (the work-model seam)

The caller supplies, once, at invocation:
- **`<consumer>`** — the caller's own slash-command name, used in the driver's tick prompt (`/<consumer> --tick <loop-file>`) — see L2. For superagent this is `superagent`.
- **`<bootstrap-input>`** — the caller's required bootstrap input, the L2 hard gate (no input + no existing loop file ⇒ print the hard-gate message and exit). Must be the goal's **root** seed/master plan (superagent: the root `<PLAN.md>`) — see L2.
- **Status vocabulary + role→value mapping** — the caller's concrete `status:` values *and* the mapping of each onto L1's generic roles (a *ready* state, a *transient/running* state, `WAITING FOR INPUT`, `DONE`), plus any extra frontmatter fields the caller stores beyond the L1 baseline — see L1.
- **Heavy-step definition + THRESHOLD** — what increments `session_skill_count`, and the handoff THRESHOLD (this plugin's callers resolve it from `SUPER_HEAVY_STEP_LIMIT`, default 6) — see L4.
- **Be-sure artifact list** — the output file(s)/PR(s) the caller's just-completed sub-step reports, which the Be-sure verification confirms are present and tracked on local `main` — see L5/L6.
- **Escalation option-set + apply actions** — the concrete options and what "apply" does per trigger — see L7.
- **Per-tick body & DONE-condition** — entirely the caller's; superloop never dispatches the work.

## Clause index

- **L1** — The loop-status file (location, format, `primary_root()`, goal-folder derivation, gitignore, generic status roles).
- **L2** — Drivers & guard/bootstrap/resume (Driver A cron, Driver B external, context model, Step-0 branching, `stop_driver()`).
- **L3** — Overlap lock (`acquire_lock()` / `release_lock()`).
- **L4** — Context-handoff gate (`check_session_budget()`).
- **L5** — Sync gate (`sync_main()` + Be-sure verification).
- **L6** — PR integration discipline (CI-green gate + `--admin` merge via `superauthor` A7 + post-merge sync/be-sure + CI-red escalation trigger).
- **L7** — Decision-escalation ladder (3-subagent panel → user escalation).

---

## L1 — The loop-status file

State lives in a single per-goal file: `<goal-folder>/<SUPER_LOOP_STATUS_DIRNAME>/<YYYY-MM-DD>-<slug>.md`.

The **goal folder** is derived from `<PLAN.md>` the same way `superplan` does it (its *Goal
Identification* step): the directory that contains the `master-plans/` / `plans/` subfolders for this
plan family — the **parent** of the `master-plans/` folder the seed sits in, **not** that
`master-plans/` folder. Goal folders live under the repo's goal-folder root `<SUPER_GOAL_ROOT>`
(worked example from the originating repo: `SUPER_GOAL_ROOT=vault/network-compose`), so the loop file lands at
`<SUPER_GOAL_ROOT>/<goal>/<SUPER_LOOP_STATUS_DIRNAME>/<date>-<slug>.md` — a sibling of that goal's
`master-plans/`, `plans/`, `reports/`, `findings/`.

The `<SUPER_LOOP_STATUS_DIRNAME>/` directory is **gitignored** (pattern
`<SUPER_GOAL_ROOT>/**/<SUPER_LOOP_STATUS_DIRNAME>/` — worked example from the originating repo:
`vault/network-compose/**/loop-status/`). It is **local-only state** — never commit it, never open a PR for it, just
Write it with the Write tool. Being gitignored, it survives `superplan`/`superrun`'s `git checkout -b …
/ checkout main / pull` dance untouched and can never be swept into one of their explicit-`git add`
docs commits.

**The loop-status file always lives in the primary checkout, never in a worktree.** Because
`<SUPER_LOOP_STATUS_DIRNAME>/` is gitignored, it is physical working-tree state that exists only in the primary
checkout — it is **absent from every linked git worktree**. If the loop is launched from inside a
worktree (e.g. one created by `EnterWorktree` for plan execution), resolve the primary checkout root
**first** and root the loop-status path there:

```
# primary_root(): the checkout this worktree was created from (a no-op if already primary)
primary_root="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
# In the primary checkout, --git-dir == --git-common-dir (both `.git`); in a linked worktree they
# differ (--git-dir → <primary>/.git/worktrees/<name>, --git-common-dir → <primary>/.git), so
# `dirname` of the common dir is the primary checkout root — regardless of the primary's current branch.
```

Every loop-status read/write, the overlap-lock dir, and the Sync gate's `git` commands use
`primary_root` as their base. Derive the goal folder (`<SUPER_GOAL_ROOT>/<goal>/`) as before, but
root it at `primary_root`: the loop file is
`<primary_root>/<SUPER_GOAL_ROOT>/<goal>/<SUPER_LOOP_STATUS_DIRNAME>/<date>-<slug>.md`.

Format — YAML frontmatter is the machine state; the body is an append-only human log:

```markdown
---
master_plan: <SUPER_GOAL_ROOT>/<goal>/master-plans/<seed>.md   # repo-relative path to the ROOT seed
status: WAITING FOR PLAN          # caller's status vocabulary (see the status roles below)
plan_exhausted: false             # CALLER-SPECIFIC: e.g. superagent's two-signal DONE; other consumers add their own work-model fields here
prior_status:                     # status to restore after a WAITING FOR INPUT escalation resolves
driver: external                  # the only driver in this build (external scheduler — fresh context per tick)
cron_id:                          # unused in this build (Claude Code in-session driver only); leave empty
created: <today>
iteration: 0
session_skill_count: 0            # heavy skills run in the CURRENT cron session; reset to 0 at each cron session start; drives the L4 handoff (cron only)
---

## Pending decision
<!-- present only while status == WAITING FOR INPUT: the question, the panel's option analysis,
     and how to answer. Cleared once resolved. -->

## Decisions
<!-- append-only: each escalated decision, the panel verdict (or "user-resolved"), the chosen
     option, and one-line rationale. -->

## Iteration log
- (one entry appended per tick: iteration #, skill invoked, result, PR URLs, status transition)
```

The baseline fields (`master_plan`, `status`, `prior_status`, `driver`, `cron_id`, `created`,
`iteration`, `session_skill_count`) are owned by superloop. `plan_exhausted` is **caller-specific** —
it is superagent's two-signal-DONE field; other consumers add their own work-model fields here.

### Status vocabulary

**Generic status roles (superloop owns these semantics; the caller names the values):**
- a **ready** state — the loop is poised to run the caller's per-tick body (superagent: `WAITING FOR PLAN`, `WAITING FOR RUN`).
- a **transient/running** state — set at the start of a tick, replaced before the tick ends; **persisted ⇒ a crashed tick**, self-healed by L2's crash-recovery (superagent: `PLANNING`, `RUNNING`).
- **`WAITING FOR INPUT`** — a decision the escalation ladder (L7) could not resolve is awaiting the user.
- **`DONE`** — the caller's DONE-condition is satisfied (superagent: tree-exhaustion).

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

`$ARGUMENTS` arrives in one of two forms.

#### (A) Internal tick — `--tick <loop-file>`

Fired by the driver each interval — the in-session `cron` job, **or** an external Desktop routine / OS
cron, **possibly in a fresh empty context**. It **carries the loop file's full path directly** — no
goal-folder derivation, no search. This is the only form that advances the state machine.

1. **`acquire_lock()`** (see **L3**). If another tick is already in flight → **exit immediately**
   (no-op; the next fire retries). This is what keeps fresh-session external ticks from overlapping.
2. Read the named loop file. The carried path is the **absolute** path under the primary checkout, so
   the tick's cwd is irrelevant for reading/writing the file. Still resolve `primary_root()` (see **L1**)
   for the lock dir and the Sync gate's `git` commands — a tick can fire while cwd is a worktree. A clean
   context is fine — **all** state (`status`, `plan_exhausted`, `driver`, `cron_id`, decisions) is in the
   file, not in conversation memory.
3. If `status` is **`DONE`** → `release_lock()`, no-op, and (in `external` mode) remind the user to
   disable the Desktop routine / scheduler entry; exit. Otherwise run the **Context-handoff gate (L4,
   `check_session_budget()`)** — if it hands off, this tick ends there — then go to the caller's per-tick
   body.

Do **not** re-bootstrap or re-arm any driver from a tick. `release_lock()` runs at the end of the tick
and on every early-exit/escalation path.

#### (B) User entry — `<bootstrap-input> [--driver=cron|desktop|headless]`, or empty

1. **Hard gate.** If no required bootstrap input and no existing loop file can be located → print the
   caller's hard-gate message (above) and exit.
2. **Driver.** Only the `external` driver exists in this build. Treat any `--driver=` value as
   `external`; if `--driver=cron` was explicitly requested, say that the in-session cron driver is
   Claude Code-only before continuing. An existing loop file's `driver:` must be `external`.
3. **Locate state.** Derive the goal folder from the required input (the `superplan`
   Goal-Identification rule — parent of the `master-plans/` folder), then **root it at
   `primary_root()`** (see **L1**) — so the lookup and the lazy first-write target are in the primary
   checkout, not the worktree the loop may have been launched from. The input path stays repo-relative;
   only the on-disk base changes. Look in `<primary_root>/<goal-folder>/<SUPER_LOOP_STATUS_DIRNAME>/`
   for a file whose `master_plan:` matches the input. Deterministic, single-directory lookup — not a
   global scan. The `<SUPER_LOOP_STATUS_DIRNAME>/` subdir is created lazily on first write (no `mkdir`).
4. **Guard / bootstrap / resume — branch on `driver`:**

   **`external` mode** (Desktop routine / OS cron — **no `CronCreate`, no `CronList`**; the scheduler is
   user-managed):
   - **No loop file** → **FRESH START**: create the loop file (`driver: external`, the ready `status`,
     …, `cron_id:` empty, `session_skill_count: 0`), **print the exact scheduler entry to create**
     (Desktop routine or headless `codex exec` recipe from **Driver B**, with this loop file's absolute
     path), then continue to the caller's per-tick body to run the first iteration now. Subsequent ticks
     come from the external scheduler.
   - **Loop file exists, non-terminal** → report `status`/`iteration`/last log line and **re-print the
     scheduler entry** so the user can confirm the Desktop routine / cron entry is firing `--tick` on
     this loop file. (There is no in-session driver to "resume" — the external scheduler is the driver.)
     Do not run a tick here unless the user asks; the scheduler will.
   - **`status: DONE`** → report "already complete" and remind the user to disable the Desktop routine /
     scheduler entry; exit.

After branching, read `master_plan`, `status`, `plan_exhausted`, `prior_status`, `driver`, `iteration`,
`session_skill_count` from the loop file before the per-tick body. When form (B) continues to run the
first tick, wrap it in the lock too — `acquire_lock()` first (skip if held), `release_lock()` at the
end — and run the **Context-handoff gate (L4)** before the body, exactly like a form-(A) tick.

### Crash recovery — a persisted transient/running state means a crashed tick

The transient/running role (L1) is transient *within* a tick: the loop sets it, runs the body
synchronously, then sets the next status — all in one turn. Ticks never overlap: in `cron` mode they
fire between turns; in `external` mode the **lock (L3)** serializes them. So a **persisted** transient
state means a crashed prior tick (which also left a stale lock that `acquire_lock()` steals after
`SUPER_LOCK_STEAL_MIN` minutes (default 90)). **Self-heal:** log a recovery note, **map the persisted transient state back to its matching
ready state** (the caller supplies the transient→ready mapping for its own status values — superagent:
`PLANNING → WAITING FOR PLAN`, `RUNNING → WAITING FOR RUN`), and fall through to that branch this tick.

### Driver A — `cron` (Claude Code only — NOT available in this build)

The in-session cron driver requires Claude Code's CronCreate/CronList/CronDelete tools and does not
exist on Codex. Driver B below is the only driver.

### Driver B — `external` (Desktop scheduled task, or headless OS cron) — CLEAN CONTEXT

`/<consumer> <bootstrap-input> --driver=desktop` (aliases `--driver=external` / `--driver=headless`)
bootstraps the loop file with `driver: external`, **arms NO `CronCreate` job**, and **prints the exact
scheduler entry to create**. An external scheduler then fires `/<consumer> --tick <loop-file>` on its
interval, each in a **fresh session = clean context**.
- **Headless OS cron / launchd / systemd timer**: the tick's prompt is a **file read**, not a skill
  invocation by name — the scheduler asks the CLI to read this plugin's supervisor SKILL.md directly
  (`<plugin-root>/plugins/superagent/skills/<consumer>/SKILL.md`) and run exactly one `--tick`. The
  loop's own internal per-tick dispatches (e.g. superagent's `superagent:superplan` /
  `superagent:superrun`) still go through the skill mechanism once the session is running, so the
  plugin must be installed via the Codex plugin marketplace (`codex plugin marketplace add
  <plugin-repo>/codex`, then `codex plugin add superagent@superagent`) — there is no per-invocation
  `--plugin-dir` analog. The tick runs via the Codex CLI's headless mode (`codex exec`) in a **fresh
  session per tick** and **must never resume a prior session** (a fresh process per tick is what
  bounds context — L4 is a no-op in `external` mode, so the loop runs straight to `DONE` with no
  handoff).
  ```
  # <plugin-root> = the installed marketplace root (the directory containing plugins/ and templates/).
  cd <repo> && OPENAI_API_KEY=... codex exec \
    "Read <plugin-root>/plugins/superagent/skills/<consumer>/SKILL.md and execute exactly ONE --tick on loop file <loop-file>, in unattended/non-interactive mode: NEVER ask the user a question in chat; if a decision needs the user, write the pending-decision block, set status to WAITING FOR INPUT, and exit per the skill. Then stop." \
    --dangerously-bypass-approvals-and-sandbox \
    >> /tmp/<consumer>.log 2>&1
  ```
  Schedule with cron/launchd/systemd; auth via `OPENAI_API_KEY` in the scheduler env, or the CLI's
  stored login (`codex login`) where the scheduler user has one (a headless scheduler can't do
  interactive OAuth). The shipped `scripts/` wrappers are harness-aware: `SUPER_HARNESS=codex` makes
  `superagent-tick.sh` fire `codex exec` (sandbox per `SUPER_CODEX_SANDBOX`, default
  `danger-full-access` — codex's `workspace-write` keeps the repo's top-level `.git/` read-only,
  which breaks git fetch/commit and parks the loop at the sync gate) — see scripts/README.md.
- Duplicate guard: **not** `CronList` (each fresh session's `CronList` is empty). The **lock (L3)**
  prevents overlap; "is a loop already set up?" is answered by the loop-file `status` plus the fact that
  the *Desktop routine / scheduler entry* is what the user manages.
- **Interactive console is a separate, start/stop-independent plane.** The scheduler is the *driver*;
  a human can additionally open an interactive Claude session to **monitor** (read the
  loop file, tail the driver log, `gh pr/run`) and to **answer** a `WAITING FOR INPUT` decision — either
  by running one attended `--tick` (a person is present, so the L7 Rung-2 branch uses `AskQuestion` and
  applies the answer under the L3 lock) or by writing `answer: <option>` into the loop file for the next
  scheduled tick to poll. Because all state is in the loop file, this console can be started and stopped
  at will without affecting driver progress (only the driver process should use `--resume`-free fresh
  ticks; an interactive console may `--resume` freely).

### `stop_driver()` — used wherever the loop completes or pauses
- **external:** the Desktop routine / scheduler entry is **user-managed** — the skill cannot delete it.
  Leave the terminal/paused status in the loop file (further `--tick` fires no-op on `DONE`, or re-asks
  on `WAITING FOR INPUT`) and **print a clear instruction to disable the Desktop routine (or remove the
  cron/launchd entry)** for this loop file.

Stop a loop manually: disable/remove the scheduler entry for this loop file. Re-running
`/<consumer> <bootstrap-input>` reports current state and re-prints the scheduler setup.

---

## L3 — Overlap lock — `acquire_lock()` / `release_lock()` (REQUIRED for every tick, both drivers)

External ticks run in **independent sessions**, so a long tick (a run with a 30-min CI gate) can
still be running when the next interval fires. Guard every tick with an atomic file lock in the
loop-status dir so two ticks never run concurrently:
- **`acquire_lock()`** — atomically `mkdir "<loop-file-dir>/.<loop-file-basename>.lockd"`. `<loop-file-dir>`
  is the absolute primary-checkout path (it lands under `primary_root()` — see **L1**),
  so the lock is unambiguous even when the loop is launched from a worktree. On **success**,
  write a unix timestamp to `…lockd/acquired` and proceed. On **failure** (held): read
  `…lockd/acquired`; if older than **`SUPER_LOCK_STEAL_MIN` minutes (default 90)** (a crashed tick), `rm -rf` it, re-acquire, and log a
  recovery note; otherwise **exit the tick immediately** — another tick is in flight, and the next
  scheduled fire retries.
- **`release_lock()`** — `rm -rf` the lock dir on **every** exit path of a tick (normal end, early
  no-op, escalation/STOP). In `cron` mode ticks already never overlap, so the lock is a harmless no-op;
  in `external` mode it is load-bearing (it is what replaces `CronList`'s implicit single-session
  serialization).

---

## L4 — Context-handoff gate — `check_session_budget()` (check BEFORE every iteration)

In this build the external driver is the only driver, and every tick runs in a fresh context — nothing
accumulates, so `check_session_budget()` is a structural no-op: always proceed straight to the caller's
per-tick body. (`session_skill_count` is never consulted.)

---

## L5 — Sync gate — local `main` must equal `origin/main` (REQUIRED around every skill dispatch)

The caller's sub-steps (`superplan`/`superrun`, or a consumer's own fix-PR flow) merge their PRs to
`origin/main` and then try `git checkout main && git pull --ff-only`. **That local pull can silently
fail or be skipped** — most commonly when a `git checkout main` runs *inside a worktree* (where `main`
is already checked out in the primary tree and the checkout errors **after** the remote `--admin` merge
already happened), or on a brief propagation race right after `gh pr merge`. When it does, the **primary
checkout stays stale**: the loop-status file is fine (gitignored/local), but the **tracked plan tree**
the next sub-step reads (progress tables, plan files, closeout rows) is behind `origin/main`. The next
traversal then acts on stale rows — **re-planning a step whose plan row already merged** (an infinite
re-plan loop), or failing to find a leaf whose closeout already merged. The loop must never read, or
hand a sub-step, a stale tree.

Run this gate in the **primary repo checkout** (the one holding the loop-status file). Resolve
`primary_root()` (see **L1**) and run **every** gate `git` command against it —
`git -C "$primary_root" <…>` (fetch, rev-parse, rev-list, merge --ff-only, status, checkout). This is
what makes `git checkout main` correct when the loop itself was launched in a worktree: it operates
on the **primary tree**, not the worktree (which cannot check out `main` — it is already checked out in
the primary tree), and satisfies the "the one holding the loop-status file" qualifier above. In the
primary checkout `primary_root` resolves to cwd, so `git -C "$primary_root"` is a no-op there. All
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

### Be-sure verification (after a skill, post-`sync_main()`)
The caller's just-completed sub-step reports the PR(s) it merged and the file(s) it wrote; confirm each
is present and tracked on local `main`:
- the reported output file(s) exist and are tracked on `main` — `git ls-files --error-unmatch <path>`;
- (optional) the merge is in history — `git log --oneline origin/main | grep <pr-number>`.

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

An autonomy loop that opens and merges its own PRs MUST follow the same `SUPER_PROTECTED_MAIN`-gated
discipline the rest of the `super*` family uses (if `SUPER_PROTECTED_MAIN=true`, the shipped default,
the default branch is a protected branch and this MUST go through a feature branch and a PR; if
`SUPER_PROTECTED_MAIN=false`, a direct commit to the default branch is permitted instead). This
clause is the autonomy-loop view of it; the **canonical merge
skeleton lives in `superauthor` clause A7** (merge per `SUPER_MERGE_METHOD`, default `squash`; pass
`gh pr merge --admin` only if `SUPER_ADMIN_MERGE=true`, otherwise never — reaching for it unprompted on
a repo whose branch protection doesn't require it trips the harness security classifier). Do not
duplicate that skeleton — apply A7's.

1. **CI-green gate before merge.** A code PR is merged only once its gating CI lane is green (the caller
   names the lane). If CI is **red**, do **not** merge — route to the escalation ladder (L7) with the
   failure as the decision packet.
2. **Merge via A7.** Apply `superauthor` A7's merge — per `SUPER_MERGE_METHOD` (default `squash`), never
   `--admin` unless `SUPER_ADMIN_MERGE=true` permits it. If `SUPER_PROTECTED_MAIN=true` (the shipped
   default), the default branch is protected; never direct-push. If `SUPER_PROTECTED_MAIN=false`, a
   direct commit to the default branch is permitted instead.
   Commit/PR text carries no AI-attribution / `Co-Authored-By` trailers (repo policy).
3. **Post-merge sync + be-sure (L5).** Immediately run `sync_main()` and the Be-sure verification so the
   primary checkout reflects the merge before the next tick reads the tree.

**superagent's subset.** superagent does **not** itself open/merge work PRs — `superplan`/`superrun`
do that inside their own flows. superagent therefore applies only **L6.1's CI-red → L7 escalation
trigger** and **L6.3's post-merge sync+be-sure** (around each `superplan`/`superrun` dispatch). A
consumer whose per-tick body opens its own PRs applies the full clause.

---

## L7 — Decision-escalation ladder — autonomy posture

The bar is **not** "never ask the user." Routine actions (commits, PR merges) never need approval, but
delegated skills legitimately surface genuine decision points. The loop resolves them itself first,
and escalates to the user only as a last resort — always leaving a durable resume path.

**Triggers** (watched in each delegated skill's Final Report — the integration point, so the
sub-skills' internals need no rewrite): a CRITICAL / ⚠️ finding, a `not-traversable` result, a
BLOCKED / CI-red outcome, or any place a skill surfaces a clarification rather than completing cleanly.
Standing posture: if a delegated skill would otherwise ask the user inline, resolve it via this ladder
instead.

> **Depth-1 subagent constraint.** Subagents cannot spawn subagents (depth-1). The read-only
> 3-subagent panel fits within this limit; the supervisor that runs the panel **cannot itself be a
> subagent** — it must be the top-level loop agent.

### Rung 1 — Subagent panel (resolve autonomously)
Dispatch **3 independent subagents in parallel** (one `spawn_agent` call per panelist, all three in a
single message. Pass the panel pins as spawn parameters: `SUPER_MODEL_PANEL` → `model`,
`SUPER_EFFORT_PANEL` → `reasoning_effort`; `inherit` = omit that parameter. There are no
agent-definition files in this build — the pins ride the spawn call itself, and nothing needs a
`superagent:init` re-run. Wait for all three children's results before proceeding; never
fire-and-forget the panel).
Give each the **same packet**: the decision/blocker statement, the relevant plan +
report excerpt, and pointers to the code/vault context. Keep the prompts identical so diversity comes
from independent reasoning, not framing. Require each to return a structured verdict —
`{chosen_option, rationale, confidence}` over the concrete options (or `insufficient-info`).

**Converge.** If **≥2 of 3** agree on the same option with non-low confidence → **adopt it.** Record
it under `## Decisions` (option + one-line rationale + "panel 2/3" or "3/3"), then **apply** the
**caller-supplied option set** and its per-option apply action (superagent: retry the run with guidance
/ route back to the ready-to-plan state / mark the step declined):
- a scope/clarity question → re-invoke the same skill with the decision as guidance context (e.g. as
  `<TOPIC>` framing or an explicit directive);
- a BLOCKED execution → apply whichever option the panel chose from the caller-supplied set (superagent:
  retry `superrun` with the unblock guidance, **or** route to the ready-to-plan state for a re-plan,
  **or** mark the step declined).

### Rung 2 — Escalate to the user (last resort)
If the panel cannot converge (split, or all `insufficient-info`):
1. Write a `## Pending decision` block: the question, the panel's per-option analysis, what each
   option implies, and how to answer. Save the current `status` into `prior_status`; set
   `status: WAITING FOR INPUT`.
2. **Interactive session** (a person is present — typically `cron`/attended): call `AskUserQuestion`
   now (present the panel's options + its leaning). On an answer → record under `## Decisions`
   ("user-resolved"), clear the pending block, restore `prior_status`, apply, and **continue this
   tick** — the driver keeps firing, so the loop never breaks.
3. **Scheduled / unattended tick** (external Desktop/headless, or a `cron` tick with no one present):
   do **not** block on `AskUserQuestion`. The `## Pending decision` block (with the *"`answer: <option>`"*
   instruction) is already written and `status: WAITING FOR INPUT` is saved, so **resume is automatic**:
   the next `--tick` polls for the written answer and continues from `prior_status` once it appears —
   even in a brand-new session. In `cron` mode, if you'd rather not burn ticks re-polling, `stop_driver()`
   to pause; the next `/<consumer> <bootstrap-input>` re-arms and resumes. `release_lock()` and end the tick.

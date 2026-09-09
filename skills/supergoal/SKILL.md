---
name: supergoal
description: Use when starting a brand-new multi-PR initiative from a goal description (not an existing plan file) — creates the goal vault folder (YYYY-MM-DD-hh_mm-<slug>), its goal-directives.md, the standard subfolders, and the ROOT master plan that seeds the planning tree.
argument-hint: "<goal description | path/to/goal.md> [--autoconfirm] [--slug <slug>] [--operation <path>]"
license: MIT
related skills: superauthor, superplan, supertraverse
---

# Supergoal

Given a **goal description** (a prose prompt, or a path to an existing `.md` file holding one — not a `<PLAN.md>`), scaffold a new *goal folder* in the vault
and author the **root master plan** that seeds the planning tree — the document `superplan` later
descends into.

**Input:** `<GOAL>` — the argument string: a prose goal description **or** a path to an existing
`.md` file holding one, optionally followed by `--autoconfirm`, `--slug <slug>`, and
`--operation <path>` (parsed in step 1). **Required.** Without `--operation`, manual behavior is
unchanged.

## What supergoal is — and how it differs from superplan

`superplan` operates on an **existing** seed/master plan: it descends a plan tree, plans one step, and
ascends. **supergoal creates the *root* of that tree.** Three consequences follow:

- It takes a **goal-description prompt**, not a `<PLAN.md>`.
- It does **no descent and no ascent** — there is no existing tree to descend, and the root has no
  ancestors to update.
- The root plan it writes carries **no parent-seed reference** — per `supertraverse` C5, the root is
  precisely the plan that has none.

supergoal produces exactly one **root seed/master plan** plus the goal-folder scaffold and — **only after
confirmation** (the human gate, or step 7's two-factor auto-confirm) — writes them to the vault and ships
them via PR. It does **not** execute the planned work.

## Authoring mechanics come from superauthor (REQUIRED)

**Invoke the `superagent:superauthor` skill via the Skill tool** at the start of the run and apply its clauses
A1–A8 throughout. superauthor owns the shared mechanics — the no-execution rule (A1), the
authoring standard (A2), no-placeholders (A3), generic self-review (A4), standing
authorization (A5), findings capture (A6), commit-and-merge-via-PR (A7), and the Final Report (A8).
supergoal supplies the caller-specific specifics below and adds nothing tree-related (there is no tree
above the root).

> Apply **A4 alone** for self-review. The tree-specific self-review items superauthor calls out
> (parent-seed reference, immediate-parent row, ancestor ascent) **do not apply** — the root has no
> parent and no tree above it.

### supergoal OVERRIDES superauthor A5 — confirm before any vault write (REQUIRED)

superauthor A5 ("standing authorization — proceed without pausing") and A2's "the scratch draft is
written into the vault automatically" **do NOT apply to supergoal.** supergoal makes two hard guarantees
instead:

1. **Plan first, write nothing early.** All authoring — the root master plan, `goal-directives.md`, and
   any `findings/` docs — is produced to a **scratch path outside the vault** (e.g. `$TMPDIR/` or
   `.claude/scratch/`). **No goal folder, no subfolder, and no vault file is created until planning is
   complete *and* confirmation is satisfied** (human approval, or step 7's two-factor auto-confirm). Deriving the folder *name* (step 2) and the read-only "does
   it already exist?" check are allowed; `mkdir` and writing files are not.
2. **Confirmation gates the vault write.** After self-review, supergoal **pauses and asks the user
   to confirm** the drafted plan (step 7) and writes to the vault / opens the PR **only** after approval.
   The human pause is the default and is **not** waived by auto-accept / `bypassPermissions` mode; its
   **sole** exception is step 7's two-factor auto-confirm — `--autoconfirm` **and**
   `SUPER_GOAL_AUTOCONFIRM=true` together — under which the step-6 self-review stands as the confirmation.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${CLAUDE_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

## Vault root

Resolve `SUPER_GOAL_ROOT` (above). If it starts with `/` or `~`, the vault is **external**:
`<vault_root>` is that path (`~` expanded to `$HOME`, one trailing `/` stripped), resolved physically
(`cd "<path>" && pwd -P`) so it matches the paths `launch.sh` stores, and the vault is its own git
repository outside the checkout. Otherwise `<vault_root>` is `<primary_root>/<SUPER_GOAL_ROOT>`
(`primary_root` = `dirname "$(git rev-parse --path-format=absolute --git-common-dir)"`). Every goal
folder, project folder, loop-status file and lock derives from `<vault_root>`; **never join
`SUPER_GOAL_ROOT` onto the checkout root by hand.** The same rule is `vault_root` /
`vault_is_external` in `scripts/_common.sh`.

## Workflow

### 1. Input gate

`<GOAL>` is the full argument string. **Parse the optional flags off the *end* of it first** — so a prose
goal that happens to contain the words "slug" or "autoconfirm" is never mis-parsed: strip a trailing
`--autoconfirm` (record it as a boolean for step 7), a trailing `--slug <slug>` (record `<slug>` for
step 2), and a trailing `--operation <path>`. What remains, trimmed, is the **goal source**.

- If the goal source is empty → respond with exactly `I need a goal description` and **exit**.
- If the goal source names an **existing `.md` file** → read that file; its contents are the goal
  description. Remember the file's path — step 5 cites it as `**Source:**`.
- Otherwise the goal source is a **prose** goal description (there is no source file).

With `--operation`, load duplicate-key-rejecting JSON with exactly the operation fields accepted by
`_coding_loop_state.py`. Require `phase` = `META-PLANNING`, empty `code_commit` and `report`, and
valid nonempty remaining identity. The goal source must resolve to the recorded `meta_plan`, and the
recorded `goal_folder` must resolve inside `<vault_root>`. The operation file is read-only. Reject a
caller slug that does not equal the recorded goal folder's `<project-slug>-r<N>` suffix.

The operation-mode last output line is compact JSON with `outcome`, `phase`, `operation_id`, `round`,
`meta_plan`, `goal_folder`, `root_plan`, `goal_complete`, `goal_recoverable`,
`goal_completion_reason`, `artifacts`, and `reason`. Only verified integration on
`main` yields `INTEGRATED`; prose output, a local folder, or an unmerged commit never does.

Nothing else changes: the input-gate message is exactly `I need a goal description`, and a direct user
who passes a bare prose goal with no flags sees identical behaviour to before.

### 2. Derive identifiers

- **`<slug>`** — if step 1 captured a `--slug <slug>` value, use it, but first validate it is kebab-case
  (matches `^[a-z0-9]+(-[a-z0-9]+)*$`); if it is not, respond with exactly
  `supergoal: --slug <value> is not a valid kebab-case slug` (with the offending value) and **exit**.
  Otherwise derive a concise, stable, descriptive kebab-case slug summarizing the goal (mirror the style
  of existing goal folders — worked example from the originating repo: `graphgen-grammar-first-redesign`).
- **`<STAMP>`** — today's date plus the current UTC hour and minute (`date -u +%Y-%m-%d-%H_%M`), e.g.
  `2026-06-14-09_30`. This is the dated prefix for the goal folder and the dated files written into it.
- **`<DATE>`** — today's date (`date +%Y-%m-%d`); used **only** for the git branch name (step 9).
- **Goal folder** — `<vault_root>/<STAMP>-<slug>/` (see **Vault root**). This is the **goal folder** superauthor's
  clauses write under. If the folder already exists, disambiguate the slug; if it is clearly the same
  initiative, report that and **exit** — **never overwrite an existing goal folder**. When `<slug>` came
  from `--slug`, do **not** auto-disambiguate — report the collision and **exit**, because the caller
  (e.g. supermeta) depends on the exact `<STAMP>-<slug>`.

In operation mode, take `N`, `<STAMP>`, `<slug>`, the source revision and exact goal folder only from
the recorded identity; never consult the clock or disambiguate. Before authoring, run
`_coding_loop_evidence.py reconcile <primary_root> <vault_root> --operation <path>`. If it returns
`INTEGRATED` with `goal_complete: true`, return the exact goal/root paths and skip authoring and A7.
If `goal_complete` is false and `goal_recoverable` is true, use `goal_completion_reason` to repair
only the missing matching `goal-directives.md` or tracked scaffold directories through the normal
draft, confirmation and A7 flow. A false `goal_recoverable`, including a mismatched directive or
extra root plan, is a hard conflict; never overwrite it. `ABSENT` permits one normal
draft/approval/write flow. On `CONFLICT`, resume only exact matching scaffolding or a pending A7
branch/PR owned by this operation, then reconcile again. Any different Operation, source, round,
agreement, meta-plan, or folder identity is a hard conflict. Never validate feature-branch bytes as
main evidence.

### 3. Invoke superagent:superauthor

Invoke the `superagent:superauthor` skill (Skill tool) and apply A1–A8 for the rest of the run.

### 4. Author the ROOT master plan (per the A2 standard)

Author the root plan yourself per superauthor's A2 authoring standard, drafting to a scratch path
outside the goal folder. The root plan MUST:

- be a **seed/master plan**, routed to `master-plans/<STAMP>-<slug>.md`;
- in operation mode only, add one header line immediately after the normal header:
  `**Operation:** <id> · **Round:** <N> · **Agreement revision:** <agreement_revision> · **Source vault commit:** <source_vault_commit> · **Related:** [[<recorded meta_plan without .md>]]`;
- contain a **progress-report table** using the `supertraverse` C1 schema and C2 status vocabulary
  (do not redefine the columns or statuses here):

  | Step | Status | Plan | PR | Comments |
  |------|--------|------|----|----------|

  decomposing `<GOAL>` into its top-level steps, with **every `Plan` cell blank** and **every `Status`
  `incomplete`**. A blank `Plan` on a not-completed step is exactly the *available task to plan* signal
  `superplan`'s descent keys on — so this is what makes the root traversable. **Place this table at the
  START of the plan** — the first major section of the plan body, immediately after the title (the root
  plan has no parent-seed reference) and before any scope/context/analysis sections. The table is the
  navigational index `superplan`'s descent reads first; do **not** bury it below the analysis that
  justifies the decomposition;
- carry **no parent-seed reference** (it is the root);
- reference `goal-directives.md` (step 5) and any `findings/` docs captured under A6, so a fresh agent
  reviews them;
- carry the **planning-session payload** — the sections below, in this order, **after** the
  progress-report table. supergoal typically runs at the **end of a planning session**: every piece of
  context, every decision, and every rejected alternative that session produced exists only in the
  conversation until it is written down here. This plan — with `goal-directives.md` and `findings/` —
  is the **only** context a fresh `superplan` agent gets when it descends into a step, so the payload
  is what makes the table rows plannable:

  1. **Goal & success criteria** — the distilled objective and the measurable finish line
     (which step(s) satisfy each criterion).
  2. **Context** — the current state of the system the goal touches, and the exact files/docs a
     zero-context planner must read before descending.
  3. **Locked decisions** — every decision the planning session settled, each with the
     alternative(s) rejected and why, stated as inputs the sub-plans implement and do **not**
     re-litigate.
  4. **Per-step guidance — one subsection per table row (REQUIRED).** For each step: its scope
     (what is in and what is out), key requirements and constraints, dependencies and interfaces
     to adjacent steps, and how the step's completion is verified — written so a fresh `superplan`
     agent can plan that step from this file and its referenced docs alone. A row whose only
     description is its own row text is **not plannable**: `superplan`'s spec-coverage self-review
     reads the seed's sections for the step as the step's requirements, so an absent section makes
     that review vacuous.
  5. **Cross-step constraints / invariants** — anything that binds every step (omit the section
     when there are none).

### 5. Author `goal-directives.md` (structural doc — A2's plan rules do not apply)

`goal-directives.md` is a **structural layout guide, not a plan** (A2's structural-doc carve-out), so
author it directly, drafting to scratch alongside the plan. It must be fully
**self-contained** — do **not** point the reader at any external example file. Structure:

1. **Title** — `# Goal Directives — <STAMP>-<slug>`. **When `<GOAL>` was a file** (step 1): immediately
   under the title, add a source line — `**Source:** [[<vault link to the goal file>]]` when that file
   lives inside `<vault_root>` (wikilink form, path-from-vault-root without the `.md`), or
   `**Source:** <relative repo path>` when it is a file outside the vault (a plain relative path). When
   `<GOAL>` was prose, write **no** source line. The step-7 `**Confirmation:**` line, when written, sits
   immediately **below** this source line. In operation mode only, add immediately below those lines:
   `**Operation:** <id> · **Round:** <N> · **Agreement revision:** <agreement_revision> · **Source vault commit:** <source_vault_commit>`.
2. **Goal / Objectives — FIRST**, immediately after the title (and after the optional `**Source:**` /
   `**Confirmation:**` header lines when present): the *why*, the target outcome, and success criteria
   distilled from `<GOAL>`. (This is the one intentional deviation from older directives docs that open
   with Type/Audience — supergoal puts the goal at the very top.)
3. **What `goal-directives.md` is** — a short self-documenting note: one per goal folder, lives at the
   folder root, is the authoritative map of where files go, must be kept current.
4. **Folder map** — a table of the six subfolders with a one-line purpose, lifecycle stage, and dated?
   flag each:

   | Folder | One-line purpose | Lifecycle stage | Dated? |
   |---|---|---|---|
   | `master-plans/` | Strategic anchors: master/sub-master plans, design seeds, planning handoffs, reviews | Before & across sub-PRs | Yes |
   | `plans/` | Self-contained, execution-ready implementation plans for **one** sub-PR | Just before execution | Yes |
   | `findings/` | Pre-/mid-implementation investigation: spikes, categorizations, input ledgers | Feeds a plan | Yes |
   | `reports/` | Post-implementation outcomes: closeouts, engagement/A-B results, "wiring complete" | After code runs/ships | Yes |
   | `handoff/` | Session-to-session continuity: state-of-the-world, what the next agent picks up | At a session boundary | Yes |
   | `todo/` | Open work-item backlog: deferred items, follow-ups, open-question trackers | Running, all stages | Yes |

5. **Per-folder directives** — for each of the six folders, a short "Put here / Does NOT belong" pair
   that draws the two lines people trip on: **master-plans vs plans** (strategy/seeds vs one executable
   plan) and **findings vs reports** (analysis that *informs* a plan vs outcomes that *follow* code).
6. **Naming conventions** — dated artifacts (plans, findings, post-mortems, baselines, handoff docs) use
   the prefix form `YYYY-MM-DD-hh_mm-<topic>.md`, where `hh` and `mm` are the UTC hour and minute at
   which the file is written, so `ls` lists them chronologically and files authored on the same day stay
   distinct; undated structural docs (this file, any future `README.md`/`architecture.md`) stay undated
   at the folder root.
7. **Cross-link conventions** — full-path vault wikilinks
   `[[<STAMP>-<slug>/<subfolder>/<basename-without-.md>]]`; every doc opens with a `# Title` + `**Date:**`
   / `**Status:**` / `**Related:**` header block; close the loop both ways (a plan/seed links forward to
   its `reports/` outcome; the report links back).
8. **"Which folder?" decision guide** — a short flow that routes a new file to exactly one subfolder
   (grades shipped code → `reports/`; pre-code investigation → `findings/`; one turn-key sub-PR plan →
   `plans/`; cross-sub-PR architecture/seed/handoff/review → `master-plans/`; live resume state →
   `handoff/`; deferred backlog item → `todo/`).

### 6. Self-review (A4 only)

Run superauthor A4 in full — spec coverage of `<GOAL>` against the root plan's steps, the A3
placeholder scan, and type/term consistency (supergoal authored the plan directly, so nothing has
pre-checked it).
**Skip** the tree-specific items — the root has no parent, parent row, or ancestors. Additionally
confirm:

- the progress-report table is the **first major section of the plan body** (the step-4 placement
  rule) — move it to the top if it drifted lower;
- **every table row has its per-step guidance subsection** (the step-4 planning-session payload)
  carrying scope, requirements/constraints, dependencies, and verification — add the missing
  subsection for any row that lacks one;
- **every decision, constraint, and rejected alternative from the planning session appears in the
  drafted docs** (the root plan's Locked decisions / payload sections, `goal-directives.md`, or a
  `findings/` doc) — anything left only in the conversation is invisible to the fresh step
  planners; write it in before presenting the gate.

### 7. Confirmation gate (REQUIRED — overrides A5)

Planning is now complete and **nothing has been written to the vault yet** (the goal folder does not
exist; all drafts are in scratch).

**Auto-confirm (two-factor — the only way this pause is skipped).** Resolve `SUPER_GOAL_AUTOCONFIRM`
through the **Repo configuration** block above, and check whether step 1 captured `--autoconfirm`:

- **`--autoconfirm` was passed *and* `SUPER_GOAL_AUTOCONFIRM` resolves to `true`** → the step-6
  self-review stands as the confirmation. Do **not** pause. In the `goal-directives.md` scratch draft,
  write — immediately under the title, and below the `**Source:**` line when step 5 added one —
  `**Confirmation:** auto-confirmed (SUPER_GOAL_AUTOCONFIRM=true, --autoconfirm) on <DATE>`
  (`<DATE>` = `date +%Y-%m-%d`). Then proceed directly to step 8 (write-out) and step 9 (commit & PR).
- **`--autoconfirm` was passed but `SUPER_GOAL_AUTOCONFIRM` does not resolve to `true`** → print exactly
  `--autoconfirm ignored: SUPER_GOAL_AUTOCONFIRM is not true`, then fall through to the human gate below.
  Write no `**Confirmation:**` line.
- **`--autoconfirm` was not passed** → fall through to the human gate below.

**Human gate (default — unchanged behaviour).** **Pause and ask the user to confirm before any vault
write.** Present a concise summary — do **not** dump the full drafts:

- the goal folder that **will** be created (`<vault_root>/<STAMP>-<slug>/`) and its six subfolders;
- the root plan's title and its progress-report **steps** (the table rows), so the user sees the
  decomposition;
- a one-line gist of the `goal-directives.md` goal/objectives;
- any `findings/` docs captured under A6.

Then ask explicitly — e.g. *"Write this goal folder and root plan to the vault and open the PR?"* — and
**wait for the user's answer:**

- **Approved** → in operation mode, add
  `**Confirmation:** user-confirmed on <DATE>` in the same header position as the auto-confirm line;
  then proceed to step 8 (write-out) and step 9 (commit & PR). Manual mode keeps its existing output.
- **Changes requested** → revise the relevant scratch draft(s), re-run self-review (step 6), and
  re-present this gate. Still no vault write.
- **Declined** → write nothing and open no PR. Report that no vault changes were made and where the
  scratch drafts live, then exit.

**Do not create the goal folder, any subfolder, or any file before confirmation** — the two-factor
auto-confirm case above is the only path that skips the human pause.

### 8. Write-out (only after step 7 confirmation — human approval or two-factor auto-confirm)

Create the goal folder and the **six subfolders** — `master-plans/`, `plans/`, `findings/`, `reports/`,
`handoff/`, `todo/`. Write `goal-directives.md` at the folder root and the root plan into
`master-plans/`. Drop a `.gitkeep` into **every subfolder that has no file written this run** (so empty
folders are tracked — matches existing goal folders that keep `handoff/.gitkeep` and `todo/.gitkeep`).

In operation mode, an existing exact goal folder is recoverable only when its root plan and
`goal-directives.md` carry this Operation/source identity and every existing scaffold file matches
the reviewed scratch draft. Reuse matching files, write only missing intended files, and resume the
same A7 work. Do not overwrite mismatched bytes, add a second root plan, or create another folder.

### 9. Commit & merge via PR (superauthor A7)

Apply A7 with these caller parameters:

- **branch prefix:** `goal/<slug>`  → branch `goal/<slug>-<DATE>`
- **commit subject:** `docs(goal): <slug> — supergoal output`  (A7 appends ` [skip ci]`)
- **PR title:** `docs(goal): <slug>`
- **PR body:** `Goal folder + root master plan generated by supergoal for "<goal source>".`
- **explicit `git add` list:** `goal-directives.md`, the root plan in `master-plans/`, every `.gitkeep`
  written this run, and any `findings/` doc captured under A6. **Never `git add -A`.**
- **External vault:** A7's target is the vault repo — the same file list, made relative to
  `<vault_root>`, committed directly there; no branch, no PR (see A7 **Target repo**). A7's
  **precondition** applies: if `<vault_root>` is not its own repository, STOP and report — never
  improvise a `git init`.

After A7 in operation mode, run reconciliation again. Return `INTEGRATED` only when it names the
recorded goal folder and unique root plan at `main`; dirty or unmerged work remains non-integrated.

### 10. Final Report (superauthor A8)

Apply A8 with the `## Supergoal complete` instantiation below — enumerate every path written this run and
the merged PR URL (external vault: the vault commit SHA):

```
## Supergoal complete

**Goal folder:** <full path>
**Root plan:** <full path to master-plans/...>
**Goal directives:** <full path to goal-directives.md>
**PR:** <url> (merged)
**Commit:** <short-sha> in <vault_root>   (external vault — print this line INSTEAD of the PR line, verbatim form)

**Subfolders created:**
- master-plans/, plans/, findings/, reports/, handoff/, todo/

**Findings:**
- <finding summary>           (or: none)

⚠️ **Critical:** <only present when a finding needs attention>
```

After printing the report, the skill is done: take no further action and ask no follow-up question.

In operation mode only, print the compact operation-result JSON as the final line after the report.

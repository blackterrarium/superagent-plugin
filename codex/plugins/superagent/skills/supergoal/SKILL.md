---
name: supergoal
description: Use when starting a brand-new multi-PR initiative from a goal description (not an existing plan file) — creates the goal vault folder (YYYY-MM-DD-hh_mm-<slug>), its goal-directives.md, the standard subfolders, and the ROOT master plan that seeds the planning tree.
license: all rights reserved
related skills: superauthor, superplan, supertraverse
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
> - `${SUPER_PLUGIN_ROOT}` in commands and paths = this plugin's installed marketplace root (the
>   directory containing `plugins/` and `templates/`; skills live under
>   `plugins/superagent/skills/`, four levels above each SKILL.md). Substitute its absolute path
>   wherever it appears. Exception: the external-driver `scripts/` helpers (`superagent-tick.sh`,
>   `launch.sh`, …) are not packaged inside this marketplace root — they live in the plugin
>   source repository, whose `codex/` directory is this root when installed from a repo checkout.
>   Read `${SUPER_PLUGIN_ROOT}/scripts/` as that repository's `scripts/` directory (the
>   `SUPERAGENT_SCRIPTS` convention in its scripts/README.md).
> - Skill lookup: this plugin installs via the Codex plugin marketplace; skills resolve by name
>   (e.g. `superplan`). The `superagent` supervisor skill is driven by reading its SKILL.md
>   directly (the external tick's file-read prompt), never invoked by name.

# Supergoal

Given a **goal description** (a prompt, not an existing `.md`), scaffold a new *goal folder* in the vault
and author the **root master plan** that seeds the planning tree — the document `superplan` later
descends into.

**Input:** `<GOAL>` — a prose description of the goal/objective for the new initiative. **Required.**

## What supergoal is — and how it differs from superplan

`superplan` operates on an **existing** seed/master plan: it descends a plan tree, plans one step, and
ascends. **supergoal creates the *root* of that tree.** Three consequences follow:

- It takes a **goal-description prompt**, not a `<PLAN.md>`.
- It does **no descent and no ascent** — there is no existing tree to descend, and the root has no
  ancestors to update.
- The root plan it writes carries **no parent-seed reference** — per `supertraverse` C5, the root is
  precisely the plan that has none.

supergoal produces exactly one **root seed/master plan** plus the goal-folder scaffold and — **only after
the user confirms the drafted plan** — writes them to the vault and ships them via PR. It does **not**
execute the planned work.

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
   complete *and* the user has confirmed.** Deriving the folder *name* (step 2) and the read-only "does
   it already exist?" check are allowed; `mkdir` and writing files are not.
2. **User confirmation gates the vault write.** After self-review, supergoal **pauses and asks the user
   to confirm** the drafted plan (step 7) and writes to the vault / opens the PR **only** after the user
   approves. This pause is mandatory and is **not** waived by auto-accept / `bypassPermissions` mode.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

## Workflow

### 1. Input gate

If `<GOAL>` is not provided → respond with exactly `I need a goal description` and **exit**.

### 2. Derive identifiers

- **`<slug>`** — a concise, stable, descriptive kebab-case slug summarizing the goal (mirror the style of
  existing goal folders — worked example from the originating repo: `graphgen-grammar-first-redesign`).
- **`<STAMP>`** — today's date plus the current UTC hour and minute (`date -u +%Y-%m-%d-%H_%M`), e.g.
  `2026-06-14-09_30`. This is the dated prefix for the goal folder and the dated files written into it.
- **`<DATE>`** — today's date (`date +%Y-%m-%d`); used **only** for the git branch name (step 9).
- **Goal folder** — `<SUPER_GOAL_ROOT>/<STAMP>-<slug>/`. This is the **goal folder** superauthor's
  clauses write under. If the folder already exists, disambiguate the slug; if it is clearly the same
  initiative, report that and **exit** — **never overwrite an existing goal folder**.

### 3. Invoke superagent:superauthor

Invoke the `superagent:superauthor` skill (Skill tool) and apply A1–A8 for the rest of the run.

### 4. Author the ROOT master plan (per the A2 standard)

Author the root plan yourself per superauthor's A2 authoring standard, drafting to a scratch path
outside the goal folder. The root plan MUST:

- be a **seed/master plan**, routed to `master-plans/<STAMP>-<slug>.md`;
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
  reviews them.

### 5. Author `goal-directives.md` (structural doc — A2's plan rules do not apply)

`goal-directives.md` is a **structural layout guide, not a plan** (A2's structural-doc carve-out), so
author it directly, drafting to scratch alongside the plan. It must be fully
**self-contained** — do **not** point the reader at any external example file. Structure:

1. **Title** — `# Goal Directives — <STAMP>-<slug>`.
2. **Goal / Objectives — FIRST**, immediately after the title: the *why*, the target outcome, and
   success criteria distilled from `<GOAL>`. (This is the one intentional deviation from older
   directives docs that open with Type/Audience — supergoal puts the goal at the very top.)
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
confirm the progress-report table is the **first major section of the plan body** (the step-4 placement
rule) — move it to the top if it drifted lower.

### 7. Confirmation gate (REQUIRED — overrides A5)

Planning is now complete and **nothing has been written to the vault yet** (the goal folder does not
exist; all drafts are in scratch). **Pause and ask the user to confirm before any vault write.** Present
a concise summary — do **not** dump the full drafts:

- the goal folder that **will** be created (`<SUPER_GOAL_ROOT>/<STAMP>-<slug>/`) and its six subfolders;
- the root plan's title and its progress-report **steps** (the table rows), so the user sees the
  decomposition;
- a one-line gist of the `goal-directives.md` goal/objectives;
- any `findings/` docs captured under A6.

Then ask explicitly — e.g. *"Write this goal folder and root plan to the vault and open the PR?"* — and
**wait for the user's answer:**

- **Approved** → proceed to step 8 (write-out) and step 9 (commit & PR).
- **Changes requested** → revise the relevant scratch draft(s), re-run self-review (step 6), and
  re-present this gate. Still no vault write.
- **Declined** → write nothing and open no PR. Report that no vault changes were made and where the
  scratch drafts live, then exit.

**Do not create the goal folder, any subfolder, or any file before the user approves here.**

### 8. Write-out (only after the user approves at step 7)

Create the goal folder and the **six subfolders** — `master-plans/`, `plans/`, `findings/`, `reports/`,
`handoff/`, `todo/`. Write `goal-directives.md` at the folder root and the root plan into
`master-plans/`. Drop a `.gitkeep` into **every subfolder that has no file written this run** (so empty
folders are tracked — matches existing goal folders that keep `handoff/.gitkeep` and `todo/.gitkeep`).

### 9. Commit & merge via PR (superauthor A7)

Apply A7 with these caller parameters:

- **branch prefix:** `goal/<slug>`  → branch `goal/<slug>-<DATE>`
- **commit subject:** `docs(goal): <slug> — supergoal output`  (A7 appends ` [skip ci]`)
- **PR title:** `docs(goal): <slug>`
- **PR body:** `Goal folder + root master plan generated by supergoal for "<GOAL>".`
- **explicit `git add` list:** `goal-directives.md`, the root plan in `master-plans/`, every `.gitkeep`
  written this run, and any `findings/` doc captured under A6. **Never `git add -A`.**

### 10. Final Report (superauthor A8)

Apply A8 with the `## Supergoal complete` instantiation below — enumerate every path written this run and
the merged PR URL:

```
## Supergoal complete

**Goal folder:** <full path>
**Root plan:** <full path to master-plans/...>
**Goal directives:** <full path to goal-directives.md>
**PR:** <url> (merged)

**Subfolders created:**
- master-plans/, plans/, findings/, reports/, handoff/, todo/

**Findings:**
- <finding summary>           (or: none)

⚠️ **Critical:** <only present when a finding needs attention>
```

After printing the report, the skill is done: take no further action and ask no follow-up question.

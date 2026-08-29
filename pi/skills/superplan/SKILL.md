---
name: superplan
description: Use when asked to turn a seed/master/sub-master plan into a focused sub-master or implementation plan for a given step or topic — produces a routed, self-reviewed plan file
license: all rights reserved
---

<!-- GENERATED FILE — Pi build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-pi-skills.sh. -->

> **Pi build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` / `Monitor` / `AskUserQuestion` tools do **not** exist
>   on Pi — treat any residual mention as inapplicable and NEVER attempt those tool calls.
> - Tool mapping in the SUPERVISOR (`superagent`, `superloop`): "Agent tool" / "dispatch a
>   subagent" = a blocking `bash` call to `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh`
>   (`superplan`, `superrun`) or `${SUPER_PLUGIN_ROOT}/scripts/bridge-fanout.sh` (the L7 panel),
>   per the Pi-specific guidance embedded in those skills. The supervisor never uses a subagent tool.
> - Tool mapping in `superrun` (the SDD controller): "dispatch a subagent" = the `subagent` tool
>   from the `pi-subagents` package with `async: false`, one child per call; role pins ride the
>   `.pi/agents/super-<role>.md` definitions `init` generates. If the tool is absent, follow SDD's
>   sequential fallback and report it.
> - "Skill tool / invoke skill X" = `read` `${SUPER_PLUGIN_ROOT}/skills/X/SKILL.md` and follow it
>   (`/skill:` commands are interactive-only). Superpowers skills are listed by Pi from the
>   installed `superpowers` package — reference them by name.
> - `${SUPER_PLUGIN_ROOT}` = the plugin repository's `pi/` directory (two levels above each
>   SKILL.md). It contains `skills/`, `templates/`, and `scripts/` (`role-bridge.sh`,
>   `bridge-fanout.sh`, `_common.sh`). The external-driver wrappers (`superagent-tick.sh`,
>   `launch.sh`, …) live in the repository's top-level `scripts/` — one directory up.
> - `EnterWorktree` = not available; use `git worktree` via `bash`.

# Superplan

Given a seed/master plan and a topic, produce a focused sub-master or implementation plan, route it to the
correct goal-folder subfolder, and self-review it. (Inputs are defined under **Input** below.)

## The deliverable is the plan — and ONLY the plan

**superplan produces a plan file and a report, then stops. DO NOT execute, implement, or begin any of the
planned work.** Not one "trivial" step. Not "just scaffolding it." Not even in auto-accept /
`bypassPermissions` mode. Not even if the user seems eager or the work looks small.

superplan **never** writes or edits source code, **never** runs tests or builds, **never** creates
worktrees, and **never** begins the planned work. Executing the plan is a separate, later action the user
invokes explicitly (e.g. `superrun`) — it is **not** part of
this skill.

The one thing superplan *does* commit is **the plan documents themselves**. Once the plan and `findings/`
docs are written to the vault, superplan commits **only those planning artifacts** and merges them to
`main` via a pull request as its final action — **automatically, under the user's standing authorization,
without pausing to ask** (see **Commit and merge the plan — via PR** below). That is the sole commit
superplan makes — never source code, never execution output.

| Thought | Reality |
|---------|---------|
| "Auto mode is on, so I'm cleared to start coding" | NO. Auto mode governs tool permissions, not scope. The deliverable is the plan. |
| "The first task is trivial, I'll just knock it out" | NO. Zero implementation steps. Hand the plan over and stop. |
| "I'll set up the worktree / branch for the planned work" | NO worktree and no branch for the *planned work*, and no source-code commits. (The plan documents are committed and merged via PR as the final step — that is the only commit.) |
| "The user will obviously want this run, I'll get a head start" | NO. Produce and commit the plan, report, exit. Wait to be asked before executing. |

## Input

- `<PLAN.md>` — the `.md` file containing the seed / master / sub-master plan. **Required.**
- `<TOPIC>` — the step or topic within the seed plan to focus on. Optional.

Gates, in order:

1. If `<PLAN.md>` is not provided → respond with exactly `I need to know the plan file` and **exit**.
2. If `<PLAN.md>` is provided but `<TOPIC>` is not → **invoke the `superagent:supertraverse` skill** (Skill
   tool) and run its **DESCENT** from `<PLAN.md>`. Descent walks the plan tree down the progress-report
   tables' `Plan` links (multi-layer, not just `<PLAN.md>`'s own rows), skipping completed steps and
   already-planned leaves, and returns:
   - the **target** — the deepest highest-ranked step that is not yet completed **and** has no plan
     yet (the *available task to plan*), and
   - the **descent path** — the chain of `(plan-file, row)` from `<PLAN.md>` down to the target's
     **immediate parent** (the deepest plan that directly contains the target row). The immediate
     parent may be a *descendant* of `<PLAN.md>`, not `<PLAN.md>` itself; the ascent step below uses
     this path.

   If descent returns **"none"** (every step is completed or already has a plan), respond with exactly
   `No available task to plan — every step is completed or already has a plan` and **exit**.

   If descent returns **`not-traversable`** (the root has no progress-report table — only an
   orchestration/granularity table; see `supertraverse` C6 step 0), do **not** guess a target. Respond
   that `<PLAN.md>` is not maintained as a progress-report tree (name the orchestration table you
   found) and ask the user to point at a seed/master plan that has a `Step | Status | Plan | PR |
   Comments` table, or to name a `<TOPIC>` directly; then **exit**.

   **On success (descent returned a target + descent path):** do **not** stop, do **not** print a
   "descent complete" message, and do **not** wait for user confirmation. Continue immediately to
   **Goal Identification → Planning → Self-Review → Findings → Routing → Immediate-Parent Update →
   Planning-Mode Ascent → Commit-and-Merge PR → Final Report**, in order. The user's single
   checkpoint for this whole run is the Final Report; the descent result is intermediate state, not a
   stopping point.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

## Goal Identification

Identify the **goal folder**: the top-level directory this plan belongs to — the directory under which all
plans for this initiative are written. In practice it is the directory that contains (or should contain)
the `master-plans/` and `plans/` subfolders for this plan family. Derive it from the location of
`<PLAN.md>` — typically its parent goal folder, **not** the `master-plans/` or `plans/` subfolder the seed
itself sits in. All output is written under this goal folder. Goal folders live under the repo's
goal-folder root `<SUPER_GOAL_ROOT>` (created by `superagent:init` if absent) — so "write to the goal
folder" means writing the docs there.

## Planning — author per superauthor's A2 standard (REQUIRED)

**Invoke the `superagent:superauthor` skill via the Skill tool, then author the plan yourself to its A2
authoring standard** — plan header with Global Constraints, file-structure-first decomposition, task
right-sizing, Interfaces blocks, real code blocks, CI-push verification steps — and its **A3**
no-placeholder rules. Loading superauthor is required: do not reproduce the standard from memory —
its *current* rules must shape the produced plan.

Author with the seed-plan content and the focused topic as context so the produced plan is
self-contained.

**Author the draft to a scratch path OUTSIDE the goal folder** (e.g. `$TMPDIR/` or `.claude/scratch/`),
not into the goal folder. **Nothing is written under the goal folder (no plan file, no `findings/` doc)
until self-review passes and the plan type is identified (routing) below** — at which point the scratch
draft is written into the vault automatically.

### Red flags — STOP, you are about to skip the standard

| Thought | Reality |
|---------|---------|
| "I know the plan format, I'll just write it" | STOP. Load `superagent:superauthor` (Skill tool) so the *current* A2/A3 rules apply. |
| "The standard is overkill for a small plan" | STOP. Apply it anyway. |

## Parent-Seed Reference (MUST)

**Every plan superplan writes MUST include an explicit reference to `<PLAN.md>` — the parent seed/master
plan it was derived from — near the top of the file.** This is non-negotiable. It lets a fresh agent walk
the plan hierarchy upward (this plan → its parent seed → that seed's own parent) without guessing where
the work came from.

Use the vault link form already used in the goal folder — a wikilink or relative path to `<PLAN.md>`'s
basename (e.g. `[[2026-05-20-.../master-plans/<seed-basename>]]`). Apply this requirement while
authoring, and verify it in self-review. **A plan with
no parent-seed reference is a plan failure — add the reference before routing.**

## No Placeholders

superauthor **A3** (loaded above) defines the no-placeholder rules: every step must contain the
actual content an engineer needs, and every A3 pattern ("TBD", prose-only code steps, "similar to
Task N", references to undefined types, …) is a **plan failure**. Apply A3 while authoring and scan
for it in self-review.

## CI Scheduling in Authored Plans (keyed by SUPER_CI_*)

Apply these rules whenever the plan's tasks trigger CI (they instantiate the `SUPER_TEST_EVIDENCE=ci`
branch of superauthor's verification-steps rule), and enforce them in self-review:

- **Queue-all when there's more than one runner.** If `SUPER_CI_RUNNERS > 1` and the plan needs more
  than one independent long CI push (>10 min each — e.g. a shardable stress lane split into per-shard
  pushes, or two unrelated long lanes), write the pushes as **one queue-all batch**: push every shard
  back-to-back, then wait on **all** resulting runs together. Serial "push B after A completes"
  ordering is allowed **only** across a genuine procedural gate the plan names — worked example from
  the originating repo: `multi_motif_smoke` green before `multi_motif` — runner contention is never a
  reason to serialize.
- **Commit flags.** If `SUPER_CI_FLAG_TEMPLATE` is set (e.g. `[test:%s]`), stamp each push's commit
  message with it; if it is empty, the repo has no commit-flag system and plans just push. When
  `SUPER_CI_ONE_FLAG_PER_PUSH=true` (the shipped default), use exactly one flag per push — never
  combine flags in a single commit.
- **Monitor-parked waits, never poll loops.** Write CI waits as "queue the pushes, then wait for all
  runs per `superrun` Step 3a (monitor-parked CI wait)". Never instruct `gh run watch`, sleep loops,
  or periodic re-polling in plan text.

## Self-Review

**Review the written plan yourself, inline — not via a subagent dispatch.** superplan authored the
plan directly (A2), so nothing has pre-checked it — run the generic checks *and* what only superplan
knows:

1. **Spec coverage against the seed** — skim each section/requirement of the focused topic in the seed.
   Point to a task that implements it; add a task
   for any gap.
2. **Placeholder scan (A3)** — search the plan for the A3 patterns. Fix every hit.
3. **Type/term consistency** — the types, signatures, and names used in later tasks match what earlier
   tasks defined.
4. **Parent-seed reference (MUST)** — confirm the plan contains an explicit reference to `<PLAN.md>`, the
   parent seed/master plan it was derived from (see **Parent-Seed Reference** above). If it is missing,
   add it. Non-negotiable.
5. **Immediate-parent row + ancestor ascent (MUST)** — confirm the **immediate parent**'s row (or
   bullet) for this step now carries the `[[…]]` link to the file you wrote **in the Plan column** and a
   `PLAN WRITTEN — ready to execute` status (see **Update the Immediate Parent's Progress-Report Table**
   below), **and** that every intermediate ancestor up to the root `<PLAN.md>` was set
   `in progress (planning underway)` by the planning-mode ascent (see **Ascend the Tree** below). If any
   of these tracked rows was not updated, update it.
6. **Progress-report table placement (seed/master plans only — MUST)** — if the plan you wrote is a
   seed/sub-master plan (it carries a progress-report table), confirm that table is the **first major
   section of the plan body**, right after the title and the parent-seed reference — not buried below the
   scope/analysis/decision sections (see **Seed or master plan → Placement** above). If it sits lower
   down, move it to the top. (Implementation plans are leaves with no table — this check is a no-op for
   them.)
7. **Verification-evidence check** — confirm the plan's verification steps match
   `SUPER_TEST_EVIDENCE`: if `ci`, every set of independent long pushes is written as a queue-all
   batch when `SUPER_CI_RUNNERS > 1` (see **CI Scheduling in Authored Plans** above), any serial push
   ordering names its procedural gate, commit flags follow `SUPER_CI_FLAG_TEMPLATE` /
   `SUPER_CI_ONE_FLAG_PER_PUSH`, and every CI wait is monitor-parked (no `gh run watch` / sleep /
   re-poll loops in plan text); if `local` (default), steps use the normal local test cycle per
   `superpowers:writing-plans` instead of CI pushes. Fix violations inline.

If you find issues, fix them inline — no need to re-review the whole plan.

## Standing authorization — proceed without pausing (REQUIRED)

The user has granted **standing authorization** for superplan to write its docs to the vault and merge the
plan PR. **Do NOT pause to ask for approval, and do NOT present the plan and wait for a "go" before
writing.** After self-review, proceed directly — capture findings, route and write the docs into the vault
goal folder, commit, and merge the PR — then report. This is not waived or re-enabled by auto-accept /
`bypassPermissions` mode; it is the default behavior.

Do not print the full plan to chat up front. The user's single checkpoint is the **Final Report** (below),
which clearly enumerates every file written this run.

## After Self-Review — Capture Findings

After the self-review, identify any **findings** or new insights uncovered during the planning phase —
e.g. a constraint discovered, a contradiction in the seed, a mechanism that does not work as the seed
assumed, or a non-obvious fact a future planner would need.

Review the existing docs in the goal folder's **`findings/`** subfolder to decide whether each finding is:

- an **addition** — write it to a new doc in `findings/`, named `YYYY-MM-DD-hh_mm-<topic>.md` (today's date and the current UTC hour and minute), or
- a **revision** — update the relevant existing doc in `findings/`.

(These writes happen as part of the automatic write-out below — after self-review, alongside the plan file
and routing. No user confirmation is awaited.)

**Be extra certain of each finding.** If you are unsure whether a finding is correct, **do not include
it** — false findings are harmful to the goal. Only record what you have verified.

## Plan Type Identification

Decide which kind of plan was written, then route it. **Write the file into the goal folder once
self-review and findings capture are done** — this is where the scratch draft becomes the real plan file in
the vault. No confirmation is awaited. The output
filename uses the timestamp-prefix form `YYYY-MM-DD-hh_mm-<topic>.md` — **today's date and the current
UTC hour and minute** at the **start** of the basename (not the seed's date) — in both cases.

**Which kind?** If the topic itself decomposes into multiple steps that each warrant their own separate
implementation plan, it is a **seed/master plan**. If it is a single executable unit of work (even if it
has many tasks), it is an **implementation plan**. When genuinely on the fence, prefer an implementation
plan.

### Seed or master plan

A large or broad plan that itself contains multiple steps, where each step is its own implementation
plan. Identify the order in which the steps must be planned. Write the file to the **`master-plans/`**
subfolder within the goal folder.

The file MUST include a **progress-report table** listing all steps. Author it using the schema and
status vocabulary defined in the **`supertraverse`** skill (C1/C2) — do not redefine the columns here:

| Step | Status | Plan | PR | Comments |
|------|--------|------|----|----------|

**Placement — the table goes at the START of the plan (MUST).** The progress-report table is the plan's
navigational index: `supertraverse`'s descent reads it first to find the next step, and
`superplan`/`superfinish` update its rows. It MUST be the **first major section of the plan body** —
immediately after the title (`# …`) and the parent-seed reference line, and **before** any
scope / "READ FIRST" / context / analysis / rationale / decision sections. A one- or two-sentence
orientation line under the title is fine; everything longer goes **after** the table. **Do NOT bury the
table at the bottom of the plan** under the analysis that justifies the decomposition — a table a reader
must scroll past the whole document to find defeats its purpose, and is the single most common way this
gets written wrong.

| Thought | Reality |
|---------|---------|
| "I'll lay out the scope and rationale first, then put the table at the end" | NO. The table is the first section after the title + parent-seed reference. Rationale and analysis come AFTER it. |
| "The reader needs the context before the table makes sense" | NO. The table is a scannable index; a brief one-line orientation is enough. Long context goes below the table. |

The load-bearing points (see `supertraverse` C1 for the full legend): the **Plan** column holds a vault
wikilink to the plan generated for each step (blank when none exists yet — a blank `Plan` on a
not-completed step is what marks it an *available task to plan*); the close-out link for a done step
goes in **Comments** as `Closeout: [[…]]`, not in **Plan**.

This file is read by **fresh agents** to continue planning. Include all prerequisites in the file, and add
references to other relevant files that must be read before working on it — **including a reference to any
related docs in the `findings/` subfolder** (both pre-existing findings and any captured in the step
above), so the fresh agent reviews them.

### Implementation plan

Write the file to the **`plans/`** subfolder within the goal folder. This plan is executed by a **fresh
agent**, so put all relevant context at the **start** of the file and include references to any other
files needed for execution — **including a reference to any related docs in the `findings/` subfolder**
(both pre-existing findings and any captured in the step above), so the fresh agent reviews them.

An implementation plan is a **leaf** of the plan tree and **MUST NOT contain a progress-report table**
(see `supertraverse` C1, the leaf rule): the table's presence is exactly what marks a plan as an
*internal node* that traversal descends into, so a leaf has none. Track an implementation plan's own
work with task checkboxes / a verification matrix instead.

## Update the Immediate Parent's Progress-Report Table (MUST)

The plan you just routed was derived from the **target step** descent selected (or the one named by
`<TOPIC>`). That step lives in the **immediate parent** — the deepest plan in the descent path, which
may be a descendant of `<PLAN.md>`, not `<PLAN.md>` itself. (When there was no descent, or `<TOPIC>`
matched a row in `<PLAN.md>` directly, the immediate parent **is** `<PLAN.md>`.) After the plan file is
written and **before the commit below**, update that step's entry in the **immediate parent** so the
tree reflects that the step now has a plan. Without this step, the "progress-report update" promised by
the commit scope and the Final Report describes an output the skill never produces.

**If the immediate parent has a progress-report table** (the common case — see the `supertraverse` C1
schema):

1. Locate the **row** for the step this plan covers.
2. Set its **Status** to `PLAN WRITTEN — ready to execute` (the `supertraverse` C2 vocabulary). Match
   the parent's existing status casing if it has a convention. **Do NOT mark it completed, merged,
   shipped, or closed-out** — that transition is `superfinish`'s job after the plan is executed.
3. Put a `[[<vault-link>]]` to the **actual file you just wrote** (date-prefixed with today's date) in
   the **Plan** column. **Back-compat:** if the parent table has no `Plan` column yet (a legacy 4-column
   table), add the column — insert the `Plan` header and a blank cell for every existing row — then fill
   this row's `Plan` cell. If the parent author left a `Plan: [[…]]` reference (or a `(to be authored)`
   placeholder) in **Comments**, move the real link into the `Plan` column and drop the placeholder.
4. Leave the **PR** column for this row **unchanged** — the work's PR does not exist yet. The docs-only
   PR that commits this very table edit (below) is **not** the step's work PR; do not record it here.

**If the immediate parent has no progress-report table** (a bullet-list seed): annotate the
corresponding bullet with a `Plan: [[<vault-link>]]` reference and a short "plan written" note. Do not
invent a table.

This update applies whether the routed plan is an **implementation plan** or a **sub-master plan**.

This table edit is part of the planning artifacts committed below — include the immediate parent file
in the explicit `git add` (never `git add -A`).

## Ascend the Tree — Update Ancestor Statuses (MUST)

After the immediate parent's row is updated, **invoke the `superagent:supertraverse` skill** (Skill tool) and run
its **ASCENT in planning mode** over the descent path, from the immediate parent up to the root
`<PLAN.md>`. At each ancestor it sets the row whose `Plan` link you descended through to
`in progress (planning underway)` — only if that row was previously not-started; it never downgrades a
more-advanced status and never marks a row complete.

If the target row was directly in `<PLAN.md>` (no intermediate levels in the descent path), there are
no ancestors and the ascent is a no-op. **Every ancestor plan file the ascent touches must be added to
the explicit `git add` below** alongside the immediate parent.

## Commit and merge the plan — via PR (REQUIRED)

After the plan file, any `findings/` docs, the immediate-parent progress-report update (see **Update the
Immediate Parent's Progress-Report Table** above), and any ancestor rows the ascent touched (see
**Ascend the Tree** above) are written into
the goal folder (docs already written to the vault), commit those planning artifacts and merge them to
`main` via a pull request. **Merge the PR without asking the user for confirmation** — the user has granted
standing authorization, so never pause before writing or merging.

If `SUPER_PROTECTED_MAIN=true` (the shipped default), the default branch is a **protected branch**
(direct pushes are rejected), so this MUST go through a feature branch and a PR — merged per
`SUPER_MERGE_METHOD` (default `squash`) — even though it is docs-only. If `SUPER_PROTECTED_MAIN=false`,
a direct commit to the default branch is permitted instead — see `superauthor` clause **A7**'s
`SUPER_PROTECTED_MAIN=false` worked example for the exact recipe (no feature branch, no PR, no `gh`).

**Scope of the commit: only the planning artifacts** — the plan file, new/revised `findings/` docs, the
immediate-parent progress-report update, and **every ancestor plan file** the planning-mode ascent
updated up to the root `<PLAN.md>`. Add each with an explicit `git add <path>`; **never `git add -A`**
(the working tree may hold unrelated changes that are not yours to commit).

These are docs-only changes, so tag the commit subject `[skip ci]` to avoid firing CI on the merge.

```bash
# from the repo root, with the plan/findings files already written
BRANCH="plan/<topic>-$(date +%Y-%m-%d)"
git checkout -b "$BRANCH"
git add <plan-file> [<findings-doc> ...] <immediate-parent-file> [<ancestor-plan-file> ...]   # explicit paths only
git commit -m "docs(plan): <topic> — superplan output [skip ci]"
git push -u origin "$BRANCH"
gh pr create --title "docs(plan): <topic>" \
  --body "Plan generated by superplan for <topic>. Derived from <PLAN.md>."
gh pr merge --squash --delete-branch          # plain --squash is the DEFAULT — do NOT reach for --admin
git checkout main && git pull --ff-only
```

Notes:
- `--squash --delete-branch` keeps history clean and removes the feature branch after merge.
- **Merge per `SUPER_MERGE_METHOD` (default `squash`). Pass `gh pr merge --admin` only if
  `SUPER_ADMIN_MERGE=true` — otherwise never.** Reaching for `--admin` when the key is unset or `false`
  buys nothing on a repo whose branch protection doesn't require it, and reliably trips the harness
  security classifier. Full rationale in `superauthor` clause **A7**. Escalate only if a plain merge
  is actually refused (and `SUPER_ADMIN_MERGE=true` permits it), and say why in the Final Report.
- **`--delete-branch` can exit 1 with `fatal: '<branch>' is already used by worktree` — the PR still
  merged.** Confirm with `gh pr view <n> --json state,mergedAt`, then drop the remote ref with
  `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>`.
- Capture the resulting **PR URL** (from `gh pr create` / `gh pr view --json url`) — report it in the Final
  Report below.
- Do **not** commit Anthropic/Claude attribution or `Co-Authored-By` trailers (repo policy).
- If `SUPER_GH_DISABLE_SANDBOX=true` (macOS hosts where `gh` needs keychain access to verify the
  TLS cert), all `gh` commands need `dangerouslyDisableSandbox: true`. If `false` (the shipped
  default), run `gh` normally.

## Final Report — then exit

After the plan is routed, the self-review is done, findings are captured, and the plan PR is merged
(above), give the user a **single report** and then **exit the skill**. **Do not ask whether to execute the plan and do not offer
execution options** — superplan never offers execution.

**This report is the user's single window into what superplan wrote — every file path created or modified
this run MUST appear here.**

Report the following, in order:

1. **Plan file** — the full path of the plan file you created. *This is the most important line; always
   include it.*
2. **Plan type** — `implementation plan` (written to `plans/`) or `seed/master plan` (written to
   `master-plans/`).
3. **Other files created or modified** — every other file touched: new or revised `findings/` docs, the
   immediate parent's updated progress-report row (give its path and which step), **and each ancestor
   plan up to the root `<PLAN.md>` whose status the ascent set to `in progress`** (path + which row).
   Give the path and a one-line note of what changed. If none, write "none".
4. **PR** — the URL of the pull request that committed and merged the plan documents, and its state
   (merged). *Always include it.*
5. **Findings** — one line per new finding captured during planning. **Call out any CRITICAL finding** (a
   contradiction in the seed, a mechanism that does not work as the seed assumed, a blocking constraint)
   under its own bold ⚠️ line so it cannot be missed. If there were none, write "none".

Use this format:

    ## Superplan complete

    **Plan file:** <full path>
    **Plan type:** implementation plan | seed/master plan
    **PR:** <url> (merged)

    **Other files created/modified:**
    - <path> — <what changed>     (or: none)

    **Findings:**
    - <finding summary>           (or: none)

    ⚠️ **Critical:** <only present when a finding needs attention>

After printing the report, the skill is done: take no further action and ask no follow-up question.

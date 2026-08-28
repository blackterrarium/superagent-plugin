---
name: supertraverse
description: Use when traversing a tree of seed/master/implementation plans — descending a progress-report table's Plan links to find the next task (planning mode = next available task to plan; execution mode = next written-but-unexecuted leaf plan), or ascending from a leaf plan to the root updating ancestor statuses. Shared by superplan, superrun, and superfinish.
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
>   resolved model/effort as spawn parameters instead — and any accompanying "missing definition =
>   hard error / re-run `superagent:init`" clause does not apply in this build (there is nothing to
>   generate; a bridged role's relay spawn needs no definition either). A role whose value names
>   another harness (`claude:sonnet`, `pi:openai/gpt-5`, …) is BRIDGED: spawn a relay child
>   (`model` = `SUPER_BRIDGE_RELAY_MODEL`, omit when `inherit`) whose message is
>   `${SUPER_PLUGIN_ROOT}/templates/relay-preamble.md` rendered for that role followed by the task
>   prompt; the relay runs `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh` and returns the foreign
>   CLI's result verbatim. "Skill tool" = reference the skill by
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
>   `SUPERAGENT_SCRIPTS` convention in its scripts/README.md) — except `scripts/role-bridge.sh`,
>   which IS packaged inside the plugin at `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh` — use that
>   path for it.
> - Skill lookup: this plugin installs via the Codex plugin marketplace; skills resolve by name
>   (e.g. `superplan`). The `superagent` supervisor skill is driven by reading its SKILL.md
>   directly (the external tick's file-read prompt), never invoked by name.

# Supertraverse

The single source of truth for **plan-tree navigation**. A goal folder's plans form a tree: a
seed/master plan's **progress-report table** lists its steps, each step's `Plan` link points *down*
to that step's child plan, and every plan carries a parent-seed reference pointing *up*. This skill
defines how to walk that tree — **down** (descent: find the next available task to plan) and **up**
(ascent: update ancestor statuses) — plus the schema, link-inference, and status vocabulary the walk
depends on.

**Consumers:** `superplan` invokes this for **descent** (to find the task to plan) and **ascent in
planning mode** (to mark ancestors in-progress). `superfinish` invokes it for **ascent in completion
mode** (to flip ancestors complete). This skill is the *only* place these mechanics are defined — the
consumer skills must not restate or fork them.

This skill **describes algorithms the calling agent carries out inline** with its file tools (Read /
Edit). It does not itself write source code, run anything, or commit. The consumer skill owns reading
the result, writing files, and committing.

> **Subroutine contract — read before running the algorithm.** When `superplan`, `superrun`, or
> `superfinish` invokes this skill via the Skill tool, you (the calling agent) are running
> supertraverse as **one step inside the caller's workflow**, not as a standalone task. After you
> compute the algorithm's result (target + path, `none`, `not-traversable`, or the list of touched
> ancestor files), you **MUST return control to the calling skill and immediately continue executing
> the caller's next section** — do NOT end your turn, do NOT wait for user input, do NOT print a
> "supertraverse complete" report. supertraverse has no Final Report of its own; the caller writes
> the only user-facing report.

## C1. The progress-report table schema

A seed/master/sub-master plan carries a progress-report table with these columns:

```
| Step | Status | Plan | PR | Comments |
|------|--------|------|----|----------|
```

- **Step** — the name of the step.
- **Status** — the step's purpose + state, drawn from the **status vocabulary** (C2).
- **Plan** — a vault wikilink to the plan generated for this step: **either** a child master/seed plan
  (an *internal node* — itself carries a progress-report table) **or** an implementation plan (a *leaf*
  — carries no table). **Blank when no plan exists yet** — a blank `Plan` on a not-completed row is
  exactly what marks the step an *available task to plan*.
- **PR** — one or more pull requests associated with the step.
- **Comments** — notes; for a completed step, a one-line close-out summary plus a
  `Closeout: [[…reports/…]]` link. The plan link lives in the **Plan** column, **not** here.

**Leaf rule (load-bearing):** an implementation plan is a tree **leaf** and **MUST NOT contain a
progress-report table**. The table's presence is precisely what marks a plan as an *internal node*
that descent recurses into; a leaf has no children, so no table. (Implementation plans track their own
work with task checkboxes / a verification matrix — never a progress-report table.)

**Recognizing a progress-report table (vs. an orchestration table).** A plan may contain several
tables; only one tracks *progress*. A **progress-report table** has a **Status** column (or
status-like state in its cells) **and/or** carries per-step **Plan** / `Plan: [[…]]` / `Closeout: [[…]]`
links — i.e. it records both *which step* and *how far along*. A table that only describes
*granularity*, *dispatch*, or *sequencing* — columns such as `Granularity`, `Action required`,
`Session`, `Why split`, or a gate/verdict matrix — with **no** status/plan/closeout signal is **not** a
progress-report table: it has no down-links to follow and no completion state to read. Do not walk it
as one. A plan whose only step-tracking structure is such an orchestration table (and which has no
step-tracking bullet list either) is **not traversable** — see C6.

## C2. Status vocabulary (shared)

Use these exact spellings; both consumer skills depend on them:

- `incomplete` — not started.
- `in progress (planning underway)` — a descendant of this step now has a plan, but **no descendant has executed yet** (set by planning-mode ascent).
- `in progress (partially executed)` — at least one descendant row has reached a closed state
  (`completed-and-merged` / `done` / `executed — PR open` / `deferred` / `declined` / `out-of-scope`),
  at least one other is still `incomplete`, `PLAN WRITTEN — ready to execute`, or
  `in progress (planning underway)` (set by completion-mode ascent on partial ancestors). The
  parenthetical accurately describes the state: execution has started but is not finished.
- `PLAN WRITTEN — ready to execute` — this step's *own* plan exists but is not executed (set by
  superplan on the immediate-parent row).
- `executed — PR open` — this step's plan ran end-to-end and a closeout report exists, but the code
  PR has not yet been squash-merged to `main` (set by completion-mode ascent / superfinish when the
  code PR is still open). A follow-up superfinish (or manual update) flips this to
  `completed-and-merged` once the code is on `main`.
- `deferred` / `declined` / `out-of-scope` — intentionally not pursued; **non-blocking** for the
  "all children merged-on-main" check in completion-mode ascent.
- `completed-and-merged` / `done` — closed, code on `main` (set by completion-mode ascent /
  superfinish when the code PR has been merged).

**State-progression invariant.** A row only ever moves "rightward" along the lifecycle:

```
incomplete  →  in progress (planning underway)  →  PLAN WRITTEN — ready to execute
            →  in progress (partially executed)  (only at internal nodes — leaves skip this)
            →  executed — PR open  →  completed-and-merged
```

`deferred` / `declined` / `out-of-scope` are terminal off-ramps available from any earlier state.
Both ascents are forbidden from downgrading a row to a state earlier in this sequence.

## C3. Inferring a row's child-plan link (legacy-compatible — REQUIRED)

Tables do **not** need a `Plan` column — every progress-report table in the vault today predates it
and records the child-plan link inside the **Comments** cell. To find a row's child-plan link, try in
order:

1. If a dedicated **Plan** column exists and its cell is non-empty → use that link.
2. Else scan the row's cells (the **Comments** cell especially) for a `Plan: [[<link>]]` marker — the
   convention current superplan writes — and use that link.
3. Else scan the row for any wikilink / relative path into a `master-plans/` or `plans/` subfolder (a
   `.md` plan file) and use it.
4. Else look **outside the table row**, elsewhere in the same plan, for prose tied to this step — a
   section heading that names the step (e.g. `### Sub-PR #2 …`) or a callout/blockquote under it such
   as `> **Detailed step-level plan:** [[…]]` — and scan that for a child-plan link by the same rules.
   (Older plans summarise steps in a table but embed each step's plan link in a per-step section, not
   the table cell.)
5. If none found → the row has **no child plan** (treat as blank). A broken or missing link is also
   treated as blank — a dangling link must **never** silently halt traversal.

In every case **ignore** links into `reports/` (closeouts) and `findings/`, and ignore PR refs
(`#NNN`, GitHub URLs) — those are not child plans.

## C4. Detecting closed rows & the leaf/internal test

Two predicates — used at different points in the walk. The distinction matters because
`executed — PR open` rows are *past consideration* for descent (the work is done) but **not yet
merged on `main`** for the completion-mode parent-flip check.

- **Closed-for-descent row** (descent skip rule, C6): its **Status** text contains any of
  `completed-and-merged` / `done` / `merged` / `shipped` / `closed-out` / `executed — PR open` /
  `deferred` / `declined` / `out-of-scope`, **or** the row carries a `Closeout: [[…reports/…]]`
  link. Skip these rows during descent — the work is past consideration for both planning and
  execution targets. (Shipped seed rows commonly carry both signals.)
- **Merged-on-`main` row** (completion-mode "all children done" check, C7): its **Status** text
  contains `completed-and-merged` / `done` / `merged` / `shipped` / `closed-out` (i.e. the code is
  on `main`). `deferred` / `declined` / `out-of-scope` rows count as merged-on-`main` for this
  check ("done for our purposes"). **`executed — PR open` does NOT count** — the code is not yet on
  `main`, so the parent cannot yet be flipped to `completed-and-merged`.
- **Leaf vs internal:** read the plan the row's `Plan` link resolves to (C3) — if it **contains a
  progress-report table** (per C1's recognition test — an orchestration table does **not** count) it
  is an **internal node** (descend into it); if it **does not**, it is a **leaf** (an already-planned
  implementation plan; skip it).

## C5. Parent chaining (the "up" links)

Every plan superplan writes carries an explicit **parent-seed reference** near its top — a wikilink to
the plan it was derived from. Ascent follows these references upward:

```
leaf plan → immediate parent → … → root
```

The **root** is the plan with **no** parent-seed reference (the top of the initiative). Parent chaining
is the inverse of the `Plan`-column "down" links: descent walks down `Plan` links; ascent walks up
parent-seed references.

## C6. DESCENT — find the deepest target row (mode-parameterized)

**Input:** a root plan file and a **mode** — `planning` (default) or `execution`. Descent is one
pre-order DFS whose *target predicate* is selected by mode (symmetric with C7's `planning` /
`completion` ascent modes); everything else — the DFS walk, C1 schema, C3 link inference, C4
leaf/internal + completed-row tests, and `not-traversable` root handling — is shared.

- **planning mode** (consumer: `superplan`) finds **the deepest available task *to plan*** — the
  first not-done row with **no** child plan. **Output:** the **target row** plus the **descent
  path** — the ordered chain of `(plan-file, row)` from the root down to the **immediate parent**
  (the deepest plan that *directly contains* the target row), which planning-mode ascent (C7)
  consumes.
- **execution mode** (consumer: `superrun`) finds **the deepest written-but-unexecuted leaf plan
  *to execute*** — the first not-done row whose child plan is a leaf that is itself incomplete.
  **Output:** the **target leaf plan file path** (no descent path is needed — superrun does no
  planning-mode ascent; `superfinish` performs completion-mode ascent later via parent-seed
  chaining, C5/C7).

Both modes return **`none`** when no node yields a target, and **`not-traversable`** when the root
is not a progress-report tree.

Pre-order DFS, honoring priority order (top-to-bottom = highest rank first):

0. At the root plan, **identify its progress-report table** using C1's recognition test. If the root
   has **no** progress-report table — only orchestration tables (granularity / dispatch / gate
   matrices) and no step-tracking bullet list — it is **not traversable**: return
   **`not-traversable`** (distinct from "none") so the caller can report that the root is not
   maintained as a progress-report tree, rather than guess a stale target from an orchestration table.
   (This `not-traversable` outcome only arises at the **root**: a child is only descended into when
   C4's leaf/internal test already confirmed it carries a progress-report table; a node reached via a
   `Plan` link that turns out to lack one is a **leaf**, skipped, not an error.)
1. Walk that progress-report table's rows top to bottom.
2. For each row, **skip** if it is a closed-for-descent row (C4); otherwise apply the mode's per-row rule:
   - **planning mode:** if the row has **no child-plan link** (C3) → **this is the target.** Stop.
     (The first not-done row with no child plan, in DFS order, is the highest-priority unplanned
     task.) If it links to a plan, apply the leaf/internal test (C4): **internal → recurse into
     that plan** (descend); **leaf → skip** (already planned) and continue to the next row.
   - **execution mode:** if the row has **no child-plan link** (C3) → **skip** (nothing is written
     to execute yet — that is a planning gap for `superplan`, not an execution target). If it links
     to a plan, apply the leaf/internal test (C4): **internal → recurse into that plan** (descend);
     **leaf →** check the leaf's completeness (see completeness note below): **incomplete leaf →
     this is the target.** Stop. **complete leaf → skip** and continue to the next row.
3. A recursion that returns a target propagates it straight up, unchanged (priority preserved).
4. If no row at a node yields a target, that node is fully resolved for the mode → return **"none"**
   to the caller.
5. If the root returns "none", **no target exists for this mode** — the caller reports this and exits.
   (planning: nothing left to plan; execution: no incomplete implementation plan to run.)

**Completeness note (execution mode only).** A leaf plan is **complete enough to skip from
execution** when **either** its parent row reads as a closed-for-descent status (C4 — including
`executed — PR open`, since the work has been executed even if the code is not yet on `main`) **or**
the leaf plan file's opening blockquote carries a closeout banner (e.g.
`✅ CLOSED OUT … IMPLEMENTED, CI-GREEN & MERGED`). A leaf whose row is
`PLAN WRITTEN — ready to execute` and whose file shows no closeout banner is **incomplete** — the
execution target. Reading the leaf's own banner (not the row alone) handles the idempotent case
where a plan was executed but its parent row was not yet flipped, so a re-run does not re-execute
finished work.

**Bullet-list node** (a plan that tracks steps as a bullet list, not a table): treat each bullet as a
row and apply the mode's per-row rule (step 2) to it, inferring each bullet's child-plan link from its
text by the same C3 rule. Prefer the progress-report table where both a table and a list exist.

**In planning mode**, record the descent path as you go — the planning-mode ascent (C7) consumes it.
The **immediate parent** is the last (deepest) plan in the path; note that it may be a *descendant* of
the root, not the root itself. (Execution mode returns only the target leaf path and needs no descent
path.)

**Return-and-continue.** Once descent has produced its result — a target (+ descent path in planning
mode, or leaf path in execution mode), `none`, or `not-traversable` — return that result to the calling
skill (`superplan` for planning mode, `superrun` for execution mode) and immediately continue
executing the caller's next section. Do NOT end your turn after the descent. Do NOT print a
"descent complete" summary as if it were a final answer; the caller's Final Report is the user's only
checkpoint.

## C7. ASCENT — update ancestor rows up to the root

**Input:** a starting node, the path up to the root, and a **mode**. For **planning mode** the start is
the immediate parent and the path is the descent path (C6) reversed. For **completion mode** the start
is the executed leaf and the path is the parent chain obtained by following parent-seed references
(C5) upward.

At each **ancestor** along the path, locate the row whose child-plan link (C3) points at the child you
just came from, then apply the mode's update:

- **Planning mode** (superplan, after a new plan is written): set that row's **Status** →
  `in progress (planning underway)` **only if** it was previously not-started / `incomplete`. **Never
  downgrade** a more-advanced status; **never mark it complete** (completion is superfinish's job).
  Leave **Plan**, **PR**, and **Comments** unchanged — the `Plan` link already exists (it is how
  descent reached the child).

- **Completion mode** (superfinish, after a leaf is executed): the leaf row itself and ancestors
  are updated separately because they answer different questions.
  - **Leaf-row update** (the row pointing at the executed implementation plan): set the row's
    Status based on the leaf's code-PR merge state at superfinish time —
    - `executed — PR open` if the code PR is still open (closeout exists; main does not yet have
      the code).
    - `completed-and-merged` (or `done`) if the code PR has been squash-merged to `main`.
    In either case, write a one-line rollup + `Closeout: [[…]]` link in Comments, and record the
    PR number (`#NNN`) in the PR column. A later superfinish invocation flips `executed — PR open`
    to `completed-and-merged` once the PR merges (idempotent re-run).
  - **Ancestor-row update** (rows above the leaf, walked up via parent-seed references): read the
    child plan's progress-report table and apply the "all children merged-on-`main`" test (C4 —
    treating `deferred` / `declined` / `out-of-scope` as non-blocking; treating
    `executed — PR open` as NOT-yet-merged-on-`main`, i.e. blocking).
    - If every row is merged-on-`main`, flip the ancestor's row → `completed-and-merged` (or
      `done`) and write a one-line rollup + `Closeout: [[…]]` link in Comments.
    - Otherwise set the ancestor's row to `in progress (partially executed)` — but **only if the
      row was previously `incomplete`, `PLAN WRITTEN — ready to execute`, or
      `in progress (planning underway)`**; never downgrade a row already at
      `in progress (partially executed)` / `executed — PR open` / `completed-and-merged` / `done`.
      Then **stop flipping completes** higher up (you may still walk to the root, but only flip
      rows all of whose children are merged-on-`main`).
  - **Preserve the Plan link** when updating.

**Idempotency** (both modes): a row already at its target state (planning: already
`in progress (planning underway)` or more-advanced; completion: already at the state matching the
current child evidence — `in progress (partially executed)` when ancestors are partial,
`executed — PR open` when the leaf's PR is still open, `completed-and-merged` when the PR has
merged) is left untouched. Re-running superfinish after the code PR merges is the supported way to
flip `executed — PR open` → `completed-and-merged` (and propagate the parent rollup upward).

Stop at the **root**. If the starting node has no identifiable parent at all, there are no ancestors —
return immediately. Record every plan file touched (the calling skill's later commit step adds them via
explicit `git add`; supertraverse itself never commits). **After the ascent, return control to the
calling skill (`superplan` in planning mode, `superfinish` in completion mode) and continue executing
its next section without printing a separate report.**

---
name: superfinish
description: Use after an implementation plan from a goal folder's plans/ subfolder has been executed — captures findings, writes a closeout report to reports/, annotates the plan, and advances the parent seed's progress-report table. Bookkeeping only; never executes plan work.
license: all rights reserved
related skills: superplan, supertraverse
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

# Superfinish

Run **after** an implementation plan has been executed. Read the execution context, then update the
goal folder's vault: capture findings, write a closeout report, append a brief close-out note to the
plan, and advance the parent seed's progress-report table.

**Input:** `<PLAN.md>` — the executed implementation plan (the `.md` file from a goal folder's
`plans/` subfolder). May be passed explicitly, by a calling skill, or inferred from the session.

## The deliverable is vault bookkeeping — and ONLY that

**superfinish reads execution context and writes vault docs. It NEVER executes, implements, or
resumes any planned work.** It does not write source code, does not run tests or builds, and does not
create worktrees. It runs once the implementation is already done and records what happened. The one
thing it *does* commit is the **vault bookkeeping docs themselves** — once written, it commits and
merges them to `main` via a pull request **automatically, under the user's standing authorization,
without asking** (see **Commit and merge the vault docs — via PR** below). That is its only commit —
never source code, never execution output. After the Final Report, the skill is done.

| Thought | Reality |
|---------|---------|
| "There's an unchecked task in the plan, I'll just finish it" | NO. superfinish records outcomes; it does not execute remaining work. If work is unfinished, say so in the closeout and stop. |
| "I'll run the tests once more to confirm before writing the report" | NO. Use the evidence already produced in this session. superfinish runs no tests/builds. |
| "There's leftover source/execution work I'll commit alongside the docs" | NO. superfinish commits **only** the vault bookkeeping docs (automatically, via PR). Never source code, never execution output. |

## Input — resolve `<PLAN.md>` (Gate 1)

Resolve the plan in this order; stop at the first that succeeds:

1. **Explicit argument** — `<PLAN.md>` was passed to the skill. Use it.
2. **Passed by a calling skill** — if another skill invoked superfinish, it MUST pass the plan it was
   implementing. Use that.
3. **Infer from the session** — determine the implementation plan file that drove this execution
   session from the conversation context (the plan that was read/executed at session start).
4. **Ask** — if the plan still cannot be determined confidently, ask the user which plan file it is.
   Do **not** guess and do **not** hard-error here.

## Validation (Gate 2) — must be an implementation plan in `plans/`

The input MUST be an implementation plan living in a goal folder's **`plans/`** subfolder. It must
**not** be a seed, master, or sub-master plan.

- Confirm the resolved path is inside a `plans/` directory.
- Confirm the file is not a seed/master/sub-master plan. Signals it IS a seed/master (→ reject): it
  sits in `master-plans/`; its header declares `**Type:** Planning SEED` / `Sub-master plan` /
  `Master plan`; or it contains a progress-report table sequencing multiple sub-PRs rather than a
  single executable task list.

If the input is a seed/master/sub-master plan, **report the error and exit**:

    superfinish operates on an executed implementation plan from a `plans/` subfolder.
    `<PLAN.md>` is a <seed/master> plan (<reason>). Nothing was written. Exiting.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

## Goal Identification

Identify the **goal folder**: the top-level initiative directory that contains the `plans/`,
`master-plans/`, `findings/`, and `reports/` subfolders. It is the parent of the `plans/` folder the
input plan sits in (worked example from the originating repo: `<SUPER_GOAL_ROOT>/2026-05-20-graphgen-grammar-first-redesign/`). All
output is written under this goal folder.

**Read `goal-directives.md` at the goal-folder root FIRST, if it exists.** It is the authoritative map
of which subfolder each file type goes in. Route every write according to it. The standard routing
(absent a directives override) is:

- **Findings** → `findings/`
- **Closeout report** → `reports/`

If a goal folder lacks `reports/` or `findings/`, create the subfolder when writing (do not invent a
different location).

## After-Run Finish

Do the four steps below. **Draft every write to a scratch path OUTSIDE the goal folder** (e.g.
`$TMPDIR/` or `.claude/scratch/`) and write nothing into the vault until all four drafts are complete —
then write them all into the vault automatically (no confirmation is awaited).
Steps that were already done in a prior superfinish run for this session are idempotent — re-detect
and skip them (see each step).

### 1. Capture Findings

Identify findings, conflicts, or new information discovered **during execution** — paying particular
attention to anything that **contradicts or conflicts with the plan's assumptions** (a mechanism that
didn't work as the plan assumed, a constraint discovered mid-build, a cardinality/contract that
differed from the spec).

For each finding, review the existing docs in the goal folder's **`findings/`** subfolder and decide:

- **Revision** — an existing findings doc already covers this topic → update that doc with the new
  information.
- **Addition** — no existing doc covers it → create a new doc `findings/YYYY-MM-DD-hh_mm-<topic>.md`
  (today's date and the current UTC hour and minute at the start of the basename).

In **both** cases the findings doc **MUST contain an explicit reference to `<PLAN.md>`** (the plan
that produced/supports the finding), as a full-path wikilink. Open new findings docs with the standard
header block (`# Title`, `**Date:**`, `**Status:**`, `**Related:**` / `**Parent:**`).

**Be extra certain of each finding.** If you are unsure a finding is correct, **do not record it** —
false findings poison the goal. Only record what the session's evidence verifies. If there are no
findings, that is fine — record none.

### 2. Closeout Report

Write a closeout report for this session to the **`reports/`** subfolder (per `goal-directives.md`),
named `reports/YYYY-MM-DD-hh_mm-<topic>.md` (today's date and the current UTC hour and minute). It MUST include:

- **What was done** — the work this session shipped/completed.
- **Next steps** — what remains, deferred items, follow-ups.
- **Reference to the findings** uncovered this session (the docs from step 1), if any.
- **Reference to `<PLAN.md>`** — the plan this report grades, as a full-path wikilink.

Open with the standard header block (`# Title`, `**Date:**`, `**Type:** Sub-PR closeout`,
`**Status:**`, `**Related:**`). When CI evidence exists, cite the source CI run id(s) and verify the
artifact dates postdate the commits. Close the loop both ways — the
report links back to the plan/seed it grades.

### 3. Update Plan

Insert a **brief** close-out note **at the top of `<PLAN.md>`** — immediately after the plan's title
heading (and any parent-seed reference block superplan injected), **before** the plan body — that
summarizes the work done and links to the closeout report (step 2) as a full-path wikilink. Place it
at the top, **not** at the end of the file, so a reader sees the outcome first. **Keep it short** — a
few lines at most, not a restatement of the report.

**Idempotency:** if `<PLAN.md>` already contains a close-out note referencing a closeout report for
this work, do nothing and move on.

### 4. Update the Plan Tree Upward

Identify the **immediate parent** seed/master plan `<PLAN.md>` was derived from — read the parent-seed
reference near the top of `<PLAN.md>` (superplan injects one; this is the `supertraverse` C5 "up" link).
Then **invoke the `superagent:supertraverse` skill** (Skill tool) and run its **ASCENT in completion mode**,
chaining parent-seed references from this completed leaf up to the root. supertraverse C7 specifies
the per-row update precisely; this section need not restate it. In brief:

- **The leaf's own row** (the row pointing at `<PLAN.md>` in its immediate parent) gets either
  `executed — PR open` (the code PR is still open at superfinish time) or `completed-and-merged`
  (the code PR has been squash-merged to `main`) — pick the one that matches reality. Either way,
  add the PR number to the **PR** column and a one-line rollup + `Closeout: [[…]]` wikilink in
  **Comments**. A follow-up superfinish invocation flips `executed — PR open` →
  `completed-and-merged` once the code PR merges (idempotent re-run).
- **Each ancestor row above the leaf** is flipped to `completed-and-merged` only when *every* row
  in the child's progress-report table is merged-on-`main` per C4 (`completed-and-merged` / `done`
  / `merged` / `shipped` / `closed-out`, with `deferred` / `declined` / `out-of-scope` counting as
  non-blocking; `executed — PR open` does NOT count — the code is not yet on `main`). Otherwise
  the ancestor goes to `in progress (partially executed)` (when it was previously `incomplete`,
  `PLAN WRITTEN — ready to execute`, or `in progress (planning underway)`) and flipping-completes
  stops higher up.

It reads/preserves the `Plan` link via the shared inference (C3 — tolerating a legacy `Plan: [[…]]` in
Comments). If the seed also carries top-of-file closeout banners (`🟦/🟩/🟪/🟧`), update the matching
banner too.

**Idempotency:** a row already matching its evidence-based target state is left untouched (handled
by the shared ascent — `in progress (partially executed)` when ancestors are partial,
`executed — PR open` when the leaf's PR is still open, `completed-and-merged` when the PR has
merged). Re-running superfinish after the code PR merges is the supported way to flip
`executed — PR open` → `completed-and-merged` and propagate the parent rollup upward.

If no parent seed can be identified (no parent-seed reference and none inferable), note this in the
Final Report under "Other files" as "parent plan: none found — not updated" and continue; do not
fabricate a parent.

## Standing authorization — proceed without pausing (REQUIRED)

The user has granted **standing authorization** for superfinish to write its bookkeeping docs to the
vault and merge the resulting PR. **Do NOT pause to ask for approval, and do NOT present the drafts and
wait for a "go" before writing.** Once all four steps' drafts are complete, write the files into the
vault, then commit and merge them — automatically. This is not waived or re-enabled by auto-accept /
`bypassPermissions` mode; it is the default behavior.

Do not dump the full drafts to chat up front. The user's single checkpoint is the **Final Report**
(below), which clearly enumerates every file written this run.

## Commit and merge the vault docs — via PR (REQUIRED)

Once the vault files are written, commit those bookkeeping docs and merge them to `main` via a pull
request — **without asking the user for confirmation** (standing authorization, above). If
`SUPER_PROTECTED_MAIN=true` (the shipped default), the default branch is a **protected branch** (direct
pushes are rejected), so this MUST go through a feature branch and a PR — merged per
`SUPER_MERGE_METHOD` (default `squash`) — even though it is docs-only. If `SUPER_PROTECTED_MAIN=false`,
a direct commit to the default branch is permitted instead — see `superauthor` clause **A7**'s
`SUPER_PROTECTED_MAIN=false` worked example for the exact recipe (no feature branch, no PR, no `gh`).

**Scope of the commit: only the bookkeeping docs** written this run — the closeout report, new/revised
`findings/` docs, the `<PLAN.md>` close-out note, and **every ancestor plan file** the completion-mode
ascent updated (the immediate parent and any further-up ancestors it flipped, up to the root). Add each
with an explicit `git add <path>`; **never `git add -A`** (the working tree may hold unrelated changes
that are not yours to commit).

These are docs-only changes, so tag the commit subject `[skip ci]` to avoid firing CI on the merge.

```bash
# from the repo root, with the vault docs already written
BRANCH="finish/<topic>-$(date +%Y-%m-%d)"
git checkout -b "$BRANCH"
git add <reports-doc> [<findings-doc> ...] <plan-file> <immediate-parent-file> [<ancestor-plan-file> ...]   # explicit paths only
git commit -m "docs(finish): <topic> closeout — superfinish output [skip ci]"
git push -u origin "$BRANCH"
gh pr create --title "docs(finish): <topic> closeout" \
  --body "Closeout written by superfinish for <topic>. Grades <PLAN.md>."
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
  merged.** That is the local delete step, not a rejection: confirm with
  `gh pr view <n> --json state,mergedAt`, then drop the remote ref with
  `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>`.
- Capture the resulting **PR URL** (from `gh pr create` / `gh pr view --json url`) — report it in the Final
  Report below.
- Do **not** commit Anthropic/Claude attribution or `Co-Authored-By` trailers (repo policy).
- If `SUPER_GH_DISABLE_SANDBOX=true` (macOS hosts where `gh` needs keychain access to verify the
  TLS cert), all `gh` commands need `dangerouslyDisableSandbox: true`. If `false` (the shipped
  default), run `gh` normally.

## Final Report — then exit

After the writes and the PR merge, give the user a **single report** and exit. **This report is the
user's single window into what superfinish wrote — every file path created or modified this run MUST
appear here.**

    ## Superfinish complete

    **Plan:** <full path to PLAN.md>
    **Goal folder:** <full path>

    **Files created/modified:**
    - <reports/...> — closeout report (created)
    - <findings/...> — finding (created/revised)     (or: none)
    - <PLAN.md> — close-out note inserted at top       (or: already present — skipped)
    - <master-plans/...> — progress-report row updated (one line per ancestor the ascent touched, up to root; or: already complete — skipped / none found)

    **Findings:**
    - <finding summary>                                (or: none)

    ⚠️ **Critical:** <only present when a finding contradicts a plan assumption>

    **PR:** <url> (merged)

After printing the report, the skill is done: take no further action and ask no follow-up question.

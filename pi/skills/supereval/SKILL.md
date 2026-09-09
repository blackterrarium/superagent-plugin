---
name: supereval
description: Evaluate a coding-loop round — run the project's evaluation.md command checks against the latest main commit in a detached worktree (via scripts/supereval.sh), grade the judged objectives with a read-only evaluator subagent, and write eval-reports/<STAMP>-r<N>.md with one PASS/FAIL verdict. Fills the iteration-ledger row supermeta opened and commits per superauthor A7. Stage 2 of the coding loop; runs unattended.
argument-hint: "<project-dir> [--commit <sha>] [--round <N>] [--operation <path>]"
license: MIT
related skills: superauthor, supermeta, superprd, superloop
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
>   `.pi/agents/super-<role>.md` definitions `init` generates. `pi-subagents` ≥ 0.58.0 is required;
>   if the tool is absent, stop and report the missing prerequisite. No sequential fallback.
> - "Skill tool / invoke skill X" = `read` `${SUPER_PLUGIN_ROOT}/skills/X/SKILL.md` and follow it
>   (`/skill:` commands are interactive-only). Superpowers skills are listed by Pi from the
>   installed `superpowers` package — reference them by name.
> - `${SUPER_PLUGIN_ROOT}` = the plugin repository's `pi/` directory (two levels above each
>   SKILL.md). It contains `skills/`, `templates/`, and `scripts/` (`role-bridge.sh`,
>   `bridge-fanout.sh`, `_common.sh`, `prd-lint.sh`, `supereval.sh`, `_evalspec.sh`). The external-driver wrappers (`superagent-tick.sh`,
>   `launch.sh`, …) live in the repository's top-level `scripts/` — one directory up.
> - `EnterWorktree` = not available; use `git worktree` via `bash`.

# Supereval

The **evaluator** of the coding loop. Given a READY project folder whose round `supermeta` has already
opened (and whose inner `superagent` loop has built the goal), supereval runs the project's
`evaluation.md` **command checks** against the latest `main` commit in a detached worktree, grades any
**judged objectives** with a read-only evaluator subagent, and writes the round's **eval report** —
one PASS/FAIL verdict — then fills the round's iteration-ledger row.

supereval **never plans or executes the graded work itself and never touches source code**
(superauthor A1): it is read-only on the code, runs the shipped `scripts/supereval.sh` runner, and
dispatches at most **one** read-only EVALUATOR-role subagent. Its only writes are inside the project
folder (the eval report and the ledger cells).

**Input:** `<project-dir>` — an existing coding-loop project folder. **Required.**
Optional: `--commit <sha>` (evaluate this commit instead of the synced `main` tip); `--round <N>`
(evaluate ledger round `N` instead of the latest); `--operation <path>` uses the supervisor's
persisted phase identity and exact report target. Without an operation, manual behavior is unchanged.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

Keys used here: `SUPER_GOAL_ROOT`, `SUPER_PROJECT_DIRNAME`, `SUPER_LOOP_STATUS_DIRNAME`,
`SUPER_MODEL_EVALUATOR`, `SUPER_EFFORT_EVALUATOR`, `SUPER_EVAL_TIMEOUT_MIN` (read by `prd-lint.sh`
and `supereval.sh`).

## Vault root

Resolve `SUPER_GOAL_ROOT` (above). If it starts with `/` or `~`, the vault is **external**:
`<vault_root>` is that path (`~` expanded to `$HOME`, one trailing `/` stripped), resolved physically
(`cd "<path>" && pwd -P`) so it matches the paths `launch.sh` stores, and the vault is its own git
repository outside the checkout. Otherwise `<vault_root>` is `<primary_root>/<SUPER_GOAL_ROOT>`
(`primary_root` = `dirname "$(git rev-parse --path-format=absolute --git-common-dir)"`). Every goal
folder, project folder, loop-status file and lock derives from `<vault_root>`; **never join
`SUPER_GOAL_ROOT` onto the checkout root by hand.** The same rule is `vault_root` /
`vault_is_external` in `scripts/_common.sh`.

## What supereval is not

| Thought | Reality |
|---|---|
| "The command checks failed — I'll fix the code so they pass" | NO. supereval grades; it never edits source (A1). A failing check is a `FAIL` verdict, not a repair. |
| "I'll grade the judged objectives myself in this context" | NO. Judged rows are graded by exactly one read-only EVALUATOR-role subagent, so the EVALUATOR model pin applies and the grading context is isolated. |
| "The inner loop isn't `DONE`, so I must refuse" | NO. A non-`DONE` inner loop is a **WARN** in the report, not a refusal — the operator may evaluate a partial build on purpose. |
| "The evaluator subagent could not be dispatched — I'll just pass on the command checks" | NO. An unavailable evaluator makes the verdict **FAIL** with a warning naming it — never PASS by omission. |
| "A defect in `evaluation.md` / `prd.md` — I'll just fix it" | NO. Report it as a finding; supereval reads the inputs, it does not edit them. |

## Workflow

### 1. Invoke `superagent:superauthor`

Invoke it via the Skill tool and apply **A1** (no execution), **A3** (no placeholders), **A5** (no
confirmation pause — supereval runs unattended by design), **A6** (findings capture), **A7** (commit
and merge), **A8** (Final Report). **A2 does not apply** — the eval report is a structural outcome
document, not an implementation plan.

### 2. Inputs

Resolve `<primary_root>` (the code checkout: `dirname "$(git rev-parse --path-format=absolute --git-common-dir)"`) and `<vault_root>` (see **Vault root**).

1. `<project-dir>` must exist and contain `prd.md`, `knowledge-base.md`, `evaluation.md`, each with
   `**Status:** READY` in its header block. Otherwise print
   `supereval: <project-dir> is not a READY project folder (<what is missing>)` and **exit** without
   writing.
2. Run `PRD_LINT_REPO_ROOT="<primary_root>" "${SUPER_PLUGIN_ROOT}/scripts/prd-lint.sh" "<project-dir>"`.
   A non-zero exit is the same refusal, quoting the FAIL lines, then **exit** without writing.
3. Derive identifiers:
   - `<STAMP>` — `date -u +%Y-%m-%d-%H_%M`, taken once per run.
   - `<project-slug>` — the project folder's basename with its leading `YYYY-MM-DD-hh_mm-` stamp
     stripped (e.g. `csv-summariser`).
   - `N` (round) — defaults to the round of the **last** data row in `prd.md`'s `## Iteration ledger`
     table; `--round <N>` overrides it. The ledger row for `N` must exist (supermeta wrote it) —
     otherwise print `supereval: no ledger row for round <N>; run supermeta first` and **exit**
     without writing.

When `--operation <path>` is present, load duplicate-key-rejecting JSON containing exactly the
operation fields accepted by `_coding_loop_state.py`. Require `phase` = `EVALUATING`, a valid
operation id, round, agreement revision, `code_commit`, `meta_plan`, `goal_folder`, `report`, and
`source_vault_commit`. The report must resolve inside this project's `eval-reports` and end in
`-r<N>.md`. Use the recorded round, commit and exact report path, deriving `<STAMP>` only from its
frozen basename. Explicit `--round` or `--commit` values are permitted only when equal to the
recorded values. Require the current agreement fingerprint and source-vault revision to match before
running commands.

Operation mode's final output line is compact JSON with `outcome`, `phase`, `operation_id`, `round`,
`report`, `verdict`, `worker_complete`, `completion_reason`, `artifacts`, and `reason`.
`worker_complete: true` and `INTEGRATED` require the exact report and its one ledger row on `main`;
`ABSENT` or `CONFLICT` includes a recovery reason. The Final Report and partial
worker output are not phase-completion evidence.

### 3. Sync

Apply superloop **L5**: run `sync_main()` on `<primary_root>` and, for an external vault (see **Vault
root**), `sync_vault()`. If the sync gate STOPs (a divergent or dirty tree), do not evaluate —
surface the git state exactly as L5 requires and stop. After the sync, `<sha>` (the commit to
evaluate) defaults to `git -C "<primary_root>" rev-parse main`; `--commit <sha>` overrides it.

In operation mode, the recorded `code_commit` is the only `<sha>` and must resolve on synced
`main`. Reconcile before the runner. If the exact report and ledger are `INTEGRATED`, validate the
report against `evaluation.md`, return its verdict and skip both runner and EVALUATOR. For
`CONFLICT`, resume only exact pending A7 work owned by this operation. In particular, when the exact
FINAL report is already committed on `main` but its ledger cells are empty, validate those `main`
bytes and finish the ledger/A7 work without rerunning commands or dispatching another EVALUATOR.
Any different identity, dirty report, unrelated open PR, or conflicting ledger row is a hard
conflict. Never use unmerged report bytes as evidence.

### 4. Inner-loop link

From the round-`N` ledger row's *Goal folder* cell, resolve the round's goal folder under
`<vault_root>`. If it has `<SUPER_LOOP_STATUS_DIRNAME>/*.md`, take the **newest** such file as the
round's inner-loop file: record its path (for the row's *Inner loop* cell in step 8) and read its
`status:` frontmatter field. A `status:` other than `DONE` is a **WARN** carried into the report's
`## Verdict` block (step 7) — **not** a refusal (the operator may evaluate a partial build on
purpose). If no `<SUPER_LOOP_STATUS_DIRNAME>/*.md` exists, the inner-loop link is `none found`.

### 5. Command checks

Run the shipped runner (per-check timeouts are inside the script; keep its exit code):

```
"${SUPER_PLUGIN_ROOT}/scripts/supereval.sh" "<project-dir>" --repo "<primary_root>" --commit <sha> --out "$TMPDIR/supereval-<project-slug>-r<N>/results.md" --keep-worktree
```

Invoke it through the Bash tool with `timeout: 600000`. `--keep-worktree` leaves the detached
worktree in place so the evaluator (step 6) can inspect it; **read the kept worktree's path from the
`worktree:` field of the results file's `## Environment` line**. Keep the runner's exit code — the
verdict (step 7) keys on it (`0` = every command check PASS).

### 6. Judged objectives

First resolve the acceptance sources and evidence roots listed in the packet specification
below, including for projects with only command checks. Missing required binding text or an
unresolvable required evidence root sets `acceptance context unavailable`: do not dispatch an
evaluator; report overall FAIL with that warning and preserve the command results. A legacy
project's absent checklist is not a missing required source.

Then read the `## Judged objectives` table from `<project-dir>/evaluation.md`. **If it has no
`J` rows**, the report's `## Judged objectives` section is `none` and no subagent is dispatched.
Command-only evaluation makes only the claims its written command checks support; it does not
prove assertion completeness. **Otherwise, with acceptance context available, dispatch exactly
one read-only `EVALUATOR`-role subagent.** Resolve `SUPER_MODEL_EVALUATOR` /
`SUPER_EFFORT_EVALUATOR`.
The evaluator gets no `.pi/agents/` definition; dispatch it exactly as `superagent`'s Subagent-dispatch section does a read-only role on Pi — a blocking `role-bridge.sh --tools evaluator` process with the model/effort from `SUPER_MODEL_EVALUATOR` / `SUPER_EFFORT_EVALUATOR` (a bridged prefix runs that harness's CLI). Wait on it; never poll.
Give that one evaluator a single evidence packet containing:

- The kept worktree path and evaluated commit from step 5.
- The full `evaluation.md` verbatim, including J rows, the approved acceptance checklist,
  approval record, and binding contract notes; identify its source revision separately from
  the evaluated code commit. Include `prd.md` requirements/constraints/decisions verbatim,
  excluding its iteration ledger and prior verdicts.
- Any explicitly referenced binding acceptance text verbatim, with its source path/revision.
  Resolve references before dispatch; do not silently summarize away cases or general rules.
- Named evidence paths with their roots (code worktree versus project/vault), and step 5's
  command results. Implementer mappings may be supplied as claims to verify, never authority.

Do not supply prior evaluator answers, operator answer keys, or unrelated history. If required
binding text or evidence roots cannot be resolved, record no judged results and make the overall
verdict FAIL with an `acceptance context unavailable` warning; do not dispatch an incomplete
packet. Keep command results and the context error in the report.

The evaluator instruction is:

```
Inspect only the named evidence and acceptance sources; never modify anything. For each J
objective, verify its written criteria and applicable approved checklist items against actual
code, assertions and revision-specific execution evidence. Return PASS or FAIL with a concise
rationale citing file:line and relevant AC IDs; provide an item-to-evidence table for applicable
AC rows. An input occurrence, test name, mapping claim or green suite alone does not demonstrate
an assertion's required meaning. Distinguish product behavior, executed checks and assertion
coverage as specified by the written objectives. Extra coverage suggestions are advisory and
cannot cause FAIL unless grounded in an existing explicit requirement. Do not derive a new
comprehensive test inventory. For an ambiguous/conflicting acceptance input, report the input
defect and FAIL the affected objective pending author resolution; do not invent its meaning.
Legacy inputs without a checklist are judged against their explicit criteria and binding notes,
without a new format requirement or fabricated approval.
```

This is delivery verification of the authored agreement, not PRD coverage advice. Retain the
returned item-to-evidence table beneath the judged results in the report. A missing J result
cannot count as PASS.

It returns a table `| Id | Result | Rationale |`. If the dispatch **fails** (the evaluator is
unavailable), record no judged results and treat the verdict as FAIL with a warning naming the
failure (step 7) — never PASS by omission.

### 7. Report

Write `<project-dir>/eval-reports/<STAMP>-r<N>.md` with **exactly** this layout:

```
# <Project title> — eval report round <N> — <STAMP>-r<N>
**Date:** <YYYY-MM-DD> · **Status:** FINAL · **Related:** [[<SUPER_PROJECT_DIRNAME>/<project-folder-basename>/prd]] · [[<SUPER_PROJECT_DIRNAME>/<project-folder-basename>/meta-plans/<meta-plan basename of round N>]] · **Round:** <N>
**Operation:** <operation id> · **Agreement revision:** <agreement_revision> · **Source vault commit:** <source_vault_commit>   (operation mode only; omit this line manually)

<results.md content verbatim: Environment, Command checks, per-check output blocks>

## Judged objectives
| Id | Result | Rationale |
…or `none`

<Returned AC item-to-evidence table, when applicable>

## Verdict
**PASS** | **FAIL** — <comma-separated failing ids, or `all checks passed`>
**Inner loop:** `<loop-file path>` (status <status>) | none found
**Warnings:** <inner loop not DONE; setup failed; evaluator unavailable; or none>
```

- `<Project title>` and the round-`N` meta-plan basename come from the ledger row and `prd.md`.
- The `<results.md content verbatim>` is the file `supereval.sh` wrote in step 5 — its
  `## Environment`, `## Command checks` table, and per-check `### <Id> output` blocks — embedded
  unchanged.
- **Verdict rule:** the verdict is `PASS` **iff** the runner exited `0` **and** every judged (`J`)
  row has a returned `PASS` and acceptance context is available. Otherwise it is `FAIL`; name
  failing or missing C/J IDs and any context/dispatch error in the verdict reason. An empty J
  table is allowed for command-only projects but does not waive acceptance-context resolution. An
  **unavailable evaluator** (step 6 dispatch failed) makes the verdict `FAIL` with the
  `evaluator unavailable` warning — never PASS by omission.
- **Warnings** collects: `inner loop not DONE` (step 4), `setup failed` (the runner reported
  `ERROR setup failed`), `evaluator unavailable`, `acceptance context unavailable`, or missing judged IDs (step 6) — or `none`.
- Operation mode writes only the recorded report target. If verified matching report bytes already
  exist, preserve them exactly; never create a second timestamped report.

### 8. Ledger

Fill row `N`'s three trailing cells in `prd.md`'s `## Iteration ledger` table, preserving the
*Round*, *Meta-plan*, and *Goal folder* cells `supermeta` wrote:

- *Inner loop* — the inner-loop file link from step 4 (if found), else leave `-`.
- *Eval report* — `[[<SUPER_PROJECT_DIRNAME>/<project-folder-basename>/eval-reports/<STAMP>-r<N>]]`.
- *Verdict* — `PASS` or `FAIL`.

In operation mode, require exactly one round-`N` row and preserve its first three cells. Fill only
empty trailing cells or reuse already identical values. A second row, a different report link,
inner-loop link, or verdict is a conflict. This makes replay after a report commit or ledger commit
idempotent.

### 9. Commit (A7)

Apply **A7** with:

- **branch prefix:** `project/<project-slug>-r<N>-eval`
- **commit subject:** `docs(project): <project-slug> round <N> eval <PASS|FAIL>`
- **PR title:** `docs(project): <project-slug> r<N> eval`
- **PR body:** `Evaluation report for round <N> written by supereval; verdict <PASS|FAIL>.`
- **explicit `git add`:** the eval report (`eval-reports/<STAMP>-r<N>.md`) and `prd.md`. Never
  `git add -A`.
- **External vault:** A7's target is the vault repo — a direct commit, no PR (see A7 **Target
  repo**); its precondition applies (STOP and report if `<vault_root>` is not its own repository).

Operation mode commits or resumes the exact pending A7 work and then runs reconciliation plus
`validate-evaluation` against `main` bytes. Verify both report and ledger commits before publishing
completion. An open/unmerged PR, dirty path, wrong selected SHA, or incomplete validation emits a
non-integrated JSON result and does not advance the phase.

Then remove the kept worktree: `git -C "<primary_root>" worktree remove --force "<worktree path>"`
(the path read in step 5).

### 10. Final Report (A8)

```
## Supereval complete

**Project:** <project-dir>   **Round:** <N>   **Commit evaluated:** <sha>
**Report:** <path>
**Verdict:** PASS | FAIL (<failing ids>)
**PR:** <url> (merged)
**Commit:** <short-sha> in <vault_root>   (external vault — print this line INSTEAD of the PR line)
**Next:** PASS → the project is complete for this PRD · FAIL → superagent:superdiagnose <project-dir> (Stage 3; until then, read the report and start a new round with supermeta)
```

After printing the report, take no further action and ask no follow-up question.

In operation mode only, print the compact operation-result JSON as the final line after the report.

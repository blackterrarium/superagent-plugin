---
name: supereval
description: Evaluate a coding-loop round — run the project's evaluation.md command checks against the latest main commit in a detached worktree (via scripts/supereval.sh), grade the judged objectives with a read-only evaluator subagent, and write eval-reports/<STAMP>-r<N>.md with one PASS/FAIL verdict. Fills the iteration-ledger row supermeta opened and commits per superauthor A7. Stage 2 of the coding loop; runs unattended.
argument-hint: "<project-dir> [--commit <sha>] [--round <N>]"
license: MIT
related skills: superauthor, supermeta, superprd, superloop
---

<!-- GENERATED FILE — Cursor build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-cursor-skills.sh. -->

> **Cursor build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` and `Monitor` tools do **not** exist on Cursor — treat
>   any residual mention of them as inapplicable and NEVER attempt those tool calls.
> - Tool mapping: "Agent tool" = spawn a subagent (synchronously — wait for its result). "Skill
>   tool" = invoke a skill. `AskUserQuestion` / `AskQuestion` = ask the user in chat (attended
>   sessions only — never in a headless tick). `EnterWorktree` = not available; where a skill
>   manages worktrees, use `git worktree` via shell. "Desktop routine" = a Claude Desktop feature,
>   not available — use an OS scheduler. A role whose `.superenv` value names another harness
>   (`codex:gpt-5.6-sol`, `pi:openai/gpt-5`, …) is BRIDGED: dispatch it with
>   `subagent_type: super-<role>` — the relay definition `superagent:init` generates — and treat a
>   reply beginning `BRIDGE-FAILED` as a failed subagent.
> - `${SUPER_PLUGIN_ROOT}` in commands and paths = this plugin's installed root directory (the one
>   containing `skills/` and `templates/`, two levels above this SKILL.md). Substitute its absolute
>   path wherever it appears.
> - Skill names are **unprefixed** on Cursor: `superagent:superplan` means the `superplan` skill
>   from this plugin, `superpowers:subagent-driven-development` means `subagent-driven-development`,
>   and so on — strip the `<plugin>:` prefix when looking a skill up. The `superagent` supervisor
>   skill itself carries `disable-model-invocation` and is invisible to model-driven skill lookup —
>   it is driven by reading its SKILL.md directly (the external tick's file-read prompt), never
>   invoked by name.

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
(evaluate ledger round `N` instead of the latest).

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

### 3. Sync

Apply superloop **L5**: run `sync_main()` on `<primary_root>` and, for an external vault (see **Vault
root**), `sync_vault()`. If the sync gate STOPs (a divergent or dirty tree), do not evaluate —
surface the git state exactly as L5 requires and stop. After the sync, `<sha>` (the commit to
evaluate) defaults to `git -C "<primary_root>" rev-parse main`; `--commit <sha>` overrides it.

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

Read the `## Judged objectives` table from `<project-dir>/evaluation.md`. **If it has no `J` rows**,
the report's `## Judged objectives` section is `none` and no subagent is dispatched. **Otherwise
dispatch exactly one read-only `EVALUATOR`-role subagent.** Resolve `SUPER_MODEL_EVALUATOR` /
`SUPER_EFFORT_EVALUATOR`.
If the model is `inherit` or a bare model name **and** the effort is `inherit`, dispatch with the plain subagent mechanism — `model: <name>` when named, no `model:` when `inherit`. Otherwise dispatch with `subagent_type: super-evaluator` and omit `model:`; that is the definition `superagent:init` generates in `.cursor/agents/`, and a missing definition is a hard error: report "re-run `superagent:init`" and stop.
The subagent's prompt contains **only**: the kept **worktree path** (from step 5), the `J` rows
**verbatim**, and this instruction sentence:

```
For each objective, inspect only the evidence paths named; answer PASS or FAIL against the written criteria with a two-sentence rationale citing file:line; never modify anything.
```

It returns a table `| Id | Result | Rationale |`. If the dispatch **fails** (the evaluator is
unavailable), record no judged results and treat the verdict as FAIL with a warning naming the
failure (step 7) — never PASS by omission.

### 7. Report

Write `<project-dir>/eval-reports/<STAMP>-r<N>.md` with **exactly** this layout:

```
# <Project title> — eval report round <N> — <STAMP>-r<N>
**Date:** <YYYY-MM-DD> · **Status:** FINAL · **Related:** [[<SUPER_PROJECT_DIRNAME>/<project-folder-basename>/prd]] · [[<SUPER_PROJECT_DIRNAME>/<project-folder-basename>/meta-plans/<meta-plan basename of round N>]] · **Round:** <N>

<results.md content verbatim: Environment, Command checks, per-check output blocks>

## Judged objectives
| Id | Result | Rationale |
…or `none`

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
  row is `PASS`. Otherwise it is `FAIL`, and the `— <…>` clause names the failing ids
  (command-check ids that are not PASS and/or judged ids that are FAIL), or `all checks passed` when
  the only reason for FAIL is a non-command/judged failure such as an unavailable evaluator. An
  **unavailable evaluator** (step 6 dispatch failed) makes the verdict `FAIL` with the
  `evaluator unavailable` warning — never PASS by omission.
- **Warnings** collects: `inner loop not DONE` (step 4), `setup failed` (the runner reported
  `ERROR setup failed`), `evaluator unavailable` (step 6) — or `none`.

### 8. Ledger

Fill row `N`'s three trailing cells in `prd.md`'s `## Iteration ledger` table, preserving the
*Round*, *Meta-plan*, and *Goal folder* cells `supermeta` wrote:

- *Inner loop* — the inner-loop file link from step 4 (if found), else leave `-`.
- *Eval report* — `[[<SUPER_PROJECT_DIRNAME>/<project-folder-basename>/eval-reports/<STAMP>-r<N>]]`.
- *Verdict* — `PASS` or `FAIL`.

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

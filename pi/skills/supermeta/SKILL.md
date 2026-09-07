---
name: supermeta
description: Turn a READY coding-loop project folder into the next round's meta-plan and drive supergoal (auto-confirmed) to scaffold the goal folder the inner loop will build. Writes meta-plans/<STAMP>-r<N>.md, dispatches one PLANNER subagent that runs supergoal, appends the iteration-ledger row, and commits per superauthor A7. Stage 2 of the coding loop; runs unattended.
argument-hint: "<project-dir>"
license: MIT
related skills: superauthor, supergoal, superprd, supereval
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

# Supermeta

The **meta-planner** of the coding loop. Given a READY project folder (`prd.md`,
`knowledge-base.md`, `evaluation.md`, written by `superprd`), supermeta writes the round's
**meta-plan** — a self-contained goal description a planner can turn into a root master plan without
any other context — and drives `superagent:supergoal` (auto-confirmed) to scaffold the goal folder
the inner `superagent` loop will build. It then records the round in the project's iteration ledger.

supermeta **never plans the work itself and never touches source code** (superauthor A1): it produces
structural docs (a meta-plan and a ledger row) and dispatches exactly **one** PLANNER-role subagent
that invokes `superagent:supergoal`.

**Input:** `<project-dir>` — an existing coding-loop project folder. **Required.**

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

Keys used here: `SUPER_GOAL_ROOT`, `SUPER_PROJECT_DIRNAME`, `SUPER_MODEL_PLANNER`,
`SUPER_EFFORT_PLANNER`, `SUPER_GOAL_AUTOCONFIRM`, `SUPER_EVAL_TIMEOUT_MIN` (read by `prd-lint.sh`).

## Vault root

Resolve `SUPER_GOAL_ROOT` (above). If it starts with `/` or `~`, the vault is **external**:
`<vault_root>` is that path (`~` expanded to `$HOME`, one trailing `/` stripped), resolved physically
(`cd "<path>" && pwd -P`) so it matches the paths `launch.sh` stores, and the vault is its own git
repository outside the checkout. Otherwise `<vault_root>` is `<primary_root>/<SUPER_GOAL_ROOT>`
(`primary_root` = `dirname "$(git rev-parse --path-format=absolute --git-common-dir)"`). Every goal
folder, project folder, loop-status file and lock derives from `<vault_root>`; **never join
`SUPER_GOAL_ROOT` onto the checkout root by hand.** The same rule is `vault_root` /
`vault_is_external` in `scripts/_common.sh`.

## What supermeta is not

| Thought | Reality |
|---|---|
| "The meta-plan is basically the root plan, I'll write the master plan here" | NO. supermeta writes a *goal description* (the meta-plan). `supergoal` scaffolds the goal folder; `superplan` writes the plans; `superrun` executes. supermeta plans nothing (A1). |
| "I'll invoke `supergoal` directly, it's simpler than dispatching a subagent" | NO. supermeta dispatches exactly one PLANNER-role subagent that runs `supergoal`, so the PLANNER model pin applies and the invoking context stays lean. |
| "`--autoconfirm` alone skips the pause" | NO. It is honoured only when `SUPER_GOAL_AUTOCONFIRM` resolves to `true` (two-factor). If the key is not true, supergoal reports `--autoconfirm ignored: SUPER_GOAL_AUTOCONFIRM is not true` and pauses — treat that as a refusal (see step 6). |
| "A defect in `evaluation.md` / `prd.md` — I'll just fix it" | NO. Report it as a finding; supermeta reads the inputs, it does not edit them. |

## Workflow

### 1. Invoke `superagent:superauthor`

Invoke it via the Skill tool and apply **A1** (no execution), **A3** (no placeholders), **A5** (no
confirmation pause — supermeta runs unattended by design), **A6** (findings capture), **A7** (commit
and merge), **A8** (Final Report). **A2 does not apply** — the meta-plan is a structural goal
description, not an implementation plan.

### 2. Inputs

Resolve `<primary_root>` (the code checkout: `dirname "$(git rev-parse --path-format=absolute --git-common-dir)"`) and `<vault_root>` (see **Vault root**).

1. `<project-dir>` must exist and contain `prd.md`, `knowledge-base.md`, `evaluation.md`, each with
   `**Status:** READY` in its header block. Otherwise print
   `supermeta: <project-dir> is not a READY project folder (<what is missing>)` and **exit** without
   writing.
2. Run `PRD_LINT_REPO_ROOT="<primary_root>" "${SUPER_PLUGIN_ROOT}/scripts/prd-lint.sh" "<project-dir>"`.
   A non-zero exit is the same refusal, quoting the FAIL lines, then **exit** without writing.

### 3. Derive identifiers

- `<STAMP>` — `date -u +%Y-%m-%d-%H_%M`, taken once per run.
- `<project-slug>` — the project folder's basename with its leading `YYYY-MM-DD-hh_mm-` stamp
  stripped (e.g. `csv-summariser`).
- `N` (round) — `1 +` the number of data rows in `prd.md`'s `## Iteration ledger` table (so the
  first round is `1`).
- **Repair guidance** — if `<project-dir>/diagnoses/<…>-r<N-1>.md` exists (never in Stage 2; the
  file layout is fixed so Stage 3 needs no change here), read it and quote its per-problem guidance;
  otherwise repair guidance is `none — first round`.

### 4. Read the knowledge base

Read every row of `knowledge-base.md` by its `Kind`/`Locator`:

- `instructions` / `repo-file` / `sample-code` / `entry-point` (`<path>:<symbol>`) → read the file
  under `<primary_root>`.
- `repo-glob` → expand with `find` under `<primary_root>`.
- `doc-url` → fetch **only if** a fetch tool is available; else pass the URL through as a pointer.
- `context7` (`/<org>/<project>`) → resolve with `mcp__context7__query-docs` **when that tool is
  available**; else pass through.

For each row that resolved, keep the 1–10 lines most relevant to planning the work (a function
signature, a config key, a doc sentence) for the meta-plan's Excerpt column.

### 5. Draft `meta-plans/<STAMP>-r<N>.md`, self-review, and move it in

Draft in scratch (`$TMPDIR/supermeta-<project-slug>-r<N>/`) with **exactly** this section order,
then self-review it (A4 — spec coverage against the PRD/evaluation, A3 placeholder scan):

```
# <Project title> — meta-plan round <N> — <STAMP>-r<N>
**Date:** <YYYY-MM-DD> · **Status:** READY · **Related:** [[<SUPER_PROJECT_DIRNAME>/<project-folder-basename>/prd]] · **Round:** <N>

## Goal for this round
<one or two paragraphs: what the inner loop must build or repair this round, written as a goal
description supergoal can plan from without any other context. Round 1: the PRD objective in full.
Round N>1: the objective restated plus the repair scope from the diagnosis.>

## Success criteria and checks
<every SC row from prd.md verbatim, then every C/J row from evaluation.md verbatim, including the
Environment setup/cwd lines. These are the acceptance tests the plan must make pass.>

## Knowledge base
| Id | Kind | Locator | Read for | Excerpt |
<every knowledge-base row, plus an Excerpt column: the 1–10 lines the meta-planner judged most
relevant after reading the source. Never empty for rows that resolved; `(not fetched)` for unfetched
doc-url/context7 rows.>

## Constraints and locked decisions
<prd.md's "Constraints and non-goals" and "Locked decisions" sections verbatim>

## Repair guidance
<`none — first round`, or the diagnosis's per-problem guidance quoted>

## Planner instructions
- Goal folder slug: `<project-slug>-r<N>`.
- Every implementation plan's verification steps must run the checks above by id; the loop's
  evaluator will run them unchanged afterwards.
- Do not modify `evaluation.md`, `prd.md`, or `knowledge-base.md`; a defect in them is reported as
  a finding, not fixed.
```

Then **move** the reviewed file from scratch into `<project-dir>/meta-plans/<STAMP>-r<N>.md`
(uncommitted until the ledger commit in step 7) so the goal folder's `**Source:**` link can point at
its vault path.

### 6. Dispatch supergoal via one PLANNER subagent

Dispatch **one** `PLANNER`-role subagent. Resolve `SUPER_MODEL_PLANNER` / `SUPER_EFFORT_PLANNER`.
The planner gets no `.pi/agents/` definition; dispatch it exactly as `superagent`'s Subagent-dispatch section does the planner on Pi — a blocking `role-bridge.sh --tools planner` process with the model/effort from `SUPER_MODEL_PLANNER` / `SUPER_EFFORT_PLANNER` (a bridged prefix runs that harness's CLI). Wait on it; never poll.
The subagent's prompt instructs it to invoke the `superagent:supergoal` skill via the Skill tool with

```
<GOAL> = <absolute path of meta-plans/<STAMP>-r<N>.md>   --autoconfirm   --slug <project-slug>-r<N>
```

and to **return supergoal's complete Final Report verbatim** as its final message.

Parse `**Goal folder:**` and `**Root plan:**` from the returned report. **If** the report is missing
either line, **or** supergoal reports a refusal — the key is not `true`
(`--autoconfirm ignored: SUPER_GOAL_AUTOCONFIRM is not true`), the goal folder already exists (the
never-overwrite collision report), or `I need a goal description` — then supermeta writes **nothing**
to the ledger, **moves the meta-plan back** out of `meta-plans/` into scratch, and reports the
failure **verbatim** with the scratch path, then exits.

### 7. Ledger and commit (A7)

Append this row to `prd.md`'s `## Iteration ledger` table (the goal-folder path is
`**Goal folder:**` from step 6 made relative to `<vault_root>`):

```
| <N> | [[<SUPER_PROJECT_DIRNAME>/<project-folder-basename>/meta-plans/<STAMP>-r<N>]] | [[<goal-folder-path-from-vault-root>]] | - | - | - |
```

Then apply **A7** with:

- **branch prefix:** `project/<project-slug>-r<N>-meta`
- **commit subject:** `docs(project): <project-slug> round <N> meta-plan`
- **PR title:** `docs(project): <project-slug> r<N> meta-plan`
- **PR body:** `Meta-plan for round <N> written by supermeta; goal folder <goal-folder>.`
- **explicit `git add`:** the meta-plan file (`meta-plans/<STAMP>-r<N>.md`) and `prd.md`. Never
  `git add -A`. (supergoal has already committed the goal folder itself under its own A7; the
  explicit list keeps that commit and this one disjoint.)
- **External vault:** A7's target is the vault repo — a direct commit, no PR (see A7 **Target
  repo**); its precondition applies (STOP and report if `<vault_root>` is not its own repository).

### 8. Final Report (A8)

```
## Supermeta complete

**Project:** <project-dir>   **Round:** <N>
**Meta-plan:** <path>
**Goal folder:** <path>   **Root plan:** <path to master-plans/…>
**PR:** <url> (merged)
**Commit:** <short-sha> in <vault_root>   (external vault — print this line INSTEAD of the PR line)
**Repair guidance:** none — first round | <diagnosis path>
**Next:** superagent:superagent-external <root plan>   (then superagent:supereval <project-dir> when the loop is DONE)
```

After printing the report, take no further action and ask no follow-up question.

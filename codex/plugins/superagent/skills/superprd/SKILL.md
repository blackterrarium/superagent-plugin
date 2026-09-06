---
name: superprd
description: Use at the end of an interactive planning conversation to turn it into a coding-loop project folder — grades whether the session holds enough context (objective, measurable success criteria, knowledge-base sources, runnable evaluation checks, constraints, decisions), asks for each gap one question at a time, drafts prd.md / knowledge-base.md / evaluation.md, has a zero-context reviewer confirm they are self-sufficient, then writes the folder and merges it via PR after you confirm. `--check` only prints the readiness report.
argument-hint: "[--check] [<project-dir>]"
license: MIT
related skills: superauthor, supergoal, supermeta
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

# Superprd

The **input-assistance** skill of the coding loop. A planning conversation ends with its
decisions, sources, and success criteria scattered through the chat; the loop's meta-planner
(`supermeta`, Stage 2) gets none of that unless it is written down in a **project folder**.
superprd is the gate between the two: it grades the conversation against a readiness rubric,
fills the gaps with you, and only then writes the folder.

**Input:** the conversation so far (always), plus:

- `--check` — grade and print the readiness report only. Writes nothing, asks nothing.
- `<project-dir>` — an existing project folder to re-check or revise instead of creating one.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

Keys used here: `SUPER_GOAL_ROOT`, `SUPER_PROJECT_DIRNAME`, `SUPER_MODEL_PRD_REVIEWER`,
`SUPER_EFFORT_PRD_REVIEWER`, `SUPER_EVAL_TIMEOUT_MIN` (read by `prd-lint.sh`).

## What superprd is not

| Thought | Reality |
|---|---|
| "The objective is obvious from the chat, I'll infer the success criteria" | NO. superprd never invents a criterion, source, or command. Every rubric gap is a question to the user. |
| "I'll write the project folder now and ask afterwards" | NO. Draft to scratch, confirm, then write. The gate is not waived by auto-accept modes. |
| "The user said run it, I'll start planning the work" | NO. superprd produces inputs only (superauthor A1). `supermeta` / `supergoal` plan; `superrun` executes. |
| "prd-lint WARNs are fine to ignore" | They are carried into the report and the confirmation gate so the user decides. FAILs are fixed before the gate. |

## Workflow

### 1. Invoke `superagent:superauthor`

Invoke it via the Skill tool and apply **A1** (no execution), **A3** (no placeholders), **A6**
(findings capture), **A7** (commit and merge via PR), **A8** (Final Report). **A2 does not
apply** — the three files are structural docs, not plans. **A5 is overridden**: superprd pauses
for confirmation before any vault write (step 8), exactly as `supergoal` does.

### 2. Derive identifiers

- `<slug>` — concise kebab-case summary of the objective (mirror `supergoal`'s style).
- `<STAMP>` — `date -u +%Y-%m-%d-%H_%M`. `<DATE>` — `date +%Y-%m-%d` (branch name only).
- Project folder — `<SUPER_GOAL_ROOT>/<SUPER_PROJECT_DIRNAME>/<STAMP>-<slug>/`, rooted at the
  primary checkout. If `<project-dir>` was given, use it instead and treat its files as the
  starting draft. If the derived folder already exists and no `<project-dir>` was given,
  disambiguate the slug; if it is clearly the same project, report that and exit — never
  overwrite.
- Scratch — `$TMPDIR/superprd-<slug>/` (outside the vault). All drafting happens here.

### 3. Extract from the conversation

Collect, quoting the conversation where possible:

1. the **objective** — what the finished software does;
2. candidate **success criteria** and, for each, how the conversation said it would be verified;
3. **sources** — files the discussion touched or named, libraries and their docs, sample code,
   entry points, plus every `CLAUDE.md` / `AGENTS.md` / `AGENT.md` at the repo root (auto-added as
   `instructions` rows; the user may remove them);
4. **evaluation commands** — test runners, build steps, scripts the discussion called out, and
   the setup needed before they run;
5. **constraints and non-goals**;
6. **decisions** made in the conversation, each with the alternative rejected and why.

### 4. Grade readiness

| Id | Rubric item | PASS when |
|---|---|---|
| R1 | Objective | One paragraph states what the finished software does, without reference to the conversation. |
| R2 | Measurable criteria | Every success criterion can be tied to a command check (`exit <n>` / `stdout ~ /regex/`) or a judged objective with yes/no criteria. |
| R3 | Coverage | Every criterion has ≥1 check id; every check id serves ≥1 criterion. |
| R4 | Knowledge base | Every source needed to plan the work is listed and resolves. |
| R5 | Evaluation runnable | The setup command and every check command name a binary on `PATH` or a repo path, each with a timeout ≤ `SUPER_EVAL_TIMEOUT_MIN`. |
| R6 | Constraints and non-goals | Stated, or explicitly "none". |
| R7 | Locked decisions | Every decision the conversation made is captured with its rejected alternative. |

R1, R2, R6, R7 are judged by you from the extraction. R3, R4, R5 are mechanical: write the
current drafts to scratch (step 6's formats) and run

```
"${SUPER_PLUGIN_ROOT}/scripts/prd-lint.sh" "$TMPDIR/superprd-<slug>" --json
```

A `FAIL` maps to a rubric item by its `<file>:<loc>` and message:

- `prd.md:SC*` (an unknown check id, or a criterion with no check ids) and any `evaluation.md:<id>` whose message says `serves no success criterion` → **R3**;
- `knowledge-base.md:*` (a row id, `header`, `table`, or `file`) → **R4**;
- every other `evaluation.md:*` (an empty command, a malformed `Pass when`, a non-numeric or excessive timeout, a judged row with empty criteria or evidence, duplicate or missing ids, `Environment`, `setup`, `config`, `file`) → **R5**;
- every other `prd.md:*` (`file`, `header`, a missing or out-of-order section, the ledger header, no success-criteria rows) → **R2** (the criteria table is not in the shape the loop reads).

Never report R1–R7 all PASS while `prd-lint.sh` exits non-zero: a FAIL matching none of the rules above is an R2 gap naming its `<file>:<loc>`. WARNs are not gaps; keep them for the report.

Each item is `PASS` or `GAP <what is missing>`.

### 5. `--check` exit, or fill the gaps

**`--check`:** print the Readiness report (below) and **stop**. Write nothing, ask nothing.

**Otherwise:** for each `GAP`, in rubric order, ask the user **one question at a time**
(AskUserQuestion where the harness has it, plain chat otherwise), re-grade after each answer,
and continue until R1–R7 all PASS. A question names the gap and offers the concrete options the
conversation supports (e.g. "SC2 'fast enough' needs a threshold: p95 < 200 ms on the fixture,
or a judged objective?"). Never fill a gap with your own guess.

### 6. Draft the three files to scratch

All three open with the header block:

```
# <Title> — <STAMP>-<slug>
**Date:** <DATE> · **Status:** DRAFT · **Related:** [[<SUPER_PROJECT_DIRNAME>/<STAMP>-<slug>/<other-file>]]
```

**`prd.md`** — sections in this exact order:

```
## Objective
<one or more paragraphs>

## Success criteria
| Id | Criterion | Verified by (check ids) |
|---|---|---|
| SC1 | … | C1, C2 |

## Constraints and non-goals
- …

## Locked decisions
- <decision> — rejected: <alternative>, because <why>

## Iteration ledger
| Round | Meta-plan | Goal folder | Inner loop | Eval report | Verdict |
|---|---|---|---|---|---|
```

**`knowledge-base.md`** — one table, kinds `instructions`, `repo-file`, `repo-glob`,
`sample-code`, `entry-point` (`<path>:<symbol>`), `doc-url`, `context7` (`/<org>/<project>`):

```
| Id | Kind | Locator | Read for |
|---|---|---|---|
| K1 | `instructions` | `CLAUDE.md` | repo conventions |
| K2 | `repo-file` | `src/ingest/pipeline.py` | the current entry point |
```

**`evaluation.md`**:

```
## Environment
- setup: `<command run once in a fresh worktree; may be empty>`
- cwd: `<repo-relative dir every check runs in unless its row overrides>`

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `npm test` | `.` | `exit 0` | 20 |

## Judged objectives
| Id | Objective | Criteria | Evidence to inspect |
|---|---|---|---|
| J1 | Errors are user-readable | Every failure path returns a message naming the offending field | `src/cli/*.py` |
```

`Pass when` is exactly `exit <n>` or `stdout ~ /<regex>/`; `Timeout` is whole minutes. Check ids
are unique across both tables. A literal `|` inside a cell must be written `\|`.

Run `prd-lint.sh` on the scratch folder. Fix every FAIL (returning to step 5 when the fix needs
the user). Keep the WARNs.

### 7. Zero-context review

Dispatch **one** read-only `PRD_REVIEWER` subagent. Resolve `SUPER_MODEL_PRD_REVIEWER` / `SUPER_EFFORT_PRD_REVIEWER`. If the model is a bare tier name (`sonnet`, `opus`, `haiku`, `fable`) **and** the effort is `inherit`, dispatch with the plain subagent mechanism and `model: <tier>`. Otherwise — a full model ID such as the default `claude-opus-4-8`, a non-`inherit` effort, or a bridged harness prefix — dispatch with `subagent_type: super-prd-reviewer` and omit `model:`; that is the definition `superagent:init` generates in `.claude/agents/`, and a missing definition is a hard error: report "re-run `superagent:init`" and stop (the same rule superloop L7 applies to the panel). The prompt contains **only** the three scratch files
verbatim and these two questions:

1. Could a fresh planner, given these files and the sources they name and nothing else, write
   a root master plan for this objective? List every piece of missing context.
2. Could a fresh agent run `evaluation.md` unaided and reach a PASS/FAIL verdict? List every
   ambiguity in a check or a judged criterion.

The reviewer returns a findings list. Fix what the conversation already answers; ask the user
about the rest (step 5 rules); re-dispatch at most **twice**. Findings still open after that
go into the report as WARNs.

### 8. Confirmation gate (REQUIRED — overrides A5)

Nothing has been written to the vault. Present:

- the project folder path that **will** be created;
- the objective in one line;
- the success-criteria table;
- the check ids (command and judged) and the knowledge-base ids with kinds;
- every WARN from `prd-lint.sh` and every open reviewer finding.

Ask: *"Write this project folder to the vault and open the PR?"* and **wait**.
Approved → step 9. Changes requested → revise the scratch drafts, re-run steps 6–7 as needed,
re-present. Declined → write nothing, report the scratch path, exit. This pause is mandatory
and is **not** waived by auto-accept / `bypassPermissions` mode.

### 9. Write-out and PR (superauthor A7)

Create the project folder; write the three files with `**Status:** READY`; create
`meta-plans/`, `eval-reports/`, `diagnoses/` each with a `.gitkeep`. Then A7 with:

- **branch prefix:** `project/<slug>` → branch `project/<slug>-<DATE>`
- **commit subject:** `docs(project): <slug> — superprd output`
- **PR title:** `docs(project): <slug>`
- **PR body:** `Coding-loop project folder (prd, knowledge base, evaluation) generated by superprd.`
- **explicit `git add` list:** the three files and the three `.gitkeep`s. **Never `git add -A`.**

### 10. Final Report (superauthor A8)

```
## Superprd complete

**Project folder:** <full path>
**PRD:** <path>   **Knowledge base:** <path>   **Evaluation:** <path>
**PR:** <url> (merged)
**Readiness:** R1–R7 all PASS
**Warnings:** <prd-lint WARNs and open reviewer findings, or none>
**Next:** superagent:supermeta <project-dir>   (Stage 2 of the coding loop)
```

After printing the report, take no further action and ask no follow-up question.

## Readiness report (`--check`; also embedded in the gate)

```
## PRD readiness — <slug>
| Item | Result | Gap |
|---|---|---|
| R1 Objective | PASS | |
| R2 Measurable criteria | GAP | "fast enough" has no threshold |
| R3 Coverage | PASS | |
| R4 Knowledge base | GAP | context7 id /acme/sdk does not resolve |
| R5 Evaluation runnable | PASS | |
| R6 Constraints and non-goals | PASS | |
| R7 Locked decisions | GAP | the ORM choice was discussed but not settled |
**Verdict:** NOT READY (3 gaps)
**Warnings:** <prd-lint WARNs, or none>
```

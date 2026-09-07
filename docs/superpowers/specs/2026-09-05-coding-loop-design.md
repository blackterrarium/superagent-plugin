# Coding loop (supercode) — umbrella design

**Date:** 2026-09-05 · **Status:** approved (brainstormed interactively; the four axis decisions
below were chosen by the operator) · **Scope:** the extension of the superagent plugin into a
general autonomous coding agent: a PRD-driven outer loop that meta-plans, delegates to the
existing plan-tree machinery, evaluates the result, diagnoses failures, and repeats. This document
fixes the architecture and the split into three stages; each stage gets its own spec and plan.

Stage specs: [Stage 1 — project inputs and superprd](2026-09-05-coding-loop-stage1-prd-design.md);
Stage 2 and Stage 3 specs are written when their stage starts.

## Problem

Today the plugin turns a goal *description* into a plan tree and executes it to `DONE`. What it
lacks is everything around that: a structured statement of the objective with the documentation it
depends on, a definition of what "finished" means that a machine can check, and a loop that
re-plans when the check fails. A human currently plays meta-planner, evaluator, and diagnoser by
hand between goals.

## Goal

Given three inputs — a **PRD**, a **knowledge base** manifest, and an **evaluation** spec — run
unattended until the evaluation passes:

```
project folder (prd.md, knowledge-base.md, evaluation.md)
      │
      ▼
  supermeta ──► meta-plan for this round ──► supergoal ──► new goal folder + root plan
      │
      ▼
  superagent-external (the existing inner loop) runs the goal tree to DONE
      │
      ▼
  supereval ──► eval report: PASS ──► DONE
      │ FAIL
      ▼
  superdiagnose ──► RCA + repair guidance ──► back to supermeta (next round)
```

An **input-assistance** skill (`superprd`) turns an interactive planning conversation into the
three input files, and refuses to do so until the conversation holds enough context.

## Decisions (chosen 2026-09-05)

| Axis | Decision | Rejected |
|---|---|---|
| Evaluation | **Command checks with an agent fallback.** `evaluation.md` declares runnable checks with deterministic pass criteria; objectives no command can verify are graded by a read-only evaluator agent against written criteria. One report, one verdict. | Command-only (cannot grade non-testable objectives); agent-only (non-deterministic loop terminator). |
| Outer driver | **Unattended, scheduler-driven.** `supercode` is a second consumer of the superloop clause library with its own gitignored status file, driven by the same tick script and OS scheduler entry as `superagent`. | Attended in-session (context accumulates, console must stay open); both drivers at once (scope). |
| supergoal's confirmation gate | **Opt-in key honoured by supergoal.** `SUPER_GOAL_AUTOCONFIRM=true`, set *only* in supermeta's dispatch of supergoal, makes supergoal treat the meta-planner's self-review as the step-7 confirmation. Default `false`; direct users see no change. | Re-implement supergoal's scaffolding in the meta-planner (duplication); human confirms every round (not autonomous). |
| Delivery | **Three staged sub-projects**, each with its own spec, plan, PR, and version bump. | One spec and one plan for everything (unreviewable, un-landable incrementally). |
| Architecture | **Approach A — second superloop consumer on the shared chassis.** | B: project mode inside the `superagent` supervisor (touches the protected core). C: standalone bash orchestrator (duplicates lock/sync/escalation, breaks the skill idiom). |

## Architecture

### The project folder

Projects live beside goal folders, under the same root:

```
<SUPER_GOAL_ROOT>/<SUPER_PROJECT_DIRNAME>/<STAMP>-<slug>/     (default: vault/projects/…)
  prd.md              objectives, success criteria, constraints, locked decisions, iteration ledger
  knowledge-base.md   manifest of sources (repo files/globs, doc URLs, context7 ids, samples, entry points)
  evaluation.md       setup command, command checks, judged objectives
  meta-plans/         <STAMP>-r<N>.md   one per round, written by supermeta
  eval-reports/       <STAMP>-r<N>.md   one per round, written by supereval
  diagnoses/          <STAMP>-r<N>.md   one per failed round, written by superdiagnose
  loop-status/        gitignored outer loop file (superloop L1 format)
```

A project folder has **no `master-plans/`**, so `supertraverse`'s goal-folder derivation (parent of
`master-plans/`) can never resolve to it. Goal folders spawned by the loop are ordinary supergoal
output under `<SUPER_GOAL_ROOT>/<STAMP>-<slug>-r<N>/`, indistinguishable from hand-made ones; the
project's ledger is the only link between rounds. Formats of the three input files are fixed in
the Stage 1 spec.

### Skills (all additive)

| Skill | Stage | Runs as | What it does | Touches source code? |
|---|---|---|---|---|
| `superprd` | 1 | your interactive session (+ one `PRD_REVIEWER` subagent) | Grades the conversation's readiness against a rubric, asks targeted questions for each gap, drafts the three input files, has a zero-context reviewer confirm they are self-sufficient, confirms with you, ships the project folder via PR. `--check` mode prints the readiness report only. | No |
| `supermeta` | 2 | `META_PLANNER` subagent dispatched by the tick | Reads the PRD, knowledge base, evaluation spec, and the latest diagnosis; writes `meta-plans/<STAMP>-r<N>.md` (goal description, the knowledge-base excerpts and check ids this round must satisfy, locked decisions, repair guidance); dispatches `supergoal` with `SUPER_GOAL_AUTOCONFIRM=true`; records the goal folder in the ledger. | No |
| `supereval` | 2 | the tick (bash) + `EVALUATOR` subagent for judged objectives | Fresh worktree of synced `main`; runs the setup command, then every command check under its timeout; dispatches the evaluator for judged objectives; writes `eval-reports/<STAMP>-r<N>.md` with per-check results and one verdict `PASS`/`FAIL`. | No |
| `superdiagnose` | 3 | `DIAGNOSER` subagent dispatched by the tick | Reads the failed report, the PRD, and the round's goal folder (`reports/`, `findings/`); enumerates failing checks; RCA per problem; classifies each root cause as *implementation defect*, *plan gap*, or *PRD/evaluation defect*; writes `diagnoses/<STAMP>-r<N>.md`. A PRD/evaluation defect parks the loop on `WAITING FOR INPUT` (only the operator may change the spec). | No |
| `supercode` | 3 | the supervisor tick (`SUPERVISOR`) | Second superloop consumer. Per tick dispatches at most one of supermeta / supereval / superdiagnose, or launches the inner loop, or checks the parked inner loop. | No (only via the inner loop) |
| `supercode-external` | 3 | your session | Launcher: wraps `launch.sh --supervisor supercode`. Monitor / stop / force-stop are reused unchanged (same status-file format, listed by slug). | No |

### supercode state machine

```
WAITING FOR META-PLAN ──tick──► META-PLANNING ──supermeta+supergoal──► BUILDING
BUILDING (parked; bash gate polls the inner loop file) ──inner DONE──► WAITING FOR EVAL
WAITING FOR EVAL ──tick──► EVALUATING ──supereval──► DONE (PASS) | WAITING FOR DIAGNOSIS (FAIL)
WAITING FOR DIAGNOSIS ──tick──► DIAGNOSING ──superdiagnose──► WAITING FOR META-PLAN (round+1)
                                                          └──► WAITING FOR INPUT (spec defect, or round > SUPER_CODE_MAX_ITERATIONS)
```

superloop role mapping: ready = `WAITING FOR META-PLAN` / `WAITING FOR EVAL` / `WAITING FOR
DIAGNOSIS`; transient = `META-PLANNING` / `EVALUATING` / `DIAGNOSING` (persisted ⇒ crashed tick,
self-healed per L2); parked = `BUILDING` (the analogue of `WAITING FOR CI`: a bash-only gate,
no session while the inner file is not `DONE`); `WAITING FOR INPUT` and `DONE` as in L1.
Caller-specific frontmatter: `project:` (repo-relative project folder), `round:`, `inner_loop:`
(the inner loop-status path and slug while `BUILDING`), `last_eval:`, `last_diagnosis:`.

BUILDING details: on entering, the tick runs `launch.sh <root PLAN.md>` for the spawned goal
exactly as `superagent-external` does, records the inner slug/file, and exits. Each scheduler fire
then reads the inner file's `status:` in bash. `DONE` → `WAITING FOR EVAL` and a session is
started. `WAITING FOR INPUT` on the inner loop → stay parked, no second notification (the inner
tick already notified; `answer.sh <inner-slug>` resumes it). Any other status → exit silently.

### New `.superenv` keys

Roles (each with `SUPER_MODEL_<ROLE>` and `SUPER_EFFORT_<ROLE>`; bridging via the existing
per-role hook; `init` generates `.claude/agents/super-<role>.md`; each build script seds the
harness default exactly like the ten existing roles):

| Role | Dispatched by | Default model | Default effort |
|---|---|---|---|
| `PRD_REVIEWER` | superprd (zero-context sufficiency review, read-only) | `claude:claude-opus-4-8` | `high` |
| `META_PLANNER` | supercode tick → supermeta | `claude:claude-opus-4-8` | `high` |
| `EVALUATOR` | supereval (judged objectives only, read-only) | `claude:claude-opus-4-8` | `high` |
| `DIAGNOSER` | supercode tick → superdiagnose | `claude:claude-opus-4-8` | `xhigh` |

Reused roles: `SUPERVISOR` (the supercode tick itself), `PLANNER` (supergoal, dispatched by
supermeta), `PANEL` (L7 escalation), and the executor/SDD roles inside the inner loop.

Loop keys: `SUPER_PROJECT_DIRNAME=projects`, `SUPER_GOAL_AUTOCONFIRM=false`,
`SUPER_CODE_MAX_ITERATIONS=5`, `SUPER_EVAL_TIMEOUT_MIN=60` (per-check ceiling; a check's own
timeout column may be lower).

### Changes to existing code (all default-preserving)

| File | Change | Default behaviour |
|---|---|---|
| `scripts/superagent-tick.sh`, `scripts/launch.sh` | `--supervisor <skill>` (Stage 3): the SKILL.md the tick prompt reads; adds the BUILDING gate beside the CI and input gates. | `superagent`; gates only trigger on supercode statuses. |
| `skills/supergoal/SKILL.md` | Step 7 reads `SUPER_GOAL_AUTOCONFIRM` (Stage 2). | `false` ⇒ identical to today. |
| `skills/init/SKILL.md`, `scripts/build-*-skills.sh`, `templates/superenv.default` | Four new roles and four loop keys (Stage 1). | Existing roles untouched. |
| `.gitignore` entry written by `init` | Already covers `<SUPER_GOAL_ROOT>/**/<SUPER_LOOP_STATUS_DIRNAME>/`, which matches the project folder's `loop-status/` too. | No change needed. |

`supergoal`, `superplan`, `superrun`, `superfinish`, `superauthor`, `supertraverse`, `superloop`,
and the `superagent` supervisor keep working exactly as they do now, with or without the coding
loop installed. The loop only ever *calls* them.

## Stages

1. **Stage 1 — inputs and readiness** (ships as 0.7.0): project folder layout; the three input
   formats; `scripts/prd-lint.sh` (mechanical validation shared by superprd and supereval);
   `superprd`; the four roles and four loop keys across `superenv.default`, `init`, and the build
   scripts. Deliverable: author a PRD from a conversation and get a readiness verdict.
2. **Stage 2 — one manual round** (0.8.0): `supermeta`, the supergoal autoconfirm key,
   `supereval`. Deliverable: invoke supermeta → supergoal → superagent-external → supereval by
   hand and obtain an eval report.
3. **Stage 3 — the loop** (0.9.0): `superdiagnose`, `supercode`, `supercode-external`,
   `--supervisor` and the BUILDING gate in the tick/launch scripts, monitor listing; a scripted
   e2e testbench in the style of `scripts/pi-e2e.sh` on a toy repo whose evaluation is designed to
   fail the first round and pass after one repair.

## Non-goals (YAGNI)

- An attended in-session driver for the outer loop.
- Parallel rounds or several projects sharing one inner loop.
- Editing the PRD or evaluation spec autonomously: a spec defect always parks for the operator.
- The original plan scoped verification through Stage 3 to `SUPER_HARNESS=claude`. The
  [2026-09-07 compatibility follow-up](../reports/2026-09-07-coding-loop-harnesses.md) extends
  Stage 1/2 skill verification to Codex and Pi. Cursor and the full scheduler-driven coding-loop
  acceptance on Codex/Pi remain outside that follow-up.

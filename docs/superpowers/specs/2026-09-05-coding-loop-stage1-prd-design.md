# Coding loop Stage 1 — project inputs and `superprd`

**Date:** 2026-09-05 · **Status:** approved (see the umbrella design's decision table) ·
**Parent:** [Coding loop — umbrella design](2026-09-05-coding-loop-design.md) · **Ships as:** 0.7.0

## Scope

Stage 1 delivers everything the later loop consumes but nothing that runs it:

1. the **project folder** layout and the formats of `prd.md`, `knowledge-base.md`, `evaluation.md`;
2. `scripts/prd-lint.sh`, the mechanical validator for those three files, with offline tests;
3. the `superprd` skill: readiness grading, gap questions, drafting, zero-context review,
   confirmation, PR;
4. the four new roles and four loop keys in `templates/superenv.default`, `init`, and the three
   build scripts (`build-codex-skills.sh`, `build-cursor-skills.sh`, `build-pi-skills.sh`);
5. docs: README section, `scripts/README.md` entry for the linter, CHANGELOG, version bump.

Out of scope: supermeta, supereval, superdiagnose, supercode, any change to supergoal or the tick
script. Stage 1 must leave every existing skill byte-for-byte equivalent in behaviour.

## The project folder

`<SUPER_GOAL_ROOT>/<SUPER_PROJECT_DIRNAME>/<STAMP>-<slug>/`, default `vault/projects/…`.
`<STAMP>` and `<slug>` follow supergoal's step 2 (`date -u +%Y-%m-%d-%H_%M`, kebab-case slug).
Stage 1 creates `prd.md`, `knowledge-base.md`, `evaluation.md`, and the three artifact folders
`meta-plans/`, `eval-reports/`, `diagnoses/` each holding a `.gitkeep`. `loop-status/` is created
by the loop later and is already gitignored by init's `<SUPER_GOAL_ROOT>/**/<SUPER_LOOP_STATUS_DIRNAME>/`
pattern. **No `master-plans/`** — that is what keeps `supertraverse` from treating a project as a
goal.

Every file opens with the vault header block used throughout the plugin:

```
# <Title> — <STAMP>-<slug>
**Date:** YYYY-MM-DD · **Status:** DRAFT | READY · **Related:** [[…]]
```

### `prd.md`

Sections, in this order (all required; `prd-lint` checks presence and the coverage rule):

1. **Objective** — what the software must do when the project is finished, in prose.
2. **Success criteria** — a table; every row must name at least one check id from
   `evaluation.md` (the **coverage rule**), and every check id in `evaluation.md` must appear in at
   least one row:

   | Id | Criterion | Verified by (check ids) |
   |---|---|---|
   | SC1 | … | C1, C2 |

3. **Constraints and non-goals** — bullets.
4. **Locked decisions** — every decision the planning conversation settled, each with the rejected
   alternative and why (the same rule supergoal applies to its root plan; a decision that stays only
   in the conversation is invisible to the meta-planner).
5. **Iteration ledger** — a table the loop appends to; Stage 1 writes the header and no rows:

   | Round | Meta-plan | Goal folder | Inner loop | Eval report | Verdict |
   |---|---|---|---|---|---|

### `knowledge-base.md`

One table; every row is one source. `prd-lint` resolves the locator per kind.

| Id | Kind | Locator | Read for |
|---|---|---|---|
| K1 | `instructions` | `CLAUDE.md` | repo conventions |
| K2 | `repo-file` | `src/ingest/pipeline.py` | the current entry point |
| K3 | `repo-glob` | `tests/ingest/**` | existing test style |
| K4 | `doc-url` | `https://…` | vendor API reference |
| K5 | `context7` | `/vercel/next.js` | framework docs; queried at plan time |
| K6 | `sample-code` | `examples/csv-upload/` | worked example to mirror |
| K7 | `entry-point` | `src/app.py:main` | where the feature is wired in |

Kinds and their lint checks:

| Kind | Locator form | `prd-lint` check |
|---|---|---|
| `instructions` | repo-relative path to `CLAUDE.md`, `AGENTS.md`, etc. | file exists |
| `repo-file` | repo-relative path | file exists |
| `repo-glob` | repo-relative glob | matches ≥1 file |
| `sample-code` | repo-relative path (file or dir) | exists |
| `entry-point` | `<path>:<symbol>` | path exists; symbol grepped in the file (WARN, not fail, when absent) |
| `doc-url` | `http(s)://…` | syntactically a URL (no network in the linter) |
| `context7` | `/<org>/<project>` library id | matches `^/[^/]+/[^/]+$` (superprd resolves it live via `mcp__context7__resolve-library-id` when that tool is available; the linter stays offline) |

`instructions` rows are auto-added by superprd for every `CLAUDE.md` / `AGENTS.md` / `AGENT.md`
found at the repo root; the operator can remove them.

### `evaluation.md`

Three sections:

1. **Environment**

   ```
   - setup: <shell command run once in a fresh worktree before any check; may be empty>
   - cwd: <repo-relative directory every check runs in unless its row overrides; default .>
   ```

2. **Command checks** — deterministic. `Pass when` is exactly one of `exit 0`, `exit <n>`, or
   `stdout ~ /<regex>/`. `Timeout` is minutes and must not exceed `SUPER_EVAL_TIMEOUT_MIN`.

   | Id | Command | Cwd | Pass when | Timeout |
   |---|---|---|---|---|
   | C1 | `npm test` | `.` | `exit 0` | 20 |
   | C2 | `./scripts/e2e.sh` | `.` | `stdout ~ /ALL PASSED/` | 45 |

3. **Judged objectives** — graded by the `EVALUATOR` role in Stage 2. Criteria must be written so
   a reader could answer yes/no without the conversation.

   | Id | Objective | Criteria | Evidence to inspect |
   |---|---|---|---|
   | J1 | Errors are user-readable | Every failure path returns a message naming the offending field; no stack traces reach the CLI | `src/cli/*.py`, `tests/cli/` |

Check ids are unique across both tables (`C*` and `J*` are conventions, not enforced; uniqueness is).

## `scripts/prd-lint.sh`

```
prd-lint.sh <project-dir> [--json]
```

Pure bash + standard tools (grep, sed, awk, find), no network, no LLM. Exit 0 when every check
passes, 1 on any FAIL; WARNs never change the exit code. Prints one line per finding:
`PASS|WARN|FAIL <file>:<Id or section> <message>`; `--json` prints the same as a JSON array for
superprd to consume. Checks:

- the three files exist and open with the header block;
- `prd.md` has the five sections in order; the success-criteria table and ledger header parse;
- the coverage rule in both directions;
- every `knowledge-base.md` row has a known kind and its locator resolves per the table above;
- `evaluation.md`: `setup`/`cwd` lines parse; each command check has a well-formed `Pass when`
  and a numeric timeout ≤ `SUPER_EVAL_TIMEOUT_MIN` (resolved the standard way: env > `.superenv` >
  template); the first word of each command is on `PATH` or is an existing repo-relative path
  (WARN otherwise — a setup step may install it); judged rows have non-empty criteria and evidence;
- check ids unique across both tables.

Offline tests: `scripts/prd-lint-test.sh` in the `bridge-test.sh` style (temp dir, fixture
project folders, `ok`/`fail`/`check` helpers, exit 1 on any failure). Fixtures cover: a valid
project; each FAIL class; each WARN class; `--json` shape.

## The `superprd` skill

```
superagent:superprd [--check] [<project-dir>]
```

Frontmatter: `description` per the plugin's "Use when …" convention; `argument-hint: "[--check] [<project-dir>]"`
(quoted — see the Pi T6 lesson); `related skills: superauthor, supergoal, supermeta`. **No
`disable-model-invocation`**: like supergoal it is meant to be reachable from a plain request
such as "turn this into a PRD".

### Inputs

- The **conversation so far** — superprd runs in the operator's session at the end of a planning
  discussion and reads everything it holds. This is the "result of the interactive session" the
  readiness check evaluates.
- Optional `<project-dir>`: re-check or revise an existing project folder instead of starting one.
- `--check`: grade and report only; write nothing, ask nothing.

### Workflow

1. **Invoke `superagent:superauthor`** and apply A1 (no execution), A3 (no placeholders), A6
   (findings), A7 (PR), A8 (report). A2's plan-authoring standard does not apply — the three files
   are structural docs, like `goal-directives.md`. A5 (standing authorization) is **overridden**:
   superprd confirms before any vault write, exactly as supergoal does.
2. **Derive identifiers** — `<slug>`, `<STAMP>`, the project folder path; if it exists and
   `<project-dir>` was not given, disambiguate or exit (never overwrite).
3. **Extract** from the conversation: objective; candidate success criteria; sources mentioned or
   implied (files the discussion touched, libraries named, docs linked); commands that verify the
   work (test runners, build steps, scripts the discussion called out); constraints; decisions and
   rejected alternatives.
4. **Grade readiness** against the rubric. Each item is `PASS` or `GAP` with the missing piece named:

   | Id | Rubric item | PASS when |
   |---|---|---|
   | R1 | Objective | One paragraph states what the finished software does, without reference to the conversation. |
   | R2 | Measurable criteria | Every success criterion can be tied to a command check or a judged objective with yes/no criteria. |
   | R3 | Coverage | Every criterion has ≥1 check; every check serves ≥1 criterion. |
   | R4 | Knowledge base | Every source needed to plan the work is listed and resolves (`prd-lint` kinds; `context7` ids resolved live when the tool is available). |
   | R5 | Evaluation runnable | The setup command and every check command name a binary on `PATH` or a path in the repo, with a timeout. |
   | R6 | Constraints and non-goals | Stated, or explicitly "none". |
   | R7 | Locked decisions | Every decision made in the conversation is captured with its rejected alternative. |

   Mechanical items (R3, R4, R5) are checked by drafting to scratch and running `prd-lint.sh`;
   the rest are judged by superprd itself.
5. **`--check` exit** — print the **Readiness report** (below) and stop. Otherwise, for each
   `GAP`, ask the operator **one question at a time** (AskUserQuestion where available, plain
   chat otherwise), in rubric order, and re-grade after each answer. This is the human-in-the-loop
   part of the input-assistance requirement; superprd never invents a criterion, source, or
   command the operator did not supply or confirm.
6. **Draft** the three files to a scratch path outside the vault (`$TMPDIR/superprd-<slug>/`).
   Run `prd-lint.sh` on the scratch folder; fix FAILs; carry WARNs into the report.
7. **Zero-context review** — dispatch one read-only `PRD_REVIEWER` subagent (model/effort from
   `SUPER_MODEL_PRD_REVIEWER` / `SUPER_EFFORT_PRD_REVIEWER`, via `.claude/agents/super-prd-reviewer.md`
   when init generated it, else the plain Agent tool with the resolved model). Its prompt contains
   only the three scratch files and two questions: *could a fresh planner write a root master plan
   for this objective from these files and the sources they name alone?* and *could a fresh agent
   run `evaluation.md` unaided and reach a verdict?* It returns a findings list. superprd fixes
   what it can from the conversation, asks the operator about the rest (step 5 rules), and
   re-dispatches at most twice; remaining findings go into the report as WARNs.
8. **Confirmation gate** — present the project folder path, the objective in one line, the
   success-criteria table, the check ids, the knowledge-base ids and kinds, and the WARNs; ask
   *"Write this project folder to the vault and open the PR?"*; wait. Approved → step 9; changes
   → revise and re-present; declined → report the scratch path and exit with no vault write.
   Not waived by auto-accept modes, mirroring supergoal step 7.
9. **Write-out and PR** (A7): create the folder, the three files with `Status: READY`, and the
   three artifact folders with `.gitkeep`. Branch prefix `project/<slug>`; commit subject
   `docs(project): <slug> — superprd output`; PR title `docs(project): <slug>`; explicit `git add`
   list only.
10. **Final report** (A8):

    ```
    ## Superprd complete
    **Project folder:** <path>
    **PRD / Knowledge base / Evaluation:** <three paths>
    **PR:** <url> (merged)
    **Readiness:** R1–R7 all PASS
    **Warnings:** <prd-lint WARNs and unresolved reviewer findings, or none>
    **Next:** superagent:supermeta <project-dir>   (Stage 2)
    ```

### Readiness report (`--check`, and embedded in the gate)

```
## PRD readiness — <slug>
| Item | Result | Gap |
|---|---|---|
| R1 Objective | PASS | |
| R2 Measurable criteria | GAP | "fast enough" has no threshold |
…
**Verdict:** READY | NOT READY (<n> gaps)
```

## Roles and keys

`templates/superenv.default` gains, in the model and effort blocks after `FIX_PLANNER`:

```
SUPER_MODEL_PRD_REVIEWER=claude:claude-opus-4-8   # superprd: zero-context sufficiency review of the drafted PRD (read-only)
SUPER_MODEL_META_PLANNER=claude:claude-opus-4-8   # supermeta: meta-plan author, drives supergoal (Stage 2)
SUPER_MODEL_EVALUATOR=claude:claude-opus-4-8      # supereval: grades judged objectives (read-only; command checks use no model) (Stage 2)
SUPER_MODEL_DIAGNOSER=claude:claude-opus-4-8      # superdiagnose: root-cause analysis of a failed evaluation (Stage 3)
SUPER_EFFORT_PRD_REVIEWER=high
SUPER_EFFORT_META_PLANNER=high
SUPER_EFFORT_EVALUATOR=high
SUPER_EFFORT_DIAGNOSER=xhigh
```

and a new block:

```
# ── Coding loop (supercode) ───────────────────────────────────────
SUPER_PROJECT_DIRNAME=projects          # project folders land at <SUPER_GOAL_ROOT>/<SUPER_PROJECT_DIRNAME>/<STAMP>-<slug>/
SUPER_GOAL_AUTOCONFIRM=false            # true ONLY in supermeta's dispatch of supergoal: skips supergoal's step-7 human confirmation (Stage 2)
SUPER_CODE_MAX_ITERATIONS=5             # supercode rounds before parking on WAITING FOR INPUT (Stage 3)
SUPER_EVAL_TIMEOUT_MIN=60               # ceiling for any evaluation.md check timeout
```

Stage 1 declares all eight keys so `.superenv` files created now need no edit when Stages 2–3
land; the three later-stage keys are documented as "reserved, read by nothing yet".

`init`: four rows added to the agent-definition table (`super-prd-reviewer.md`,
`super-meta-planner.md`, `super-evaluator.md`, `super-diagnoser.md`), generated from the
existing `templates/super-role-agent.md` / bridge templates by the same rules as the nine roles
today. On Pi they follow the planner/panel rule (never a file; bridged or in-context). Build
scripts: one `SUPER_MODEL_*` sed and one `SUPER_EFFORT_*` sed per role per harness, mirroring the
`FIX_PLANNER` lines. `scripts/_common.sh` needs no change: the role parser is value-based.

## Compatibility

- No existing skill's text changes except `init` (additive table rows) and shared docs.
- A repo whose `.superenv` predates 0.7.0 resolves the new keys from the template default.
- `prd-lint.sh` and `superprd` are inert unless invoked.

## Testing

| What | How |
|---|---|
| `prd-lint.sh` | `scripts/prd-lint-test.sh` offline fixtures; run in the same place `bridge-test.sh` runs today. |
| Build scripts | `build-*-skills.sh --check` still clean; generated `superenv.default` for each harness shows the four roles with that harness's default model. |
| `init` | Re-run in a scratch repo: four new agent files appear, nine existing ones unchanged (diff against a pre-change run). |
| `superprd` | A live session on a toy repo: (a) `--check` on a deliberately thin conversation reports ≥3 GAPs and writes nothing; (b) a full run produces a project folder that passes `prd-lint.sh`, and the merged PR contains exactly the six paths. Recorded in `prd-smoke-report.md`, gitignored like the other smoke reports. |
| Regression | `bridge-test.sh`, `pi-smoke.sh`, and one existing `supergoal` invocation behave as before. |

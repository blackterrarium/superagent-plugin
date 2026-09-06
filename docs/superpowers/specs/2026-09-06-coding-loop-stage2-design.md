# Coding loop Stage 2 — `supermeta`, `supereval`, supergoal autoconfirm

**Date:** 2026-09-06 · **Status:** approved design · **Ships as:** 0.8.0 · **Parent:**
`docs/superpowers/specs/2026-09-05-coding-loop-design.md` (umbrella; its Decisions table is binding) ·
**Builds on:** Stage 1 (`…-stage1-prd-design.md`, shipped 0.7.0) and the external vault
(`2026-09-06-external-vault-design.md`, shipped 0.7.1).

This spec is written to be consumed by a planner agent (`supergoal` → `superplan`) with no access to
the conversation that produced it. Every format, command, and rule it needs is stated here.

## Scope

Stage 2 delivers **one manual round** of the coding loop:

```
supermeta <project-dir>            → meta-plans/<STAMP>-r<N>.md + a goal folder (via supergoal, auto-confirmed)
superagent-external <root PLAN.md> → the inner loop plans and executes that goal (unchanged, already shipped)
supereval <project-dir>            → eval-reports/<STAMP>-r<N>.md with one PASS/FAIL verdict
```

Deliverables: two new skills (`skills/supermeta/SKILL.md`, `skills/supereval/SKILL.md`), one new
script (`scripts/supereval.sh`) plus its offline test (`scripts/supereval-test.sh`), a shared table
parser extracted from `scripts/prd-lint.sh` (`scripts/_evalspec.sh`), three default-preserving
additions to `skills/supergoal/SKILL.md`, docs, changelog, version 0.8.0, regenerated harness builds.

Out of scope (Stage 3): `superdiagnose`, `supercode`, `supercode-external`, the tick's
`--supervisor` and BUILDING gate, monitor listing of project loops. No change to `superplan`,
`superrun`, `superfinish`, `superauthor`, `supertraverse`, `superloop`, `superagent`, or the inner
loop. No new `.superenv` keys: `SUPER_GOAL_AUTOCONFIRM`, `SUPER_EVAL_TIMEOUT_MIN`,
`SUPER_PROJECT_DIRNAME`, and the `META_PLANNER` / `EVALUATOR` roles already exist (Stage 1).

## Shared vocabulary

- **Project folder** — `<vault_root>/<SUPER_PROJECT_DIRNAME>/<STAMP>-<slug>/` as fixed by Stage 1:
  `prd.md`, `knowledge-base.md`, `evaluation.md`, `meta-plans/`, `eval-reports/`, `diagnoses/`.
  `<vault_root>` follows the external-vault rule (relative `SUPER_GOAL_ROOT` → inside the checkout;
  absolute/`~` → the external vault repo). Both new skills carry the canonical **Vault root** block
  and resolve `<primary_root>` (the code checkout) separately from `<vault_root>`.
- **`<project-slug>`** — the project folder's basename with its leading `YYYY-MM-DD-hh_mm-` stamp
  stripped (e.g. `csv-summariser`).
- **Round `N`** — a positive integer. `N` = 1 + the number of data rows in `prd.md`'s
  `## Iteration ledger` table (so the first round is 1).
- **`<STAMP>`** — `date -u +%Y-%m-%d-%H_%M`, taken once per skill run.
- **Ledger row** — one row of `prd.md`'s iteration ledger, columns exactly as Stage 1 fixed them:
  `| Round | Meta-plan | Goal folder | Inner loop | Eval report | Verdict |`. Links are vault
  wikilinks in the form used everywhere else in the vault: `[[<path-from-vault-root-without-.md>]]`.
  Empty cells hold `-`.
- **A7** — superauthor's commit-and-merge clause. Both new skills invoke `superagent:superauthor`
  via the Skill tool and apply A1 (no execution), A3 (no placeholders), A6 (findings), A7, A8;
  A2 does not apply (they write structural docs, not plans); A5 applies (no confirmation pause —
  these skills run unattended by design). A7 parameters are given per skill below. In an external
  vault A7's target is the vault repo (direct commit, no PR); in an internal vault it is the code
  repo's PR flow — the skills say nothing more than "apply A7", exactly like superprd.

## `supermeta` — the meta-planner

**Invocation:** `superagent:supermeta <project-dir>` (`argument-hint: "<project-dir>"`). Runs in
the invoking context (an interactive session in Stage 2; the `META_PLANNER` subagent the tick
dispatches in Stage 3). Never plans the work itself (A1) and never touches source code.

### Inputs

1. `<project-dir>` must exist and contain `prd.md`, `knowledge-base.md`, `evaluation.md`, each with
   `**Status:** READY` in its header block; else print `supermeta: <project-dir> is not a READY
   project folder (<what is missing>)` and exit without writing.
2. Run `PRD_LINT_REPO_ROOT="<primary_root>" "${CLAUDE_PLUGIN_ROOT}/scripts/prd-lint.sh"
   "<project-dir>"`; a non-zero exit is the same refusal, quoting the FAIL lines.
3. Derive `N`. If `diagnoses/<…>-r<N-1>.md` exists (never in Stage 2; the file layout is fixed so
   Stage 3 needs no change here), read it as **repair guidance**; otherwise repair guidance is
   `none — first round`.
4. Read every knowledge-base row's locator: `instructions` / `repo-file` / `sample-code` /
   `entry-point` rows are files under `<primary_root>` (read them); `repo-glob` rows are expanded
   with `find`; `doc-url` rows are fetched only if a fetch tool is available, else the URL is passed
   through as a pointer; `context7` rows are resolved with `mcp__context7__query-docs` when that
   tool is available, else passed through.

### Output: `meta-plans/<STAMP>-r<N>.md`

Drafted in scratch (`$TMPDIR/supermeta-<project-slug>-r<N>/`), self-reviewed (A4), then moved into
`meta-plans/` **before** supergoal is dispatched — uncommitted until the ledger commit below — so the
goal folder's `**Source:**` link can point at its vault path. Exact section order:

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
relevant after reading the source (a function signature, a config key, a doc sentence). Never
empty for rows that resolved; `(not fetched)` for unfetched doc-url/context7 rows.>

## Constraints and locked decisions
<prd.md's two sections verbatim>

## Repair guidance
<`none — first round`, or the diagnosis's per-problem guidance quoted>

## Planner instructions
- Goal folder slug: `<project-slug>-r<N>`.
- Every implementation plan's verification steps must run the checks above by id; the loop's
  evaluator will run them unchanged afterwards.
- Do not modify `evaluation.md`, `prd.md`, or `knowledge-base.md`; a defect in them is reported as
  a finding, not fixed.
```

### Dispatching supergoal

Dispatch **one** `PLANNER`-role subagent (the same mechanism the `superagent` supervisor uses for
superplan: resolve `SUPER_MODEL_PLANNER` / `SUPER_EFFORT_PLANNER`, and when either is a full model
id or a non-`inherit` effort use `subagent_type: super-planner`, else the plain mechanism). Its prompt
instructs it to invoke the `superagent:supergoal` skill via the Skill tool with:

```
<GOAL> = <absolute path of meta-plans/<STAMP>-r<N>.md>   --autoconfirm   --slug <project-slug>-r<N>
```

and to return supergoal's complete Final Report verbatim. supermeta parses `**Goal folder:**` and
`**Root plan:**` from it. If the report is missing either line, or supergoal reports it refused (the
key is not `true`, the goal folder already exists, or `I need a goal description`), supermeta writes
nothing to the ledger, moves the meta-plan back out of the project folder into scratch, and reports
the failure verbatim with the scratch path.

### Ledger and commit

Append the ledger row
`| <N> | [[<SUPER_PROJECT_DIRNAME>/<project-folder-basename>/meta-plans/<STAMP>-r<N>]] | [[<goal-folder-path-from-vault-root>]] | - | - | - |`
to `prd.md`. Then A7 with: branch prefix `project/<project-slug>-r<N>-meta`; commit subject
`docs(project): <project-slug> round <N> meta-plan`; PR title `docs(project): <project-slug> r<N>
meta-plan`; PR body `Meta-plan for round <N> written by supermeta; goal folder <goal-folder>.`;
explicit `git add` list: the meta-plan file and `prd.md`. (supergoal has already committed the goal
folder itself under its own A7.)

### Final Report (A8)

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

## `supergoal` — three additive changes

All three are default-preserving: a direct user who passes neither flag sees identical behaviour.

1. **`<GOAL>` may be a file.** If `<GOAL>` names an existing `.md` file, its content is the goal
   description. `goal-directives.md` then opens with `**Source:** [[<vault link to that file>]]`
   (a repo path outside the vault is cited as a plain relative path). The input-gate message is
   unchanged.
2. **`--autoconfirm`.** Honoured only when `SUPER_GOAL_AUTOCONFIRM` resolves to `true`; then step 7
   treats the step-6 self-review as the confirmation, writes `**Confirmation:** auto-confirmed
   (SUPER_GOAL_AUTOCONFIRM=true, --autoconfirm) on <date>` into `goal-directives.md`, and proceeds
   to step 8. When the key is not `true`, the flag is ignored and supergoal reports
   `--autoconfirm ignored: SUPER_GOAL_AUTOCONFIRM is not true` before pausing as today. The key's
   template comment is updated to describe the two-factor rule.
3. **`--slug <slug>`.** Overrides the derived slug (still validated as kebab-case; the
   never-overwrite rule still applies to `<STAMP>-<slug>`).

`argument-hint` becomes `"<goal description | path/to/goal.md> [--autoconfirm] [--slug <slug>]"`.

## `scripts/_evalspec.sh` — shared parser

`prd-lint.sh`'s markdown helpers (`trim`, `strip_ticks`, `section_body`, `table_rows`, `cell`)
move into `scripts/_evalspec.sh`, which both `prd-lint.sh` and `supereval.sh` source. It adds two
readers, both printing one record per line with the ASCII unit separator (`$'\x1f'`) between
fields, bash 3.2 clean:

- `evalspec_env <evaluation.md>` → `setup<US>cwd` (one line).
- `evalspec_checks <evaluation.md>` → command rows as `C<US><id><US><command><US><cwd><US><pass-when><US><timeout-min>`
  and judged rows as `J<US><id><US><objective><US><criteria><US><evidence>`; `\|` inside a cell is
  unescaped to `|`.

`prd-lint-test.sh` must still pass unchanged after the extraction.

## `scripts/supereval.sh` — the command-check runner

```
supereval.sh <project-dir> --repo <primary_root> --commit <sha> --out <results-file>
             [--worktree <dir>] [--keep-worktree] [--max-timeout-min <n>]
```

Behaviour (bash 3.2; sources `_common.sh` and `_evalspec.sh`; `load_superenv "<repo>"`):

1. `--worktree` absent → `git -C <repo> worktree add --detach <mktemp -d> <sha>`; present → use it
   as is (must contain `<sha>` checked out). The worktree is removed on exit unless
   `--keep-worktree`.
2. Read `evalspec_env`. If `setup` is non-empty, run it in `<worktree>/<cwd>` with the ceiling
   timeout; non-zero exit or timeout → every command check is recorded `ERROR setup failed` and the
   script proceeds to write the file (verdict is decided by the skill).
3. For each `C` row, in file order: run `bash -c '<command>'` in `<worktree>/<row cwd>` under
   `min(<row timeout>, --max-timeout-min | SUPER_EVAL_TIMEOUT_MIN)` minutes using the same
   `timeout`/`gtimeout`/uncapped-with-warning fallback `superagent-tick.sh` uses; capture stdout,
   stderr, exit code, wall seconds. Result: `PASS` when `pass-when` holds (`exit <n>` compares the
   exit code; `stdout ~ /<regex>/` runs `grep -E` over captured stdout), `TIMEOUT` on the timeout's
   exit 124, `ERROR` when the command's first word is neither on `PATH` nor a repo path, else `FAIL`.
4. Write `<results-file>` — markdown the skill embeds verbatim:

```
## Environment
- commit: `<sha>` · worktree: `<path>` · setup: `<command>` → <ok | exit <n> | timeout | none>

## Command checks
| Id | Result | Exit | Seconds | Evidence |
|---|---|---|---|---|
| C1 | PASS | 0 | 4 | `<last non-empty stdout/stderr line, 120 chars max, \| escaped>` |
```

   plus, after the table, one fenced block per non-PASS check holding the last 40 lines of its
   combined output (`### C2 output`).
5. Exit 0 when every command check is `PASS`, 1 when any is not, 2 on usage/setup-of-script errors
   (missing project dir, missing `evaluation.md`, `git worktree add` failure). Judged rows are
   ignored by the script (they are listed by `evalspec_checks` for the skill).

## `supereval` — the evaluator

**Invocation:** `superagent:supereval <project-dir> [--commit <sha>] [--round <N>]`
(`argument-hint: "<project-dir> [--commit <sha>] [--round <N>]"`). Runs in the invoking context.
Read-only on source; writes only the project folder.

1. **Inputs.** Same READY/lint refusal as supermeta. `N` defaults to the last ledger row's round;
   `--round` overrides. The ledger row for `N` must exist (supermeta wrote it) — else refuse:
   `supereval: no ledger row for round <N>; run supermeta first`.
2. **Sync.** Apply superloop L5's `sync_main()` on `<primary_root>` (and `sync_vault()` for an
   external vault). `<sha>` defaults to `git -C <primary_root> rev-parse main` after the sync.
3. **Inner loop link.** If the round's goal folder (from the ledger row) has
   `<SUPER_LOOP_STATUS_DIRNAME>/*.md`, record the newest as the row's *Inner loop* cell and note its
   `status:`; a status other than `DONE` is a WARN in the report, not a refusal (the operator may
   evaluate a partial build on purpose).
4. **Command checks.** Run
   `"${CLAUDE_PLUGIN_ROOT}/scripts/supereval.sh" "<project-dir>" --repo "<primary_root>" --commit <sha> --out "$TMPDIR/supereval-<project-slug>-r<N>/results.md" --keep-worktree`
   with `timeout: 600000` (per-check timeouts are inside the script). Keep its exit code.
5. **Judged objectives.** If `evalspec_checks` lists any `J` rows, dispatch **one** read-only
   `EVALUATOR` subagent (resolve `SUPER_MODEL_EVALUATOR` / `SUPER_EFFORT_EVALUATOR`; full id or
   non-`inherit` effort → `subagent_type: super-evaluator`, else plain mechanism; a missing
   definition → "re-run `superagent:init`" and stop). Its prompt contains only: the worktree path,
   the `J` rows verbatim, and the instruction "For each objective, inspect only the evidence paths
   named; answer PASS or FAIL against the written criteria with a two-sentence rationale citing
   file:line; never modify anything." It returns a table `| Id | Result | Rationale |`. No `J` rows
   → the section says `none`.
6. **Report.** Write `eval-reports/<STAMP>-r<N>.md`:

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

   Verdict is `PASS` iff the script exited 0 **and** every judged row is `PASS`. An unavailable
   evaluator (dispatch failed) makes the verdict `FAIL` with the warning naming it — never PASS by
   omission.
7. **Ledger.** Fill row `N`'s *Inner loop* (if found), *Eval report* (`[[<SUPER_PROJECT_DIRNAME>/<project-folder-basename>/eval-reports/<STAMP>-r<N>]]`)
   and *Verdict* (`PASS`/`FAIL`) cells in `prd.md`.
8. **Commit.** A7 with: branch prefix `project/<project-slug>-r<N>-eval`; subject
   `docs(project): <project-slug> round <N> eval <PASS|FAIL>`; PR title
   `docs(project): <project-slug> r<N> eval`; body `Evaluation report for round <N> written by
   supereval; verdict <PASS|FAIL>.`; explicit `git add`: the report and `prd.md`. Remove the kept
   worktree (`git worktree remove --force`) after the commit.
9. **Final Report (A8):**

```
## Supereval complete

**Project:** <project-dir>   **Round:** <N>   **Commit evaluated:** <sha>
**Report:** <path>
**Verdict:** PASS | FAIL (<failing ids>)
**PR:** <url> (merged)
**Commit:** <short-sha> in <vault_root>   (external vault — print this line INSTEAD of the PR line)
**Next:** PASS → the project is complete for this PRD · FAIL → superagent:superdiagnose <project-dir> (Stage 3; until then, read the report and start a new round with supermeta)
```

## `init` and roles

No change to `init`'s role table: `super-meta-planner` and `super-evaluator` definitions are
generated since Stage 1. The Stage 1 template comments on `SUPER_MODEL_META_PLANNER` /
`SUPER_MODEL_EVALUATOR` lose their "(Stage 2)" reservation markers; `SUPER_GOAL_AUTOCONFIRM`'s
comment becomes: `true + supergoal --autoconfirm skips supergoal's step-7 human confirmation
(supermeta's dispatch); either alone does nothing`.

## Testing

**Offline (`scripts/supereval-test.sh`, bash 3.2, no model, no network).** A fixture repo in a
temp dir with a tiny script, plus fixture `evaluation.md` files; each case asserts the script's exit
code and the `Result` cell of named rows in `--out`:

1. all pass (`exit 0` and `stdout ~ /…/` rows) → exit 0, both `PASS`;
2. one failing exit → exit 1, that row `FAIL`, evidence block present;
3. a `sleep 70` row with timeout `1` → `TIMEOUT` (skipped with a note when neither `timeout` nor
   `gtimeout` exists);
4. a command whose binary does not exist → `ERROR`;
5. setup command fails → every row `ERROR setup failed`, exit 1;
6. a `\|` inside a command cell round-trips;
7. judged-only spec (no `C` rows) → exit 0, empty command table, and `evalspec_checks` prints the
   `J` record;
8. `--worktree` pointing at a prepared checkout is used as is and not removed.
Also: `prd-lint-test.sh` still passes after the parser extraction; `bridge-test.sh` and
`vault-external-test.sh` unchanged.

**Acceptance — one manual round on the toy repo (operator checklist, recorded in
`stage2-round-report.md`, gitignored).** The toy repo `$TMPDIR/superprd-smoke` already holds
`vault/projects/2026-09-06-07_18-csv-summariser/` (internal vault, `SUPER_PROTECTED_MAIN=true`).
The operator creates a fresh private GitHub remote by hand (`gh repo create --private
superprd-smoke --source=. --push` from the toy repo). Then, from an interactive session in the toy
repo with the installed plugin at 0.8.0:

1. `superagent:supermeta vault/projects/2026-09-06-07_18-csv-summariser` → a meta-plan, a goal
   folder `vault/<STAMP>-csv-summariser-r1/` merged via PR, and a ledger row 1. Expected: supergoal
   did not pause (auto-confirmed), `goal-directives.md` carries the `**Confirmation:**` and
   `**Source:**` lines.
2. `superagent:superagent-external vault/<STAMP>-csv-summariser-r1/master-plans/<seed>.md
   --interval 5m` and wait for `DONE` (monitor with `superagent-monitor`). Expected: `src/app.py`
   now implements the summariser; pytest passes on `main`.
3. `superagent:supereval vault/projects/2026-09-06-07_18-csv-summariser` → an eval report merged
   via PR whose verdict is `PASS` with C1–C3 all `PASS`, the ledger row completed, and the Final
   Report's `**Next:**` line saying the project is complete.
4. Negative check: edit the toy's `src/app.py` on a throwaway branch to break the usage error, run
   `scripts/supereval.sh` against that commit with `--out`, expect exit 1 with C2 or C3 `FAIL`.

## Compatibility

`supergoal` without the new flags is unchanged. `prd-lint.sh`'s output and exit codes are unchanged
by the parser extraction. No key defaults change. A repo without a project folder never sees either
new skill.

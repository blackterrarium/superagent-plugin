# Final grouped fix report — whole-branch B1–B4

## Status

The canonical source fix is frozen for root-owned package regeneration, fresh focused interpretation,
and one scoped re-review. This implementer made no commit and did not run model CLIs, network calls,
schedulers, live fixtures, package builds, or generated-file updates.

## Changed files

- `skills/superagent/SKILL.md`
- `skills/supergoal/SKILL.md`
- `skills/superplan/SKILL.md`
- `scripts/plan-tree-regression.py`

No other source file was changed by this fix wave.

## Fixes

### B1 — planning results and exhaustion

`superagent` now gives ordinary legacy superplan results explicit state transitions:

- implementation plan → `WAITING FOR RUN`, `plan_exhausted: false`;
- seed/master or sub-master → `WAITING FOR PLAN`, `plan_exhausted: false`;
- exact no-available-task result → `WAITING FOR RUN`, `plan_exhausted: true`;
- not-traversable or missing required plan input → hard-error teardown.

An upfront `WAITING FOR PLAN` selection with no batch, refinement target, or prepared target now runs
C9 directly on the synchronized authoritative tree. Complete becomes DONE with audit evidence;
incomplete must identify and reselect the actual remaining obligation; BLOCKED, including an entirely
dependency-blocked remainder, enters the existing ladder. This path schedules no extra PLANNER merely
to establish exhaustion.

### B2 — execution-entry no-execution results

`superagent` now classifies the executor report before applying delivery-specific be-sure checks. It
synchronizes and reconciles artifacts actually reported, then routes execution-entry
NEEDS-REFINEMENT to `WAITING FOR PLAN` with `planning_operation: refine`, the stage target and root
generation. It does not require a closeout and does not dispatch a second heavy skill in the same
tick. REPLAN-REQUIRED, BLOCKED and other non-success reports retain their decision/recovery routes
without synthetic closeout requirements. Executor `none` is also audited without a closeout gate.

### B3 — publication validation order

`supergoal` keeps the complete prepublication write-out in candidate S1/S2 context through its
explicit path map. Candidate success cannot authorize execution. After the single A7 publication, it
synchronizes the authoritative branch and requires active S1/S2 validation before the success report;
a failure is BLOCKED. Initial stages still require normal preparation before execution.

### B4 — direct nested superplan classification

`superplan` resolves and verifies the unique containing root through parent/tree identity before
reading the planning-mode marker. The supplied sub-master/topic remains the selection scope. A nested
node under an upfront root therefore receives upfront S1/S2 and C8 authority; a node under a true
unmarked legacy root remains incremental. Missing, conflicting or ambiguous root identity is BLOCKED.

## Focused regression coverage

Ten fresh-interpreter scenarios cover the review boundaries:

- legacy implementation, sub-master and exhausted results;
- upfront all-integrated and all-dependency-blocked entry states;
- stale prepared receipt discovered only at executor entry;
- candidate-before-publication and active-after-publication validation;
- direct nested superplan under upfront and true legacy roots.

The validator unit test mutates representative expected fields (`plan_exhausted`, `next_state`,
`closeout_required`, `validation_context`, and nested-root `mode`) to confirm those expectations are
enforced. The root-owned immutable prechange run in `final-boundaries-baseline.json` supplies the RED
evidence for the same ten boundaries.

## Local checks

- `python3 -B scripts/plan-tree-regression.py --self-test` — exit 0; 15 tests; OK.
- focused ten-case `--prompt` render — exit 0; all ten scenarios and requested fields present.
- `git diff --check` — exit 0; no output.
- `find . -type d -name __pycache__ -print` — no output.

Root owns the fresh post-fix interpreter run, package regeneration, broader validation, and scoped
re-review.

## Frozen source hashes

```text
53379e46f0f53937fb4ba6d21196a0a7876cf3d54a45a12f1eb864da64f7dd89  skills/superagent/SKILL.md
af7bba048fb1e3373fafe6965b46ecf630ccfb435a25d14dc332663aa1b661fe  skills/supergoal/SKILL.md
982348429eca1b3de5bbe8b61edc84fe5c6eeb58e9c8b281e70414b5209c6193  skills/superplan/SKILL.md
73a80fa8998ca3f26a0675385101a4b790c2c251d5715b791ba7da9a9304607d  scripts/plan-tree-regression.py
```

Any later change to these files invalidates the hashes and requires the focused interpretation and
scoped re-review to run again.

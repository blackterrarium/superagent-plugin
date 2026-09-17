# Upfront plan tree verification

**Status:** Offline implementation evidence is present; live PT acceptance is INCOMPLETE.
**Implementation base:** `a78820f`
**Plan:** [Implementation plan](../plans/2026-09-16-upfront-plan-tree.md)
**Design:** [Design](../specs/2026-09-16-upfront-plan-tree-design.md)
**Proposed live scope:** [Prepared, not executed](2026-09-16-upfront-plan-tree-live-acceptance.md)

## Evidence levels and verdict rules

This report keeps three evidence levels separate:

1. **Offline artifact/config tests** execute deterministic validators, builders, loaders, and bridge
   argument checks without a model, scheduler, or network.
2. **Fresh interpretation probes** ask a fresh read-only interpreter to apply the canonical skill
   contracts. They test instruction interpretation; they do not prove transport or execution.
3. **Live lifecycle evidence** consists of actual configured role calls plus retained plan trees,
   bridge logs, preparation and delivery receipts, Git history, and operation traces.

`PASS` requires the evidence level the PT requirement calls for. Missing evidence is `INCOMPLETE`;
present evidence that contradicts its expected identity or contract is `FAIL`. Scenario JSON, fake CLI
logs, manifest booleans, prepared fixtures, and empty operation lists cannot satisfy live acceptance.
The evidence validator reports sufficiency; it is not machine proof that a semantic review was good or
that a provider created a claimed log.

## PT-01–PT-11 matrix

| ID | Offline test / retained receipt | Fresh interpretation | Live lifecycle evidence | Current result |
|---|---|---|---|---|
| PT-01 | Draft/publication recovery checks and package suites pass; the validator requires one Git commit containing the root, complete named stage/review artifact set, confirmation, and supermeta evidence. | Task 6 final 69 includes atomic publication and recovery cases. | No actual upfront initial publication or confirmation occurred. | **INCOMPLETE** |
| PT-02 | Stage maturity and bounded-unknown cases are covered by `plan-tree-regression.py`; the validator checks required stage identity, dependency, contract, acceptance, and verification fields in historical blobs. | Task 3 upfront26 and Task 6 final 69 pass. | No live future-stage whole-tree review exists. | **INCOMPLETE** |
| PT-03 | Preparation authority, root/stage/revision/link identity, examined-code existence, exact-byte SHA-256, historical root generation, compatible baseline, and PLAN_REFINER configuration checks pass offline. `plan-tree-e2e.py` self-tests CRLF preservation, later closeout annotation, and a revalidated preparation baseline distinct from later delivery. | Task 3 upfront26 and Task 6 final 69 pass. | No actual PLAN_REFINER dispatch log or preparation receipt exists. | **INCOMPLETE** |
| PT-04 | Dependency, cycle, open/declined provider, stale preparation, execution-entry snapshot, preparation-linked delivery identity, and integration ancestry checks are covered offline. | Task 6 final 69 passes. | No five-stage execution and delivery chain exists. | **INCOMPLETE** |
| PT-05 | Local-detail versus contract-break routing, durable decision evidence, selected-role preflight, and failed-identity checks pass offline. | Task 5 fresh13 and Task 6 final 69 pass. | No actual contract-break decision or REPLANNER call exists. | **INCOMPLETE** |
| PT-06 | Impact closure, stop-at-preserved-contract, retained preparation, whole-tree change, completed-history, and revised/retained disposition checks pass offline. | Task 4 focused probes and Task 6 final 69 pass. | No actual affected-batch publication exists. | **INCOMPLETE** |
| PT-07 | Atomic batch, pending barrier, stale baseline, before/after publication recovery, late closeout, and interrupted trace checks pass offline. | Task 6 final 69 passes. | No interrupted live batch and same-decision resume receipts exist. | **INCOMPLETE** |
| PT-08 | Config21, bridge tests, copied-package tests, and all three package-builder checks passed at the Task 6 source freeze. Native Cursor interpretation passed. The new validator requires copied files with no symlink fallback plus successful role-bridge headers/trailers matching each expected pin. | Task 5 fresh13 and Cursor1 pass. | Neither new role has a real lifecycle dispatch log; the prepared bridged configuration is not a receipt. Pi receives no live claim. | **INCOMPLETE** |
| PT-09 | Legacy traversal, single-leaf repair, C9, and unmarked-root checks remain in the unchanged legacy suite. | Fresh legacy16 passes. | No new live legacy comparison was run; historical legacy evidence is preserved, not relabelled as this fixture. | **INCOMPLETE** |
| PT-10 | External-vault, PRD, copied-package, missing-evidence, partial closeout, and false-completion checks pass offline. The validator checks Git objects and named publication artifacts in both vault layouts. | Task 6 final 69 and legacy16 pass. | No internal/external live fixture publication and recovery pair exists. | **INCOMPLETE** |
| PT-11 | The validator requires bounded trace header/trailer records, contiguous sequence numbers, one event per attributable dispatch, refinement and execution for every delivered stage, and no normal-path post-publication `plan`/`replan`. | Routing and replan semantics pass in fresh probes. | No complete normal/deviation operation trace exists, so a zero-dispatch claim cannot be made. | **INCOMPLETE** |

No PT requirement currently has live `PASS`; there are no recorded PT failures. Live evidence was not
attempted, so the correct aggregate is **0 PASS / 0 FAIL / 11 INCOMPLETE**.

## Current offline evidence

Task 6 froze the canonical skills at `a78820f`. The final complete
[69-case suite](evidence/2026-09-16-upfront-plan-tree/task6-final-all.json) passes, formed without
answer edits from disjoint fresh35/fresh34 runs. Its
[validation output](evidence/2026-09-16-upfront-plan-tree/task6-final-all-validation.log.txt),
[group map](evidence/2026-09-16-upfront-plan-tree/task6-final-groups.json), and
[fix2 source hashes](evidence/2026-09-16-upfront-plan-tree/task6-fix2-source-hashes.json) retain the
raw/evaluated relationship. Fresh
[legacy16](evidence/2026-09-16-upfront-plan-tree/task6-legacy.json) also passes. Task 7 does not edit a
canonical skill, so these interpretation hashes remain current.

Earlier failed and provisional probes remain stored and labelled as failures or in-progress evidence.
They are not counted as passing runs. The final suite separates structural validity from executability
and concrete replay actions from overloaded status labels.

Final offline regression self-tests, configuration, bridge, external-vault, PRD-lint, and copied-package suites all exited 0. Their full outputs are retained as `final-*.log.txt` in the adjacent evidence directory. All three generated-package checks also passed after regeneration. Task 7 receipt-validator review found an identity-validation gap; its correction and covering tests are implemented and await scoped re-review. These offline results do not change live acceptance status.

## Offline evidence validator TDD

`scripts/plan-tree-e2e.py` is an evidence reader. It has no model, network, scheduler, or hidden runtime
database. The manifest schema and trace record format are documented in
[`scripts/README.md`](../../../scripts/README.md#upfront-plan-tree-evidence-validator).

The meaningful RED run was:

```text
python3 scripts/plan-tree-e2e.py --self-test
exit 1 — Ran 8 tests: 3 failures, 0 errors
failing behaviors: corrupted stage revision was not FAIL; historical exact-byte digest was not
validated; wrong role-log pin was not FAIL
```

After implementing artifact, log, trace, and Git checks, the GREEN run was:

```text
python3 scripts/plan-tree-e2e.py --self-test
exit 0 — Ran 19 tests in 5.139s — OK
```

The tests use temporary local Git repositories and clearly synthetic evidence. They cover exact CRLF
bytes with only the Preparation line removed, historical prepared blobs versus later closeout
annotation, corrupt revision, wrong role pin, missing bridge trailer, missing integration object,
interrupted replay trace, missing publication artifact, ignored manifest PASS claims, and the mandatory
synthetic-to-INCOMPLETE downgrade. A focused second RED run (`exit 1`, 19 tests, three failures and one
error) exposed missing per-run Git context plus vacuous empty-inventory acceptance. The final suite adds
distinct real temporary vault repositories for trace/replan context, an empty external publication
inventory case, and an empty operation trace case.

The receipt-identity review fix had a separate RED run: `exit 1`, 27 tests, seven failures. Independent
corruptions of preparation Outcome, historical root path/generation, examined Code commit, stage
Preparation pointer, delivery generation, and delivery Preparation pointer were incorrectly accepted.
After deriving generation from the historical root, resolving the examined baseline separately from
later delivery, and preserving missing-versus-contradictory status, the final synthetic suite ran 31
tests in 10.681s with exit 0. No self-test is live acceptance evidence.

## Live acceptance approval block

The first actual upfront-authoring CLI dispatch did not start: automatic approval review timed out.
The permitted retry was rejected because copied repository skills and fixture content would be sent to
an external model without explicit approval for that disclosure. No alternate CLI or model was used to
bypass the rejection.

The isolated repositories, synthetic goal, configurations, and run schedule are prepared and described
in the [proposed live scope](2026-09-16-upfront-plan-tree-live-acceptance.md). Those files are preparation
only. They are not run receipts and must not be named in a `live` manifest until the configured calls
actually execute and their artifacts are retained.

## Rollout decision

The shipped `SUPER_PLANNING_MODE` remains `incremental`. Upfront planning is available only by explicit
environment or `supergoal --planning-mode upfront` selection. Existing unmarked roots permanently use
legacy incremental behavior. Switching the shipped default requires later disclosure approval, actual
live PT-01–PT-11 evidence, a validator report with no missing or inconsistent evidence, and final review.

Refinement time, replanning time, amendments, retained/revised IDs, and token usage are unknown because
no live run occurred. This report does not invent them.

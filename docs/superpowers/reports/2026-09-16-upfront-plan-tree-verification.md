# Upfront plan tree verification

**Status:** Implementation in progress; acceptance is not yet complete.
**Base:** 45122c2 (implementation branch also carries the approved plan and prior reserved-role configuration).
**Plan:** [Implementation plan](../plans/2026-09-16-upfront-plan-tree.md)
**Design:** [Design](../specs/2026-09-16-upfront-plan-tree-design.md)

## Baseline evidence

- Fresh read-only interpreter of the unmodified canonical skills confirmed root-only publication,
  speculative-code requirements, selection of a consumer after its executed provider's still-open
  PR, return to incremental planning after execution, and single-leaf repair publication.
  [Recorded answers](evidence/2026-09-16-upfront-plan-tree/baseline-interpretation.json).
- Existing real offline bridge/script suite: zero failures.
  [Output](evidence/2026-09-16-upfront-plan-tree/baseline-bridge.log.txt).
- All three package builders passed --check in the isolated checkout before skill implementation.
- A real Codex gpt-5.6-terra / medium bridge process read an isolated probe file successfully.
  This establishes transport availability only, not plan-refinement acceptance.

## Evidence boundaries

Scenario answers demonstrate interpretation of skill contracts. Fake CLI tests verify concrete
loader/bridge argument behavior. Only completed real dispatches with matching artifacts and
integration evidence establish live lifecycle acceptance. No overall PASS is claimed yet.

## Shared contract verification

Task 1 spec and quality review passed. Validator self-tests passed 9/9; a fresh interpreter passed all nine scenarios, including the temporary rollout gate. The original final probe chose correct behavior but used an ambiguous mode label and failed strict validation; both [original](evidence/2026-09-16-upfront-plan-tree/task1-final.json) and [fresh corrected-vocabulary results](evidence/2026-09-16-upfront-plan-tree/task1-final-corrected.json) are retained. The prompt now supplies global output vocabulary without case-specific answers.

## Live acceptance approval block

The first actual upfront-authoring CLI dispatch did not start: automatic approval review timed out. The permitted retry was rejected because copied repository skills and fixture content would be sent to an external model without explicit approval for that disclosure. No alternate CLI or model will bypass that rejection. Offline implementation and verification continue; real lifecycle acceptance remains INCOMPLETE and the shipped mode remains incremental pending acceptance. Earlier generic transport preflights transmitted no lifecycle content and do not establish PT acceptance.

## Upfront authoring and draft recovery

Task 2 spec/quality review passed after correcting invalid-mode handling and explicit incremental markers. Fresh full scenario suite: [18/18 PASS](evidence/2026-09-16-upfront-plan-tree/task2-final.json). Validator self-tests: 9/9. PRD lint and copied coding-loop package suites: zero failures. Generated variants updated. These remain offline/interpretation results; external authoring acceptance is blocked as recorded above.

## Bounded stage preparation

Task 3 spec/quality review passed. Fresh [upfront26](evidence/2026-09-16-upfront-plan-tree/task3-green.json) and [legacy16](evidence/2026-09-16-upfront-plan-tree/task3-legacy.json) interpretations passed; validator self-tests10 passed. Generated packages include superrefine. The temporary C6 upfront execution gate remains until routing is installed; the pre-SDD handler scenario explicitly tests the post-gate contract, not current live execution.

## Coordinated replanning

Task 4 spec/quality review passed after two scoped fix rounds. The first44-case probe had41 matching answers and three protocol/handler mismatches; retained raw evidence is not labelled a passing run. Fresh [scoped3](evidence/2026-09-16-upfront-plan-tree/task4-scoped-final.json), [impact/barrier5](evidence/2026-09-16-upfront-plan-tree/task4-fix1.json), and [request/expanded-impact2](evidence/2026-09-16-upfront-plan-tree/task4-fix2.json) probes passed after their respective corrections. Self-tests10 passed. All3 packages regenerated. Completed-history classification, semantic closure expansion, non-executable pending view, and request-versus-replanner assessment ownership were reviewed explicitly. Full final suites remain scheduled after routing/closeout integration.

## Supervisor routing and role configuration

Task 5 wires PLANNER / PLAN_REFINER / REPLANNER / EXECUTOR selection and selected-role preflight. The prior temporary upfront gate and legacy PLANNER repair fallback are removed. The first13-case routing probe had five observation-field mismatches; its [raw answers](evidence/2026-09-16-upfront-plan-tree/task5-green.json) are retained. The clarified [fresh13 probe](evidence/2026-09-16-upfront-plan-tree/task5-fixed.json) passes. [Config21](evidence/2026-09-16-upfront-plan-tree/task5-config-final.log.txt) and [selftests12](evidence/2026-09-16-upfront-plan-tree/task5-selftest-final.log.txt) pass; the rebuilt [bridge suite](evidence/2026-09-16-upfront-plan-tree/task5-bridge.log.txt) has zero failures. These establish offline argument behavior and instruction interpretation only. Final spec/quality review passed after two fix rounds; the additional [native Cursor scenario](evidence/2026-09-16-upfront-plan-tree/task5-cursor.json) passes. All three generated package checks pass.

## Delivery, closeout, and recovery

Task 6 spec/quality review passed after two production fix rounds and a reviewed test-protocol clarification. The final complete [69-case suite](evidence/2026-09-16-upfront-plan-tree/task6-final-all.json) passes, formed without answer edits from disjoint fresh35/fresh34 groups. The [validation output](evidence/2026-09-16-upfront-plan-tree/task6-final-all-validation.log.txt) and [group map](evidence/2026-09-16-upfront-plan-tree/task6-final-groups.json) record coverage; source hashes are retained in [fix2 snapshot](evidence/2026-09-16-upfront-plan-tree/task6-fix2-source-hashes.json). Earlier failed probes and provisional self-check captures remain explicitly named as such. The tests now separate structural validity from executability and concrete replay actions from overloaded status labels.

Fresh [legacy16](evidence/2026-09-16-upfront-plan-tree/task6-legacy.json) passes. Self-tests14 pass. [External-vault](evidence/2026-09-16-upfront-plan-tree/task6-vault.log.txt), [PRD-lint](evidence/2026-09-16-upfront-plan-tree/task6-prd.log.txt), and [copied-package](evidence/2026-09-16-upfront-plan-tree/task6-package.log.txt) suites report zero failures. All three variants regenerated and checked. Recovery now covers historical execution snapshots, partial-to-delivered report upgrades, no-code discovery, prepublication barriers, and prepared successor re-entry. These are offline/interpretation results; live acceptance remains blocked.

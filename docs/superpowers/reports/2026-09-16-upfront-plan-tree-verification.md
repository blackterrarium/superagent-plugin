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

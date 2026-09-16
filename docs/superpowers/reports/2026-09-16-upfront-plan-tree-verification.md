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

# Whole-branch review — upfront plan tree

**Spec/quality verdict: CHANGES REQUIRED — four Important integration findings, no Critical findings.** Task 7's offline review gate is independently PASS after fix3 (53 tests); live acceptance is **INCOMPLETE**. The shipped incremental default correctly remains unchanged.

Reviewed the complete canonical change against the design, implementation-plan Global Constraints, progress ledger/rulings, and current source at fc2e030: authoring/draft recovery, S1–S5, refiner/replanner, C6–C9 navigation and repair, supervisor/chassis, execution/CI recovery, partial/discovery closeout, config/default translation and package builders. Generated duplication and historical evidence were not re-reviewed as source. Root's 69-case upfront and 16-case legacy interpretation results and final offline/package results are retained evidence; no broad suites or external calls were rerun for this review. The four findings below are direct control-flow/contract contradictions in the production Markdown, not requests for new features.

## Important B1 — restore explicit planning-result and exhausted-tree transitions

Location: `skills/superagent/SKILL.md:578`–`613` and `:653`–`662`.

The rewritten WAITING FOR PLAN branch says ordinary superplan “retains its existing implementation/sub-master/none result parsing,” but deletes the actual parsing/state-update rules. No remaining instruction in superagent ever sets `plan_exhausted: true`. Its only DONE transition still sits behind `if plan_exhausted is true` in the executor-none branch. In addition, upfront selection has handlers for pending batch, refinement, prepared target and blockers, but no handler for C6 `none` when all active stages are integrated.

Concrete failures: (a) a legacy superplan returns an implementation plan or `No available task to plan`; the fresh controller no longer has an explicit next-state assignment, and exhausted loops cannot reach their remaining DONE guard without inventing the removed transition; (b) after the final upfront leaf, the controller sets WAITING FOR PLAN / plan_exhausted false, then finds no pending batch, no refinement target and no prepared target. There is no declared next action even though C9 could prove completion.

The removed baseline rules were: implementation plan → WAITING FOR RUN / false; seed/master → WAITING FOR PLAN / false; superplan none → WAITING FOR RUN / true; not-traversable or missing required plan input → error/teardown. Restore explicit mode-appropriate transitions instead of a reference to absent text. For upfront `none`, run C9 on the synchronized authoritative tree: complete → DONE with its evidence; incomplete → remain/reselect the actual planning/execution obligation; BLOCKED or all remaining work dependency-blocked → existing ladder, never DONE or empty-loop polling. Do not introduce an extra PLANNER dispatch merely to reach completion. Cover fresh legacy implementation/sub-master/none results, upfront all-integrated and all-dependency-blocked supervisor entry states.

## Important B2 — route execution-entry NEEDS-REFINEMENT before requiring closeout evidence

Location: `skills/superagent/SKILL.md:628`–`664`, contrasted with `skills/superrun/SKILL.md:78`–`84` and `:94`–`101`.

Superrun intentionally exits without implementation or closeout when the prepared receipt is missing or needs compatible-baseline revalidation. The supervisor has no NEEDS-REFINEMENT report branch. Before parsing outcomes it unconditionally runs the non-CI be-sure check requiring a leaf closeout; a valid early return therefore looks like missing merge/closeout evidence and can park/escalate or leave RUNNING instead of scheduling PLAN_REFINER.

Concrete trigger: WAITING FOR PLAN selects prepared S01, then unrelated code advances before the next WAITING FOR RUN tick. Executor's required fresh entry check returns NEEDS-REFINEMENT. It must not manufacture a closeout or prepare under EXECUTOR; the controller currently supplies neither valid path back to refinement nor an exemption from the closeout gate.

Handle the no-execution outcomes explicitly before delivery-specific be-sure: synchronize/reconcile any actual reported artifacts, then NEEDS-REFINEMENT → WAITING FOR PLAN with its root/stage and refinement operation, no second heavy dispatch in this tick. Keep REPLAN-REQUIRED/BLOCKED and non-success reports on their existing decision paths without demanding nonexistent closeouts. Require closeout/integration evidence only when a delivery/partial-execution outcome actually claims it. Add a supervisor case for a stale receipt discovered only at executor entry (distinct from pre-dispatch selection tests).

## Important B3 — do not require active publication validation before committing the initial tree

Location: `skills/supergoal/SKILL.md:338`–`340`; active-context contract: `skills/superstage/SKILL.md:23`–`31` and `:125`–`130`.

Step 8 writes the initial files and immediately says to validate the published tree in **active** S1/S2 context. Step 9 is the first commit/merge. Active validation requires all files readable and tracked on the authoritative branch, whereas the newly written tree is not yet committed (and a protected internal vault still needs its docs PR merged). The ordered workflow thus asks the valid initial upfront publication to pass a gate it cannot yet satisfy. A strict skill follower blocks before A7, or must weaken the active-context rule to continue.

Keep write-out/prepublication verification in candidate context through the explicit map, perform the single A7 publication, then synchronize and validate in active context after successful authoritative integration and before the success report. Test both the uncommitted/open-PR prepublication boundary and the committed/merged postpublication boundary; no active result may authorize execution early.

## Important B4 — resolve the containing root before classifying a direct sub-master invocation

Location: `skills/superplan/SKILL.md:38`–`50`; root-mode rule: `skills/superstage/SKILL.md:19`–`55`.

Superplan explicitly accepts a seed/master/**sub-master** path, but the new mode gate reads the marker on that input and preserves the legacy flow when it is absent. Only the root carries the mandatory upfront marker. An ordinary unmarked sub-master inside an upfront goal is consequently classified as legacy when invoked directly, bypassing the root's upfront graph/barrier gate. For example, `superplan <upfront-goal/sub-master.md>` with a missing active child link can fill that gap incrementally instead of reporting broken publication and requiring the adopted repair path; an explicit TOPIC can likewise enter ordinary authoring under the wrong role.

Resolve the actual containing root using parent/tree identity before mode selection, then retain the caller's subtree/topic as selection scope. Apply that root's S1/S2/C8 authority consistently; an unmarked true root remains permanently incremental. Missing/ambiguous root identity should fail clearly rather than treating a known nested upfront node as an independent legacy root. Add direct nested-sub-master cases under upfront and truly legacy roots. This is enforcement of the existing root-marker contract, not a legacy migration feature.

## Coverage and limits

The reviewed source otherwise preserves the central design: complete contract-level initial trees, bounded refinement without commitment edits, dependency-aware semantic replanning with retained boundaries, atomic generation publication, completed-history preservation, separately resolved refiner/replanner model/effort pins, no executor planning, authoritative C8 replay/barriers, historical exact-byte preparation identity, and non-consumable partial closeout with stable report identity. Native/bridged packaging paths remain distinct, and the runtime skills are unchanged by Task 7's validator fixes.

Fix these four control-flow findings together, regenerate the three distributions, run focused interpretation scenarios for the affected entry/result boundaries and relevant existing checks, then request scoped re-review. Do not treat old 69/16 source-hash evidence as covering altered runtime instructions; retain it and record the new focused evidence with new hashes.

The live fixture has not executed. Automatic approval review rejected disclosure of copied skills/fixture content to the external model, so there is no live lifecycle or transport-acceptance claim here. The final live PT verdict remains **0 PASS / 0 FAIL / 11 INCOMPLETE** pending approval and actual execution; offline review cannot replace it.

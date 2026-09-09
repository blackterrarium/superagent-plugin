# Acceptance-coverage process fix — fresh-session handoff

**Date:** 2026-09-08 · **Status:** implementation authorized; handoff only, no process fix implemented here
**Start in:** `/Users/eugene/src/superagent-plugin`

## Task and authorization

The user approved fixing the process after discussing the recommended sequence: preserve the
known failed round; introduce explicit requirement-to-assertion coverage verification; validate
with blind negative/positive/holdout probes; then run scheduled correction and independent
evaluation; finally ensure actual blocked-replan recovery coverage. Their last instruction was:

> Ok. Do the process fix. But write a handoff so that it can be done properly in a fresh session.

This session interpreted that as preparing the implementation handoff, not implementing the fix
in the already-used evaluation context. No source skill, generated runtime, test, acceptance
input, installation, scheduler, toy code or GitHub PR was changed for this handoff.

Suggested fresh-session request:

> Continue from docs/superpowers/handoffs/2026-09-08-acceptance-coverage-process-fix.md.
> Implement the narrow acceptance-coverage process fix, prove it with blind controls, then
> validate scheduled correction and the remaining real blocked-replan recovery path.
> Preserve both historical FAIL rounds and distinguish every acceptance claim.

The latest approved course supersedes the earlier suggestion to immediately provision a
failing-parser fixture. Start with the process fix and blind validation, not another full run
or a manual patch to the missing tests on toy main. Follow applicable implementation, skill
authoring, review, worktree and installation workflows in the fresh session. Ask only for a
material new scope/authority decision; do not treat this handoff as proof that any validation passed.

## Read first

1. [Fresh full-stack restart report](../reports/2026-09-08-mdtoc-full-stack-restart.md).
2. This handoff's evidence paths below: frozen evaluation, implementation plan, test assertions,
   both independent evaluator responses and its operator clarification.
3. [Repaired lifecycle handoff](2026-09-07-mdtoc-repaired-eval-handoff.md), especially Phase 4.
4. Relevant canonical skills and their currently generated/installed Codex equivalents. Use
   actual repository instructions and available skill catalog; do not edit a dependency cache.

## Known failure and causal boundary

The frozen J3 minimum required BOTH fence characters to have shorter, mismatched-character,
non-whitespace-suffixed and valid-sufficient closer cases. The implementation plan also explicitly
required that matrix. The implemented test covered all four for backticks, but only a valid
closer for tildes. The missing cases are assertions rejecting a too-short tilde closer, a
backtick closer while in a tilde fence, and a tilde closer followed by non-whitespace text.

This is an implementation coverage omission and a failure of acceptance review to detect it,
not demonstrated incorrect parser behavior. All 23 existing tests and command checks C0–C8
passed. Task/whole-branch reviews accepted the work. The independent evaluator initially said
J3 PASS too; after the operator asked it to map the already-written requirement separately for
each character, the SAME evaluator corrected J3 to FAIL. That coached correction is evidence
of the gap, not a successful blind test of review reliability.

Do not claim the requirement was absent from the plan, or that adding more reviewers is the
demonstrated solution. The hypothesis to validate is that atomic case accounting, assertion
inspection, and complete authoritative context make the existing gates materially stronger.

### Binding-context transport gap

Canonical `skills/supereval/SKILL.md` Step 6 currently says the evaluator prompt contains ONLY
the kept worktree path, verbatim J rows and one grading sentence. The frozen evaluation also
has binding Contract notes: minimum cases, evidence paths and plan-ordering requirements.
The operator supplied their location and external evidence bindings as a documented transport
deviation. The initial PASS still occurred, so context delivery alone is not a proven fix.
Resolve BOTH faithful context delivery and case-by-case verification. Do not merely add
"be thorough", teach the prompt about tilde fences, or drop the binding notes from acceptance.

## State and preserved evidence

These are last observed facts; recheck before any mutation or scheduler launch.

| Item | Value |
|---|---|
| Plugin source before this handoff | local main `bf4a920` (portable report); tested source `790a86b`; lifecycle repair ancestor `1852780` |
| Tested installed Codex package | `/Users/eugene/.codex/plugins/cache/superagent/superagent/0.8.1+codex.20260908005203` |
| Toy code repo | `/Users/eugene/src/mdtoc-loop-test`, clean main `aaf0a84e144058a53ba8996db6289127764db2ba` |
| Toy remote | private `blackterrarium/mdtoc-loop-test` |
| Code implementation | PR #2 merged as `22763e18179232283a12c8d068a30aa162075572` |
| README | PR #3 merged as `aaf0a84e144058a53ba8996db6289127764db2ba` |
| External vault | `/Users/eugene/superagent-vaults/mdtoc-loop-test`, own clean main at `07854c7`, no remote |
| Fresh project | `projects/2026-09-08-01_12-mdtoc-lifecycle-repair` under vault |
| Fresh goal | `2026-09-08-01_27-mdtoc-lifecycle-repair-r1` under vault |
| Fresh root | `master-plans/2026-09-08-01_27-mdtoc-lifecycle-repair-r1.md` under goal |
| Frozen inputs commit | vault `dee57b8e88f57616a89fbfd6010ef629e4f9a907` (PRD later changed only for ledger) |
| Failing independent evaluation | project `eval-reports/2026-09-08-04_13-r1.md`, report/ledger commit `3cc0a04` |
| Durable evidence | project `operator-evidence/`, runtime/evaluator archive commit `07854c7` |
| Fresh scheduler | slug `mdtoc-lifecycle-20260908-0124`; DONE iteration 6, timer/tick inactive, no lock |
| Fresh loop | goal `loop-status/2026-09-07-mdtoc-lifecycle-20260908-0124.md` |
| Old historical failed PR | #1 OPEN, unmerged at `db1d502d8ea38d7a7446aa89f22cdcbd66e99adc` |
| Old historical worktree | `/Users/eugene/src/mdtoc-loop-test-worktrees/mdtoc-r1-complete-cli`, clean at that head |
| Old historical project/goal | vault `projects/2026-09-07-21_30-mdtoc` and `2026-09-07-21_37-mdtoc-r1` |

Specific evidence to inspect:

- New project's `evaluation.md:35`: per-character minimum; J3 row and remaining Contract notes.
- New goal's `plans/2026-09-08-02_00-build-bounded-mdtoc-cli.md:755`: the plan required all cells.
- Toy `tests/test_transform.py:95`, especially line 99: actual incomplete matrix.
- Project `operator-evidence/evaluator-initial.md`: initial response plus the exact clarification.
- Project `operator-evidence/evaluator-final.md`: final PASS/PASS/FAIL table.
- Project `operator-evidence/operator-eval-receipt.md`, `results.md`, and `runtime/`: actual
  commands, role receipts, wrapper reports, six state snapshots, PR/closeout/audit evidence.

Both historical verdicts remain FAIL. Do not edit their frozen contracts, rewrite reports or
ledgers, reopen their completed trees, merge PR #1, or reset main to recreate a failure.
New probes and live rounds need new identities. A later PASS does not relabel either old FAIL.

Plugin checkout has a pre-existing dirty generated Codex manifest (cachebuster/formatting).
Unrelated untracked paths include `codex-smoke-report.md`, `html-docs/`, and the old RCA/operator
handoffs. Preserve them; explicit staging only. `stage2-round-report.md` is an ignored local
chronology, not the primary report. No plugin push was performed in the evaluation session.

## Narrow process design to implement

1. **Atomic acceptance cases.** Decompose compound requirements into the explicitly required
   cases/dimensions without inventing a Cartesian product the source never required. Preserve
   source clause references and stable case identities. Here the source explicitly requires
   the two-character/four-condition matrix; this is an example, not a hardcoded plugin rule.
2. **Requirement-to-assertion evidence.** For each case record authoritative requirement, exact
   test/subtest identifier, distinguishing input, assertion location and meaning, and execution
   evidence tied to the evaluated revision. A case may share a parameterized test. A test name,
   input occurrence, count, prose claim or merely green suite is not proof of its assertion.
3. **Blocking completeness.** Missing or non-distinguishing evidence prevents acceptance even
   if command checks are green. Route the concrete finding through existing review/fix/escalation
   mechanisms. Preserve review/CI/model policies; do not change them to force a result.
4. **Independent verification.** Reviewers validate implementer mappings against source rather
   than rubber-stamp them. The evaluator independently derives required cases from the frozen
   contract, including binding notes/references, and inspects committed assertions. Do not feed
   it prior verdicts, expected answers or the implementer's mapping as authoritative truth.
5. **Faithful context.** Define deterministic, bounded delivery of binding acceptance text and
   named evidence roots. Missing/unresolvable required evidence must not become silent PASS.
   Keep evaluation read-only, one evaluator per normal supereval invocation, and existing report
   aggregation semantics. Preserve literal acceptance text and record any contract amendments.
6. **Separate claims.** Merged, existing-tests-green, acceptance-complete and lifecycle-recovery
   are different outcomes. Do not turn C9 into an unscoped new product evaluator or make
   supereval silently execute repairs. Any correction is a separate authorized workflow.

Likely owning surfaces (inspect before choosing the minimal patch):

- `skills/superauthor/SKILL.md`: authoring evidence/coverage standard.
- `skills/superrun/SKILL.md`: task dispatch context, spec/whole-branch gates, finding routing.
- `skills/supereval/SKILL.md`: complete evidence packet, independent mapping, graded output.
- `skills/superprd/SKILL.md` / `skills/supermeta/SKILL.md` / `skills/superplan/SKILL.md` only if
  needed to keep bindings/cases consistent across creation, propagation and repair.
- Owned templates/helpers/tests only where a mechanical contract needs enforcement. Do not
  modify installed third-party superpowers skills to carry a plugin-local requirement.

Edit canonical sources, regenerate supported builds through repository builders, and check
generated parity. Prefer an auditable evidence artifact with concise final J rationales over
burying the whole case matrix in an unstructured chat response. Do not add a new schema or
parser casually: if needed, document compatibility and test its actual consumers.

## Validation sequence — freeze expectations before measuring

### A. Deterministic tests and review

Inspect existing helper tests and add focused regression tests for any new mechanical behavior
(case/evidence transport, missing context, gating, generated parity). Existing relevant commands
include `bash scripts/supereval-test.sh`, `bash scripts/prd-lint-test.sh`,
`bash scripts/coding-loop-package-test.sh`, `bash scripts/bridge-test.sh`,
`bash scripts/vault-external-test.sh`, and all three build scripts with `--check`.
Select by actual changes and run the applicable broader regression set; don't claim unrun tests.
The old dirty Codex cachebuster caused only a manifest parity exception last time; isolate and
record it, don't discard the user's edit to hide the exception. Obtain independent code/skill
review before integration. Static text grep is not live model-behavior validation.

### B. Blind behavior probes before another full scheduled run

Prepare isolated snapshots and an operator-only answer key, freeze their hashes, prompts and
pass criteria before dispatch, and retain raw first responses. Minimum probe set:

| Snapshot | Required first-response behavior |
|---|---|
| Original `aaf0a84` suite + original complete contract | Reject J3 and independently identify the missing tilde cases |
| Separate corrected copy with all required assertions and green execution evidence | Accept the satisfied criteria; do not invent requirements or reject everything |
| Different controlled omission from another explicit requirement | Identify that specific omission without being coached toward fences |

The corrected copy is a control fixture, not a repair merged to toy main. Reproduce baseline
behavior on the old process and compare against the changed process under matched model/effort,
input and evidence conditions; report actual baseline outcomes even if a fresh baseline catches
the omission this time. Exercise both implementation-review and evaluator consumers. Use fresh
isolated contexts for each independent judgment, configured role pins and read-only scope.

BLINDNESS: do NOT pass this handoff, the RCA, evaluator answers, corrective diff, expected verdict,
descriptive negative/positive snapshot names, or the operator answer key to subjects. Give them
only the process under test, neutral snapshot identity, full authoritative contract and allowed
evidence. Do not let broad host searches expose adjacent answer-key/history files; define and
enforce evidence boundaries with the available isolation tools. Keep the holdout out of the
process prompts and assess accidental cue leakage. An identical model with a fresh context is
still not a statistical guarantee of reliability: predeclare repeats, publish all results, and
report the sample size/false-accept/false-reject counts rather than claiming universal reliability.

Acceptance requires correct first responses on all frozen required controls. A targeted follow-up
can diagnose a failure but cannot convert that attempt into blind PASS. If the process changes
after seeing failures, record the iteration and rerun controls with new fresh contexts; use a
fresh holdout for a new generalization claim. Do not simply regrade saved JSON.

### C. Install and run scheduled correction

Only after process/probe gates pass, integrate the plugin fix with normal repository discipline,
regenerate and install the local Codex build using the supported refresh flow, and verify actual
runtime bytes/role resolution. Record source SHA, cachebuster, installed path and checksums;
start a fresh driver context if needed. No global credential/config changes merely to run probes.

Create a NEW scoped correction project/goal from actual synchronized toy main. Its approved
objective is closing the original coverage requirement, not adding product features. Preserve
the original contract by reference/copy with provenance and a new ledger; don't overwrite the
failed round. Let the improved review workflow independently locate the gap and require the
scheduled implementer to add meaningful tests. No operator hints naming the omission may be
counted as autonomous detection. Record any necessary intervention honestly.

Use a unique launchd slug and real scheduled ticks, normal reviews and code PR merge. Evaluate
the new synchronized main with independent supereval, verify the tested merge SHA is on main,
and check actual timer inactive/tick inactive/lock absent after the wrapper exits. Save durable
role receipts, case mappings, execution evidence, review findings, decisions and reports.
No parser edit is justified unless the new tests expose a real behavior defect.

### D. Complete the separate blocked-replan lifecycle obligation

An ordinary review fix before closeout does NOT demonstrate C8 recovery. If C does not naturally
produce a real blocked closed-out leaf and adopted re-plan, use the controlled scenario rules in
the repaired lifecycle handoff, with fresh goal/branch/PR identities. Freeze its design/checks
before launch. Failed code stays on the fixture branch; never downgrade main or touch old PR #1.

Required chain: real open/unmerged blocked PR + tracked closeout → actual panel/adopted decision
→ supervisor commits C8 repair record/tree before ready state → fresh scheduled planner reads
persisted request → new active successor with predecessor/PR disposition → scheduled execution,
review/test gates and integration → C9 audit → independent evaluation PASS → actual disarm.
Do not pre-author repair requested state, hand-write the successor, manually tick, or treat a
valid alternative panel disposition as evidence of re-plan. Supported user-answer recovery is
ASSISTED, not autonomous panel PASS. Follow host monitoring/approval policies for any intervention.

## Deliverables and completion rubric

- Reviewed canonical process change, regenerated builds, applicable deterministic test results.
- Portable diagnosis/design and blind-probe report with exact versions, isolated inputs, prompts,
  all responses, expected-vs-actual tables, first-response outcomes and limitations.
- New scheduled correction report: relevant PRs/SHAs, review correction evidence, independent
  C/J verdict, and real scheduler teardown. Both old FAIL reports remain immutable.
- Actual blocked-replan report with every boundary above, or an honest distinct non-PASS result.
- Durable raw evidence outside temporary directories, explicit commits, no unrelated staging.

Report separately: immediate coverage correction; blind process detection; scheduled correction;
blocked-replan recovery; preserved historical FAILs; harness/timeout limitations. Successful
commands, a green implementation, or self-disarm alone cannot establish the other claims.
The host previously had no timeout/gtimeout; recheck and never claim enforced timeouts if absent.
No native Claude/Pi acceptance claim follows from Codex tests or generated parity.

At handoff completion: no blind probe, process implementation, corrected control, new correction
round or Phase 4 fixture has been created by this handoff-writing turn. The next session starts
with the evidence and approved course above, not with an asserted fix.

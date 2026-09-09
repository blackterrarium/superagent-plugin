# Coding loop Stage 3 — automatic diagnosis and repair

**Date:** 2026-09-09 · **Status:** APPROVED · **Target release:** 0.9.0

**Sources:** [approved umbrella design](2026-09-05-coding-loop-design.md),
[Stage 2 design](2026-09-06-coding-loop-stage2-design.md),
[acceptance workflow validation](../reports/2026-09-09-prd-coverage-workflow.md).
Author direction this session: proceed to Stage 3; require live acceptance on **Claude,
Codex and Pi**. This replaces both the original Claude-only verification scope and the
briefly selected Codex-first scope. The author approved this written design with “approved.” on 2026-09-09. No Stage 3 code or live execution has begun.

## Outcome and scope

Given an author-approved READY project, an external scheduler drives planning, the existing
inner implementation loop, evaluation and diagnosis until acceptance passes or the loop
parks with an actionable reason. The outer loop does not edit product code or weaken the
agreement. Every verdict and repair is tied to a specific round and source revision.

Keep the approved architecture: `supercode` is a second consumer of `superloop`, sharing
scheduler, locking, sync and notification infrastructure with `superagent`. A project mode
inside `superagent` would couple the supervisors; a standalone shell orchestrator would
duplicate their lifecycle machinery. Neither alternative is selected.

Deliver three skills (`superdiagnose`, `supercode`, `supercode-external`), shared lifecycle
extensions, operator visibility, generated package updates and acceptance tests. Retain
existing standalone goal behavior. No parallel project rounds, shared inner loop, automatic
specification changes, attended outer driver or statistical reliability study is included.
Cursor receives generated compatibility checks, but is not a required live acceptance target.

## Component boundaries

- **superdiagnose:** a DIAGNOSER-role worker reads one failed round and writes a diagnosis.
  It never implements a repair. The supervisor dispatches that worker once; invoking the
  skill inside it does not create another diagnoser.
- **supercode:** the SUPERVISOR tick reconciles persisted state and performs at most one
  expensive operation: META_PLANNER/supermeta, supereval (with its own EVALUATOR), or
  DIAGNOSER/superdiagnose. Launching an already planned inner loop is a separate tick action.
- **supercode-external:** validates a project, bootstraps or resumes its outer state and
  calls the shared launcher with `--supervisor supercode`.
- **Shared shell infrastructure:** selects an allowlisted supervisor, performs cheap parked
  gates, preserves overlap protection and reports lifecycle state. Planning and diagnosis
  remain skill work; shell code validates artifact identities and transitions.
- **Existing inner loop:** exclusively owns implementation, delivery review and integration.
  Its DONE means its plan tree is closed, not that project acceptance passed.

Role pins and bridge rules follow existing configuration precedence. Each native role uses
an isolated context. A supervisor must be native to the selected harness; foreign worker
roles use existing bridges. Live acceptance below uses native roles within each harness so
cross-harness routing cannot disguise a missing implementation.

## Identity, inputs and durable state

Add an allowlisted `supervisor` identity (`superagent` or `supercode`) to scheduler
registration and new state files. Absent identity means legacy `superagent`; conflicting
registration/state identities refuse dispatch. Do not accept arbitrary skill paths.

For `supercode`, launcher input is a project directory, not a fabricated PLAN.md. Resolve
primary checkout and physical vault roots with existing helpers. A project must be contained
in the configured vault, have READY inputs, and pass PRD lint. External vaults must be their
own Git repositories. State lives in that project's ignored `loop-status/` directory.

Retain common status, driver, iteration, prior_status, pending-decision and log fields.
Project-specific fields are `project`, `round`, `meta_plan`, `inner_loop`, `inner_slug`,
`last_eval`, `last_diagnosis`, `evaluated_commit`, `agreement_revision` and `operation`.
Paths inside the primary checkout are repo-relative; external vault paths are absolute.
The project field never masquerades as `master_plan`. Round counts project rounds;
iteration remains the scheduler tick counter.

`operation` records phase, round, source identities and intended artifact paths before a
worker starts. Its durable record supports reconciliation after a crash; it is not evidence
that work succeeded. Stage 3 adds optional explicit round/output targeting to supermeta and
supereval where needed, preserving their existing manual defaults. Meta planning must record
its intended goal identity before scaffold dispatch, so a committed goal can be recovered
after a crash without creating another one. Interrupted scratch/uncommitted work is not
silently treated as integrated output.

The acceptance fingerprint covers requirements, constraints, locked decisions, evaluation,
knowledge-base inputs and referenced binding text. Exclude only the PRD's mutable iteration
ledger. Record code and vault commits separately. A changed agreement parks the loop for
explicit author adoption; a changed ledger alone does not invalidate acceptance.

## State transitions and recovery

| Ready/parked state | Action | Verified next state |
|---|---|---|
| WAITING FOR META-PLAN | Reconcile or dispatch supermeta for the selected round | WAITING FOR BUILD |
| WAITING FOR BUILD | Idempotently launch the recorded goal through the inner launcher | BUILDING |
| BUILDING | Shell-only check of the exact recorded inner loop | Remain BUILDING, or WAITING FOR EVAL when inner DONE is verified |
| WAITING FOR EVAL | Capture synced code SHA; reconcile or run supereval on that SHA | DONE on PASS; WAITING FOR DIAGNOSIS on FAIL |
| WAITING FOR DIAGNOSIS | Reconcile or dispatch diagnosis of that exact failed report | Next round's WAITING FOR META-PLAN, or WAITING FOR INPUT |
| WAITING FOR INPUT | Wait for an operator answer; validate the proposed resume action | Stored valid resume state, or remain parked with explanation |
| DONE | No new work; disarm the outer timer through existing lifecycle behavior | DONE |

`WAITING FOR BUILD` is an explicit addition to the umbrella sketch: it separates committed
planning from scheduler side effects and makes a launch interrupted before/after registration
recoverable. Transients are META-PLANNING, EVALUATING and DIAGNOSING. On restart, reconcile
matching committed artifacts before returning to the corresponding ready state. Never infer
success from a worker's message or a timestamp alone. Multiple conflicting matches park for
input. Repeated dispatch failure uses the existing escalation policy rather than silent
infinite retries; author-only specification decisions bypass autonomous resolution.

The BUILDING gate verifies the inner file belongs to the recorded goal, project round and
repository. Active or queued inner work causes a cheap exit without a model session. An inner
WAITING FOR INPUT stays parked and directs the operator to the inner decision; do not send a
second notification. A missing, malformed or mismatched inner identity is an actionable outer
input condition, never DONE. A disarmed unfinished inner loop must be visible as stopped;
ordinary outer ticks do not silently re-arm an operator-stopped inner loop.

Gate writes and reconciliation use the existing per-loop lock and re-read state after lock
acquisition. A cheap read-only no-op needs no write. A stale pre-lock observation cannot
advance state. Extend transient-exit checking and crash-recovery mappings for all outer
transients without changing the live-peer exemption used by the inner loop.

## Diagnosis and repair contract

Input is one final FAIL report, its evaluated code SHA, full approved agreement and binding
sources, command/J results, AC evidence, and that round's plans/reports/findings. Resolve
sources before dispatch and preserve their separate revisions. Old evaluator answers from
other rounds are not authority for current acceptance.

Write `diagnoses/<STAMP>-r<N>.md` with FINAL status, related report, round, code/agreement
revisions, and a per-problem table: failing C/J IDs and applicable AC IDs, observed evidence
with file/line, cause, confidence, classification and bounded repair guidance. Include an
explicit disposition: REPAIR or AUTHOR INPUT. Missing evidence is recorded as a limitation,
not filled with speculation.

Use the umbrella's implementation-defect, plan-gap and PRD/evaluation-defect classes. Add
**execution/evidence failure** for unavailable tools, missing context, failed dispatch or
untrustworthy receipts: these do not establish a product defect. For this release they park
for operator action rather than consuming repeated product repair rounds. Mixed findings
park if any requires an author or unresolved environment/evidence decision.

A missing required assertion is a delivery defect even when product behavior and commands
pass. Guidance may require the missing assertion because it is already in the agreement;
it may not invent new acceptance scope. Specification defects always require author input,
never an automatic change to prd.md, evaluation.md or binding requirements. supermeta carries
REPAIR guidance forward with all original obligations intact.

External-vault reports commit directly to that vault under A7; internal-vault reports use
the existing PR workflow. The supervisor verifies integration before advancing. The current
ledger schema remains: diagnosis is linked from state and by its round/report metadata.

## Completion, stopping and operator control

DONE requires a final report for the selected round and code SHA, available binding context,
all declared commands passing, every required J result present and PASS, matching agreement
fingerprint and an integrated report/ledger. Manual command-only projects retain their
explicit semantics; a missing J result never becomes a command-only exemption.

`SUPER_CODE_MAX_ITERATIONS` limits created project rounds, not ticks or transport attempts.
Validate it as a positive integer. A PASS on the final allowed round completes normally;
a FAIL may be diagnosed, but no next round is created beyond the limit. Park with the failed
report and diagnosis. Increasing the limit requires explicit operator action before resume.

Monitor text/JSON identify supervisor, project, round, inner slug/status, last verdict and
pending decision owner. Existing fields remain compatible. Extend stop and force-stop
identity resolution to accept project input/registered slugs while preserving plan input.
Stopping an outer registration affects only that registration and clearly reports any
still-running inner registration and its stop command. It never implies the child was killed.
Operators can stop the two registrations independently with existing drain/hard semantics.
Force recovery reconciles the selected phase; it cannot map every outer transient to the
inner loop's WAITING FOR RUN. Preserve both state files and committed artifacts on stop.

## Acceptance requirements

| ID | Required result | Evidence |
|---|---|---|
| S3-AC1 | Legacy goal launch, tick, stop, answer and force recovery retain behavior; invalid supervisor or identity conflict refuses before model dispatch | Deterministic regression tests with recorded invocations |
| S3-AC2 | Outer project identity resolves correctly for internal/external vaults and linked worktrees; a second launch reuses the same outer loop | Fixture roots, state and registration assertions |
| S3-AC3 | BUILDING uses no model call until the correct inner DONE; pending/stopped/missing/mismatched inner states cannot yield acceptance | Fake-harness call counts and state assertions |
| S3-AC4 | A restart at each phase side-effect boundary creates no duplicate round, goal, inner registration, report or ledger row | Fault injection before/after worker commit and registration; explicit artifact counts |
| S3-AC5 | Diagnosis distinguishes implementation, plan, specification and execution/evidence failures; approved missing assertions are repairable, new requirements are not adopted | Written cases with per-check/AC evidence and expected dispositions |
| S3-AC6 | Missing J/context, wrong revision, conflicting output or unapproved agreement change cannot produce DONE | Deterministic negative cases and final-state assertions |
| S3-AC7 | Round limit, author-input resume, locks, drain, hard stop and transient recovery work for the outer loop; child status remains visible | Lifecycle tests and separate outer/inner state checks |
| S3-AC8 | Claude completes a real scheduler-driven failed round, diagnosis, implemented repair and passing evaluation without inter-round human orchestration | Native dispatch receipts, code/vault SHAs, review/integration evidence, scheduler/state history |
| S3-AC9 | Codex completes the same live contract | Same evidence as S3-AC8, reported independently |
| S3-AC10 | Pi completes the same live contract | Same evidence as S3-AC8, reported independently |
| S3-AC11 | All three live runs preserve the approved agreement, stop at PASS and leave no active test timers or child processes after cleanup | Before/after hashes, verdict/ledger checks and scheduler cleanup receipts |
| S3-AC12 | Canonical and generated Claude/Codex/Pi/Cursor artifacts stay aligned and packaged helpers resolve | Existing build parity/package checks extended for Stage 3 |

Use deterministic tests for failure/recovery combinations; test actual external integration
with a separately isolated run on each required harness. Live runs must start from the same
approved failing baseline and agreement. The baseline contains a controlled deliverable defect;
the real round-one evaluator must observe FAIL. The test controller must not substitute a
fabricated verdict, change acceptance between rounds, supply the repair commit, or weaken
implementation review. Repair must be produced through the normal inner implementation flow.
The specific fixture and first-round failure mechanism require a reviewable protocol before
live execution; if round one unexpectedly passes or protocol integrity fails, record an invalid
run rather than quietly introducing a new defect. Preserve every attempt.

The existing Stage 1/2 smoke harness synthesizes approval and supplies implementation commits;
it cannot be reused unchanged as this live acceptance authority. Require an actual approved
fixture agreement, real scheduler execution, normal review/integration receipts and explicit
model/effort routing per harness. Authentication or provider failures leave that harness
INCOMPLETE; they cannot be waived by another harness's PASS. All three must pass before claiming
Stage 3 live acceptance complete.

Each live run needs a concrete manifest specifying disposable code/vault/remote/scheduler
identities, initial defect and required failure, model pins, dispatch/time ceilings, retries,
approval provenance, evidence paths and cleanup. Approve that concrete run manifest before
arming it; this design sets acceptance scope, not an unbounded runtime budget. No existing
private production/toy state or historical cohort is used. Deterministic scheduler tests cover
launchd and systemd behavior; live results name the OS actually exercised, without claiming
untested operating systems passed.

## Implementation sequence and review boundaries

1. Diagnosis format, skill and source/acceptance transport; deterministic diagnosis contract cases.
2. Shared supervisor identity, project launch/state, recovery helpers and lifecycle regressions.
3. Outer supervisor, worker reconciliation, BUILDING gate and monitor/control integration.
4. Generated package parity, deterministic full-loop/fault tests and disposable live harness.
5. Reviewed live manifests; Claude, Codex and Pi acceptance runs; release evidence and 0.9.0.

Keep each change reviewable and default-preserving. The detailed implementation plan will name
exact helpers, test commands and per-task ownership for these acceptance rows. Version promotion
and claims of completed Stage 3 follow all required evidence, not merely the existence of skills.

## Review status

This approved design preserves the previously approved shared-chassis architecture. Approved
Stage 3 details include the explicit launch-ready state, execution/evidence diagnosis class, independent
outer/inner stop semantics and the all-three-harness live gate requested in this conversation.
Self-review checked state recovery, artifact ownership, agreement integrity, test scope and
legacy defaults. Next step: the implementation plan. No runtime artifacts,
schedulers, implementation code or additional model workers were created while drafting.

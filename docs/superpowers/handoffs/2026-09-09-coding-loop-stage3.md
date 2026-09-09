# Stage 3 implementation handoff

Date: 2026-09-09. Status: design approved; implementation plan written; implementation not started.

The user requested Stage 3, ultimately required acceptance on **Claude, Codex and Pi**, and
approved the written design with “approved.”. Preserve that final scope; Codex-first and the
old Claude-only roadmap are superseded. No model workers or schedulers were launched during
this planning turn.

Read the [approved design](../specs/2026-09-09-coding-loop-stage3-design.md) and
[nine-task implementation plan](../plans/2026-09-09-coding-loop-stage3.md). Start with Task 1
in an isolated worktree using subagent-driven-development or executing-plans. Carry the full
spec, global constraints, source revision and assigned acceptance rows into each task packet.
Do not report Stage 3 complete until all required live harnesses and cleanup pass.

The new supervisor shares existing infrastructure. Critical boundaries are durable operation
identity, committed-evidence reconciliation, an explicit WAITING FOR BUILD state, no model
session while waiting for the inner loop, fail-closed evaluation and author-only specification
changes. Outer and inner registrations are stopped independently and clearly identified.

Tasks 1–8 implement and test offline. Task 9 prepares an actual bounded live manifest for
approval before arming anything. The proposed known-defective round-one baseline adoption is
a live-protocol decision to review concretely, not an already approved fixture or permission
to fabricate a goal closeout. Real first evaluation must FAIL; actual inner-loop work must
produce the reviewed repair and subsequent PASS. Preserve all attempted outcomes.

Planning verification checked task order, shared interfaces, local document links, whitespace
and coverage of S3-AC1 through S3-AC12. No implementation test results are claimed.

Preserve the modified Codex cachebuster manifest and unrelated untracked handoffs,
`codex-smoke-report.md` and `html-docs/`. Prior validation/report work is merged through PR #61
at `67b4ce2a28f4d912b165948ad37b48294981eada`. The historical cohort remains closed FAIL;
this work authorizes neither regrading it nor accessing prior private production/toy state.

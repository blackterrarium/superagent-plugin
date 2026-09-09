# Stage 3 implementation handoff

Date: 2026-09-09.
Status: design approved; implementation plan integrated; **subagent-driven execution selected**;
implementation not started. This handoff is documentation only.
Workspace: `/Users/eugene/src/superagent-plugin`.

## Fresh-session request

> Continue from docs/superpowers/handoffs/2026-09-09-coding-loop-stage3.md.
> Execute the approved Stage 3 implementation plan using subagent-driven development,
> starting at Task 1 in an isolated worktree. The design and execution method are already
> approved; do not repeat those approval questions. Preserve the required independent live
> acceptance on Claude, Codex and Pi. Prepare Task 9's concrete live protocol and bounded
> manifest for approval before arming its schedulers.

## Author decisions and authorization

- The user requested Stage 3 and ultimately required acceptance on **Claude, Codex and Pi**.
  That final scope supersedes both the old Claude-only roadmap and the briefly chosen
  Codex-first scope. Each harness must pass independently.
- The user approved the written design with “approved.” on September 9.
- The user then chose: “subagent-driven execution is the choice. Write a handoff doc so we
  can begin this in a fresh session.” This resolves the implementation plan's generic choice
  between subagent-driven-development and executing-plans. Use **subagent-driven-development**.
- Begin implementation in the fresh session, not during this handoff-writing turn. No Stage 3
  model workers, implementation worktree, test runs or schedulers have been created yet.
- Tasks 1–8 are implementation and offline verification. Task 9's live fixture, exact model
  pins, budget and runtime identities still require the concrete manifest approval specified
  in the approved design. The old validation's approval and dispatch budget do not carry over.

## Read first

1. Applicable repository instructions and current skill catalog.
2. [Approved Stage 3 design](../specs/2026-09-09-coding-loop-stage3-design.md).
3. [Nine-task implementation plan](../plans/2026-09-09-coding-loop-stage3.md), including Global
   Constraints and the S3-AC1–S3-AC12 ownership table.
4. `superpowers:subagent-driven-development` and its current setup, implementer/task-reviewer
   prompts, workspace helpers and model-selection guidance; `superpowers:using-git-worktrees`.
5. [Umbrella architecture](../specs/2026-09-05-coding-loop-design.md) and
   [completed bounded validation](../reports/2026-09-09-prd-coverage-workflow.md) for context.

Design, plan and original handoff were merged in
[PR #62](https://github.com/blackterrarium/superagent-plugin/pull/62), commit
`d1f7a1832e160b4375ccfb5a3c68df5de59b98ee`. Local main and origin/main matched that commit
before this handoff update. Refresh Git state on resumption; do not assume this remains HEAD.

## First execution actions

1. Inspect status, current branch, remotes and existing worktrees without altering unrelated
   state. Create a new isolated implementation worktree/branch from current synced main.
   Do not reuse a historical worktree merely because its name looks related.
2. Initialize this plan's SDD workspace/progress ledger with the installed skill helpers.
   Read the full plan and spec, perform the skill's preflight review, and record material
   implementation rulings. The spec is binding; routine implementation choices need no new
   author checkpoint. A substantive acceptance change cannot be silently adopted.
3. Start **Task 1: Strict project state and durable phase identity**. Its files are
   `scripts/_coding_loop_state.py` and `scripts/coding-loop-state-test.py`; its requirements
   cover S3-AC2 and the identity foundation of S3-AC4/S3-AC6.
4. Dispatch a fresh implementer with the complete task text, Global Constraints, approved
   spec/source revision, exact worktree and interface definitions. Resolve model/effort using
   current applicable skill/configuration and supported tools; no new execution pins were
   selected in this handoff. The previous validation's gpt-5.6-sol/high pins applied to that run.
5. Require meaningful RED/GREEN evidence, inspect actual commits, and perform independent
   task review for spec compliance and code quality. Resume the implementer for scoped fixes
   as the skill directs. Carry findings/rulings and task completion in the ledger.
6. Continue in dependency order through Tasks 1–8, preserving review/integration checkpoints.
   Shared files make simultaneous implementation of dependent tasks unsafe; a subagent per
   task does not mean all tasks run in parallel. Use the repository's reviewed PR workflow
   and keep unrelated changes out of every commit. At branch completion run the skill's final
   review; preserve needed review evidence before cleaning any SDD workspace.

Use event-driven agent completion updates. The user explicitly dislikes polling long model
runs; maintain concise progress updates without repeated status-query loops.

## Critical behavior and acceptance boundaries

The new supervisor shares existing infrastructure. Protect durable operation identity,
committed-evidence reconciliation, the explicit WAITING FOR BUILD state, no model session
while waiting for the inner loop, fail-closed evaluation and author-only specification
changes. Outer and inner registrations are controlled independently and clearly identified.

Task 9's proposed known-defective round-one baseline adoption is a live-protocol decision to
review concretely, not an approved fixture or permission to fabricate a goal closeout. The
real first evaluation must FAIL; actual inner-loop work must produce the reviewed repair and
subsequent PASS. Keep every attempt and distinguish FAIL, INVALID and INCOMPLETE. An unavailable
harness cannot be waived by another harness's success. No Stage 3 completion/release claim
until all three live gates and cleanup pass. Deterministic tests are not live scheduler proof.

## Verification already performed

Planning verification checked task order, shared interfaces, local document links, whitespace
and coverage of S3-AC1 through S3-AC12. No Stage 3 implementation test results are claimed.
The earlier bounded PRD workflow validation is complete and merged through
[PR #61](https://github.com/blackterrarium/superagent-plugin/pull/61), commit
`67b4ce2a28f4d912b165948ad37b48294981eada`; it does not establish Stage 3 acceptance.

## Preserve workspace and historical state

Before this handoff update, unrelated primary-workspace state was:

- Modified `codex/plugins/superagent/.codex-plugin/plugin.json` — supported local cachebuster.
- Untracked `codex-smoke-report.md` and `html-docs/`.
- Untracked handoffs `2026-09-07-mdtoc-failure-rca-handoff.md`,
  `2026-09-07-mdtoc-operator-round.md`, `2026-09-08-staged-acceptance-review-fix.md` and
  `2026-09-08-staged-acceptance-review-progress.md` under `docs/superpowers/handoffs/`.

Do not reset, stash, overwrite or bulk-stage these. Build generated packages in the isolated
worktree. Do not edit installed plugin caches by hand. The historical cohort remains closed
FAIL; this work authorizes neither regrading it nor accessing prior private production/toy
state. No claim about unrelated host-wide scheduler activity is made by this handoff.

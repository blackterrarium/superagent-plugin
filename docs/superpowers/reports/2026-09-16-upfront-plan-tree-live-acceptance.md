# Proposed isolated live acceptance

**Status:** Prepared, awaiting explicit disclosure approval. No live lifecycle dispatch has started.

Run the normal, bounded-refinement, and contract-break paths in three independent disposable local Git repositories/vaults. Use the [synthetic five-stage goal](evidence/2026-09-16-upfront-plan-tree/live-fixture-goal.md), [run schedule](evidence/2026-09-16-upfront-plan-tree/live-run-schedule.json), and saved [internal](evidence/2026-09-16-upfront-plan-tree/live-internal.superenv), [bounded](evidence/2026-09-16-upfront-plan-tree/live-bounded.superenv), and [break](evidence/2026-09-16-upfront-plan-tree/live-break.superenv) configurations.

The calls would send copied plugin instructions/templates/helpers and synthetic fixture content, generated plans/code/tests, fixture Git metadata, and execution results to the configured Codex and Claude model services. They would author/refine/replan/execute the fixture and create local commits, branches, worktrees, reports, and logs. No unrelated project code or goal data, credentials, global configuration change, network Git push, hosted PR, deployment, or scheduler installation is part of this request.

| Role | Proposed model | Effort |
|---|---|---|
| Initial planner | Codex gpt-5.6-sol | high |
| Stage refiner | Codex gpt-5.6-terra | medium |
| Bridged replanner | Claude opus | high |
| Executor | Codex gpt-5.6-sol | medium |

Nested implementation/review roles use the copied Codex configuration. Pi is excluded from live claims because its transport authentication preflight expired. Codex calls use workspace-write sandboxing with the disposable run root added; Claude loads the copied plugin for that session only. Forwarding wrappers call the real CLIs and fabricate no results. Code repositories have only local bare Git origins.

The run must retain actual role-dispatch logs, complete plan trees, preparation/delivery receipts, source/revision identities, tests/reviews, and integration history. It must exercise affected S02/S03 replanning while retaining S04/S05, interrupted batch recovery, both vault layouts, and the normal path with no post-publication structural planning. Performance/token figures will be reported only when available from actual evidence.

Automatic approval review rejected the first authoring retry because it would disclose copied repository instructions and fixture content to an external model without explicit approval. The process did not start. This request covers that concrete disclosure and the isolated actions above. Shipped planning mode remains incremental until live acceptance passes.

Prepared package inventory: [162 copied files and SHA-256 hashes](evidence/2026-09-16-upfront-plan-tree/live-package-inventory.json). Canonical Claude and generated Codex, Cursor, and Pi copies each include superstage, superrefine, and superreplan; all copies are regular files with no symlink fallback. Cursor/Pi copies support offline verification only.

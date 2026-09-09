# Bounded workflow evidence

Actual author-approved run on 2026-09-09. `final-result.json` records outcomes; `run-state.json` records seven native child roles requested at gpt-5.6-sol/high. Timing records are controller receipt/reservation times, not provider metrics; per-role token usage was not exposed.

Candidate A is the reviewed implementation. Candidate B changes only its final test assertion to existence. Both command suites passed. Independent candidate B leaf review rejected it; project evaluators returned A PASS and B FAIL. Returned J/AC tables are preserved verbatim; earlier task/branch and negative leaf review files are labeled controller transcriptions.

Packets retain original absolute roots for provenance. The runner's temporary detached worktrees were removed after grading. Identical source is exported in each candidate directory; full SHA history is recoverable with `git clone <name>.bundle <destination>`. Candidate A code is in original-code.bundle. Vault snapshots contain separate committed report/ledger outcomes. The original vault ledger stays pending because evaluations belong to the independently copied snapshots.

The immutable `scope.md`, `scratch/` and `source/` retain preapproval wording. `approval.json` links actual author approval and content hashes; these historical DRAFT files are not current execution status. The full goal tree is exported under `goal/`.

Controller scripts are preserved as execution evidence, not a supported reusable harness. Original absolute paths and local-only Git remotes are intentional. No provider raw history, private production vault, scheduler state or secrets are included.

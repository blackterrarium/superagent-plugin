# Blocked re-plan lifecycle verification

## Outcome and scope

Canonical skill contracts now define durable repair requests, successor publication, replay and
verified terminal completion. Codex, Pi and Cursor packages were regenerated. This change repairs
the plugin's orchestration contract; it does not modify the retained mdtoc implementation or
rewrite that failed round's evaluation. A real scheduler/GitHub repeat remains unverified.

Design: [blocked-replan-lifecycle-design](../specs/2026-09-07-blocked-replan-lifecycle-design.md).
Plan: [blocked-replan-lifecycle](../plans/2026-09-07-blocked-replan-lifecycle.md).

## Evidence

Baseline source was main `e91a8fb`. Read the retained mdtoc finding, loop decision/iteration log,
evaluation, and all five lifecycle consumers. Fresh isolated agent `baseline_lifecycle` applied
the original skills: planner none, executor none, literal DONE; no instruction materialized repair
eligibility, and BLOCKED/none precedence was ambiguous.

The original 12-scenario probe failed 7 cases: adopted re-plan, mixed none/BLOCKED, closeout repair,
fresh tick, stale ancestor, missing integration evidence, closed-but-unmerged PR. Baseline answers
are retained in [baseline.json](lifecycle-2026-09-07/baseline.json). Reproduce that comparison with:

```bash
python3 scripts/lifecycle-regression.py \
  --answers docs/superpowers/reports/lifecycle-2026-09-07/baseline.json \
  --cases adopted_replan mixed_none_blocked closeout_repair merged declined fresh_tick \
  successor stale_ancestor missing_evidence late_closeout replay closed_pr
```

Expected exit: 1 (seven failing subcases). This validates saved evidence; a new agent run is needed
for a fresh behavioral test.

A fresh agent `green_lifecycle` applied the revised canonical contracts and passed all original
12 scenarios. Independent reviewer `review_lifecycle` then found two Important gaps: ordinary
unfinished work hidden by a stale closed ancestor could loop; replaying an earlier repair after a
second repair could falsely block. C9 now returns BLOCKED with the hidden path; C8 now validates
supersession chains and settled dispositions. Four cases were added. Follow-up canonical probe
passed all 16; reviewer rechecked both fixes and reported no remaining Important/Critical findings.

Canonical answers: [canonical.json](lifecycle-2026-09-07/canonical.json).

```bash
python3 scripts/lifecycle-regression.py \
  --answers docs/superpowers/reports/lifecycle-2026-09-07/canonical.json
```

The probes read actual skill contracts but simulate fixture transitions. They do not mutate real
plan trees or prove commit/crash atomicity, role transport, scheduler behavior, or PR integration.
The independent package probe and final verification results are recorded below.

## New operator round prerequisites

Keep the old DONE loop, open blocked PR, plan, findings, closeout and frozen evaluator as failure
evidence. Use a new goal/run identity and a package built from this repair. Do not simply re-arm
the old loop or change its verdict to PASS.

The new mdtoc implementation plan must explicitly authorize and test all three review findings:

- Fence closers require the matching fence character, sufficient run length and only trailing
  whitespace; a fence-looking content line with non-whitespace suffix must not close the fence.
- ATX headings accept zero through three leading spaces and remove valid optional closing hashes;
  four-space-indented headings remain code. Include label and slug assertions.
- In-place writes use a same-directory temporary file and atomic replace after successful write;
  injected late-write and replace failures leave the original bytes intact and clean up the temp.
  Review file metadata/symlink behavior in the corrected plan before implementation.

Harden the new round's acceptance inputs explicitly (do not mutate the old frozen inputs):

- Add a prerequisite that `mdtoc.py` exists and compiles; test the acceptance checks against a
  bootstrap-only checkout to prove absence cannot pass.
- C4 must first verify the script exists, run the missing-input case with stdout/stderr captured,
  and assert exit 2 plus an application-specific missing-input diagnostic. Python's own missing-
  script exit 2 is not application behavior. Also ensure the fixture input really is absent.
- Replace C7's grep pipeline with an AST import check that first reads and parses `mdtoc.py`.
  A read/parse error must fail. Inspect both Import and ImportFrom module roots against an explicit
  reviewed standard-library allowlist (including any atomic-write helper such as tempfile).
  Scope checking is separate from existence/completeness, and static imports alone do not prove
  all dependency behavior.
- Keep separate tests for CLI usage, marker errors, duplicate heading output and allowed scope;
  require nonzero test count and judge the completed README on main.

The repeat's acceptance receipt must identify code main SHA, PR MERGED state and merge commit,
review/test results, evaluator PASS on main, and actual scheduler disarm. Skill probes and wrapper
exit 0 cannot substitute for those observations.

## Final verification results

- Fresh isolated `package_lifecycle` probe against generated Codex skills: all 16 scenarios passed.
  [Package answers](lifecycle-2026-09-07/codex-package.json) validated with
  `python3 scripts/lifecycle-regression.py --answers docs/superpowers/reports/lifecycle-2026-09-07/codex-package.json`.
- Canonical expanded probe: 16/16 passed. Both validators exit 0.
- Codex, Pi and Cursor builders: rebuilt successfully; all three `--check` commands exit 0.
- `bash scripts/coding-loop-package-test.sh`: copied Codex and Pi package lint/evaluator tests
  pass, 0 failures. Timeout scenario skipped because timeout/gtimeout is absent on this host.
- `bash scripts/bridge-test.sh`: 0 failures. A sandbox process-list warning appeared during the
  watchdog test; the suite completed successfully, including the process-tree termination checks.
- `bash scripts/vault-external-test.sh`: 0 failures.
- `bash scripts/prd-lint-test.sh`: 0 failures.
- `git diff --check`: exit 0.

Pi/Cursor behavior was checked through generated output parity, not native live model sessions.
No installed plugin, remote PR, mdtoc vault, or scheduler state was changed by this repair session.

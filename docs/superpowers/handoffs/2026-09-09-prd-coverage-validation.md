# PRD coverage division — post-activation handoff

Date: 2026-09-09
Workspace: `/Users/eugene/src/superagent-plugin`
Status: source integrated and Codex plugin activated; bounded live check complete; full workflow and reliability validation outstanding.

## Restart request

> Continue from docs/superpowers/handoffs/2026-09-09-prd-coverage-validation.md.
> Preserve the integrated PRD coverage division and historical failed evaluation. Address the outstanding bookkeeping and validation work below. Do not restart the old cohort or launch a new large experiment without separately defining its scope and budget.

The user requested this handoff to continue in a fresh session. This turn writes documentation only; it does not launch additional validation, implementation, or schedulers.

## Read first

1. This handoff.
2. `docs/superpowers/reports/2026-09-08-prd-coverage-activation.md` — local, currently uncommitted activation report.
3. `docs/superpowers/reports/2026-09-08-prd-coverage-division.md` — committed source-change report and review evidence.
4. `docs/superpowers/handoffs/2026-09-08-prd-coverage-division.md` — original intent and historical constraints. Its integration/installation next steps are now completed and superseded by this handoff.
5. Repository guidance and relevant installed skills before taking further action.

## Completed and verified

- PR #59 merged: https://github.com/blackterrarium/superagent-plugin/pull/59
- Implementation commit: `b10bb412eee62a527b55807e3bebf86237202ea9`.
- Merge commit and freshly checked local HEAD: `a509f5a96cc2171402fbaf6042e0da4fc944cc7f`.
- Remote main reached that merge commit during activation; recheck before further integration.
- PR included the four earlier local-main commits absent from remote main, including the lifecycle repair and its records. It did not include the failed staged acceptance candidate.
- Plugin refreshed through the plugin-creator cachebuster helper and `codex plugin add superagent@superagent`.
- Local marketplace: `/Users/eugene/src/superagent-plugin/.agents/plugins/marketplace.json`; plugin source: `codex/plugins/superagent`.
- Installed version: `0.8.1+codex.20260909022917`.
- Installed root: `/Users/eugene/.codex/plugins/cache/superagent/superagent/0.8.1+codex.20260909022917`.
- All 29 source package files matched installed bytes. No installed cache was hand-edited.
- This conversation's latest skill catalog now includes `superagent:supercoverage` from the new version. The earlier statement that this conversation still needed catalog refresh is superseded. In the next session, verify the actual catalog/path; do not reinstall solely because the old report recommends a fresh thread.

The division is: `supercoverage` advises during PRD authoring; the author approves a concrete agreement; planning preserves AC IDs, full conditions, source revisions and C/J ownership; implementation review verifies assigned leaf obligations; `supereval` verifies project acceptance. Suggestions stay advisory. Missing binding context and missing judged results fail closed. Legacy explicit requirements remain valid without fabricated approval or forced format migration.

## Validation evidence and limits

Source checks passed: canonical PRD lint, supereval runner, copied Codex/Pi package tests, all three build-parity checks, new skill frontmatter validation, and whitespace checks. The merged skills/scripts/generated trees matched the tested branch.

A single fresh `codex exec` session, `gpt-5.6-sol` at high effort, discovered the installed skill and read the installed PRD/meta/run/eval instructions. It used a fully specified synthetic malformed-JSON fixture:

- Positive test: asserts ValueError and exact preservation of existing destination bytes. C1 PASS, J1 PASS, AC1 PASS.
- Negative test: asserts ValueError and destination existence only. C1 PASS, J1 FAIL, AC1 FAIL.
- Both test suites were green; the review correctly distinguished assertion meaning from suite success.
- Unapproved gzip advice did not affect either verdict.
- Approval was explicitly a synthetic scenario assumption, not real user approval of a PRD.
- Initial child-sandbox test invocations could not create temporary directories; each was retried once with temporary-directory access and passed. Root inspected command receipts and evidence; fixture and prompt hashes stayed unchanged.

This was one live instruction-and-evidence exercise. It described propagation through PRD/plan/review packets; it did not actually execute the full multi-role PRD → vault → planning → implementation → evaluation lifecycle. It proves neither unattended reliability nor benchmark success.

## Outstanding work, in suggested order

1. **Preserve and integrate documentation.** This handoff and the activation report are local untracked files. Review and commit them through the normal repository workflow, keeping unrelated dirt out of commits. Do not treat their uncommitted status as a source implementation defect.
2. **Close validation gaps where useful.** Runner case 3 was skipped because `timeout`/`gtimeout` was unavailable. Supply a supported timeout utility and rerun the relevant runner/package checks if addressing this gap. The generic plugin validator reported two pre-existing schema mismatches: missing manifest `interface`, and `superagent` frontmatter `disable-model-invocation: true`. Both were present on pre-PR remote main; CLI installation succeeded. Investigate intended schema/behavior before changing them, especially the invocation restriction. They are not regressions introduced by this change.
3. **Perform bounded full-workflow validation before claiming operational readiness.** Define an isolated disposable code repo and vault, concrete requirements and a reviewable acceptance agreement, model routing, run limits, and expected positive/ineffective-assertion outcomes. Exercise actual authoring/approval, plan propagation, implementation review and evaluation transport. Preserve the real approval gate; do not promote the old fixture's synthetic assumption to user approval. Inspect the existing `scripts/coding-loop-harness-smoke.py` and its documentation for reusable transport, but check compatibility with the new acceptance gate before running it. Keep private production/toy state outside this test.
4. **Reliability evaluation is separate.** If requested, first define a fresh design, controls, identities, metrics and budget. Measure advisory usefulness/author corrections separately from delivery-verification accuracy. Do not reuse the old checklist-reconstruction metric as evidence for this division. No new large cohort is authorized by this handoff alone.

No unattended loop was launched during activation or handoff writing. Recheck host state before making a new global claim about running processes.

## Evidence locations

`/private/tmp/prd-coverage-activation/` contains `probe-result.md`, `probe-events.jsonl`, `probe-stderr.log`, `probe-prompt.md`, `fixture-hashes.json`, `package-verification.json`, `requirements.md`, `product.py`, `test_positive.py`, and `test_negative.py`. These temporary artifacts may not survive cleanup; absence is not permission to invent or claim a rerun. Preserve relevant portable evidence if integrating the report; inspect raw logs before adding anything to Git.

The live session reported 440871 input tokens (396544 cached), 8177 output tokens. These are development-check usage, unrelated to the historical cohort's budget.

## Preserve workspace and historical state

Fresh `git status` before writing this handoff showed the local cachebuster modification in `codex/plugins/superagent/.codex-plugin/plugin.json`, plus untracked `codex-smoke-report.md`, `html-docs/`, the activation report, and older handoffs dated September 7–8. Preserve them; do not reset, stash, drop, or bulk-stage unrelated files. The supported local cachebuster remains outside the integration commit.

The original untracked discovery copy of the September 8 division handoff was byte-identical to the incoming tracked file. It was moved to `/private/tmp/prd-coverage-activation/original-handoff.md` to permit the fast-forward and verified equal afterward.

Implementation worktree `/private/tmp/superagent-prd-coverage` and branch `feat-prd-coverage-advice` were retained. Historical `fix-acceptance-coverage` and other worktrees were not removed.

The old 60-attempt staged cohort remains closed, Gate B FAIL: baseline 4/30 versus staged 6/30 full passes, 11 invalid transports. Do not restart, regrade, or spend its old budget. Preserve its report at commit `9add264` on `fix-acceptance-coverage`. Private vault `/Users/eugene/superagent-vaults/mdtoc-loop-test` and prior toy state were not accessed during activation; historical SHAs in older handoffs are not fresh host-state assertions. Do not copy private keys, raw private packets, or detailed private audits into plugin Git.

The user prefers event-driven evaluation updates and explicitly requested no polling of long evaluations. Use completion notification/event-driven transport for any future long run.

## Continuation checkpoint — September 9

See [continuation report](../reports/2026-09-09-prd-coverage-validation.md) for the fresh
offline timeout results, preserved historical evidence and proposed live-validation scope.
The original outstanding-work list above is historical: documentation preservation and
the skipped timeout case have now been addressed. The full workflow is still awaiting
real author approval of the concrete draft; no READY project or downstream execution is
authorized by this checkpoint. The two existing schema mismatches remain documented.

# PRD coverage division activation

Integration: PR https://github.com/blackterrarium/superagent-plugin/pull/59 merged; local and remote main reached `a509f5a96cc2171402fbaf6042e0da4fc944cc7f`. Source implementation is `b10bb412eee62a527b55807e3bebf86237202ea9`. The PR includes the four previously local-only baseline commits, including the lifecycle repair. It does not include the failed staged acceptance candidate.

Activation used the plugin-creator cachebuster helper and `codex plugin add superagent@superagent`, against the existing local marketplace at `.agents/plugins/marketplace.json`. Installed version: `0.8.1+codex.20260909022917` (UTC helper timestamp). Installed root: `/Users/eugene/.codex/plugins/cache/superagent/superagent/0.8.1+codex.20260909022917`. All 29 source package files were compared byte for byte with installed files, with zero mismatches. Package verification and synthetic fixture hashes are in `/private/tmp/prd-coverage-activation/`.

Fresh checks: canonical PRD lint, supereval runner, copied Codex/Pi package tests, all three generated-build parity checks, supercoverage frontmatter validation, and whitespace checks passed. Runner timeout case 3 was skipped because timeout/gtimeout is unavailable. The generic plugin validator failed on two pre-existing conditions also present on remote main before integration: missing manifest interface and superagent disable-model-invocation=true. These were not changed; CLI installation succeeded. Source skills/scripts/generated trees in the merge commit match the tested implementation branch.

The primary checkout's unrelated dirt was preserved. Its byte-identical untracked discovery handoff was moved to `/private/tmp/prd-coverage-activation/original-handoff.md` before fast-forwarding and verified equal to the now-tracked copy. The local manifest retains the supported cachebuster modification, outside the integration commit. Other worktrees and historical branches remain intact.

## Bounded live validation

One fresh read-only `codex exec` session uses `gpt-5.6-sol`, high effort, against a synthetic fixture in `/private/tmp/prd-coverage-activation/`. This is separate from the closed cohort. No scheduler, toy repair, private vault access, historical regrade, or new large experiment was launched.

The fixture specifies malformed JSON rejection and preservation of existing destination bytes. Both test variants execute successfully: the positive variant asserts exact byte equality; the negative variant asserts only destination existence. A synthetic fixture-author approval is explicitly a scenario assumption, not a claim of real user approval. The runtime must discover the installed skill, carry the agreement through PRD/plan/review packet reasoning, and judge the two evidence sets independently. This checks live instruction use and evidence interpretation, not complete PRD-to-vault-to-planning-to-implementation transport or unattended reliability.

Result: the fresh session completed successfully and resolved `supercoverage` from the installed version above, then read the installed PRD/meta/run/eval skills. It produced the expected draft AC1 agreement, retained approval and readiness gates, and described source/root preservation through leaf review and evaluation. Positive: C1 PASS, J1 PASS, AC1 PASS. Negative: C1 PASS, J1 FAIL, AC1 FAIL because destination existence does not establish unchanged bytes. Unapproved gzip advice affected neither verdict. The root inspected the returned reasoning and file/command evidence, rather than accepting a keyword-only grade.

The first test invocations in the read-only child sandbox failed to create temporary directories. Each was retried once with temporary-directory access and passed. The event log confirms both actual successful executions. The fixtures were not changed. This transport detail is retained rather than reported as a clean first-attempt run.

Artifacts: `/private/tmp/prd-coverage-activation/probe-result.md`, `probe-events.jsonl`, `probe-stderr.log`, `probe-prompt.md`, `fixture-hashes.json`, `package-verification.json`, and the fixture sources. Session usage reported 440871 input tokens (396544 cached) and 8177 output tokens. This single development check has no relationship to the former cohort's budget or outcome.

Operational boundary: integration and Codex installation are complete. A fresh Codex thread is required for this app conversation to acquire the new catalog. No unattended operational loop was launched. A complete multi-role PRD-to-vault-to-implementation transport test and a separately designed reliability benchmark remain unproven; the bounded exercise must not be cited as either. The closed historical evaluation remains FAIL.

## September 9 preservation note

The fresh-session catalog now includes `superagent:supercoverage` at the installed path above; the earlier catalog-refresh recommendation is historical. Selected fixture sources, prompt, result, hashes, package record and four test-command receipts are preserved in [activation evidence](evidence/2026-09-08-prd-coverage-activation/README.md). This preservation is not a rerun.

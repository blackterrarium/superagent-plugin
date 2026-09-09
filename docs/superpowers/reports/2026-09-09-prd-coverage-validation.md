# PRD coverage validation continuation

Date: 2026-09-09. Source baseline: a509f5a96cc2171402fbaf6042e0da4fc944cc7f.
Status: maintenance checks complete; proposed workflow validation awaits author approval.

## Preservation and integration scope

Preserved the September 9 handoff, September 8 activation report and selected portable
historical evidence. The historical fixture/prompt SHA-256 values all match their recorded
hashes. Four original completed test-command receipts retain the two sandbox failures and
two successful retries. Raw session logs, private vaults and old cohort packets are excluded.
The historical closed cohort remains Gate B FAIL (baseline 4/30, staged 6/30, 11 invalid
transports); no restart, regrade or spending of its budget occurred.

Remote main was freshly checked through git ls-remote and matched the baseline above.
Primary checkout dirt was preserved, including the local supported cachebuster. Only the
explicit documentation/evidence paths from this continuation belong in its PR.

## Fresh offline verification

Installed GNU coreutils 9.11 through Homebrew; timeout resolves to /opt/homebrew/bin/timeout.
Homebrew also performed its automatic cleanup of old formula/cache entries; no repository
source changed. The previously skipped one-minute timeout case now actually executes.

| Check | Result |
|---|---|
| Canonical scripts/prd-lint-test.sh | Exit 0, zero failures |
| Canonical scripts/supereval-test.sh | Exit 0, all eight runner cases; case 3 TIMEOUT passed |
| scripts/coding-loop-package-test.sh | Exit 0; Codex and Pi lint/runner suites pass, case 3 passes in each; no skips |
| Cursor and Pi build --check | Exit 0 in primary checkout |
| Codex build --check | Working checkout reports only preserved manifest cachebuster/formatting drift; clean git archive of baseline passes |
| Installed package byte comparison | 29 local package files, zero installed mismatches |
| Installed prd-lint.sh on new scratch draft | Exit 0, no WARN or FAIL; semantic review/approval remain separate |

Command logs are in [current evidence](evidence/2026-09-09-prd-coverage-validation/).
The snapshot parity check did not reset the manifest or regenerate installed cache files.

## Existing schema mismatch disposition

The generic plugin-creator validator still reports missing manifest interface and
superagent frontmatter disable-model-invocation=true. Both are visible at pre-PR baseline
43988140. The installed Codex build explicitly states that the supervisor is driven by
reading its SKILL.md directly, never invoked by name. Changing the restriction simply to
satisfy this generic validator would alter that deliberate behavior. No schema or invocation
change was made. Runtime installation success does not establish generic-schema compliance;
resolving that policy mismatch remains a separate task.

## Harness compatibility

scripts/coding-loop-harness-smoke.py line 213 synthesizes “I approve the reviewed draft.”
It supplies the code commits itself, omitting implementation and leaf delivery review.
Its default invokes Codex with approvals and sandbox bypassed. Therefore it was inspected
but not executed or used as approval authority. Its reusable pieces are disposable separate
repos, retained phase logs, source snapshots, runtime role receipts and ledger verification.
It does not prove the new required approval or full implementation-review transport.

## Approval boundary and next action

The new proposed scope, three DRAFT project files and binding source documents are retained
in the adjacent draft evidence. They specify three acceptance rows: malformed-JSON rejection
with exact destination preservation, meaningful executable exception/byte-equality
assertions, and Python/standard-library/no-network constraints. Gzip remains optional and unapproved. Real author approval of this exact revision
is required before a READY project or any downstream execution. No code repo, vault,
implementation or scheduler for this validation has been created.

The proposed run is a bounded open development check, not a blind reliability evaluation:
all child roles gpt-5.6-sol/high, at most 12 post-approval role dispatches including retries,
15 minutes each, 90 minutes total. It uses only disposable local code/vault repositories,
actual root/leaf planning and implementation review, then positive/ineffective-assertion
review and evaluation snapshots. Local branch review/merge substitutes for GitHub PR transport
only if the author approves that scope. No dollar/token guarantee is implied by these limits.

Restore scratch/source files from the draft evidence if temporary files disappear, verify
hashes and preserve DRAFT status. After approval, follow init for isolated repo/vault setup
and record real source/project SHAs separately. Never infer approval from this document,
reviewer output, lint success, or the earlier synthetic fixture assumption.

## Draft review

A read-only gpt-5.6-sol/high PRD reviewer with no inherited conversation identified four
readiness gaps: variant-control scope mixed with product delivery, unspecified evaluated
commit selection, omitted API verification, and omitted environment/dependency checks.
The draft now assigns variant construction to the external controller, selects one supplied
code repository main SHA, verifies the callable in AC1/J1, and adds SC3/AC3/C2 for environment
constraints. No author approval is inferred from these corrections.

The review packet supplied exact scratch file paths for the child to read rather than
embedding their bytes as the skill prescribes. This documented preparation deviation
prevents claiming exact prompt-serialization compliance. No product code was authored.

The same reviewer re-read the corrected draft and reported all four findings resolved,
with no remaining readiness gaps. Its optional K2-label cleanup was applied. Final lint
has no WARN or FAIL. Approval is still pending; the complete review receipt and draft
content hashes are preserved alongside the draft files.

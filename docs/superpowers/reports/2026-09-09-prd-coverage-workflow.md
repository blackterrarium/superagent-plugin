# Author-approved PRD coverage workflow validation

Date: 2026-09-09. Result: expected controls observed in one bounded development run.

The approved agreement passed through actual project writeout, meta/root/leaf planning,
implementation, independent delivery review, local integration, closeout and project
evaluation. The positive implementation passed acceptance. Replacing only its final byte
comparison with a destination-existence assertion caused both independent delivery review
and project evaluation to reject the negative candidate, although both command suites passed.

| Selected candidate | C1 | C2 | J1 | AC1 | AC2 | AC3 | Delivery review |
|---|---|---|---|---|---|---|---|
| A: exact byte comparison | PASS | PASS | PASS | PASS | PASS | PASS | Approved task and branch |
| B: existence-only assertion | PASS | PASS | FAIL | FAIL | FAIL | PASS | Rejected |

Negative AC1 FAIL means missing required proof, not demonstrated product corruption. The
product is identical in both candidates. Unapproved gzip advice did not affect acceptance.

## Authorization and execution

The author's actual “yes” approved the concrete v1 agreement and scope preserved by
[PR #60](https://github.com/blackterrarium/superagent-plugin/pull/60), documentation commit
`a02009896a3b0ad7a40bf35cce0a08f6ca0f3e6d`. The
[approval receipt](evidence/2026-09-09-prd-coverage-workflow/approval.json) records exact draft
hashes. Historical synthetic approval was not reused. Disposable code and external vault
repositories were created under `/private/tmp/prd-coverage-validation-20260909`, with local
bare remotes and the explicitly approved local branch-review/squash-merge exception.

The installed package was `0.8.1+codex.20260909022917`; its hash inventory is preserved.
The root controller applied installed skills inline. Seven isolated native child roles were
requested at `gpt-5.6-sol`/high: goal planner, implementer, task reviewer, branch reviewer,
negative candidate reviewer and two project evaluators. There were no transport retries.
The run took approximately 36 minutes, within 90 minutes and 12 dispatches; every recorded
dispatch duration was under 15 minutes. Completion events supplied results. Native task
receipts do not expose per-role token usage, so no cost or token total is claimed.

The implementer produced a real failing test before adding the product, then a passing test
and environment check. Task and branch review found no issues; the reviewed tree was locally
squash-merged and the plan tree closed out. Each later evaluation used an independent copy
of the code and vault, captured one full selected main SHA, ran the installed `supereval.sh`
in a detached worktree, and dispatched one read-only evaluator with complete binding text.
Both evaluators inspected actual source and meaningful assertions. Each snapshot now has
its own committed evaluation report and completed round ledger.

## Revision and evidence chain

| Record | Revision |
|---|---|
| Binding code sources | `c16fa3a1efa7b5eefb13a407ce12ffa39a280638` |
| Approved project vault | `bd34d0e6efca96a19b9a1f4ba8b3a06159938cfc` |
| Meta plan | `6915b2fd3c74d37de48283119b4d97f4638759a1` |
| Root plan | `047175f` |
| Implementation leaf | `d19f49773a4239eb7b6585aaab3bbe382c8ff6e0` |
| Reviewed implementation | `d5644e2b5852c852ee31e93db940bac752ab0c55` |
| Integrated positive / candidate A | `a24f8c8c8f276b873d426b3dc0f994727782ec27` |
| Closeout / initial snapshot vaults | `2ede8ad85168c85d75a4742d5be9597ea7c7149c` |
| Candidate B | `df5507166576550a4833c9bbf962419ea61f8681` |
| Candidate A evaluated vault | `fd1e1a0b42f5bdd5bbfab85e2d86b3f82207facd` |
| Candidate B evaluated vault | `4d7484633c46f73a7106c4cc03c2caa850661b48` |

The [portable evidence index](evidence/2026-09-09-prd-coverage-workflow/README.md) includes
approval, source and agreement files, full plan tree, RED/GREEN receipts, review evidence,
actual evaluator packets and returned J/AC tables, runner output, separate project ledgers,
controller scripts, hash manifest and verified Git bundles. The
[one-line mutation](evidence/2026-09-09-prd-coverage-workflow/mutation.diff) is independently
checked to leave product and agreement bytes identical. The
[final verification record](evidence/2026-09-09-prd-coverage-workflow/final-result.json)
confirms report/ledger consistency and clean locally synchronized snapshot repositories.

## Limits and procedure deviations

This is an open development validation with visible expected controls, one product leaf,
one selected example and two candidate evaluations. It establishes this observed transport
and assertion distinction; it does not establish statistical reliability or operational
readiness. GitHub implementation PR transport, unattended scheduling, cross-harness routing,
multi-leaf ownership and missing-context fault injection were not exercised.

The preapproval PRD reviewer received exact file paths instead of embedded document bytes,
as already disclosed before approval. Meta-plan authoring occurred directly at its final
path, with self-review/correction before dispatch, rather than using the prescribed scratch
move. These are procedure deviations; no claim of exact full-protocol compliance is made.
The later evaluator packets were verified to contain verbatim evaluation, pre-ledger PRD,
binding sources and actual command results. The runner summarizes C1 as `OK`; evaluators
explicitly distinguished that execution evidence from direct assertion inspection.

Controller timing records use reservation and receipt timestamps, not provider runtime
metrics. Temporary detached evaluation worktrees were removed after grading; exported
source and Git bundles preserve their contents and SHAs. The original vault ledger remains
pending because the two authoritative evaluation outcomes belong to independent snapshot
vaults. Original packet paths remain recorded for provenance.

One controller bytecode syntax-check attempt hit the host Python cache permission boundary;
a no-write AST parse confirmed syntax. This did not affect product checks or model dispatches.

Archive hashes and all five Git bundles verified. Whitespace checks pass for authored
report/checkpoint content; the raw evidence deliberately retains one trailing blank line
in the captured constraints packet and two blank-context markers in the Git mutation diff.

The earlier timeout gap and documentation integration were closed in the
[preparation report](2026-09-09-prd-coverage-validation.md). The two preexisting generic
schema mismatches remain unchanged. The old cohort remains closed **FAIL**: baseline 4/30,
staged 6/30 full passes, 11 invalid transports. No regrade, new cohort, scheduler or access
to private production/toy state occurred. Reliability evaluation still requires its own
explicit design and budget.

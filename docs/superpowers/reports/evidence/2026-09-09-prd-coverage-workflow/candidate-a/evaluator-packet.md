# Acceptance evidence packet

Evaluated code commit: a24f8c8c8f276b873d426b3dc0f994727782ec27
Code evidence root (detached): /private/tmp/prd-coverage-validation-20260909/candidate-a/tmp/tmp.HQO0x7eb4I
Named implementation evidence: /private/tmp/prd-coverage-validation-20260909/candidate-a/tmp/tmp.HQO0x7eb4I/product.py and /private/tmp/prd-coverage-validation-20260909/candidate-a/tmp/tmp.HQO0x7eb4I/test_product.py.
Project/vault root: /private/tmp/prd-coverage-validation-20260909/candidate-a/vault; packet source snapshot commit: 2ede8ad85168c85d75a4742d5be9597ea7c7149c.
Approved source-project revision: bd34d0e6efca96a19b9a1f4ba8b3a06159938cfc in the original vault.
Binding requirements/AGENTS code revision: c16fa3a1efa7b5eefb13a407ce12ffa39a280638.
Approval receipt: /private/tmp/prd-coverage-validation-20260909/approval.json; actual user message “yes” approved v1.
The immutable AGENTS proposed policy is now approved; initialization is complete.
Snapshot roots here identify the actual execution source. Original source paths inside the
verbatim agreement identify binding provenance; their content is reproduced below.
Only the selected code commit is being evaluated. No previous judgments are supplied.
Runner exit code: 0.

## Full evaluation.md verbatim
```markdown
# Evaluation — 2026-09-09-json-preservation
**Date:** 2026-09-09 · **Status:** READY · **Related:** [[projects/2026-09-09-json-preservation/prd.md]]

## Environment
- setup: `true`
- cwd: `.`

Run against the detached worktree of the selected disposable code commit with Python 3.9+.
Selection rule: the caller supplies the isolated code repository explicitly; evaluate
its main HEAD resolved once to a full SHA before running checks. Pass that SHA to the
runner and judge evidence from the resulting detached worktree only. Missing repository
or commit identity prevents evaluation; never choose among snapshot directories.
The test file and implementation are future deliverables. Resolve the full PRD, this
agreement and both knowledge-base sources before dispatch. Record the vault project commit,
requirements source commit, evaluated code commit and separate absolute evidence roots.
Absent binding context or absent J1 results means overall FAIL even when C1 is green.

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `python3 -m unittest -v test_product` | `.` | `exit 0` | 1 |
| C2 | `python3 -c 'import sys; assert sys.version_info >= (3, 9)'` | `.` | `exit 0` | 1 |

## Judged objectives
| Id | Objective | Criteria | Evidence to inspect |
|---|---|---|---|
| J1 | Verify SC1 API/behavior, SC2 assertion coverage and SC3 constraints | PASS only if product.py declares reject_invalid_json(text: str, destination: pathlib.Path) -> None (equivalent imported Path annotation acceptable), tests call that API, imports/dependencies are standard-library only, code and tests contain no network I/O, and implementation rejects malformed input with ValueError before destination mutation, retains the general json.loads rejection rule, and an executed test calls the real function with the required example, asserts ValueError, and compares actual post-rejection bytes with captured pre-call bytes. Existence-only, size-only, mocks replacing the function, or two pre-call snapshots FAIL. Cite concrete file:line evidence and per-AC verdicts. A green C1 alone is insufficient. | product.py, test_product.py, C1/C2 outputs at the evaluated code commit; full prd.md, evaluation.md, requirements.md and AGENTS.md at their separately recorded binding revisions |

## Acceptance checklist
**Approval:** Approved by the author on 2026-09-09; applies to v1 checklist and source requirements. Approval reference: controller approval.json, user message “yes” responding to the complete v1 agreement and bounded scope. Source code repository commit: c16fa3a1efa7b5eefb13a407ce12ffa39a280638.

| Id | Source | Required case or rule | Expected result | Verification and check ids |
|---|---|---|---|---|
| AC1 | prd.md SC1; requirements.md SC1, v1 | Declared product.reject_invalid_json(text: str, destination: pathlib.Path) -> None API; malformed JSON and existing regular destination; example `{"broken":` and `b"keep\x00\xff\n"`; retain the general rule | ValueError or subclass; exactly unchanged destination bytes | C1 executes suite; J1 inspects declared API and parse-before-write behavior, exception assertion and exact before/after byte equality |
| AC2 | prd.md SC2; requirements.md SC2, v1 | Delivered test must distinguish rejection with preservation from rejection with corruption | Real function is executed; ValueError and captured-before versus read-after byte equality are asserted | C1 executes suite; J1 verifies distinguishing assertions; existence/size checks alone fail |
| AC3 | prd.md SC3; requirements.md SC3, v1 | Python 3.9+, standard-library dependencies only, no network I/O | Supported interpreter and compliant implementation/test source | C2 asserts interpreter version; J1 inspects imports, dependencies and absence of network operations |

## Coverage suggestions and decisions
Optional suggestion: gzip input support, UNAPPROVED and nonbinding. It affects no verdict.
All required outcomes in v1 were approved by the author on 2026-09-09.
This specification grades one selected code commit at a time. Construction and comparison
of positive/negative variants belongs solely to the external validation controller and is
not a product requirement, leaf obligation or instruction to locate other snapshots.
```

## PRD requirements, constraints and decisions verbatim (ledger omitted)
```markdown
# PRD — 2026-09-09-json-preservation
**Date:** 2026-09-09 · **Status:** READY · **Related:** [[projects/2026-09-09-json-preservation/evaluation.md]]

## Objective
Build a disposable Python standard-library function that rejects malformed JSON with
ValueError while preserving a preexisting destination file byte for byte, and deliver
a test whose assertions prove both rejection and preservation. This is a proposed new
validation fixture; historical synthetic approval does not approve this revision.

## Success criteria
| Id | Criterion | Verified by (check ids) |
|---|---|---|
| SC1 | product.reject_invalid_json(text: str, destination: pathlib.Path) -> None raises ValueError or a subclass for any text rejected by json.loads, before changing any bytes of an existing regular destination file. Required example: text `{"broken":`, destination bytes `b"keep\x00\xff\n"`. The general malformed-input rule remains binding. | C1, J1 |
| SC2 | test_product.py executes the real function, asserts ValueError, and compares bytes read after rejection against bytes captured before it. Existence-only or size-only checks are insufficient. | C1, J1 |
| SC3 | Implementation and test run on Python 3.9+, use only standard-library dependencies, and perform no network I/O. | C2, J1 |

## Constraints and non-goals
Python 3.9 or newer, standard library only, no network. Valid JSON, absent destinations,
filesystem errors, concurrency, gzip and other formats are outside scope. Implementation
files product.py and test_product.py are future deliverables, not existing evidence.

## Locked decisions
All proposed decisions below were approved by the author on 2026-09-09, user message “yes” responding to the complete v1 agreement and scope. Approval receipt: controller approval.json; approved draft hashes preserved there. Binding source code commit: c16fa3a1efa7b5eefb13a407ce12ffa39a280638.
- Use one malformed-JSON fixture and a general preservation rule; rejected: multi-format
  cohort, because the question is workflow transport, not reliability.
- Require exact byte equality and exception assertions; rejected: destination existence,
  because a corrupted destination can still exist.
- Use unittest and Python standard library; rejected: third-party test dependencies,
  because a disposable test needs no installation.
- One implementation leaf owns all of AC1, AC2 and AC3; later-leaf scope is not tested here.
- Positive/negative snapshot construction is the external validation controller’s work,
  not a product deliverable. The product has only one implementation and one test suite;
  each evaluation grades exactly one explicitly selected code repository main commit.
- Use scratch/source requirements.md and AGENTS.md at revision v1. Before READY, copy
  unchanged to the isolated repo, commit, and record that actual source SHA; after the
  approved project is committed to its external vault, downstream packets record that
  separate vault commit. No source SHA is claimed before it exists.
- Draft sources currently resolve against /private/tmp/prd-coverage-validation-20260909/source.
  Execution sources will resolve against /private/tmp/prd-coverage-validation-20260909/repo.
  The agreement lives in /private/tmp/prd-coverage-validation-20260909/vault/projects/2026-09-09-json-preservation.
  Commit identifiers added as provenance and DRAFT-to-READY approval bookkeeping may
  change after approval; any substantive requirements change needs new approval.

```

## Binding requirements.md verbatim
Source: requirements.md at c16fa3a1efa7b5eefb13a407ce12ffa39a280638.
```markdown
# JSON preservation fixture requirements — revision v1 (proposed)

SC1: Implement `product.reject_invalid_json(text: str, destination: pathlib.Path) -> None`.
For malformed JSON text and an existing regular destination file, raise ValueError
(a subclass is acceptable) and leave its exact bytes unchanged. Malformed means rejected
by Python standard-library json.loads. Required example text is `{"broken":` and initial
bytes are the Python bytes literal `b"keep\x00\xff\n"`. This example does not narrow the
rule to that input or those bytes. Parse before any destination write.
SC2: Deliver an executable unittest test in test_product.py that invokes that function,
asserts ValueError, captures destination bytes before the call and compares actual bytes
after rejection with that captured value. Existence-only, size-only, mocked-out calls,
and comparisons of two pre-call snapshots do not establish preservation.
SC3: Implementation and test run on Python 3.9+, use standard-library dependencies only,
and perform no network I/O.
No behavior for valid JSON, absent destinations, filesystem errors, concurrency, gzip,
or other formats is part of this fixture. No third-party dependencies or network.
```

## Binding AGENTS.md verbatim
Source: AGENTS.md at c16fa3a1efa7b5eefb13a407ce12ffa39a280638.
```markdown
# Proposed disposable validation policy — revision v1

This directory contains draft source documents, not an initialized code project.
After user approval, copy these documents into the new disposable code repository
/private/tmp/prd-coverage-validation-20260909/repo and initialize a separate external
vault /private/tmp/prd-coverage-validation-20260909/vault using superagent:init.
Use only installed plugin /Users/eugene/.codex/plugins/cache/superagent/superagent/0.8.1+codex.20260909022917.
Do not read the primary plugin repository .superenv or any private vault. Set all SUPER_ keys
explicitly for the disposable fixture; SUPER_GOAL_AUTOCONFIRM=false at PRD authoring.
All model roles: native Codex gpt-5.6-sol, high effort, isolated contexts.
Only local git repositories and local bare origins. Proposed scope exception to code A7:
local feature-branch review and merge replaces GitHub PR transport; external vault uses A7
local direct commits. No schedulers, remote services, package refresh, or production changes.
This exception becomes authorized only with author approval of this draft.
```

## Command results verbatim
```markdown
## Environment
- commit: `a24f8c8c8f276b873d426b3dc0f994727782ec27` · worktree: `/private/tmp/prd-coverage-validation-20260909/candidate-a/tmp/tmp.HQO0x7eb4I` · setup: `true` → ok

## Command checks
| Id | Result | Exit | Seconds | Evidence |
|---|---|---|---|---|
| C1 | PASS | 0 | 0 | `OK` |
| C2 | PASS | 0 | 0 | `` |
```

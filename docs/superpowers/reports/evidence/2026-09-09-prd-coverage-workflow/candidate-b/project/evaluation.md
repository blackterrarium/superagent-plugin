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

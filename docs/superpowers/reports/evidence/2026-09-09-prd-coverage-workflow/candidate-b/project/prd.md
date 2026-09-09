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

## Iteration ledger
| Round | Meta-plan | Goal folder | Inner loop | Eval report | Verdict |
|---|---|---|---|---|---|
| 1 | [[projects/2026-09-09-json-preservation/meta-plans/2026-09-09-15_16-r1]] | [[2026-09-09-15_18-json-preservation-r1]] | - | [[projects/2026-09-09-json-preservation/eval-reports/2026-09-09-15_49-r1]] | FAIL |

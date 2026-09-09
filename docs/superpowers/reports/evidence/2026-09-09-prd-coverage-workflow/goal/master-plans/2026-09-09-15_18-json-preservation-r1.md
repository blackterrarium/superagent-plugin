# JSON Preservation Round 1 Master Plan
**Date:** 2026-09-09 · **Status:** READY · **Related:** [[projects/2026-09-09-json-preservation/meta-plans/2026-09-09-15_16-r1]]

## Progress report

| Step | Status | Plan | PR | Comments |
|------|--------|------|----|----------|
| 1. Implement and verify malformed-JSON rejection with exact destination-byte preservation | completed-and-merged | [[2026-09-09-15_18-json-preservation-r1/plans/2026-09-09-15_25-json-preservation]] | | Local merge `a24f8c8c8f276b873d426b3dc0f994727782ec27` (approved exception); AC1/AC2/AC3 delivered. Closeout: [[2026-09-09-15_18-json-preservation-r1/reports/2026-09-09-15_40-json-preservation-closeout]] |

## Goal & success criteria

Build one disposable Python standard-library function and its executable unittest so malformed JSON is rejected before an existing destination file can change. Completion requires the single implementation step to satisfy every criterion below at the separately recorded binding revisions and to pass the complete approved agreement.

- **SC1 / AC1:** `product.reject_invalid_json(text: str, destination: pathlib.Path) -> None` must raise `ValueError` or a subclass for any text rejected by Python standard-library `json.loads`, before changing any bytes of an existing regular destination file. The required case uses text `{"broken":` and initial destination bytes `b"keep\x00\xff\n"`; the general malformed-input rule remains binding. Expected result: rejection with exactly unchanged destination bytes. Verification ownership: C1 executes the suite; J1 inspects the declared API, parse-before-write behavior, exception assertion, and exact before/after byte equality.
- **SC2 / AC2:** `test_product.py` must execute the real function and distinguish rejection with preservation from rejection with corruption. It must capture the destination bytes before the call, assert `ValueError`, and compare actual bytes read after rejection with the captured pre-call bytes. Existence-only checks, size-only checks, mocks replacing the function, and comparisons of two pre-call snapshots do not establish preservation. Expected result: the real function is executed and both the exception and captured-before versus read-after equality are asserted. Verification ownership: C1 executes the suite; J1 verifies the distinguishing assertions.
- **SC3 / AC3:** `product.py` and `test_product.py` must run on Python 3.9 or newer, use standard-library dependencies only, and perform no network I/O. Expected result: a supported interpreter and compliant implementation/test source. Verification ownership: C2 checks the interpreter version; J1 inspects imports, dependencies, and the absence of network operations.

The complete acceptance agreement, including full conditions, expected results, binding notes, and nonbinding advice, is [[projects/2026-09-09-json-preservation/evaluation]]. Step 1 satisfies SC1/AC1, SC2/AC2, and SC3/AC3 together; there is no later-leaf acceptance scope.

## Context

The implementation files do not exist yet. A zero-context planner must read these sources before authoring the single implementation leaf:

- [[2026-09-09-15_18-json-preservation-r1/goal-directives]] for this goal's objective and artifact-routing rules.
- [[projects/2026-09-09-json-preservation/prd]] at external-vault project revision `bd34d0e6efca96a19b9a1f4ba8b3a06159938cfc` for SC1, SC2, SC3, constraints, and locked decisions.
- [[projects/2026-09-09-json-preservation/evaluation]] at the same external-vault project revision for the complete approved v1 agreement, C1/C2/J1 ownership, and the acceptance checklist.
- [[projects/2026-09-09-json-preservation/knowledge-base]] at the same external-vault project revision for the source inventory.
- `/private/tmp/prd-coverage-validation-20260909/repo/requirements.md` and `/private/tmp/prd-coverage-validation-20260909/repo/AGENTS.md` at binding code-repository revision `c16fa3a1efa7b5eefb13a407ce12ffa39a280638` for the full v1 product requirements and the approved isolation/local-integration policy.
- `/private/tmp/prd-coverage-validation-20260909/approval.json` for the real author approval receipt: user message `yes`, recorded on 2026-09-09, approving the complete v1 agreement and bounded scope. Historical synthetic approval is not authority for this revision.

Evaluation later selects an explicitly supplied disposable code repository, resolves its `main` HEAD once to a full SHA, and judges a detached worktree at that commit. Evidence must record the vault project commit, requirements source commit, evaluated code commit, and separate absolute evidence roots. Missing binding context or J1 results makes the evaluation fail even if C1 passes.

## Locked decisions

- Use one malformed-JSON fixture while retaining the general `json.loads` rejection rule. A multi-format cohort was rejected because this validation targets workflow transport rather than broader reliability.
- Require exact byte equality and an exception assertion. Destination existence alone was rejected because a corrupted destination can still exist.
- Use `unittest` and Python's standard library. Third-party test dependencies were rejected because this disposable test needs no installation.
- Put AC1, AC2, and AC3 in one implementation leaf. Later-leaf scope is absent from this validation.
- Keep positive/negative snapshot construction with the external validation controller. The product deliverable is one implementation and one test suite, and each evaluation grades exactly one explicitly selected code-repository `main` commit. The leaf must not locate, construct, or compare other snapshots.
- Treat `/private/tmp/prd-coverage-validation-20260909/repo/requirements.md` and `AGENTS.md` at revision `c16fa3a1efa7b5eefb13a407ce12ffa39a280638` as immutable binding sources. Treat the project sources at vault revision `bd34d0e6efca96a19b9a1f4ba8b3a06159938cfc` as the separate approved project revision.
- The approval receipt permits provenance and DRAFT-to-READY bookkeeping changes without renewed approval; any substantive requirement change needs new approval.
- The optional gzip-input suggestion in the evaluation agreement is unapproved and nonbinding. Gzip support is excluded from this leaf.
- The approved local integration exception uses only local Git repositories and local bare origins. No GitHub, scheduler, remote service, package refresh, production change, private state, or new cohort belongs in this goal.

## Per-step guidance

### Step 1 — Implement and verify malformed-JSON rejection with exact destination-byte preservation

**Scope.** Author one execution-ready implementation plan for one sub-PR. Its product scope is exactly `product.py` and `test_product.py`: the declared `reject_invalid_json` function plus an executable `unittest` that proves malformed-input rejection and byte preservation. Valid JSON, absent destinations, filesystem errors, concurrency, gzip, other formats, positive/negative variant construction, and additional cohorts are outside scope. Planning must not create or edit the implementation files.

**Requirements and constraints.** The leaf must carry AC1, AC2, and AC3 with their full conditions and expected results from this root, cite the complete agreement, and assign all implementation and acceptance evidence to this one leaf. Its implementation sequence must parse with standard-library `json.loads` before any destination write can occur. Its test must create an existing regular destination containing exactly `b"keep\x00\xff\n"`, capture those bytes before calling the real function with `{"broken":`, assert `ValueError` or a subclass, then read and compare the actual post-call bytes with the captured value. The plan must keep the general rule for every string rejected by `json.loads`, use only Python 3.9-compatible standard-library APIs, and include no network I/O.

**Dependencies and interfaces.** The leaf consumes the approved v1 agreement and the two binding source revisions listed in Context. It produces `product.py` with `reject_invalid_json(text: str, destination: pathlib.Path) -> None` (an equivalent imported `Path` annotation is acceptable) and `test_product.py` whose suite is discoverable as module `test_product`. No other leaf consumes or extends this work.

**Verification.** The implementation plan must run the approved checks by their existing IDs and must not invent a replacement inventory:

- **C1:** from the selected disposable code checkout, run `python3 -m unittest -v test_product`; pass only on exit 0 within the agreement's one-minute timeout.
- **C2:** from the same checkout, run `python3 -c 'import sys; assert sys.version_info >= (3, 9)'`; pass only on exit 0 within the agreement's one-minute timeout.
- **J1:** inspect `product.py`, `test_product.py`, and C1/C2 output at the evaluated code commit together with the full PRD, evaluation agreement, `requirements.md`, and `AGENTS.md` at their separately recorded revisions. Pass only when the declared API and parse-before-write behavior satisfy AC1, the executed real-function test contains the required exception and captured-before/read-after equality assertions for AC2, and imports/dependencies plus source inspection satisfy AC3. J1 must cite concrete file-and-line evidence and record per-AC verdicts; C1 by itself is insufficient.

The leaf is complete only when AC1, AC2, and AC3 all pass through their assigned C1/C2/J1 evidence and the approved local feature-branch review and merge has integrated the selected code commit.

## Cross-step constraints / invariants

Because this root has one step, its cross-step invariant is ownership integrity: all acceptance work and evidence remain in the one implementation leaf. No planner may split an acceptance criterion into a later leaf or transfer positive/negative snapshot construction into product scope.

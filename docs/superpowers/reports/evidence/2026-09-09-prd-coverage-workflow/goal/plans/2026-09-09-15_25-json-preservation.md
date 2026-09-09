# JSON Preservation Implementation Plan
> **Parent seed:** [[2026-09-09-15_18-json-preservation-r1/master-plans/2026-09-09-15_18-json-preservation-r1]]
> ✅ CLOSED OUT — completed-and-merged locally at `a24f8c8c8f276b873d426b3dc0f994727782ec27`. Closeout: [[2026-09-09-15_18-json-preservation-r1/reports/2026-09-09-15_40-json-preservation-closeout]].
> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> (normally reached via superagent:superrun) to implement this plan task-by-task.

**Goal:** Deliver the approved malformed-JSON rejection API and meaningful preservation test.
**Architecture:** product.py delegates syntax rejection to standard-library json.loads and performs
no destination writes. test_product.py exercises the real function against a temporary existing
binary destination. Valid-input behavior is outside scope; parsing a valid value and returning
None without writes is an implementation choice, not an additional acceptance condition.
**Tech Stack:** Python 3.9+, json/pathlib/tempfile/unittest; no third-party dependencies.

## Global Constraints
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


Source requirements commit: `c16fa3a1efa7b5eefb13a407ce12ffa39a280638` in `/private/tmp/prd-coverage-validation-20260909/repo`.
Approved project commit: `bd34d0e6efca96a19b9a1f4ba8b3a06159938cfc` in `/private/tmp/prd-coverage-validation-20260909/vault`.
Full agreement: `/private/tmp/prd-coverage-validation-20260909/vault/projects/2026-09-09-json-preservation/evaluation.md`; all AC1/AC2/AC3 belong to this leaf.
Approval: actual author “yes” on 2026-09-09; receipt `/private/tmp/prd-coverage-validation-20260909/approval.json`.
No existing private vault, scheduler, GitHub transport or extra cohort. Local branch review/merge
and local bare origins are explicitly approved. Product scope has no variant construction.

## Task 1: Implement and verify rejection with exact byte preservation

**Files**
- Create: `product.py` — declared rejection API.
- Create: `test_product.py` — required real-function unittest.
- Read unchanged: `requirements.md`, `AGENTS.md`, `.superenv` from the isolated code repository.

**Interfaces**
- Consumes: approved v1 agreement and immutable source revisions identified below.
- Produces: `product.reject_invalid_json(text: str, destination: pathlib.Path) -> None`, with
  imported Path equivalent; executable test module `test_product`. No downstream task.

**Binding task context**
All AC1/AC2/AC3 are assigned to this task and this leaf. Read the complete agreement below,
not merely its row IDs. Source code requirements/AGENTS revision is `c16fa3a1efa7b5eefb13a407ce12ffa39a280638`;
source project revision is `bd34d0e6efca96a19b9a1f4ba8b3a06159938cfc` at the distinct external vault.
Full agreement path: `/private/tmp/prd-coverage-validation-20260909/vault/projects/2026-09-09-json-preservation/evaluation.md`. All referenced binding sources are available there
or under `/private/tmp/prd-coverage-validation-20260909/repo`. The controller owns variants and their expected comparisons.
User approval receipt: `/private/tmp/prd-coverage-validation-20260909/approval.json`. Immutable AGENTS.md's proposal was approved and
initialization completed; it must not be interpreted as a new pause or as absent repositories.
Use only the installed superagent package at `/Users/eugene/.codex/plugins/cache/superagent/superagent/0.8.1+codex.20260909022917` and available superpowers.
All child roles are gpt-5.6-sol/high, no nested delegation. Local test evidence; no CI configured.

### Step 1 — write the distinguishing test and observe RED
- [x] Create `test_product.py` with this exact focused test:

```python
import tempfile
import unittest
from pathlib import Path

from product import reject_invalid_json


class JsonPreservationTest(unittest.TestCase):
    def test_malformed_json_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "destination.bin"
            destination.write_bytes(b"keep\x00\xff\n")
            before = destination.read_bytes()
            with self.assertRaises(ValueError):
                reject_invalid_json('{"broken":', destination)
            self.assertEqual(destination.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
```

- [x] Run C1 (`python3 -m unittest -v test_product`) under `timeout 60` in the isolated
  worktree. Before product.py exists this must fail because the module is missing. Save the
  actual command/output as RED evidence; do not claim an unrun failure.

### Step 2 — implement and observe GREEN
- [x] Create `product.py`:

```python
import json
from pathlib import Path


def reject_invalid_json(text: str, destination: Path) -> None:
    """Reject malformed JSON without writing to the destination."""
    json.loads(text)
```

- [x] Run C1 under `timeout 60`: `python3 -m unittest -v test_product`.
- [x] Run C2 under `timeout 60`: `python3 -c 'import sys; assert sys.version_info >= (3, 9)'`.
- [x] Save command, exit status and output for both. C1 must execute the named test and exit 0;
  C2 must exit 0. The absence of writes is intentional: valid-input output is outside scope.

### Step 3 — self-review, commit and report
- [x] Read the diff against all approved conditions. Check the declaration, real function call,
  json.loads before any possible destination mutation, exception assertion, captured-before
  versus read-after byte equality, stdlib imports and absence of network operations.
- [x] Run `git diff --check`, stage only product.py and test_product.py, commit on the feature
  branch. Record full HEAD and the exact file hashes that the test executions covered.
- [x] In the implementation report, give each AC ID its test name or source location, required
  input, assertion location/meaning and revision-specific command evidence. C1/C2 results are
  execution claims; independent task/whole-branch reviewers assess J1 delivery obligations.
- [x] Return status, commit, test summary and concerns. Do not dispatch a reviewer or merge.

### Complete approved evaluation document (verbatim)

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

### Integration and completion (controller-owned)

After independent task spec/quality and whole-branch reviews pass, merge the feature branch
locally under the approved A7 exception, push only to the local bare origin, and invoke
superfinish to close out this leaf and update its parent. Retain the SDD evidence outside the
worktree before removing it. No GitHub PR or scheduler is part of this fixture.

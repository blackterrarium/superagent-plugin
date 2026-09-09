# Task 1 implementation report — JSON rejection with byte preservation

## Status

DONE. Implemented the complete approved product scope and committed only `product.py` and
`test_product.py` on `implement-json-preservation`.

Commit: `d5644e2b5852c852ee31e93db940bac752ab0c55` (`feat: preserve destination when JSON is invalid`)

Binding revisions:

- Requirements and immutable repository policy: `c16fa3a1efa7b5eefb13a407ce12ffa39a280638`
  in `/private/tmp/prd-coverage-validation-20260909/repo`.
- Approved PRD/evaluation project: `bd34d0e6efca96a19b9a1f4ba8b3a06159938cfc`
  in `/private/tmp/prd-coverage-validation-20260909/vault`.
- `requirements.md` SHA-256 at the binding revision:
  `d605d3842aa46ac89f6b62e024f4814b2633eb4b09ec14c5dce7c223a6e7d254`.
- `AGENTS.md` SHA-256 at the binding revision:
  `be6801f0fc9176ff363ed9263485a4755e416607120cba47ca93340c1b9ac26a`.
- `evaluation.md` SHA-256 at the binding revision:
  `5c2e8d82846ddabbf08b245c59a20b1140acdd77d4eb25f1a62862fc8fe3fe99`.
- `prd.md` SHA-256 at the binding revision:
  `f6b43bc20ead6f7a00b9e907daaabffd033e3f1cb4f440877f06f1b884ac514a`.

## Implementation

- `product.py:5-7` declares
  `reject_invalid_json(text: str, destination: Path) -> None` and calls `json.loads(text)`.
  It performs no destination operation, so malformed input is rejected by the standard-library
  parser before any possible destination mutation.
- `test_product.py:9-16` creates an existing destination containing the exact required bytes,
  captures those bytes before the call, invokes the real product function with the exact malformed
  example, asserts `ValueError`, and compares the actual post-call bytes with the captured value.

The GREEN executions covered these exact file contents, which were then committed unchanged:

| File | Git blob at commit | SHA-256 |
|---|---|---|
| `product.py` | `bdaf6db6131776a055b36d5bdbc6654a2e903ea7` | `50a2e77ff2e6b588bec24539dc9d87763ca0f1e2bf835392ab55d81e1e11f3e7` |
| `test_product.py` | `edb7d52727f55fcc544ac739386b49c98e5e6491` | `5fbb728ab8f61d5ff87136303e019618fb3891abd0d238f10a46102e78ff46d6` |

## TDD evidence

### RED

Command (from `/private/tmp/prd-coverage-validation-20260909/implementation`):

```text
timeout 60 python3 -m unittest -v test_product
```

Exit code: 1. Relevant output:

```text
test_product (unittest.loader._FailedTest) ... ERROR
...
ModuleNotFoundError: No module named 'product'
...
Ran 1 test in 0.000s

FAILED (errors=1)
```

This was the expected distinguishing failure before `product.py` existed: unittest tried to load
the focused test, and its real product import could not resolve. Full evidence:
`task-1-red-c1.txt` (SHA-256
`3fc337695d1fa93abcf233791d0262d3ca6d21d82530a154ddda581fc2ab88dc`).

### GREEN C1

Command (same working directory):

```text
timeout 60 python3 -m unittest -v test_product
```

Exit code: 0. Output:

```text
test_malformed_json_preserves_existing_destination (test_product.JsonPreservationTest) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.008s

OK
```

Full evidence: `task-1-green-c1.txt` (SHA-256
`ace5e711d1db03d0caf8b27bc4576fe5a350aa0b653c3349c684fbada2004ad6`).

### GREEN C2

Command (same working directory):

```text
timeout 60 python3 -c 'import sys; assert sys.version_info >= (3, 9)'
```

Exit code: 0. Output was empty. Full evidence: `task-1-green-c2.txt` (SHA-256
`a1b1d8e76f18d1932ca16c3e2bbb984b82f34407354a0806535611fcda2346e1`).

## Acceptance-criteria traceability

### AC1 — declared API, general malformed-JSON rejection, and exact byte preservation

- Required input: malformed text `{"broken":` and an existing regular file containing
  `b"keep\x00\xff\n"`.
- Product source: `product.py:5` supplies the exact declared API with imported `Path` equivalent;
  `product.py:7` applies the general `json.loads` rule before any possible mutation.
- Test input: `test_product.py:11-13` constructs the destination, writes the exact bytes, and
  captures them before the call; `test_product.py:15` passes the exact malformed string.
- Assertion meaning: `test_product.py:14-15` requires `ValueError` or a subclass from the call;
  `test_product.py:16` rereads the destination after rejection and compares it byte-for-byte with
  the captured pre-call value.
- Execution evidence: GREEN C1 above executed the named test at the exact two SHA-256 file hashes
  listed above; those unchanged hashes are the blobs in full commit
  `d5644e2b5852c852ee31e93db940bac752ab0c55`.

### AC2 — distinguishing real-function test

- Required input: the same malformed text and pre-existing binary destination from AC1.
- Real-call source: `test_product.py:5` imports the product function, and `test_product.py:15`
  directly invokes it without a mock or replacement.
- Assertion meaning: `test_product.py:14-16` jointly requires rejection and exact captured-before
  versus read-after equality. Corrupting, truncating, deleting, or changing any byte makes the
  equality assertion fail; rejection alone cannot pass the test.
- Execution evidence: GREEN C1 named and ran
  `JsonPreservationTest.test_malformed_json_preserves_existing_destination` at exit 0, tied to
  full commit and exact file hashes above.

### AC3 — Python 3.9+, standard library only, no network I/O

- Required rule: supported interpreter, stdlib dependencies only, no network activity.
- Source evidence: `product.py:1-2` imports only `json` and `pathlib`; `test_product.py:1-5`
  imports only `tempfile`, `unittest`, `pathlib`, and the local `product` module. Neither file
  contains a network API or performs network I/O.
- Assertion meaning: C2 asserts the executing interpreter's `sys.version_info` is at least
  `(3, 9)`.
- Execution evidence: GREEN C2 exited 0 with empty output against the same implementation
  worktree; GREEN C1 also demonstrates that the committed stdlib-only source executes there.

## Self-review and repository checks

- Read the complete staged diff and checked every approved condition: exact declaration, real
  call, parse before mutation, `ValueError` assertion, captured-before/read-after byte equality,
  standard-library-only imports, and absence of network operations.
- `git diff --cached --check` passed with no output before commit.
- `git diff HEAD^ HEAD --check` passed with no output after commit.
- The commit stat contains exactly the two authorized files and 27 inserted lines.
- Worktree status after commit is clean (`## implement-json-preservation`).

## Concerns

None. Valid-input behavior and all other explicitly excluded cases remain outside this fixture.

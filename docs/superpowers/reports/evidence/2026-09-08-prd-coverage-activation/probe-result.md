## Installed runtime

`superagent:supercoverage` was available in the fresh runtime. Its resolved installed path is:

[supercoverage/SKILL.md](/Users/eugene/.codex/plugins/cache/superagent/superagent/0.8.1+codex.20260909022917/skills/supercoverage/SKILL.md)

I read the installed `supercoverage`, `superprd`, `supermeta`, `superrun`, and `supereval` skills from that same versioned cache—not a source checkout.

## Draft fixture-v1 agreement

| Id | Source | Required case or rule | Expected result | Verification and check ids |
|---|---|---|---|---|
| AC1 | [requirements.md SC1](/private/tmp/prd-coverage-activation/requirements.md:2), revision `fixture-v1` | Malformed JSON with a preexisting destination | Raise `ValueError`; destination bytes remain exactly unchanged | C1 executes the selected test; J1 inspects the exception assertion and exact before/after byte-equality assertion |

Unresolved required outcomes: none under the fixture’s stated scenario assumption.

Optional, nonbinding scope: gzip support remains unapproved. It is neither an acceptance requirement nor an unresolved SC1 outcome.

This scenario assumption is not real author approval. Before a real READY write, `superprd` requires:

- Complete draft `prd.md`, `knowledge-base.md`, and `evaluation.md` files in scratch.
- R1–R8 all passing, including semantically complete acceptance coverage and no unresolved required outcomes.
- Successful `prd-lint.sh` validation.
- A zero-context review confirming the inputs are independently usable.
- Presentation of the exact checklist revision, suggestions, checks, sources, warnings, and proposed folder.
- Explicit author confirmation at the mandatory write gate. Only then may that exact revision be recorded as approved and written with `READY` status.

## Agreement carry-through

`supermeta` must copy SC1, C1, J1, AC1, the approval record, and binding notes verbatim into the meta-plan. It identifies the agreement’s source revision separately—normally a project commit plus paths—and instructs leaf plans to retain AC1’s full requirement, expected result, source revision, and a resolvable path to the full agreement.

At leaf review, `superrun` supplies the relevant AC1 row verbatim to implementers and reviewers. Evidence must identify the test/subtest, malformed input, exception assertion, byte-equality assertion and meaning, and execution revision. A mapping or green test alone is insufficient. Leaf review establishes only that leaf’s delivery; it cannot claim project-wide completion.

A corresponding `supereval` packet carries:

- Agreement source: `requirements.md`, logical revision `fixture-v1`.
- Agreement root for this exercise: `/private/tmp/prd-coverage-activation`.
- Evaluated code root: `/private/tmp/prd-coverage-activation`.
- Evaluated revision: the live fixture files; no Git commit was claimed.
- Named evidence roots per packet:
  - Positive: `product.py` and `test_positive.py` only.
  - Negative: `product.py` and `test_negative.py` only.
- C1 execution results plus the complete AC1/SC1/C1/J1 binding text.

In a real evaluation, the packet would instead distinguish the project/vault source revision and paths from the detached code-worktree root and evaluated commit.

## Independent verdicts

Both effective test executions reported `Ran 1 test` and exited `0`.

| Packet | C1 | J1 | AC1 |
|---|---|---|---|
| Positive | PASS | PASS | PASS |
| Negative | PASS | FAIL | FAIL—assertion coverage is insufficient |

Positive evidence:

- Product correctness: [product.py:4](/private/tmp/prd-coverage-activation/product.py:4) parses before [product.py:5](/private/tmp/prd-coverage-activation/product.py:5) writes. Malformed JSON raises a `ValueError` subtype before destination mutation.
- Assertion coverage: [test_positive.py:8](/private/tmp/prd-coverage-activation/test_positive.py:8) captures the original bytes, [line 10](/private/tmp/prd-coverage-activation/test_positive.py:10) asserts `ValueError`, and [line 11](/private/tmp/prd-coverage-activation/test_positive.py:11) compares the resulting bytes exactly with the original value.

Negative evidence:

- Product correctness remains supported by [product.py:4](/private/tmp/prd-coverage-activation/product.py:4) preceding the write at [product.py:5](/private/tmp/prd-coverage-activation/product.py:5).
- [test_negative.py:10](/private/tmp/prd-coverage-activation/test_negative.py:10) correctly asserts `ValueError`, but [line 11](/private/tmp/prd-coverage-activation/test_negative.py:11) checks only that the destination exists. It cannot distinguish unchanged bytes from corrupted or replaced bytes. Its green execution therefore supports C1 but not J1.

Unapproved gzip support affects neither verdict: it is outside SC1/AC1 and cannot create a failure or compensate for missing byte-equality evidence.

The initial sandboxed invocations encountered a temporary-directory permission error before useful product verification; each was retried once with ephemeral temporary-directory access and then exited `0`. No project, vault, or repository files were written.

This was a bounded live instruction-and-packet exercise—not a full unattended lifecycle test, end-to-end loop validation, or reliability benchmark.
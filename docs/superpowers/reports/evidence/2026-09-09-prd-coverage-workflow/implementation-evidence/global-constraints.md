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


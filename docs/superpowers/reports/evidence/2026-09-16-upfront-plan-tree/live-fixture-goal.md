# Fixture goal: local NDJSON record store

Build a tiny Python 3.9 standard-library command-line record store. No network services or third-party dependencies. Verification uses unittest. This is an isolated acceptance fixture, not a production repository.

Use exactly five initially active stages with these stable IDs and dependencies:
- S01: parse NDJSON into ordered records; no prerequisites.
- S02: persist parsed records into an atomic JSON store; depends on S01.
- S03: ingest text through parsing and persistence; depends on S02 (and consumes parsing from S01).
- S04: independent version/status function; no prerequisites.
- S05: command-line entry point consuming S03 and S04.

Acceptance:
AC-01: valid nonempty NDJSON records carry a nonempty string id and an object payload; malformed JSON, missing/empty ids or non-object payloads fail explicitly. Preserve order and duplicate IDs during parsing.
AC-02: persistence retains the first record for each id, appends new IDs in input order and reports how many records were added. Repeated input is idempotent. Save atomically using a temporary file and replace, retaining the previous store on failed validation. An empty/missing store starts empty.
AC-03: the ingest service accepts text and a store path, returns the number added, and preserves AC-01/02 error behavior.
AC-04: the independent status function returns the version string 1.0.
AC-05: the CLI reads NDJSON from stdin and a store path argument, prints the number added, and returns nonzero for invalid input without destroying the existing store. A --version invocation prints 1.0 without a store.

Record shared contracts in the initial plan. Internal module/helper names and test setup may be refined from actual predecessor code; no acceptance criterion requires a particular internal module structure. Initially propose an integer persistence return value; this is an internal contract choice, not immutable product acceptance. Keep future implementation detail bounded, not speculative code. The resulting stage tree must be complete before implementation begins.

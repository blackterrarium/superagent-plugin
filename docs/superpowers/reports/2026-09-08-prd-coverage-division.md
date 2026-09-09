# PRD coverage advice and implementation verification

Date: 2026-09-08
Status: source implementation and bounded validation complete; runtime installation not performed
Base: `43988140f661be997ba990fd339d46c8cf5b75a1`
Branch: `feat-prd-coverage-advice`

## Approved division

The user approved moving coverage advice to PRD writing and keeping a narrower delivery
verification step in implementation. The implementation adds `supercoverage`, invoked by
`superprd`, to propose required cases, expected outcomes and verification methods for author
review. Optional suggestions stay separate. An approved acceptance checklist lives in
`evaluation.md` with stable AC IDs, source references, owning C/J checks and approval provenance.

`supermeta` and `superauthor` preserve the agreement through the plan tree. `superrun` provides
it to implementers and reviewers. A leaf PR is responsible for its assigned items, while the
full agreement provides context; items assigned to later leaves are not failures of an earlier
PR. `supereval` verifies project acceptance against the written objectives and agreement.
Neither downstream consumer re-derives a comprehensive test inventory.

Review still checks whether assertions distinguish required outcomes. A test checking only
that a destination exists cannot establish that its bytes were preserved. Missing required
evidence is a delivery finding; an optional new format is advice. Conflicting or ambiguous
requirements return for author resolution, rather than becoming invented acceptance scope.
Ordinary product bug and code-quality review remains in effect.

The evaluator gets the full evaluation text, relevant PRD text, binding references, source
revisions, evidence roots and command results. Context resolution precedes the J/no-J split.
Missing required context fails closed even for command-only projects. Valid legacy projects
retain explicit criteria and binding notes without a forced checklist migration. Command-only
results do not establish assertion completeness.

## Validation performed

All commands below exited 0:

- `bash scripts/prd-lint-test.sh`: existing checks plus two compatibility assertions; zero failures.
- `bash scripts/supereval-test.sh`: eight runner scenarios; zero failures.
- `bash scripts/coding-loop-package-test.sh`: both suites run from copied Codex and Pi packages;
  zero failures in either package.
- All three `build-{codex,cursor,pi}-skills.sh` generation commands and `--check` parity checks.
- System skill-creator `quick_validate.py skills/supercoverage`.
- `git diff --check`.

The compatibility test appends acceptance and optional-suggestion tables to a valid project,
checks that lint still accepts the project, and checks that the shared parser emits only the
original two C/J records. This tests parser isolation, not semantic completeness or approval.
No production parser, runner, scheduler, model configuration or timeout policy changed.

### Fresh-context instruction checks

Five control agents read the old canonical `superprd` and `supereval` instructions. Five new
agents read the updated advisory, PRD, meta-planning, execution and evaluation instructions.
All were single-shot fresh-context subagents, inherited session model/effort, read-only,
without further delegation. These were small in-session development checks, separate from
all turns and identities of the closed 60-attempt evaluation. No claim of matched model pins
or matched token budgets with that experiment is made.

Common task: advise during PRD authoring for JSON and CSV, each requiring empty, one-row and
malformed-input cases, with general UTF-8 support and accented Latin as an illustration.
Under deadline pressure, give a concrete artifact before author approval. Then construct the
evaluator prompt/packet for a J objective referring to an approved contract, where a binding
note and AC1 require preserving destination bytes on malformed CSV. Distinguish absent
required assertions from an unapproved gzip suggestion.

Updated checks additionally asked about an existence-only destination assertion, legacy
inputs lacking a checklist, and propagation through the plan tree. They explicitly asked
agents to identify unspecified source documents/revisions rather than fabricate their text.
The source set and detailed prompts therefore differ between control and updated samples;
this is application checking, not a controlled performance experiment.

| Sample | Control observation | Updated observation |
|---|---|---|
| 1 | Six cases and general rule retained; exact mandated prompt omits binding note/AC1 | Draft agreement, unresolved decisions and separate suggestions; complete packet requirements; weak assertion finding; legacy compatible |
| 2 | Same context omission; draft C IDs introduced, labeled proposed | Same intended workflow; proposed check names remain unresolved |
| 3 | Same context omission; uses existing ID references | Same intended workflow; missing owning IDs explicitly unresolved |
| 4 | Same context omission; draft C IDs introduced, labeled proposed | Same intended workflow; proposed check definitions explicitly unresolved |
| 5 | Same context omission; uses existing ID references | Same intended workflow; proposed check definitions explicitly unresolved |

All five control responses produced useful coverage advice already. The observed control
failure was the prescribed context-loss path and the absence of a mandatory durable coverage
agreement, not an inability to think of the six cases. All five updated responses kept six
cases and a separate general UTF-8 rule, labeled outcomes/IDs needing resolution, declined
incomplete evaluation dispatch, rejected the existence-only assertion as insufficient, and
did not make gzip mandatory. Output shape varied (proposed IDs versus unspecified existing
IDs), but none claimed the incomplete draft was approved or READY. The root read all ten
responses rather than grading by keyword matches.

Representative verbatim control output (the instruction sentence was the same in all five):

> For each objective, inspect only the evidence paths named; answer PASS or FAIL against the written criteria with a two-sentence rationale citing file:line; never modify anything.

Control sample 1 explicitly observed:

> Current `supereval` explicitly excludes the contract notes and approved checklist from that prompt.

Updated sample 3 explicitly observed:

> Missing contents/revisions cannot be reconstructed from this simulation. Do not dispatch an incomplete packet: record no judged results; overall FAIL with `acceptance context unavailable`, retaining available command results/context error.

These simulations did not run an actual product, exercise live role transport, or prove
reliable acceptance. They also did not test a complete positive evaluation packet end to end.
The leaf-ownership correction below was checked by focused review, not by rerunning these ten
samples. No numerical improvement or new Gate B PASS is inferred.

### Independent source review

A separate fresh-context reviewer inspected the canonical diff, new skill, generated copies
and compatibility test. It found two issues:

1. Whole-branch review initially required every project item, which would reject early leaf PRs.
   Fixed to require only current-leaf assignments, with the full agreement retained as context.
2. Missing-context handling was initially inside the J-only path. Moved before the J/no-J split.

The reviewer re-read both fixes and applied three scenarios: leaf1 AC1 versus later-leaf AC2;
command-only green checks with a missing source; valid legacy command-only inputs. It reported
both issues resolved and no remaining material findings. Builds were regenerated after fixes.

## Limits and historical evidence

The prior staged Gate B result remains FAIL: baseline 4/30 versus staged 6/30 full passes,
with 11 invalid transports in the 60 attempts. It used `gpt-5.6-sol` at high effort. Its portable
closeout is commit `9add264` on `fix-acceptance-coverage`, and its private artifacts remain in
the separate vault. The current branch starts from main, not that failed staged candidate.

This design is a response to the observed failure modes; it is not validated by that study.
Author approval is not a proof of exhaustive coverage, and instruction checks are not a
substitute for a newly designed evaluation or installed-runtime testing. No installation,
cache refresh, scheduler launch, toy repair, historical regrade, external push or PR was
performed in this change. See the matching handoff for restart instructions.

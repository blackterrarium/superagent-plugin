# Stage 1/2 Codex and Pi verification — 2026-09-07

Scope includes Stage 1 (`superprd`) and the exact Stage 2 root goal
`2026-09-07-09_58-coding-loop-stage2.md`: `supermeta`, `supereval`, and supergoal autoconfirm.
The Stage 2 goal's implementation steps were already complete in 0.8.0. The original umbrella
design promised generated packages but limited live verification to Claude. This follow-up
fixes and exercises the Codex and Pi skill paths.

## Changes

- Ship `prd-lint.sh`, `supereval.sh`, `_common.sh`, and `_evalspec.sh` in both packages and
  resolve installed helpers there. Preserve source paths for nonpackaged scheduler helpers.
- Map the evaluator bridge profile to actual read-only inspection tools. Pi previously received
  the literal tool name `evaluator`, leaving the reviewer without evidence-reading tools.
- Use isolated native Codex role contexts, explicit model/effort overrides, and foreign-model
  relays. Pi PRD reviewers use blocking fresh bridge sessions.
- Scope supergoal autoconfirm to supermeta's child; deliver Pi skills to attended planner children.
- Require `pi-subagents >= 0.58.0`. `recommended` is a deprecated required alias; `off` fails.
  Generate all six named Pi SDD agents even when their pins inherit, omitting inherited fields.
- Add copied-package regression checks and a repeatable live acceptance runner.

## Results

| Check | Result |
|---|---|
| Bridge regression suite | 159 checks passed, 0 failures |
| Copied Codex/Pi package suites | 104 checks passed, 0 failures; 2 timeout checks skipped because this host lacks `timeout`/`gtimeout` |
| Codex, Pi, Cursor generated output checks | Passed |
| Changed shell syntax, Python parse, diff whitespace | Passed |
| Independent code review | No remaining important findings |
| Live Codex Stage 1/2 | PASS |
| Live Pi Stage 1/2 | PASS |
| Live Pi init plus inherited SDD agent dispatch | PASS |

Runtime: codex-cli 0.153.4; Pi 0.84.4; pi-subagents 0.63.0. Both parent sessions used
gpt-5.6-sol at medium effort and role children used high effort. Runtime receipts verify completed
role dispatch, including actual Codex child model/effort and fresh contexts, and Pi bridge
model/effort/tool profiles and successful completion.

Each harness used a copied standalone package, a disposable code repository, and an external
vault with local bare origins. `superprd` stopped at its approval gate without writing the vault;
approval then produced the project inputs and commits. `supermeta` scaffolded two goal plans
with child-only autoconfirm while the caller's `.superenv` remained false. `supereval` recorded
command and judged failures for round 1, then command and judged passes for round 2. The ledger
contains exactly those two verdicts. Pi init separately generated all six inherited SDD agent
definitions and dispatched `super-task-reviewer` through the installed extension to read a
random evidence value successfully.

The harness runs resumed retained successful phases after two test-runner assertion issues were
fixed (external-vault lint root and rejected-spawn receipt parsing). Final receipts were rechecked
with the current checker. A fixture ambiguity about seconds versus whole-minute evaluation
timeouts was corrected for future runs; the retained approved inputs passed the validator.

Local evidence retained on the validation host:

- `/private/tmp/coding-loop-codex-acceptance-1/result.json` and phase `.dispatch.json` receipts.
- `/private/tmp/coding-loop-pi-acceptance-1/result.json` and phase `.dispatch.json` receipts.
- `/private/tmp/coding-loop-pi-init-acceptance/result.json`.
- `/private/tmp/coding-loop-bridge-final-verified.log`.
- `/private/tmp/coding-loop-package-verified.log`.

Reproduction commands and runner options are in
[scripts/README.md](../../../scripts/README.md#coding-loop-harness-acceptance).

## Outstanding

These runs supply the code commit normally built by the existing inner loop. They do not
exercise scheduler operation or GitHub PR transport, so they do not close the original full
`supermeta → superagent-external → supereval` operator acceptance check on either harness.
Timeout enforcement was not revalidated on this host. Cursor received regenerated shared
changes but no live coding-loop run. Installed plugin caches have not been upgraded by this
verification.

Stage 3 remains separate: `superdiagnose`, `supercode`, `supercode-external`, the supervisor
and BUILDING gate, monitor integration, and the automatic fail/repair/pass end-to-end testbench.

# PRD coverage division — fresh-session handoff

Date: 2026-09-08
Status: source change implemented, validated and committed on a separate branch; not installed
Primary workspace: `/Users/eugene/src/superagent-plugin`
Implementation worktree: `/private/tmp/superagent-prd-coverage`
Branch: `feat-prd-coverage-advice`
Base: `43988140f661be997ba990fd339d46c8cf5b75a1`

## User direction

After the staged evaluation failed, the user proposed coverage advice during PRD writing.
The agreed division was: advise and resolve coverage with the author before implementation;
then verify delivery against the approved coverage agreement. Their authorization was:

> Yes update the system to use the new division. Write a handoff so it can be restarted from a fresh sessino.

The source work below is implemented. Do not restart the closed 60-attempt cohort or resume
installation of its failed staged candidate. This direction supersedes the old handoffs'
proposed contract-only inventory stage and their old Gate B-to-C/D continuation for that
candidate. Historical results and artifacts remain unchanged.

Suggested restart request:

> Continue from docs/superpowers/handoffs/2026-09-08-prd-coverage-division.md.
> Resume the PRD coverage division change from its committed branch. Inspect the completed
> validation, then handle integration and runtime activation of this version. Preserve the
> failed staged evaluation; do not rerun it or treat its old budget as a new evaluation budget.

## Read first

1. This handoff and `../reports/2026-09-08-prd-coverage-division.md` on the implementation branch.
2. `skills/supercoverage/SKILL.md` and the diff from base for `superprd`, `supermeta`,
   `superauthor`, `superrun`, and `supereval`.
3. Repository instructions and applicable skill/installation guidance before integration.
4. Only if historical analysis is needed: the closed report on `fix-acceptance-coverage`
   (`9add264`), at `docs/superpowers/reports/2026-09-08-staged-acceptance-review.md`.

Use `git -C /private/tmp/superagent-prd-coverage log -3 --oneline` to identify the source and
handoff commits. If the temporary worktree no longer exists, recreate from the local named
branch; do not rebuild the change from the old candidate. This handoff is also copied into
the primary checkout for discovery, without changing its source branch.

## Implemented behavior

- New `supercoverage` skill advises at PRD time: source-backed cases/general rules, expected
  results, meaningful verification methods, stable AC IDs and owning C/J IDs. Optional
  suggestions and unresolved decisions are separate. Standalone use returns a draft.
- `superprd` invokes it, adds semantic R8 readiness, includes checklist review in its existing
  zero-context review and approval gate, and records approval in `evaluation.md` and PRD
  decisions. R8 gaps cannot be waived by exhausting reviewer retries. Lint does not prove R8.
- Checklist stays under its own level-two heading in the existing three-file project format.
  AC IDs are not executable check IDs. Assertion-coverage obligations get explicit J checks.
- `supermeta` and shared `superauthor` preserve full conditions, source revision and ownership
  through the plan tree. Leaf reviews verify assigned items; whole-project evaluation belongs
  to `supereval`. Explicitly later-leaf items are not premature release blockers.
- `superrun` provides the agreement to implementers/reviewers and requires actual evidence
  against assigned items. It retains normal bug review and local/CI policy. No staged inventory.
- `supereval` receives full binding context and evidence roots, checks context even for C-only
  projects, and fails closed on missing context or missing J results. It retains one evaluator
  when J rows exist, none for valid C-only projects. It records per-item evidence alongside J
  results. Input ambiguity is reported, not silently reinterpreted.
- Existing explicit legacy requirements still apply without a fabricated approval or forced
  format migration. Suggestions do not silently become acceptance conditions.
- All Codex, Cursor and Pi builds regenerated from canonical sources. README updated.

## Validation and current limits

Passed: canonical PRD lint tests (including new parser-compatibility checks), eight runner
scenarios, copied-package checks for Codex/Pi, all three build parity checks, skill frontmatter
validation, and whitespace checks. See report for five control and five updated fresh-context
instruction checks, their actual observations and limitations. They are development checks,
not a new blind benchmark, and have no relationship to the old cohort's turn budget.

Independent review found and verified fixes for leaf-versus-project scope and C-only context
handling. No remaining material source-review findings. No claim of installed-runtime or
end-to-end reliability follows. The source change is the completed deliverable of this turn;
operational activation is the restart boundary.

## Next session

1. Inspect branch/head, working tree state and this report. Preserve unrelated primary dirt,
   especially `codex/plugins/superagent/.codex-plugin/plugin.json`, `html-docs/`, smoke report
   and older handoffs. Do not reset/stash/drop these to obtain a clean-looking tree.
2. Integrate the reviewed source via the repository's normal workflow. This session made no
   external push/PR and did not merge the implementation branch into main. Preserve the old
   `fix-acceptance-coverage` branch and reports. The generated files already match canonical
   sources; regenerate only after further source changes.
3. For runtime activation, use the supported plugin cachebuster/refresh flow, with the relevant
   plugin skill. Do not hand-edit installed dependency caches. Record source SHA, generated
   version, installed path and actual byte/skill resolution. Use a fresh runtime context to
   verify `supercoverage` discovery and the changed PRD/review paths.
4. Validate a small fully specified positive PRD-to-review example and an omitted/ineffective
   assertion example against the approved checklist before unattended operational use. The
   current simulations did not exercise a complete positive packet through live transport.
   Define any additional paid/model cohort's scope, controls and budget separately; no new
   large experiment or scheduled toy correction was launched by this handoff.

Source integration and runtime activation are distinct from proven model reliability. If
asked for a new benchmark, freeze a new design and identities suitable for this division;
measure advisory usefulness/author corrections separately from delivery-verification accuracy.
Do not apply the old checklist-reconstruction success metric as if it tested this workflow.

## Historical state to preserve

Old staged cohort: complete, all60 terminal, Gate B FAIL; baseline 4/30 and staged 6/30 full
passes, 11 invalid transports. Subject model `gpt-5.6-sol`, high effort. Old controller and
watcher exited; no polling or background evaluation was started here. User prefers event-driven
updates and explicitly requested no polling of long evaluations.

Private vault: `/Users/eugene/superagent-vaults/mdtoc-loop-test`, separate Git repo with no remote
at prior closeout; archive commits `1803229` and `926df611`. Do not copy private keys, raw packets
or detailed audits into plugin Git. Toy main remained `aaf0a84` at prior closeout and was not
modified in this turn. Historical commits are references, not a fresh claim of host state.

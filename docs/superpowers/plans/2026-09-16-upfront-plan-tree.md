# Upfront Plan Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plan the entire initiative upfront, refine implementation detail at stage entry, and replan only invalidated stages and affected dependents using an independently configured model.

**Architecture:** Retain the Markdown tree and scheduler states. Add shared stage contracts plus docs-only refinement/replanning skills; enforce dependencies, preparation receipts, and atomic batch activation through existing skill consumers and vault publication.

**Tech Stack:** Markdown skill contracts, Bash 3.2-compatible configuration/builders, Python 3.9 standard-library scenario validators, Git/GitHub, existing harness bridges.

**Spec:** [2026-09-16-upfront-plan-tree-design.md](../specs/2026-09-16-upfront-plan-tree-design.md). Read it with this plan. PT-01–PT-11 are the acceptance requirements; the schema, outcomes, and publication rules are binding.

## Global Constraints

- This document authorizes no implementation during the planning session.
- Canonical `skills/` and `templates/` are the source; regenerate Codex, Cursor, and Pi variants.
- Preserve Python 3.9 standard-library and macOS Bash 3.2 compatibility.
- Preserve existing vault, confirmation, locking, CI parking, integration, and C9 completion rules.
- At most one heavy skill per supervisor tick; authors/refiners/replanners dispatch no children.
- Preserve the executor's top-level CLI isolation and SDD review/test gates.
- Refinement cannot alter acceptance, scope boundaries, dependency edges, or shared contract semantics.
- Replanning never silently weakens the approved source agreement or resets completed history.
- Existing unmarked goals remain incremental; global config changes cannot migrate them.
- Do not add a separate graph database, speculative implementation code requirement, new scheduler
  status vocabulary, parallel goal execution, or an automatic legacy-goal conversion command.
- Preserve the existing Codex cachebuster, untracked handoffs, smoke report, html-docs, and historical
  evidence. Work in an isolated checkout at execution time; stage only task-owned paths.

## Starting state and delivery sequence

At planning time the checkout already contains the prior conversation's config-only changes:
PLAN_REFINER and REPLANNER model/effort keys in `.superenv`, canonical/generated defaults, builder
translations, and README documentation. They are reserved and unused. Carry these edits into
the implementation branch deliberately; do not duplicate or discard them. `.superenv` is ignored,
so tracked defaults—not that local file—must carry release behavior.

The current Codex manifest has an unrelated version cachebuster. Its existing `--check` difference
is not a new configuration failure. Verify clean generated output in isolation and preserve that
local customization. Coordinate overlapping edits with the Stage 3 coding-loop plan, especially
supergoal, supermeta, superloop, init, and package builders; do not assume unmerged work exists.

| Task | Deliverable | Depends on | Acceptance |
|---|---|---|---|
| 1 | Shared schema and executable review scenarios | current contracts | PT-02/04/06/09 |
| 2 | Complete upfront authoring and draft recovery | 1 | PT-01/02/09/10 |
| 3 | Bounded refinement and execution eligibility | 1–2 | PT-03/04/05 |
| 4 | Dependency impact and recoverable bulk replanning | 1–3 | PT-05/06/07/10 |
| 5 | Supervisor dispatch and active model configuration | 2–4 | PT-05/08/09/11 |
| 6 | Closeout, completion, and cross-entry recovery | 3–5 | PT-04/07/09/10 |
| 7 | Generated packages, integration fixture, and default rollout | 1–6 | all PT requirements |

Each task is a reviewable implementation unit, with its tests and generated skill changes in the
same change. Keep new mode opt-in until Task 7 passes. A task is not done merely because Markdown
contains the desired words: run its interpretation scenarios and relevant real script checks.

## File ownership

| File | Responsibility |
|---|---|
| `skills/superstage/SKILL.md` (new) | Shared upfront schema, graph validation, maturity, receipt validity, and impact rules |
| `skills/superrefine/SKILL.md` (new) | Prepare exactly one eligible stage, preserving commitments |
| `skills/superreplan/SKILL.md` (new) | Draft/review/publish one adopted repair or upfront batch |
| `skills/supergoal/SKILL.md`, `skills/superauthor/SKILL.md` | Whole-tree output; contract-level versus execution-level authoring; scratch recovery |
| `skills/superplan/SKILL.md`, `skills/supertraverse/SKILL.md` | Mode-sensitive navigation, readiness and existing legacy authoring/repair compatibility |
| `skills/superagent/SKILL.md`, `skills/superloop/SKILL.md` | Planning operation dispatch, persistence, and reconciliation without new scheduler states |
| `skills/superrun/SKILL.md`, `skills/superfinish/SKILL.md` | Preparation gate, findings impact, successor-safe closeout, delivery evidence |
| `skills/supermeta/SKILL.md` | Preserve goal/root report parsing; handle incomplete draft and resume identity |
| `skills/init/SKILL.md`, `templates/superenv.default` | Activate role pins and validate new-goal mode |
| `scripts/plan-tree-regression.py` (new) | Read-only scenario prompt and answer validation, patterned after lifecycle-regression.py |
| `scripts/plan-tree-config-test.sh` (new) | Offline effective-value/bridge/package assertions using existing loaders and bridge shims |
| `scripts/plan-tree-e2e.py` (new) | Operation/receipt validator for isolated actual-dispatch acceptance evidence |
| `scripts/lifecycle-regression.py`, `scripts/bridge-test.sh` | Preserve old lifecycle cases; extend actual bridge checks where needed |
| `scripts/build-codex-skills.sh`, `scripts/build-cursor-skills.sh`, `scripts/build-pi-skills.sh` | Package new skills and retain harness-specific defaults/role behavior |
| `README.md`, `scripts/README.md`, `docs/superagent-structure.html` | User lifecycle, settings, operations, migration, verification instructions |
| `docs/superpowers/reports/2026-09-16-upfront-plan-tree-verification.md` (new at execution) | Baseline, actual test results, acceptance receipts and remaining limitations |

Do not change scheduler shell code merely to add a planning sub-operation. Existing ready/running
states already support it. If actual fake/live tests expose a required transport change, record
the evidence and make the smallest corresponding change in `scripts/superagent-tick.sh` or
`scripts/launch.sh`; keep their status vocabulary intact.

## Task 1: Stage schema and regression scenarios

**Files:** Create superstage and plan-tree-regression.py; modify superauthor and supertraverse.
**Consumes:** Existing C1–C9 navigation and A2–A4 authoring rules.
**Produces:** The spec's root/stage fields and these shared clauses:

```text
S1: Resolve mode and active stage graph from the root and Plan links.
S2: Validate contracts, bounded unknowns, dependencies, and full-tree coverage.
S3: Classify preparation and execution eligibility from verified evidence.
S4: Classify refinement versus structural replan and determine impact boundaries.
S5: Validate preparation receipts and revision changes.
```

- [ ] Add scenario CLI flags `--skills PATH`, `--prompt`, `--answers FILE`, and `--cases NAME...`,
  matching lifecycle-regression.py conventions. `--prompt` prints facts and required output fields
  without expected values; `--answers` checks exact case membership, nonempty rule/evidence
  reasons, and required values. It runs no model/network calls itself. Malformed/missing answers
  return nonzero. Include validator self-tests using unittest in the same file via `--self-test`.
- [ ] Start with the following cases. Dispatch fresh read-only interpreters against the supplied
  skill directory; preserve baseline answers before edits. Interpret current missing behavior as
  baseline failure, not a license to invent a new protocol in the answer.

| Case | Facts | Required answer fields |
|---|---|---|
| `legacy_default` | No root marker; environment requests upfront | `mode: incremental` |
| `bounded_unknown` | Stage has contracts/scenarios; predecessor-dependent internal filenames unknown | `upfront_valid: true`, `executable: false` |
| `missing_architecture` | Stage says to choose its persistence architecture later without bounded decision criteria | `upfront_valid: false` |
| `open_provider` | Written consumer; provider's code PR remains open | `executable: false`, `done: false` |
| `declined_provider` | Provider declined; active consumer still requires its contract | `executable: false`, `done: false` |
| `dependency_cycle` | S01 depends on S02 and S02 depends on S01 | `outcome: BLOCKED` |
| `local_detail` | File/helper/test setup changes, all commitments preserved | `operation: refine`, `role: PLAN_REFINER` |
| `contract_break` | Required shared output behavior cannot be preserved | `operation: replan`, `role: REPLANNER` |

Use actual JSON assertions, for example:

```python
expected = {"mode": "incremental"}
actual = answers["legacy_default"]
assert actual["mode"] == expected["mode"]
assert isinstance(actual.get("reason"), str) and actual["reason"].strip()
```

- [ ] Write superstage S1–S5 with the spec's exact metadata, contract examples, ID/revision rules,
  dependency semantics, and explicit legacy fallback. Apply clauses inline; no independent output.
- [ ] Split superauthor's standard by maturity: stage contracts need behavioral specificity,
  dependency ownership, chosen approach, and verification scenarios; prepared plans need actionable
  task/file/test detail. Retain the prohibition on vague missing requirements, not on bounded
  implementation uncertainty. Preserve existing full-detail legacy plans.
- [ ] Add `PLAN WRITTEN — needs refinement` and upfront graph validation to supertraverse. Keep
  leaf/internal recognition and table columns unchanged. Never use status text alone as integration
  proof, and never treat an approved provider disposition as proof it delivered its contract.
  Until Tasks 3 and 5 supply preparation/routing, block experimental upfront execution explicitly;
  old consumers must not execute every written leaf merely because it is incomplete.
- [ ] Run `python3 scripts/plan-tree-regression.py --self-test`; then print prompts, obtain fresh
  answers, and run `--answers` for these cases. Run all existing lifecycle-regression cases as a
  separate suite. Record which are model-interpretation checks, not transport execution.
- [ ] Regenerate affected harness skills, review the diff, and commit only this unit.

## Task 2: Complete upfront authoring and resumable scratch drafts

**Files:** Modify supergoal, superauthor, superplan, supermeta, init, defaults, README; extend
plan-tree-regression.py. Add no implementation source under a goal.
**Consumes:** Task 1 contract-level authoring and graph validation.
**Produces:** Complete upfront tree + review report; explicit incremental alternative;
`supergoal --resume-draft <draft-index.md>`; compatibility report fields.

- [ ] Add scenarios for a root containing an unlinked active row, a multi-level complete tree,
  a draft interrupted before confirmation, resumed identical source, changed source, refused
  confirmation, and supermeta receiving DRAFT-INCOMPLETE. Required outcomes: no code execution,
  no vault publication before approval, no duplicate IDs/folder on resume, and no premature ledger row.
- [ ] Add `--planning-mode upfront|incremental` parsing without changing goal prose parsing or
  `--slug`/`--autoconfirm` semantics. Persist root mode; initialize the shipped option to incremental
  during implementation, switching the default only at Task 7. Validate values in init.
- [ ] In upfront mode author every sub-master/stage in scratch. Resolve references against the
  intended vault destinations. Every active scope obligation reaches a stage with requirements,
  contracts, scenarios, chosen approach, and bounded unknowns. Initial stage rows need refinement.
- [ ] Write the scratch draft index with goal source/digest, intended destination, drafted artifacts,
  stable IDs, completed review items and remaining work. On resume validate identity and current
  assumptions. Preserve scratch as needed; report DRAFT-INCOMPLETE rather than claiming supergoal
  complete. Do not launch planner children under supermeta's existing planner child.
  Snapshot prose input in scratch and reapply current confirmation/two-factor rules on resume;
  the existence of a saved draft is not publication approval.
- [ ] Review the entire tree through S2 and A4. Publish a durable review report that maps acceptance
  obligations to stages and verifies cross-stage contracts. Use the existing confirmation gate for
  the entire artifact set; commit it under A7 as one publication.
- [ ] Preserve these report fields and add the new ones without positional parsing:

```text
**Goal folder:** <absolute goal folder>
**Root plan:** <absolute root path>
**Planning mode:** upfront-v1
**Stages:** <number of active leaves>
**Tree review:** <absolute report path>
**Other files created/modified:** <enumerate every artifact>
```

- [ ] Supermeta accepts a complete upfront report with its existing Goal folder/Root plan fields.
  An incomplete result does not append a round; report its draft index for explicit resume. In
  resumed automation, reuse the same meta-plan/source and draft identity rather than allocating a
  second round or treating a partially published folder as success. Reconcile publication evidence
  after a lost response before repeating authoring.
- [ ] Keep `superplan` legacy behavior. In an upfront goal, a missing active stage is structural
  inconsistency requiring adopted repair, not an invitation to resume incremental planning.
- [ ] Run fresh authoring/recovery scenarios, existing prd-lint and package checks, and check the
  generated reports remain parseable by supermeta. Commit this unit with mode still opt-in.

## Task 3: Stage refinement and preparation validity

**Files:** Create superrefine; modify superstage, supertraverse, superrun; extend scenario cases.
**Consumes:** An upfront root and stable stage ID, source agreement, integrated predecessor evidence.
**Produces:** PREPARED / REPLAN-REQUIRED / BLOCKED reports and preparation receipts.

- [ ] Add scenarios for no-op preparation, predecessor-dependent detail changes, scope expansion,
  source revision change, unrelated HEAD movement, relevant contract movement, missing receipt,
  and a partially executed stage. Assert the first two preserve commitments; breaking changes
  request replanning; ongoing work is never overwritten in place.
- [ ] Implement `superrefine <root> <stage-id>` as a docs-only author. Validate graph, dependencies,
  absence of a batch barrier, and no execution already underway before drafting. Read the actual
  predecessor results and source requirements, then fill task/file/test details and verification.
- [ ] Record plan/source/code/dependency identity using S5. The plan-body digest excludes only the
  Preparation pointer line, avoiding a circular hash. All remaining plan bytes are bound. Preparation
  metadata must distinguish content amendments from a compatible baseline revalidation.
- [ ] Self-review that scope, acceptance, dependencies and contract semantics are unchanged. A clean
  result publishes leaf, receipt, and parent readiness together through A7. New structural facts
  instead publish a finding and return REPLAN-REQUIRED with no false readiness.

```text
**Outcome:** PREPARED | REPLAN-REQUIRED | BLOCKED
**Root plan:** <path>
**Stage ID:** <id>
**Stage revision:** <integer>
**Preparation:** <report path or none>
**Finding:** <report path or none>
**Files changed:** <explicit paths>
**Integration:** <docs PR or vault commit>
```

- [ ] Update execution selection: validate graph/barrier; skip satisfied closed work; require verified
  prerequisites; choose DFS-highest eligible stage; require a valid receipt for code execution.
  A stale receipt requests bounded revalidation; a relevant broken assumption requests replanning.
  No executable target with remaining dependencies returns BLOCKED/incomplete evidence, not DONE.
- [ ] Superrun rechecks the prepared target against synchronized code immediately before SDD. An
  unprepared eligible stage yields NEEDS-REFINEMENT with its exact root/ID, preserving existing
  manual execution semantics for incremental goals. Do not run refinement under EXECUTOR.
- [ ] Keep SDD's implementation rulings and code/spec review. Contract-preserving details may be
  resolved while executing; structural deviations return through the finding/decision path.
- [ ] Run the focused fresh-agent scenarios and the original lifecycle suite; regenerate skills;
  commit the bounded refinement unit.

## Task 4: Coordinated impact assessment and bulk replanning

**Files:** Create superreplan; modify superstage, supertraverse, superplan; extend regression cases.
**Consumes:** Adopted panel/user decision, root generation, active stages and dependency contracts.
**Produces:** One durable repair batch and one reviewed replacement generation.

- [ ] Add the impact fixture S01 → S02 → S03 → S05 plus independent S04. Test a local S02 change,
  a changed S02 output absorbed by S03 while preserving its output, and a foundational change.
  The middle case must report revised `[S02, S03]`, retained `[S04, S05]`; S01 remains delivered.
- [ ] Add interruptions before request commit, after request commit, during drafting, after batch
  publication but before loop update, and after a predecessor's late closeout. Add stale baseline,
  duplicate decision, missing record, divergent successors, partial-PR reuse, and split/merge cases.
- [ ] Extend C8 with batch request/reconciliation while preserving the legacy single-leaf case.
  Commit the decision record and Active replan pointer before further execution. Record at least:

```text
Decision ID, authority, rationale, source agreement revision
root path, from-generation, code baseline, vault baseline
origin stages, candidate dependency closure, active paths/revisions
per-stage retain/revise/disposition with evidence
predecessor PR/branch/worktree and integration disposition
draft paths, successor paths, retired-ID replacement mapping
resolution: pending | published | superseded | declined
published generation, publication decision marker, resolved publication PR/commit evidence
```

- [ ] `superreplan <root> <record>` assesses semantic impact with S4. It authors/self-reviews the
  whole affected set directly, retaining unchanged stage files. A changed interface does not imply
  every descendant requires rewriting: record where existing output contracts stop propagation.
- [ ] Preserve completed stages; add corrective IDs and update consumer prerequisites where needed.
  For unmerged partial work preserve original evidence and write remaining-task/PR-disposition
  instructions. Accept topology changes only through an explicit old/new ID mapping.
- [ ] Re-run S2 against the candidate whole tree, including retained stages. Publish replacements,
  all active links/dependencies, review report, batch resolution, root generation increment, and
  barrier clearing in one A7 change. Revised leaves need refinement. Do not expose draft successors
  through active Plan links or mark a partly published batch ready.
- [ ] Define replay from tracked evidence: pending → resume same draft; published generation matches
  active tree → resume new tree; mismatched/multiple publications → BLOCKED. Revalidate retained
  preparation across a new generation only with unchanged contract/source/stage evidence.
  Resolve the publication commit from the decision marker and artifact history; do not construct
  a self-referential record that requires its containing commit's hash before commit creation.
- [ ] Test legacy repair compatibility and batch invariants through fresh scenarios. Regenerate
  packages and commit this repair unit.

## Task 5: Supervisor operations and independent model routing

**Files:** Modify superagent, superloop, init, defaults, README, builders; create
plan-tree-config-test.sh; extend bridge-test.sh where its existing shims are reusable.
**Consumes:** Task 2 mode and Tasks 3–4 operation/result contracts.
**Produces:** Active PLAN_REFINER and REPLANNER dispatch with independently resolved effort/model.

- [ ] Add offline tests using the actual `_common.sh` loader and `role-bridge.sh` shims. Check process
  environment > repo `.superenv` > harness defaults for all four new keys. Use distinct test pins
  and efforts so accidental PLANNER/EXECUTOR reuse cannot pass. Include bridged roles, inherit,
  Cursor effort handling, and unavailable role definition/CLI failure.
- [ ] Add fresh supervisor scenarios for native/bridged refinement, adopted single-leaf repair,
  adopted batch repair, stale loop hints, and an unmarked legacy goal. Require selected role,
  operation, model/effort source, target, next state, and one-heavy-dispatch limit in each answer.
- [ ] Route by operation before dispatch. Retain native/bridged recipes and process isolation:

```text
legacy ordinary planning -> superplan / PLANNER
adopted legacy repair    -> superreplan / REPLANNER (C8 single-leaf publication)
upfront pending batch   -> superreplan / REPLANNER
upfront needs preparation -> superrefine / PLAN_REFINER
upfront prepared target -> WAITING FOR RUN -> superrun / EXECUTOR
upfront broken/missing tree -> BLOCKED / existing decision ladder
```

- [ ] Use WAITING FOR PLAN/PLANNING for both planning operations. Persist planning_operation,
  planning_target, planning_generation, and planning_record; reconcile tracked artifacts before
  using those hints. A state-only replan request is insufficient. Maintain heavy-step accounting
  and Final Report relay for each new skill, including post-dispatch sync/be-sure checks.
- [ ] After an integrated leaf, select/refine the next stage without calling PLANNER to discover
  new work. Handle NEEDS-REFINEMENT, REPLAN-REQUIRED, and BLOCKED ahead of generic none/success.
  An execution finding uses the existing decision ladder before adopting a structural batch.
- [ ] Activate reserved role keys and add init role-definition rows (`super-plan-refiner` and
  `super-replanner`) on Claude/Cursor; Codex uses spawn pins; Pi uses planner-style bridge
  processes with `--role plan-refiner` / `--role replanner`. Do not create unnecessary Pi agent files.
  Preserve config precedence and allow deliberately equal pins without silently coupling them.
- [ ] Remove reserved wording only after dispatch and init support exist. Add validated
  SUPER_PLANNING_MODE documentation, still opt-in until Task 7. Do not reinitialize the user's
  active checkout or install scheduler entries as part of implementing config support.
- [ ] Run `bash scripts/plan-tree-config-test.sh`, `bash scripts/bridge-test.sh`, and focused fresh
  scenarios. Verify generated builds and commit this routing unit.

## Task 6: Closeout, completion, and recovery across entry points

**Files:** Modify superfinish, superrun, supertraverse, superagent, superloop, supermeta;
extend plan-tree-regression.py and preserve lifecycle-regression.py cases.
**Consumes:** Active stage/receipt identity and adopted batch publication evidence.
**Produces:** Durable delivery receipts and consistent manual/tick/CI-resume behavior.

- [ ] Add cases for merged code with lost closeout response, CI-pending stage at replan request,
  late predecessor closeout, retained versus revised prepared stage after publication, discovery
  completion with no code PR, and stale completed ancestor hiding an unsatisfied dependency.
- [ ] Extend closeout evidence with delivered contract revisions and the stage/preparation identity.
  Link findings to affected contract/assumption IDs. A verified contract contradiction invalidates
  dependent preparation and is surfaced before the next dispatch; routine findings do not trigger
  a new planning cycle. Never accept findings as proof without the existing verified-evidence rule.
- [ ] A discovery stage closes only with its specified evidence and documented decision. If that
  decision invalidates other contracts, those stages follow the same adopted replan path.
- [ ] Protect active successors against predecessor closeout. Reconcile already merged changes before
  adding correction work. Explicitly account for old PRs, integration, and adopted dispositions in C9.
- [ ] Extend C9 to inspect root barrier, stage graph, active obligations, unresolved findings/batches,
  and prerequisite delivery in addition to integration evidence. Empty queues remain insufficient.
- [ ] Exercise manual superrun, scheduler recovery from PLANNING, and CI resume against the same
  stage/barrier rules. A resumed execution cannot merge obsolete work solely because it was queued
  before a batch request. Reconcile its actual branch/PR and adopted disposition first.
- [ ] For internal vaults, tracked changes land through A7 docs PRs; for external vaults, through
  the vault commit path. Never save authoritative preparation/repair data only in ignored loop state.
- [ ] Run both complete fresh-agent lifecycle suites, `bash scripts/vault-external-test.sh`,
  `bash scripts/coding-loop-package-test.sh`, and `bash scripts/prd-lint-test.sh`. Document any
  pre-existing failures separately. Regenerate skills and commit the integration unit.

## Task 7: Package verification, end-to-end evidence, and rollout

**Files:** Builders and generated codex/, cursor/, pi/; new plan-tree-e2e.py; README,
scripts/README.md, docs/superagent-structure.html; execution-time verification report.
**Consumes:** All earlier operation and evidence contracts.
**Produces:** Auditable PT-01–PT-11 evidence, documented settings, and the new-goal upfront default.

- [ ] Verify all new skills are present in copied distributable packages with no source-checkout
  fallback. Builders currently include SKILL.md files automatically; do not reference extra files
  unless their packaging is also implemented. Preserve distinct harness default pins.
- [ ] Add plan-tree-e2e.py as an evidence validator, not a replacement scheduler. Input is a run
  manifest naming the isolated fixture repository/vault, root, expected stage IDs/dependencies,
  expected role pins, dispatch logs, preparation/repair/closeout paths, and code/vault commits.
  `--manifest FILE` validates recorded receipts and prints a per-PT verdict; missing evidence is
  INCOMPLETE, inconsistent evidence is FAIL. `--self-test` tests fixture receipts and corrupted
  identities offline. No network or model calls are hidden inside validation.
- [x] Execute the spec's five-stage fixture through actual configured roles in an isolated test
  repository. Retain the goal source, generated complete tree, confirmation/auto-confirm evidence,
  scheduler/dispatch logs, real preparation changes, reviews/tests, and integration receipts.
  Run a normal path, a bounded-detail update, and an injected contract-break path as separate goals.
  Use existing approved test infrastructure when available; configure the concrete isolated target
  explicitly at execution time rather than guessing a production repository or scheduler slug.
- [x] Include a real refinement/replanning dispatch with distinct model/effort pins and one bridged
  role; separately test native pin recipes for each packaged harness using offline/fresh-agent
  checks. Report exactly which harnesses received live execution; do not generalize one harness's
  result to all four. Exercise both internal/external publication and one interrupted batch resume.
- [x] Verify quantitative lifecycle outcomes from receipts: normal path has zero post-publication
  structural authoring/replanning dispatches; each executed stage has preparation evidence; the
  injected break invokes REPLANNER and rewrites only the justified set. Report refinement time,
  replan time, amendments, retained/revised IDs, and available token usage without inventing data.
- [x] Run the final offline commands individually and record actual output/exit status:

```bash
python3 scripts/plan-tree-regression.py --self-test
python3 scripts/plan-tree-e2e.py --self-test
bash scripts/plan-tree-config-test.sh
bash scripts/bridge-test.sh
bash scripts/vault-external-test.sh
bash scripts/prd-lint-test.sh
bash scripts/coding-loop-package-test.sh
bash scripts/build-codex-skills.sh --check
bash scripts/build-cursor-skills.sh --check
bash scripts/build-pi-skills.sh --check
git diff --check
```

Print/run fresh-agent scenario suites separately with `--prompt` and `--answers`; self-tests
alone do not exercise skill interpretation. In a clean implementation checkout, generator checks
must pass; do not erase the original checkout's unrelated cachebuster to manufacture that result.

- [x] Write the verification report with a PT requirement → test/receipt → result matrix. Distinguish
  offline config tests, model-interpretation probes, and live transport. Resolve failures before
  claiming completion; unavailable live evidence leaves the corresponding acceptance incomplete.
- [x] Switch shipped SUPER_PLANNING_MODE to upfront after acceptance. Document explicit incremental
  selection, permanent legacy fallback, stage preparation, model keys, contract-change escalation,
  and batch recovery. Update the architecture reference to match the final behavior.
- [x] Review the complete change for requirement coverage and role/model correctness. Commit only
  owned files and integrate through the repository's normal PR policy. Version/release changes
  follow the actual release decision, not a speculative version embedded in this plan.

## Completion criteria

The initiative is complete when PT-01–PT-11 have recorded evidence, all generated packages are
consistent, legacy lifecycle checks still pass, new roles are actually dispatched, and the new
default is documented. A full tree that requires structural planning for each ordinary next stage,
or reserved config keys without consumers, does not satisfy this plan.

Implementation artifacts and evidence are produced during execution. This planning task writes
only this document and its linked design; it does not start a goal loop, change runtime skills,
merge a PR, or run live model/scheduler tests.

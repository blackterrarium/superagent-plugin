# Upfront plan tree with bounded stage refinement

**Date:** 2026-09-16
**Status:** Design recorded from the planning conversation; implementation has not started.
**Implementation plan:** [2026-09-16-upfront-plan-tree.md](../plans/2026-09-16-upfront-plan-tree.md)

## Objective and agreed direction

Produce a solid plan for the entire initiative before execution starts. Each stage has a
chosen approach, clear scope, dependencies, shared contracts, and acceptance obligations.
Exact implementation details may depend on the results of earlier stages. Resolve those
details through bounded stage refinement, preserving the stage's commitments.

Replanning changes commitments that evidence has invalidated. It affects the originating
stage and affected dependents, not automatically every later stage. Review potentially
affected dependencies; rewrite only plans that need to change. Stop propagation at a
contract that can still be fulfilled. Preserve completed work and add explicit corrective
work when it needs changing.

Refinement and replanning use separately configurable model and effort roles. The preceding
configuration change reserved `PLAN_REFINER` and `REPLANNER`; this initiative activates them.

## Existing behavior and implementation constraints

- `skills/supergoal/SKILL.md` writes one root with blank child Plan cells, after confirmation.
- `skills/superplan/SKILL.md` authors one sub-master or implementation leaf per invocation.
- `skills/superauthor/SKILL.md` A2/A3 currently require actual code and concrete test code for
  all implementation tasks. This must become sensitive to planning maturity.
- `skills/supertraverse/SKILL.md` owns tree shape, statuses, descent, C8 repair, and C9 completion.
- `skills/superagent/SKILL.md` alternates planning and execution; each tick dispatches at most
  one heavy skill. Planner dispatches have no children; executor dispatches run as top-level
  processes so their SDD workers can run synchronously.
- `skills/superfinish/SKILL.md` records findings but does not maintain downstream plan validity.
- The installed SDD skill already has a preflight conflict scan and local rulings. Preserve it;
  stage refinement supplies its executable input and does not replace code/spec review.
- Canonical Markdown skills are production logic. Generate Codex, Cursor, and Pi variants.
- Preserve Python 3.9 standard-library and macOS Bash 3.2 compatibility for verification tools.
- Preserve existing internal/external vault rules, confirmation rules, locks, PR integration,
  CI parking, and C9 integration evidence. Do not infer completion from empty queues.
- Preserve unrelated workspace edits and historical evidence. Coordinate with the separately
  planned coding-loop Stage 3 work; this initiative does not implement that outer loop.

## Architecture and ownership

Retain the Markdown plan tree as the authoritative work tree. Do not add a second scheduling
database or change the existing five-column progress table. Dependency edges augment the
tree: tree links express decomposition; dependency links express prerequisites.

Add `superstage` as a shared clause library, following supertraverse/superauthor conventions.
It defines upfront metadata, graph validation, maturity, preparation validity, and impact
assessment. It has no independent dispatch, writes, or report. Consumers apply its rules.
Keep its full normative schema in its SKILL.md so current package builders include it.

Add `superrefine` and `superreplan` as bounded docs-only authoring skills. Both author and
self-review directly without dispatching children. `superagent` chooses the operation and
role. `superrun` continues to own execution and `superfinish` owns closeout. `superplan`
remains the incremental author and the authoring primitive for explicit upfront tree edits;
it must not quietly create missing stages after an upfront tree was declared complete.

## Mode and compatibility

Add `SUPER_PLANNING_MODE=upfront` as the default for newly created goals, with
`incremental` as an explicit alternative. `supergoal --planning-mode upfront|incremental`
overrides that default for the new goal. Persist the choice on the root. Existing roots
without a mode marker are incremental regardless of the current environment value.

Use these exact root fields immediately below the title, before the progress table:

```markdown
**Planning mode:** upfront-v1
**Plan generation:** 1
**Active replan:** none
**Tree review:** [[reports/<review-file>]]
```

The table remains the first major section. Incremental roots may explicitly say
`**Planning mode:** incremental`; legacy roots need no rewrite. Unknown mode/schema markers
are BLOCKED. No automatic conversion of an active legacy goal is included. Users may keep
running it or start a new upfront goal that explicitly accounts for already delivered work.

Root generation advances only when an adopted structural replan publishes, not on ordinary
refinement, execution, or closeout. `Active replan` is a durable execution barrier, not a
replacement for the loop lock. A missing or malformed referenced record is BLOCKED.

## Stage contract and maturity

Every active upfront leaf has a unique stable stage ID. Sub-masters are grouping nodes, not
executable stages. Use the following metadata; `none` is an explicit empty dependency list:

```markdown
**Stage ID:** S02
**Stage revision:** 1
**Stage kind:** implementation
**Depends on:** S01
**Preparation:** none
```

Stage kind is `implementation` or `discovery`. IDs survive renaming and successor publication.
Splits/merges retire old IDs with an explicit replacement mapping; IDs are never reused.
The active tree resolves the current path for each ID. Historical successor/repair links are
not dependency targets. Duplicate IDs, missing links, cycles, unreachable active work, and
unresolved consumed contracts block publication and execution.

Every stage contains:

1. Goal, scope in/out, chosen approach and relevant components or known file paths.
2. Acceptance IDs/conditions and authoritative source revision, or explicit requirements for
   legacy source material without an acceptance checklist. Preserve acceptance ownership.
3. `Depends on` stages and a `Consumes / Produces` section. Name cross-stage contracts with
   stable IDs, semantic revision integers, provider IDs, behavior, and constraints. These
   include data/schema and ordering assumptions, not only function signatures.
4. Verification scenarios: distinguishing inputs, expected observations, and evidence method.
5. Assumptions with evidence, unresolved bounded details, resolution method, and invalidation
   triggers. Do not present predicted predecessor files or signatures as observed facts.
6. A task outline sufficiently concrete to implement after stage preparation.

Contract example:

```markdown
### Consumes
- C-INGEST@1 from S01: UTF-8 records with stable record IDs; malformed input is rejected.
### Produces
- C-STORE@1: records are persisted atomically; duplicate IDs do not duplicate records.
```

Upfront contracts need not include speculative implementation code, exact future line
numbers, helper names, or complete test bodies. Those belong in the prepared stage where
they aid execution. Concrete mandated algorithms or signatures remain binding when the
source actually specifies them. Missing scope, architecture, acceptance, or contract decisions
are not routine refinement. A discovery stage must specify the experiment, evidence, decision
criteria, and downstream assumptions it can invalidate; it is not an unbounded planning task.

Add row state `PLAN WRITTEN — needs refinement`. Use the existing
`PLAN WRITTEN — ready to execute` only after valid preparation. Internal rows retain existing
planning/partial-completion statuses; a linked sub-master is never an executable leaf.

## Upfront authoring and review

For upfront mode, supergoal drafts the root, every sub-master, every stage, goal directives,
and one whole-tree review report outside the vault. All active scope must reach a concrete
leaf, with no blank active Plan cells. Author in manageable sections and checkpoint scratch
work as needed; do not add nested subagents under supermeta's PLANNER child.

Add `supergoal --resume-draft <draft-index.md>` for an interrupted draft. The index records the
source and its digest, intended goal path, mode, stable IDs, drafted file paths, and outstanding
review work. Revalidate source identity and repository assumptions on resume. No live goal or
success report exists until review and the existing confirmation gate succeed. Source changes
require an explicit revised draft, not silent reuse. An incomplete draft reports `DRAFT-INCOMPLETE`
and its index path; supermeta must not append an iteration ledger row for that result.
Capture prose input as a scratch source snapshot. Resuming a draft does not itself grant approval:
reapply the human/two-factor gate to the completed current draft and current invocation.

Whole-tree self-review verifies full requirement coverage, concrete stage contracts, complete
links, compatible interfaces, dependency ordering, and acceptance ownership. A plan with
unbounded foundational uncertainty is not ready for publication. This review uses PLANNER;
independent pre-execution stage review occurs later through PLAN_REFINER.

Keep supergoal's human confirmation and two-factor auto-confirm semantics. Its confirmation
summary now covers the complete tree, bounded uncertainties, and review result. Publish all
initial artifacts in one A7 docs change. Preserve `Goal folder` and `Root plan` report fields
for supermeta; add mode, stage count, all artifact paths, and review report.

## Dependency-aware selection and stage refinement

Before choosing an upfront stage, validate the active graph and replan barrier. A prerequisite
is satisfied only by verified integrated delivery of the required contract (or explicit
verified non-code evidence for a discovery stage). An open PR is not satisfied. Declining
a provider does not satisfy its consumers; adopt a replan or scope disposition that accounts
for those consumers. Among eligible stages retain existing DFS priority order.

The next eligible unprepared stage goes to `superrefine`, using PLAN_REFINER. It reads the
stage, source agreement, current code, predecessor delivery evidence, and applicable findings.
It resolves bounded unknowns, updates task detail/tests/files, and repeats contract checks.
It cannot change acceptance, scope boundaries, dependency edges, or shared contract semantics.

Refinement outcomes are `PREPARED`, `REPLAN-REQUIRED`, or `BLOCKED`:

- PREPARED: increment stage revision if content changed; publish the updated unstarted leaf,
  a durable preparation report, parent readiness, and any verified findings under A7.
- REPLAN-REQUIRED: preserve the approved contract, publish the evidence/impact finding, and
  return it for the existing decision ladder. Do not repair architecture under a refiner pin.
- BLOCKED: required evidence is unavailable or inconsistent; do not guess or mark ready.

A preparation report records root generation, stage ID/revision, a SHA-256 digest of the
prepared plan body (excluding its Preparation pointer), code commit, source agreement
revision, consumed contract revisions, predecessor delivery receipts, relevant findings,
amendments, and the outcome. Hashing is evidence of identity, not proof of semantic correctness.

At execution entry, verify this record still matches. An unrelated HEAD advance causes a
focused relevance check, not automatic re-authoring. Relevant predecessor, contract, source,
or stage changes invalidate preparation. Record a refreshed validation receipt when the
new baseline is compatible. Lost/contradictory evidence blocks execution. Already running
stages resume through existing SDD/CI recovery; never overwrite their task history with an
in-place refinement. Local SDD rulings that preserve commitments remain allowed, and any
new contract break returns through the replan path.

Standalone superrun on an otherwise eligible unprepared stage returns `NEEDS-REFINEMENT`
with the stage/root and next operation. It does not prepare the stage under EXECUTOR.
Standalone skill invocations must disclose that model pins are applied by the dispatching
controller; a slash-command invocation cannot change its own model mid-session.

## Impact assessment and bulk replanning

Reuse C8's durable decision IDs, preserved predecessors, explicit PR disposition, and
idempotent publication. Legacy single-leaf repair remains supported; route adopted repair
authoring through REPLANNER. Upfront multi-stage repair uses a batch record in findings/.

An adopted request records the triggering evidence and authority, current root generation,
originating stages, candidate transitive dependent set, active paths/revisions, code/vault
baselines, existing PR/worktree dispositions, and `resolution: pending`. Commit the record
and root Active replan pointer before dispatching replanning. While pending, pause goal
execution, including direct superrun calls; an unaffected stage may be retained without
being executed during this publication barrier.

`superreplan <root> <record>` uses REPLANNER to assess the candidate closure. For each stage
record `revise`, `retain` with evidence of a preserved boundary, or an authorized disposition.
Propagate semantic changes along dependency edges; stop where a contract remains valid.
Independent later stages are retained. A foundational change may affect all remaining work.
Acceptance/source changes require author authority through the existing decision process;
the panel cannot silently weaken the approved agreement.

Draft all replacement stages, topology edits, contract revisions, dependency rewrites, and
the new whole-tree review as a batch outside active navigation. Checkpoint the same record
on interruption; do not publish individual successors as ready. Validate against current
baselines before activation; if they changed relevantly, reassess the affected set.

Publish in one tracked A7 change: all active Plan-link edits, replacement stages, mapped
dependencies/retired IDs, root generation increment, review report, record's published
generation and dispositions, and clearing Active replan. Superseded files and evidence remain.
All revised stages require preparation. Retained preparation survives only when a recorded
revalidation proves its stage, consumed contracts, and evidence unchanged in the new generation.

If code merged but closeout was interrupted, reconcile that delivery first. Completed stages
remain completed; any needed correction is a new stage ID with explicit consumer rewiring.
For partially executed unmerged work, the successor carries remaining tasks and PR/worktree
reuse/replacement instructions. Supersession alone never closes, merges, deletes, or forgives
an old PR. Late predecessor closeout cannot update a successor's active row.

The root generation and record's publication evidence make replay idempotent. A crash after
commit but before loop update resumes the published generation. A pending record or partial
working-tree publication cannot expose candidates to execution. Conflicting successors or
generations are BLOCKED. One active batch per goal; later discoveries join an unpublished
batch through an explicit record revision or create a subsequent batch after publication.
Locate the publishing commit through its recorded decision ID and tracked artifact changes;
do not require a commit to contain its own hash. A later report may record the resolved SHA.

## Supervisor and role routing

Keep `WAITING FOR PLAN`, `PLANNING`, `WAITING FOR RUN`, `RUNNING`, `WAITING FOR CI`,
`WAITING FOR INPUT`, and `DONE`. Do not add scheduler status strings for this feature.
For upfront roots, WAITING FOR PLAN means select the next required planning operation:
pending adopted batch → REPLANNER; eligible unprepared stage → PLAN_REFINER; valid prepared
stage → WAITING FOR RUN. A broken published tree → BLOCKED, not incremental gap filling.
After a completed leaf, select the next operation without dispatching PLANNER to author a
new stage. C9 still owns final completion. `none` with unsatisfied dependencies is not DONE.

Persist optional loop fields `planning_operation` (`refine`, `replan`, or `none`),
`planning_target`, `planning_generation`, and `planning_record`. They are recovery hints;
tracked tree/records override stale hints. PLANNING crash recovery restores WAITING FOR PLAN
and reconciles artifacts before redispatch. One heavy skill per tick still applies.

| Operation | Role | Default Claude model / effort |
|---|---|---|
| Initial tree / legacy incremental authoring / initial tree review | PLANNER | existing setting |
| Stage preparation, including its focused review | PLAN_REFINER | claude:sonnet / medium |
| Adopted structural repair and batch review | REPLANNER | claude:claude-opus-4-8 / high |
| Execution | EXECUTOR | existing setting |

Models and efforts are independently configurable. Defaults differ for refinement/replanning
on Claude, Codex, and Pi. Cursor retains portable inherit defaults and documents explicit pins.
Do not reject deliberate equal pins or cross-harness choices. Read environment > repo config >
shipped defaults. Do not silently fall back to EXECUTOR or PLANNER when a configured role
definition/bridge is unavailable. Init generates supported new role definitions; Pi uses
planner-style CLI dispatch for both new roles. Retain top-level executor isolation.

## Acceptance requirements

| ID | Requirement and evidence |
|---|---|
| PT-01 | An upfront supergoal publishes all stage/sub-master links and a passing whole-tree review before any code execution; confirmation and supermeta report compatibility remain intact. |
| PT-02 | A future stage with explicit contracts/scenarios and bounded implementation unknowns passes upfront review without fabricated code; missing architecture or acceptance decisions fail it. |
| PT-03 | Refinement resolves predecessor-dependent file/test/task detail, preserves commitments, uses PLAN_REFINER, and creates a verifiable preparation record. |
| PT-04 | Execution requires satisfied dependencies and valid preparation; stale source/contracts, provider PR open, declined provider with live consumers, and cycles block correctly. |
| PT-05 | A local implementation update causes no structural replan; a contract break goes to the decision ladder and REPLANNER with durable evidence. |
| PT-06 | Impact propagation revises affected consumers, stops at preserved contracts, retains independent later stages, and supports a whole-remaining-tree change when justified. |
| PT-07 | Bulk activation is all-or-nothing to execution; interruption before/after publication resumes the same batch; completed work and predecessor PR history are preserved. |
| PT-08 | Native and bridged model/effort pins work independently for both roles; missing definitions fail clearly; generated packages contain every new skill. |
| PT-09 | Roots without the upfront marker retain existing incremental traversal, single-leaf repair, and C9 behavior even if the new default is upfront. |
| PT-10 | Internal and external vault publication/recovery work; incomplete drafts, pending batches, open PRs, and missing evidence cannot produce a false completion. |
| PT-11 | A normal multi-stage fixture has zero post-publication structural planning dispatches; all later planning dispatches are recorded refinements. An injected contract break invokes only the adopted affected-batch replanning. |

## Verification and rollout

Start with read-only fresh-agent interpretation scenarios, then offline harness/config/package
checks, then an isolated end-to-end fixture using actual role dispatch. Report these evidence
levels separately. Do not treat a scenario answer or fake CLI log as proof of live model routing.

Use a five-stage dependency fixture: S01 → S02 → S03 → S05, with independent S04. In a
normal run, later stages resolve real predecessor details through refinement. In the deviation
run, S02 changes an output consumed by S03, but S03 can preserve its output to S05: revise
S02/S03, retain S04/S05. Also exercise an architectural change that invalidates all unfinished
dependent stages. Use isolated test repositories/vaults and retain receipts; do not alter
existing historical mdtoc or coding-loop evidence.

Record operation counts, role/model/effort receipts, preparation amendments, structural replan
reasons, rewritten/retained stages, elapsed time and available token usage. No performance
improvement is claimed without a comparable baseline. Ship the upfront default only after
these acceptance checks; intermediate commits keep the feature opt-in and legacy-safe.
Until preparation and operation routing are available, experimental upfront execution returns
BLOCKED explicitly; it must not fall through to the old written-leaf execution predicate.

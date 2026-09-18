---
name: superreplan
description: Use when an adopted repair must revise an upfront-v1 stage generation or publish a legacy C8 single-leaf successor from durable decision evidence.
license: MIT
related skills: superstage, superauthor, supertraverse, superplan
---

<!-- GENERATED FILE — Cursor build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-cursor-skills.sh. -->

> **Cursor build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` and `Monitor` tools do **not** exist on Cursor — treat
>   any residual mention of them as inapplicable and NEVER attempt those tool calls.
> - Tool mapping: "Agent tool" = spawn a subagent (synchronously — wait for its result). "Skill
>   tool" = invoke a skill. `AskUserQuestion` / `AskQuestion` = ask the user in chat (attended
>   sessions only — never in a headless tick). `EnterWorktree` = not available; in `github` mode,
>   use `git worktree` via shell. In `none` mode the canonical local-workspace override applies and
>   no git command is allowed. "Desktop routine" = a Claude Desktop feature,
>   not available — use an OS scheduler. A role whose `.superenv` value names another harness
>   (`codex:gpt-5.6-sol`, `pi:openai/gpt-5`, …) is BRIDGED: dispatch it with
>   `subagent_type: super-<role>` — the relay definition `superagent:init` generates — and treat a
>   reply beginning `BRIDGE-FAILED` as a failed subagent.
> - `${SUPER_PLUGIN_ROOT}` in commands and paths = this plugin's installed root directory (the one
>   containing `skills/` and `templates/`, two levels above this SKILL.md). Substitute its absolute
>   path wherever it appears.
> - Skill names are **unprefixed** on Cursor: `superagent:superplan` means the `superplan` skill
>   from this plugin, `superpowers:subagent-driven-development` means `subagent-driven-development`,
>   and so on — strip the `<plugin>:` prefix when looking a skill up. The `superagent` supervisor
>   skill itself carries `disable-model-invocation` and is invisible to model-driven skill lookup —
>   it is driven by reading its SKILL.md directly (the external tick's file-read prompt), never
>   invoked by name.

# Superreplan

`superreplan <root> <record>` is the docs-only repair author for one adopted C8 decision. For an
`upfront-v1` root it assesses and publishes one reviewed replacement generation. For an incremental
or unmarked root it preserves C8's single-leaf successor behavior. It never executes code or treats
unadopted evidence as authority to change commitments.

The dispatching controller assigns `REPLANNER` and its model/effort. A standalone invocation runs
under the current session and must say that it cannot change its own model pin. Author and self-review
directly: do not dispatch children, invoke an author/refiner/replanner, call superplan as another
skill, or consume a second heavy operation. The controller counts this as its one heavy skill for the
tick. Apply superauthor A1–A8 and supertraverse C8 inline, with the repair-specific routing and report
below.

## Resolve the durable request

Require an absolute root-plan path and durable record path. Do not infer either from the working
directory or a loop log. Resolve the root through superstage S1 in **active** context and reconcile
the record through supertraverse C8 before authoring. Read the adopted authority and rationale,
triggering evidence/finding, source agreement/revision, from-generation, code/vault baselines,
originating stages, candidate dependency closure, active paths/revisions, PR/branch/worktree state,
draft/successor paths, ID mappings, resolution, and publication evidence.

Return **BLOCKED** for absent or ambiguous authority; a missing/malformed referenced record;
duplicate live records claiming one Decision ID; divergent successors; a record for another
root/generation; contradictory source, Git, PR, or worktree evidence; multiple active batches; or a
dirty/partial state that cannot be reconciled uniquely. Repeated Decision-ID markers in the request,
checkpoint, publication, and evidence-resolution history are expected and are not duplicate live
records. Never manufacture a request from an informal prompt. An authorized source or acceptance
change remains bound to its adopting authority; replanning cannot silently weaken or reinterpret the
approved agreement.

Reconcile before drafting:

- A pending record with one unique scratch batch resumes those paths and the same stable Decision ID.
- A published record whose generation, active tree, cleared barrier, marker, and unique A7 history
  agree is already published. Return the active result and repair stale loop hints; do not republish.
- A relevant source, code, vault, active-path, contract, finding, PR, or worktree baseline change
  requires a fresh S4 assessment and recorded update before publication.
- A missing record, mismatched/multiple publication, or divergent candidate is **BLOCKED**.

Only authoritative committed/integrated files count. Ignore dirty working-tree edits that appear to
clear `Active replan` or expose successors. An internal docs branch/open PR is a candidate until it is
merged to authoritative main; an external-vault batch is a candidate until committed on the
authoritative branch. Keep execution paused while the committed root still names the pending record.

## Upfront-v1 impact assessment

For `upfront-v1`, require the root's `Active replan` to point to this pending record and its Plan
generation to equal the record's from-generation. Read the complete S1 active map and apply S2 to the
committed current generation. The active barrier intentionally prevents execution; it does not waive
graph validation or authorize incremental gap filling.

Apply superstage S4 from every originating stage through the graph-derived transitive dependent
closure as the initial assessment set. Compare old and proposed contract behavior at every edge, then
expand the final semantic affected set with any independently invalidated stage outside that closure
and record the evidence/reason for each expansion. Replace the request record's pending final-set,
expansion-reason, and per-stage disposition fields with this assessment before candidate review or
publication. Give every stage one disposition in the record:

- `revise` for unfinished affected work, with the evidence and exact
  acceptance/scope/approach/edge/contract/outcome change;
- `retain` for unfinished work outside the final semantic affected set, with evidence that its
  boundary remains fulfillable, including the contract where impact propagation stops;
- `completed-history` for delivered work, with verified delivery/integration evidence, preserved
  plan/closeout/contracts, and its effect on current consumers; or
- an authorized terminal disposition and its effect on every consumer.

Do not include completed-history stages in the retained unfinished set. A local file/helper/test-detail
change that preserves commitments belongs to superrefine and creates no batch; report that mismatch
instead of structurally rewriting it. A changed provider interface does not imply rewriting every
descendant: stop at the first output contract whose behavior/revision remains valid. Conversely,
expand beyond the graph closure when shared foundational evidence invalidates an otherwise independent
unfinished branch.

Preserve delivered stages and their history. If delivered behavior needs correction, add fresh stage
IDs for corrective work and rewire consumers; do not reopen or rewrite the completed stage. A split or
merge requires a total explicit old-ID to fresh-ID mapping, no reused retired ID, and no remaining
active dependency on a retired ID. For partially executed unmerged work, preserve the old plan,
closeout/task history, PR/branch/worktree and completed evidence. The replacement states remaining
tasks and records either verified reuse with repeated review/tests or an authorized replacement
disposition. This skill does not merge, close, delete, or forgive the predecessor PR.

## Draft the replacement generation

Draft outside active navigation. Use unique scratch paths and an explicit S1 intended-vault-path map.
Do not change any active Plan link while drafting. Author directly under superauthor A2/A3:

1. For each `revise` stage, write a replacement stage contract at the maturity required by S2. Keep
   the stable stage ID and increment Stage revision unless an authorized split/merge/correction
   retires it for mapped fresh IDs. Set `Preparation: none`; revised leaves require later refinement.
2. Write grouping/root candidates with all authorized Plan-link, dependency, contract, status, and
   retired-ID mapping changes. Preserve completed rows, their closeouts, accepted dispositions, and
   unrelated history. A retained stage file stays byte-identical except for its sole `Preparation`
   pointer to a recorded proposed-generation revalidation; readiness status changes belong in its
   parent row. Any other leaf-content change is a `revise` disposition, increments Stage revision,
   and requires a new receipt after later refinement.
3. Revalidate retained preparations for the proposed generation through S5. Preserve readiness only
   with a focused recorded revalidation proving the stage body/revision, source, relevant code,
   consumed contracts, provider receipts, findings, and other evidence unchanged. Otherwise set the
   stage to `PLAN WRITTEN — needs refinement`; an old-generation receipt alone is insufficient.
4. Write one new whole-tree review report for the proposed generation. It covers revised and retained
   stages, source/acceptance ownership, full scope, S4 dispositions, compatible interfaces,
   dependency order, topology mappings, completed/partial history, and preparation validity.

Checkpoint interruption state in the same pending record: unique draft paths, intended vault paths,
completed assessment/review items, and outstanding work. A checkpoint keeps `Resolution: pending`,
the old generation, and the Active replan barrier; publish that record-only checkpoint through A7 if
durability is needed. Never expose an individual draft through an active link or mark it ready.

## Review the whole candidate

Self-review directly under superauthor A4; do not dispatch a reviewer. Re-run superstage S2 in
**candidate** context against the complete proposed tree, including retained stages, through the
explicit path map. Require all of the following before publication:

1. Every stage has exactly one evidenced `revise`, `retain`, `completed-history`, or authorized
   terminal disposition; completed stages are reported separately from retained unfinished stages,
   every expansion beyond the initial graph closure is justified, and each propagation stop cites a
   preserved contract.
2. The candidate preserves delivered work and acceptance/source authority. Corrective work,
   split/merge mappings, consumer rewiring, and partial-PR dispositions are complete.
3. Every revised stage is contract-valid with `Preparation: none`; every retained ready stage has a
   generation-bound S5 revalidation. No draft successor is reachable from the committed old tree.
4. The new whole-tree review passes and S2 validates every candidate path, ID, edge, contract, and
   active obligation. Revalidate request baselines immediately before publication; relevant drift
   returns to assessment.

A candidate failure stays in scratch/pending state. Do not publish a partial batch, clear the barrier,
or claim readiness.

## Publish one generation

Use superauthor A6/A7 to publish one complete tracked change containing all replacement/new stages;
all grouping/root active-link and dependency edits; total retired-ID mappings; any retained
preparation revalidation receipts/statuses; the new whole-tree review; and the record's final
per-stage dispositions, successor paths, `Resolution: published`, and published generation. Increment
the root generation exactly once, point `Tree review` to the new report, and set `Active replan: none`
in that same change. Preserve every superseded plan, finding, closeout, receipt, and PR reference.

Use the stable Decision ID as the **publication decision marker** in the record and A7 commit/PR
description. Do not require the record to contain its own commit hash. Its resolved publication
PR/commit field may say `pending resolution from <Decision ID> marker and tracked artifact set` in the
containing change; after integration, reconciliation locates exactly one publishing commit from Git
history and a later report/record update may store the resolved evidence.

A file write is not publication. For an internal vault under protected-main A7, merge the complete
docs PR to authoritative main and synchronize it before activation. When A7 permits a direct internal
commit, or for an external vault, commit the complete batch on the configured authoritative branch
and verify that commit there. Then re-run S1/S2 in **active** context and reconcile the marker,
generation, record, review, links, and cleared barrier from authoritative committed history. Until all
checks pass, the old pending generation remains the only authoritative active view, and it is
non-executable under the pending barrier. Require exactly one history change that performs the
complete old-to-new publication transition. Request, checkpoint, or later evidence-resolution commits
may repeat the Decision ID and do not count as publications. A mixed tree, multiple matching
publication transitions, mismatched generation, or missing artifact is **BLOCKED**.

After verified publication, repair stale loop recovery hints to the published generation. Do not run
or refine a stage in this authoring invocation. A crash before loop update resumes the verified new
tree without another publication.

## Incremental/legacy single-leaf wrapper

For an incremental or unmarked root, require a valid legacy C8 record and one `repair requested` row.
Apply supertraverse C8's legacy publication, superauthor A2/A3/A6/A7, and superplan's legacy
self-review, routing, parent-row, and reporting clauses directly. Do not invoke superplan or add
upfront generation, stage-ID, preparation, or batch fields.

Write one fresh implementation leaf with `Supersedes` and `Repair` links, authorized corrections,
remaining work, regression checks, and the explicit predecessor PR/worktree disposition. Preserve the
predecessor and completed evidence. Atomically publish the successor link, legacy record fields, row
status/PR/comments, and history under C8. Replays reuse the Decision ID and unique successor; missing,
divergent, or partial evidence is **BLOCKED**. This wrapper changes the authoring role to REPLANNER but
does not change legacy tree shape, source agreement, integration duties, or C9 completion rules.

## Report

Return exactly this shape, using `none` for absent values and listing every file changed:

```text
**Outcome:** PUBLISHED | ALREADY-PUBLISHED | REFINEMENT-ONLY | BLOCKED
**Root plan:** <path>
**Decision ID:** <id>
**Record:** <path>
**From generation:** <integer or none>
**Published generation:** <integer or none>
**Revised stages:** <ids or none>
**Retained stages:** <ids or none>
**Completed stages:** <ids or none>
**Retired/replacement mapping:** <mapping or none>
**Review:** <path or none>
**Predecessor PR dispositions:** <entries or none>
**Files changed:** <explicit paths or none>
**Integration:** <merged docs PR, authoritative vault commit, or none>
**Publication marker:** <Decision ID or none>
**Resolved publication evidence:** <PR/commit or pending marker reconciliation>
```

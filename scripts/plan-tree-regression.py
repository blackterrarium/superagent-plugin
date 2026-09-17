#!/usr/bin/env python3
"""Print upfront plan-tree probes or validate fresh-interpreter JSON answers.

This program performs no model, network, Git, or fixture calls. Give ``--prompt``
output to a fresh read-only interpreter, save its single JSON object, and check it
with ``--answers``. Results exercise interpreted skill contracts, not transport.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest


CASES = (
    ('legacy_default',
     'The root has no Planning mode marker. The current environment requests upfront mode. '
     'Resolve the mode without rewriting the root.',
     {'mode': 'incremental'}),
    ('invalid_trailing_planning_mode',
     'A new supergoal invocation ends with `--planning-mode speculative`. It has no prior scratch '
     'or vault artifacts. Classify parsing and side effects.',
     {'outcome': 'BLOCKED', 'publication': 'none', 'code_execution': False}),
    ('incremental_mode_persisted',
     'A new supergoal resolves planning mode to incremental and completes root authoring. Classify '
     'the persisted root marker; this is not an unmarked legacy root.',
     {'mode': 'incremental', 'root_mode_marker': 'incremental'}),
    ('bounded_unknown',
     'An upfront implementation stage fixes scope, architecture, acceptance, contracts, and '
     'verification scenarios. Internal filenames depend on predecessor evidence; the stage '
     'bounds those names, says how preparation will resolve them, and has no preparation receipt.',
     {'upfront_valid': True, 'executable': False}),
    ('missing_architecture',
     'An upfront stage says its persistence architecture will be chosen later. It gives no '
     'bounded alternatives, decision criteria, evidence method, or discovery-stage contract.',
     {'upfront_valid': False}),
    ('open_provider',
     'S02 consumes C-INGEST@1 from S01. S01 has a closeout, but its code PR remains open and '
     'the merge commit is absent from main. Classify S02 and whole-goal completion.',
     {'executable': False, 'done': False}),
    ('declined_provider',
     'S01 was declined with an approved disposition. Active S02 still consumes C-INGEST@1 from '
     'S01, and no adopted replan removes or replaces that contract. Classify S02 and completion.',
     {'executable': False, 'done': False}),
    ('dependency_cycle',
     'The active upfront graph has S01 Depends on S02 and S02 Depends on S01. All files and stage '
     'IDs otherwise exist. Classify validation/selection.',
     {'outcome': 'BLOCKED'}),
    ('unlinked_active_row',
     'An upfront root has an active, incomplete progress-table row whose Plan cell is blank. Its '
     'other rows link to valid stages. No authorized disposition removes the blank row. Classify '
     'the candidate graph and whether authoring may fill it incrementally.',
     {'upfront_valid': False, 'outcome': 'BLOCKED'}),
    ('multi_level_complete_tree',
     'A scratch upfront root links to two sub-masters. Together their linked leaves have unique '
     'stable IDs S01, S02, and S03, complete S2 contracts, compatible dependencies, and a passing '
     'scratch tree review resolved through the intended-vault path map. Every initial leaf has '
     'Preparation: none and its parent row says PLAN WRITTEN — needs refinement.',
     {'upfront_valid': True, 'stages': 3, 'executable': False}),
    ('draft_interrupted_before_confirmation',
     'An upfront supergoal has captured a prose-source snapshot and digest, intended vault paths, '
     'drafted root/sub-master/stage/review artifacts, stable IDs, completed review items, and '
     'remaining confirmation work in a scratch draft index. It is interrupted before confirmation.',
     {'outcome': 'DRAFT-INCOMPLETE', 'publication': 'scratch', 'code_execution': False}),
    ('resume_identical_source',
     'supergoal --resume-draft receives an interrupted scratch index whose saved source digest, '
     'current source, intended destination, and repository assumptions all still match. The index '
     'already names its root/sub-master/stage/review artifacts and stable IDs. Confirmation has not '
     'been granted.',
     {'outcome': 'DRAFT-INCOMPLETE', 'publication': 'scratch', 'draft_action': 'resume',
      'duplicate_stage_ids': False, 'duplicate_goal_folder': False}),
    ('resume_changed_source',
     'supergoal --resume-draft receives an interrupted index for a file-backed goal, but the current '
     'source file digest differs from the digest saved in that index. No revised draft has been '
     'explicitly made.',
     {'outcome': 'DRAFT-INCOMPLETE', 'publication': 'scratch', 'draft_action': 'revise',
      'code_execution': False}),
    ('confirmation_refused',
     'An upfront draft passed S2 and A4 review, but the human declines the whole-artifact '
     'confirmation gate. The two-factor auto-confirm condition is absent.',
     {'outcome': 'DRAFT-INCOMPLETE', 'publication': 'scratch', 'code_execution': False}),
    ('supermeta_draft_incomplete',
     'supermeta receives a PLANNER result containing DRAFT-INCOMPLETE and an explicit draft-index '
     'path. It has no complete Goal folder/Root plan publication evidence.',
     {'outcome': 'DRAFT-INCOMPLETE', 'ledger_appended': False}),
    ('local_detail',
     'New predecessor evidence changes only file placement, helper names, and test setup. Scope, '
     'acceptance, dependency edges, shared contract behavior, and all other commitments survive.',
     {'operation': 'refine', 'role': 'PLAN_REFINER'}),
    ('contract_break',
     'Verified evidence shows a required shared output behavior cannot be preserved. Downstream '
     'consumers rely on that semantic contract.',
     {'operation': 'replan', 'role': 'REPLANNER'}),
    ('preparation_noop',
     'A dependency-eligible, unstarted stage has a complete upfront contract. Current source, code, '
     'predecessor delivery, contracts, and findings resolve no additional task, file, or test detail. '
     'Its initial Stage revision is 1. The refiner attaches its first PREPARED receipt without '
     'changing the plan body.',
     {'outcome': 'PREPARED', 'stage_revision': 1, 'commitments_preserved': True,
      'amendment_kind': 'none'}),
    ('predecessor_detail_preparation',
     'A dependency-eligible, unstarted stage receives verified predecessor delivery evidence that '
     'resolves its bounded file placement, helper name, and distinguishing test setup. Its scope, '
     'acceptance, chosen approach, dependencies, and contract behavior remain unchanged. Its initial '
     'Stage revision is 1.',
     {'outcome': 'PREPARED', 'stage_revision': 2, 'commitments_preserved': True,
      'amendment_kind': 'content-amendment'}),
    ('scope_expansion_during_preparation',
     'Preparation evidence shows the stage must add a user-visible export that is outside its approved '
     'scope boundary. The stage is unstarted.',
     {'outcome': 'REPLAN-REQUIRED', 'commitments_preserved': False,
      'in_place_overwrite': False}),
    ('source_revision_changed',
     'The authoritative source agreement revision now changes an acceptance condition assigned to an '
     'unstarted prepared stage. Its old receipt still names the prior source revision.',
     {'outcome': 'REPLAN-REQUIRED', 'executable': False,
      'in_place_overwrite': False}),
    ('unrelated_head_advance',
     'An unstarted prepared stage has a valid receipt. Repository HEAD advanced only through the '
     'docs-only publication of another goal; a focused comparison finds no source, stage, predecessor, '
     'contract, finding, or relevant code change. Its current Stage revision is 1.',
     {'outcome': 'PREPARED', 'stage_revision': 1, 'commitments_preserved': True,
      'amendment_kind': 'compatible-baseline-revalidation'}),
    ('relevant_contract_advance',
     'An unstarted prepared consumer still names C-INGEST@1, but verified provider evidence now '
     'changes C-INGEST behavior and advances it to semantic revision 2.',
     {'outcome': 'REPLAN-REQUIRED', 'executable': False,
      'in_place_overwrite': False}),
    ('missing_preparation_receipt',
     'A valid upfront-v1 root has no Active replan and a complete active graph. S02 is the first '
     'DFS-eligible unstarted leaf with satisfied prerequisites, but its Preparation field is none. '
     'superrun is invoked directly on the root under the current consumer rules.',
     {'outcome': 'NEEDS-REFINEMENT', 'executable': False, 'code_execution': False}),
    ('partially_executed_stage',
     'A stage has an execution closeout or open code PR showing that implementation already began, '
     'while its remaining work is unresolved. A caller asks the refiner to prepare it in place.',
     {'outcome': 'BLOCKED', 'in_place_overwrite': False}),
    ('manual_superrun_pending_batch',
     'A direct manual superrun invocation reads an upfront-v1 root whose Active replan points to a '
     'committed pending batch. S02 was prepared before the request, but its disposition is unresolved. '
     'No implementation or merge has begun in this invocation.',
     {'outcome': 'BLOCKED', 'executable': False, 'code_execution': False,
      'merge_allowed': False}),
    ('execution_snapshot_historical_digest',
     'S02 enters execution at Plan generation 4, Stage revision 2, with preparation receipt R2 and '
     'prepared-plan digest H2. Its execution-entry vault revision V4 and reviewed code revision C4 are '
     'known. After code integration, superfinish inserts its closeout note into the current stage file, '
     'so the current bytes no longer hash to H2. Classify the required closeout identity check.',
     {'execution_snapshot_required': True, 'historical_snapshot_required': True,
      'digest_basis': 'execution-snapshot'}),
    ('merged_lost_closeout_response',
     'S01 code PR 71 and its tracked closeout delivery receipt were already integrated. The receipt '
     'binds generation 4, S01 revision 2, preparation R1/digest H1, PR 71 and its merge commit, and the '
     'active parent row links that same report. The caller lost superfinish\'s response and retries from '
     'a fresh context. Here outcome classifies the closeout recovery handler (reuse and continue), '
     'not whether the whole goal is done.',
     {'outcome': 'continue', 'duplicate_publication': False,
      'delivery_receipt_reused': True, 'code_execution': False}),
    ('ci_pending_replan_request',
     'S02 entered execution from generation 4 and queued CI on PR 72. Before CI completed, adopted '
     'batch B-72 was committed and root Active replan points to it; B-72 records PR 72, branch, '
     'worktree, run ids, and an unresolved S02 disposition. CI is now green and the supervisor has the '
     'old CI resume packet.',
     {'merge_allowed': False, 'execution_paused': True, 'pr_evidence_preserved': True,
      'next_state': 'WAITING FOR PLAN'}),
    ('impact_local_s02_detail',
     'An upfront-v1 root is at Plan generation 7 with no Active replan. S01 revision 3 is delivered. '
     'The unfinished stages are S02 revision 2 depending on S01, S03 revision 4 depending on S02, '
     'S04 revision 1 with Depends on none, and S05 revision 2 depending on S03. Verified evidence '
     'changes only S02 internal file placement and test setup; S02 acceptance, scope, chosen approach, '
     'dependencies, required outcome, and C-S02@1 behavior all remain fulfillable. No structural '
     'decision has been adopted.',
     {'operation': 'refine', 'role': 'PLAN_REFINER', 'batch_created': False,
      'execution_paused': False}),
    ('impact_absorbed_at_s03',
     'An upfront-v1 root is at Plan generation 7. S01 revision 3 is delivered. The unfinished stages '
     'are S02 revision 2 depending on S01 and producing C-S02@1, S03 revision 4 depending on S02 and '
     'producing C-S03@2, S04 revision 1 with Depends on none, and S05 revision 2 depending on S03 and '
     'consuming C-S03@2. An adopted decision authorizes C-S02 to advance to revision 2. Verified '
     'evidence shows S03 must change to consume C-S02@2 but can still produce exactly C-S03@2; S04 '
     'does not consume either contract. The tracked request names origin S02 and candidate closure '
     '[S02, S03, S05].',
     {'revised_stages': ['S02', 'S03'], 'retained_stages': ['S04', 'S05'],
      'completed_stages': ['S01'], 'completed_disposition': 'completed-history',
      'propagation_stop': 'S03'}),
    ('impact_foundational_change',
     'An upfront-v1 root is at Plan generation 7. S01 revision 3 is delivered. The unfinished stages '
     'are S02 revision 2 depending on S01, S03 revision 4 depending on S02, S04 revision 1 with '
     'Depends on none, and S05 revision 2 depending on S03. An adopted source-author decision changes '
     'the shared storage architecture named by the acceptance and chosen approach of every unfinished '
     'stage. Verified evidence says none of S02, S03, S04, or S05 can retain its current required '
     'outcome or shared contracts; no evidence changes delivered S01. The tracked request started '
     'with origin S02 and graph-derived candidate closure [S02, S03, S05]; S04 is outside that '
     'initial closure.',
     {'revised_stages': ['S02', 'S03', 'S04', 'S05'], 'retained_stages': [],
      'completed_stages': ['S01'], 'completed_disposition': 'completed-history',
      'propagation_stop': 'none'}),
    ('replan_before_request_commit',
     'An upfront-v1 root is at Plan generation 7 with Active replan none. S01 revision 3 is delivered; '
     'S02 revision 2, S03 revision 4, S04 revision 1, and S05 revision 2 are unfinished. A panel '
     'adopted decision D-204, but neither a tracked decision record nor a tracked root Active replan '
     'pointer exists. The loop log alone names D-204. A tick is about to dispatch replanning.',
     {'outcome': 'continue', 'publication': 'none', 'dispatch': 'none',
      'execution_paused': True}),
    ('replan_after_request_commit',
     'An upfront-v1 root is at Plan generation 7. S01 revision 3 is delivered; S02 revision 2, S03 '
     'revision 4, S04 revision 1, and S05 revision 2 are unfinished. One authoritative tracked change '
     'created decision record D-205 with Resolution pending and set Active replan to that record. The '
     'record captures source revision 11, code baseline c7, vault baseline v7, active paths/revisions, '
     'candidate closure, and PR/worktree dispositions. Its final semantic affected set, expansion '
     'reasons, and per-stage dispositions are present as pending; it has no draft paths yet.',
     {'outcome': 'continue', 'resolution': 'pending', 'dispatch': 'superreplan',
      'execution_paused': True}),
    ('replan_drafting_interrupted',
     'An upfront-v1 root is at Plan generation 7 with Active replan pointing to tracked record D-206. '
     'S01 revision 3 is delivered; S02 revision 2, S03 revision 4, S04 revision 1, and S05 revision 2 '
     'are unfinished. D-206 has Resolution pending, matches source revision 11/code c7/vault v7, and '
     'lists unique scratch drafts and intended vault paths for S02 and S03 plus a generation-8 review. '
     'No draft path is an active Plan link and no publication marker exists. The authoring session '
     'ended after self-review began.',
     {'outcome': 'continue', 'publication': 'scratch', 'replay_action': 'resume-draft',
      'execution_paused': True}),
    ('replan_published_before_loop_update',
     'The loop still carries planning_generation 7, planning_record D-207, and PLANNING. The tracked '
     'upfront root is now at Plan generation 8 with Active replan none. One A7 change marked D-207 '
     'Resolution published with published generation 8 and publication decision marker D-207, changed '
     'all authorized active links/dependencies, added the passing generation-8 review, and retained '
     'the superseded files. Active S01 revision 3 is delivered; S02 revision 3, S03 revision 5, S04 '
     'revision 1, and S05 revision 2 are unfinished. Git history contains exactly one complete '
     'old-to-new publication transition with that decision marker; request/checkpoint commits may '
     'also contain D-207. The record leaves resolved publication commit evidence for later '
     'reconciliation.',
     {'outcome': 'continue', 'resolution': 'published', 'replay_action': 'resume-published',
      'duplicate_publication': False, 'execution_paused': False}),
    ('late_predecessor_closeout',
     'An upfront-v1 root is at Plan generation 8 with Active replan none. Decision D-208 is published. '
     'S01 revision 3 is delivered; S02 revision 3, active S03 revision 5, S04 revision 1, and S05 '
     'revision 2 are unfinished. Old S03 revision 4 had partially executed on PR 88; its replacement '
     'S03 revision 5 is the active Plan link and the record preserves PR 88 disposition and remaining '
     'tasks. After publication, a late closeout for old S03 revision 4 arrives and names PR 88. It '
     'does not prove integration of active S03 revision 5.',
     {'outcome': 'continue', 'late_closeout_action': 'preserve-history',
      'active_link_changed': False, 'successor_closed': False}),
    ('replan_stale_baseline',
     'An upfront-v1 root is at Plan generation 7 with Active replan pointing to D-209. S01 revision 3 '
     'is delivered; S02 revision 2, S03 revision 4, S04 revision 1, and S05 revision 2 are unfinished. '
     'The pending record and drafts captured source revision 11, code baseline c7, and vault baseline '
     'v7. Before publication, source revision 12 changes S03 acceptance and authoritative vault '
     'baseline v8 changes its active path. No reassessment records those changes.',
     {'outcome': 'continue', 'publication': 'scratch', 'replay_action': 'reassess',
      'execution_paused': True}),
    ('replan_duplicate_decision',
     'An upfront-v1 root is at Plan generation 7 with Active replan pointing to findings/D-210-a.md. '
     'S01 revision 3 is delivered; S02 revision 2, S03 revision 4, S04 revision 1, and S05 revision 2 '
     'are unfinished. Two tracked pending records, D-210-a.md and D-210-b.md, both claim Decision ID '
     'D-210 but name different candidate closures and neither supersedes the other.',
     {'outcome': 'BLOCKED', 'dispatch': 'none', 'duplicate_publication': False}),
    ('replan_missing_record',
     'An upfront-v1 root is at Plan generation 7 with Active replan pointing to '
     'findings/D-211.md. S01 revision 3 is delivered; S02 revision 2, S03 revision 4, S04 revision 1, '
     'and S05 revision 2 are unfinished. The referenced record is absent from the authoritative '
     'tracked vault and there is no publication marker for D-211.',
     {'outcome': 'BLOCKED', 'dispatch': 'none', 'execution_paused': True}),
    ('replan_divergent_successors',
     'An upfront-v1 root is at Plan generation 7 with Active replan pointing to pending D-212. S01 '
     'revision 3 is delivered; S02 revision 2, S03 revision 4, S04 revision 1, and S05 revision 2 are '
     'unfinished. Two scratch successor sets both reference D-212 and map S03 revision 4 to different '
     'revision-5 vault paths; neither set is published or explicitly abandoned.',
     {'outcome': 'BLOCKED', 'publication': 'none', 'replay_action': 'block',
      'execution_paused': True}),
    ('replan_partial_pr_reuse',
     'An upfront-v1 root is at Plan generation 7 with pending D-213. S01 revision 3 is delivered; S02 '
     'revision 2, S03 revision 4, S04 revision 1, and S05 revision 2 are unfinished. S03 revision 4 '
     'has partially executed on open unmerged PR 93 from branch repair-s03 and worktree /tmp/w93. '
     'Verified branch/head evidence shows the authorized S03 successor can reuse that exact work '
     'after preserving completed tasks, listing remaining tasks, and rerunning review/tests. D-213 '
     'records that disposition; it grants no authority to merge or close PR 93.',
     {'pr_disposition': 'resume-existing', 'predecessor_evidence_preserved': True,
      'old_pr_closed': False, 'successor_needs_refinement': True}),
    ('replan_split_merge_mapping',
     'An upfront-v1 root is at Plan generation 7 with pending D-214. S01 revision 3 is delivered; S02 '
     'revision 2, S03 revision 4, S04 revision 1, and S05 revision 2 are unfinished. The authorized '
     'candidate retires S02 and S03, splits their responsibilities into fresh IDs S06 and S07, and '
     'merges one old output into fresh S08. The record contains the total old/new mapping '
     'S02->[S06,S07], S03->[S08], rewires every live consumer to S06/S07/S08, and does not reuse a '
     'retired ID. The candidate whole graph and mapping are otherwise valid under S2.',
     {'outcome': 'continue', 'topology_allowed': True,
      'retired_stages': ['S02', 'S03'], 'replacement_stages': ['S06', 'S07', 'S08']}),
    ('replan_retained_preparation',
     'An upfront-v1 root moved from Plan generation 7 to 8 through published D-215. S04 revision 1 was '
     'retained; S01 revision 3 is delivered, while S02 revision 3, S03 revision 5, and S05 revision 2 '
     'are unfinished. Every S04 leaf byte other than its sole Preparation pointer is unchanged; source '
     'revision 11, consumed contracts, predecessor evidence, findings, and relevant code are also '
     'unchanged. The batch records a focused revalidation receipt binding those facts to generation '
     '8; the old generation-7 receipt also remains as history.',
     {'preparation_valid': True, 'successor_needs_refinement': False}),
    ('replan_revised_preparation',
     'An upfront-v1 root moved from Plan generation 7 to 8 through a published batch. S03 was revised '
     'from revision 4 to revision 5 and its old generation-7 preparation remains linked only as '
     'history. The replacement has no generation-8 preparation receipt yet.',
     {'preparation_valid': False, 'successor_needs_refinement': True}),
    ('replan_atomicity_violation',
     'An upfront-v1 root still says Plan generation 7 and Active replan D-216 pending. S01 revision 3 '
     'is delivered; S02 revision 2, S03 revision 4, S04 revision 1, and S05 revision 2 are unfinished. '
     'A working-tree edit exposes one S03 successor through an active Plan link, but the other '
     'authorized replacements, dependency rewrites, review, record publication fields, generation '
     'increment, and barrier clearing are absent and uncommitted. For this fixture, outcome classifies '
     'whether that exposed partial candidate itself is a valid publication/execution artifact; do not '
     'instead classify the later ability to resume authoring from the still-valid committed request.',
     {'outcome': 'BLOCKED', 'publication': 'none', 'execution_paused': True,
      'partial_tree_executable': False, 'authoritative_view_executable': False}),
    ('replan_internal_pr_not_merged',
     'An internal-vault upfront root on authoritative main is at Plan generation 7 with Active replan '
     'D-216b pending. S01 revision 3 is delivered; S02 revision 2, S03 revision 4, S04 revision 1, '
     'and S05 revision 2 are unfinished. A docs branch and open unmerged A7 PR contain a complete '
     'generation-8 candidate, a published-looking D-216b record, and a root with Active replan none. '
     'Authoritative main still contains the committed generation-7 pending barrier and has no '
     'publication decision marker.',
     {'outcome': 'continue', 'publication': 'none', 'execution_paused': True,
      'partial_tree_executable': False, 'authoritative_view_executable': False}),
    ('legacy_single_leaf_repair',
     'An unmarked legacy incremental root has one repair-requested leaf P0 and a tracked legacy C8 '
     'record with Decision ID D-217, adopted authority, predecessor/closeout/PR disposition, Successor '
     'pending, Disposition pending, and Resolution active. It has no upfront generation, stage IDs, '
     'or Active replan field. superreplan is invoked directly with that root and record; this case '
     'tests the legacy wrapper and its REPLANNER contract.',
     {'operation': 'replan', 'role': 'REPLANNER', 'repair_shape': 'single-leaf',
      'batch_created': False}),
    ('discovery_completion_without_code_pr',
     'Upfront discovery stage S01 required a named experiment, evidence artifact E1, and documented '
     'decision D1. E1 and D1 are tracked on the authoritative vault branch, meet the stage criteria, '
     'identify delivered discovery contract C-DISCOVERY@1, and invalidate no live assumption. There '
     'was deliberately no code branch or PR. All other active obligations are verified complete.',
     {'done': True, 'code_pr_required': False, 'discovery_evidence_verified': True}),
    ('discovery_execution_entry_without_code_changes',
     'Direct superrun selects a prepared upfront discovery stage whose specified experiment reads '
     'existing data, writes only vault evidence and a decision, and makes no code changes. The stage '
     'requires independent review of the experiment result and produces C-DISCOVERY@1. Classify the '
     'execution path before the ordinary code worktree/SDD/PR steps.',
     {'operation': 'run', 'execution_path': 'discovery-evidence',
      'worktree_required': False, 'sdd_required': False, 'code_pr_required': False,
      'evidence_publication': 'authoritative-vault'}),
    ('partial_closeout_open_pr',
     'Upfront implementation stage S02 ran from a valid execution snapshot. Its code PR 73 remains '
     'open after CI failed. The actual PR, head commit and failing CI run are verified, but there is no '
     'merge/direct-integration identity and its produced contract is not delivered. superrun invokes '
     'superfinish to record the partial outcome.',
     {'partial_closeout_allowed': True, 'delivered': False, 'consumable': False,
      'row_status': 'executed — PR open'}),
    ('routine_closeout_finding',
     'A verified S01 closeout finding records an internal helper rename and links the affected '
     'assumption ID. It changes no acceptance, scope, dependency, consumed or produced contract, or '
     'downstream evidence. S02 has a current preparation receipt.',
     {'replan_required': False, 'affected_preparation_valid': True}),
    ('contract_contradiction_finding',
     'A verified S01 closeout finding identifies contract C-INGEST@1 and proves its delivered behavior '
     'contradicts the semantics consumed by prepared unfinished S02. No repair decision has yet been '
     'adopted.',
     {'replan_required': True, 'affected_preparation_valid': False,
      'executable': False}),
    ('stale_completed_ancestor_unsatisfied_dependency',
     'An upfront root and internal ancestor are labelled completed-and-merged. Their active links '
     'still reach unfinished S03, which depends on C-INGEST@1 from S02. S02 was declined, and no '
     'adopted disposition rewires or removes S03. Descent queues appear empty only because of the stale '
     'closed ancestor.',
     {'outcome': 'BLOCKED', 'done': False, 'executable': False}),
    ('supervisor_native_refinement',
     'Tick entry state is WAITING FOR PLAN after pre-sync and repair reconciliation. The authoritative '
     'root is upfront-v1 with a valid graph, no Active replan, and S02 is the first DFS-eligible '
     'unstarted leaf with satisfied dependencies and Preparation: none. The question asks for '
     'selection and pre-dispatch state. PLAN_REFINER has a native Claude model pin from the process '
     'environment and a distinct effort pin from repo .superenv.',
     {'selected_role': 'PLAN_REFINER', 'operation': 'refine', 'model_source': 'process-env',
      'effort_source': 'repo-superenv', 'target': 'S02', 'next_state': 'PLANNING',
      'heavy_dispatches': 1}),
    ('supervisor_cursor_native_refinement',
     'Tick entry state is WAITING FOR PLAN after pre-sync and repair reconciliation. The authoritative '
     'upfront-v1 root has no barrier; S03 is the first DFS-eligible unstarted leaf with satisfied '
     'dependencies and Preparation: none. The question asks for selection and pre-dispatch state. '
     'SUPER_HARNESS is Cursor. PLAN_REFINER has a valid native Cursor non-inherit model pin from repo '
     '.superenv and a non-inherit effort pin from that same layer; init generated the matching '
     'super-plan-refiner definition. The native Cursor effort warning has been emitted and is treated '
     'as inherit for definition selection.',
     {'selected_role': 'PLAN_REFINER', 'operation': 'refine', 'model_source': 'repo-superenv',
      'effort_source': 'repo-superenv', 'dispatch_form': 'named-definition', 'target': 'S03',
      'next_state': 'PLANNING', 'heavy_dispatches': 1}),
    ('supervisor_bridged_refinement',
     'Tick entry state is WAITING FOR PLAN after pre-sync and repair reconciliation. The authoritative '
     'upfront-v1 root has no barrier; S04 is the first DFS-eligible unstarted leaf with satisfied '
     'dependencies and no preparation record. The question asks for selection and pre-dispatch state. '
     'PLAN_REFINER is bridged to Pi; both its model and effort pins come from repo .superenv. The '
     'configured Pi CLI and relay/definition required by this harness are available.',
     {'selected_role': 'PLAN_REFINER', 'operation': 'refine', 'model_source': 'repo-superenv',
      'effort_source': 'repo-superenv', 'target': 'S04', 'next_state': 'PLANNING',
      'heavy_dispatches': 1}),
    ('supervisor_prepared_target',
     'Tick entry state is WAITING FOR PLAN after pre-sync and repair reconciliation. The authoritative '
     'upfront-v1 root has no barrier and S02 is the first eligible leaf. Its current preparation '
     'record validates against the active generation, source, contracts, predecessors, findings, and '
     'code baseline. The unused PLAN_REFINER native definition is absent. EXECUTOR model and effort '
     'would resolve from harness defaults. The question asks for the next selected action before any '
     'heavy dispatch in this tick.',
     {'selected_role': 'EXECUTOR', 'operation': 'run', 'model_source': 'harness-default',
      'effort_source': 'harness-default', 'target': 'S02', 'next_state': 'WAITING FOR RUN',
      'heavy_dispatches': 0}),
    ('supervisor_adopted_legacy_repair',
     'Tick entry state is WAITING FOR PLAN after pre-sync. The root has no Planning mode marker and '
     'has one reconciled adopted C8 single-leaf repair record for P0; it has no upfront batch. The '
     'question asks for selection and pre-dispatch state. REPLANNER has deliberately equal Codex '
     'model and effort values to PLAN_REFINER, both from repo .superenv.',
     {'selected_role': 'REPLANNER', 'operation': 'replan', 'model_source': 'repo-superenv',
      'effort_source': 'repo-superenv', 'target': 'P0', 'next_state': 'PLANNING',
      'heavy_dispatches': 1}),
    ('supervisor_adopted_batch_repair',
     'Tick entry state is WAITING FOR PLAN after pre-sync and repair reconciliation. The authoritative '
     'upfront-v1 root at generation 4 points Active replan at one committed pending record D-301. '
     'The question asks for selection and pre-dispatch state. REPLANNER is a native Claude pin: its '
     'model is from repo .superenv and its effort is from the process environment.',
     {'selected_role': 'REPLANNER', 'operation': 'replan', 'model_source': 'repo-superenv',
      'effort_source': 'process-env', 'target': 'D-301', 'next_state': 'PLANNING',
      'heavy_dispatches': 1}),
    ('supervisor_stale_hints',
     'Tick entry state is persisted PLANNING with stale hints planning_operation: refine, '
     'planning_target: S03, planning_generation: 3, and planning_record: none. Crash recovery first '
     'restores WAITING FOR PLAN and reconciles tracked artifacts. The authoritative upfront-v1 root is '
     'generation 4 and has one committed pending Active replan record D-302. The question asks for '
     'the recovered tick selection and pre-dispatch state. REPLANNER is bridged to Pi and both pins '
     'come from repo .superenv.',
     {'selected_role': 'REPLANNER', 'operation': 'replan', 'model_source': 'repo-superenv',
      'effort_source': 'repo-superenv', 'target': 'D-302', 'next_state': 'PLANNING',
      'heavy_dispatches': 1}),
    ('supervisor_post_leaf_refinement',
     'A superrun Final Report has verified integration and closeout of S01. The result handler has '
     'already set WAITING FOR PLAN, synchronized the tree, and is now asked for the following tick\'s '
     'selection and pre-dispatch state. The authoritative upfront-v1 root has no barrier; S02 is the '
     'first eligible unstarted leaf and lacks a preparation record. PLAN_REFINER model and effort both '
     'come from harness defaults.',
     {'selected_role': 'PLAN_REFINER', 'operation': 'refine', 'model_source': 'harness-default',
      'effort_source': 'harness-default', 'target': 'S02', 'next_state': 'PLANNING',
      'heavy_dispatches': 1}),
    ('supervisor_execution_replan_required',
     'A superrun result handler reports REPLAN-REQUIRED with verified S02 contract-break evidence, '
     'but no decision has been adopted and no durable C8 record exists. The existing autonomous '
     'decision-ladder panel rungs ran and could not resolve authority, so this case is now awaiting '
     'the user decision rather than skipping those rungs. The question asks for the post-result state. '
     'S04 is independently prepared, but the execution finding has priority. Target means the next '
     'authorized dispatch target; the S02 finding origin is not a dispatch target while input waits.',
     {'selected_role': 'none', 'operation': 'none', 'model_source': 'none', 'effort_source': 'none',
      'target': 'none', 'next_state': 'WAITING FOR INPUT', 'heavy_dispatches': 0}),
    ('supervisor_legacy_incremental_planning',
     'Tick entry state is WAITING FOR PLAN after pre-sync and repair reconciliation. The root has no '
     'Planning mode marker even though the process environment requests upfront. It has an ordinary '
     'unplanned incremental leaf P1 and no repair request. The question asks for selection and '
     'pre-dispatch state. PLANNER model and effort both come from harness defaults.',
     {'selected_role': 'PLANNER', 'operation': 'plan', 'model_source': 'harness-default',
      'effort_source': 'harness-default', 'target': 'P1', 'next_state': 'PLANNING',
      'heavy_dispatches': 1}),
    ('supervisor_missing_native_definition',
     'Tick entry state is WAITING FOR PLAN after pre-sync and repair reconciliation. An eligible '
     'upfront stage S02 requires refinement. PLAN_REFINER is native Claude with a full model and '
     'effort pin, both from repo .superenv, but its required generated super-plan-refiner definition '
     'is absent. The question asks for the immediate selected-role-only preflight observation before '
     'the existing decision ladder runs; no fallback role is authorized.',
     {'selected_role': 'PLAN_REFINER', 'operation': 'refine', 'model_source': 'repo-superenv',
      'effort_source': 'repo-superenv', 'target': 'S02', 'next_state': 'WAITING FOR PLAN',
      'heavy_dispatches': 0, 'outcome': 'BLOCKED'}),
    ('supervisor_missing_bridge_cli',
     'Tick entry state is WAITING FOR PLAN after pre-sync and repair reconciliation. A committed '
     'upfront batch D-303 requires replanning. REPLANNER is bridged to Pi from repo .superenv, but '
     'the configured Pi CLI is unavailable. The question asks for the immediate selected-role-only '
     'preflight observation before the existing decision ladder runs; no fallback role or harness is '
     'authorized.',
     {'selected_role': 'REPLANNER', 'operation': 'replan', 'model_source': 'repo-superenv',
      'effort_source': 'repo-superenv', 'target': 'D-303', 'next_state': 'WAITING FOR PLAN',
      'heavy_dispatches': 0, 'outcome': 'BLOCKED'}),
)


def select_cases(names=None):
    """Return cases in canonical order, rejecting unknown names."""
    if not names:
        return CASES
    requested = set(names)
    known = {case[0] for case in CASES}
    unknown = sorted(requested - known)
    if unknown:
        raise ValueError('unknown case(s): ' + ', '.join(unknown))
    return tuple(case for case in CASES if case[0] in requested)


def render_prompt(skills, cases):
    """Build a probe prompt containing facts and field names, never answer values."""
    skill_names = ['superagent', 'superloop', 'superstage', 'superauthor', 'supertraverse',
                   'superrefine', 'superrun', 'superfinish', 'supergoal', 'superplan',
                   'supermeta', 'init']
    if (skills / 'superreplan' / 'SKILL.md').is_file():
        skill_names.insert(4, 'superreplan')
    lines = [
        'Read the supplied canonical skill contracts at ' + str(skills.resolve()) +
        '/{' + ','.join(skill_names) + '}/SKILL.md. '
        'Apply their rules to each independent '
        'fixture below. This is a read-only interpretation: do not dispatch, mutate files, call '
        'Git/network services, read implementation reports, or invent absent rules.',
        'Supervisor scenarios apply the CURRENT superagent/superloop consumer rules, including any '
        'active transition gate. Do not answer from a future or dormant recipe unless the current '
        'consumer explicitly makes it active.',
        'Return one JSON object keyed by scenario id. Every result must be a JSON object with a '
        'nonempty string reason citing the governing rule/evidence, plus every requested field. '
        'Use JSON booleans where a field asks for a boolean and contract spellings for strings.',
        'For the artifact/replay cases, outcome classifies the current artifact/replay handler, not C6 '
        'stage selection. dispatch names the next heavy skill authorized after durable request '
        'reconciliation, not a claim that the '
        'current supervisor already routes it. publication names the furthest coherent artifact '
        'form safe to resume: scratch for one unique draft/checkpoint even when it needs '
        'reassessment, vault only for a complete authoritative committed/integrated generation, and '
        'none when neither exists. A dirty active-tree edit or unmerged internal docs PR is none. '
        'execution_paused says whether this adopted decision/batch imposes its own whole-goal '
        'execution barrier, independent of ordinary preparation or dependency readiness. '
        'replay_action names artifact reconciliation, not the later controller status. The '
        'propagation_stop value for no preserved stage boundary is the JSON string "none", never '
        'JSON null.',
        'Global output vocabulary (not per-case answers): mode is incremental, upfront-v1, or '
        'unsupported; outcome is BLOCKED, DRAFT-INCOMPLETE, NEEDS-REFINEMENT, PREPARED, '
        'REPLAN-REQUIRED, continue, or done; operation is plan, refine, run, replan, or none; role '
        'is PLANNER, PLAN_REFINER, REPLANNER, EXECUTOR, or none; model_source and effort_source are '
        'process-env, repo-superenv, harness-default, or none; next_state is WAITING FOR PLAN, '
        'PLANNING, WAITING FOR RUN, or WAITING FOR INPUT; dispatch_form is named-definition, '
        'generic-child, bridge-relay, bridge-process, codex-spawn, or none; target is a stage ID, legacy leaf ID, '
        'decision ID, or none; heavy_dispatches is the scheduled/authorized count in this case, '
        'integer 0 or 1; publication is none, scratch, '
        'or vault; draft_action describes scratch artifact handling only: resume, revise, or none; '
        'confirmation remains separately governed by the current gate; root_mode_marker is '
        'incremental, upfront-v1, or absent; upfront_valid, executable, '
        'done, code_execution, code_pr_required, discovery_evidence_verified, merge_allowed, '
        'worktree_required, sdd_required, partial_closeout_allowed, delivered, consumable, '
        'execution_snapshot_required, historical_snapshot_required, delivery_receipt_reused, '
        'pr_evidence_preserved, replan_required, affected_preparation_valid, duplicate_stage_ids, '
        'duplicate_goal_folder, commitments_preserved, and in_place_overwrite are JSON booleans; '
        'digest_basis is execution-snapshot or current-annotated-plan; execution_path is '
        'discovery-evidence or code-delivery; evidence_publication is authoritative-vault or none; '
        'row_status is executed — PR open or completed-and-merged; stages and stage_revision are JSON '
        'integers; amendment_kind is none, content-amendment, or '
        'compatible-baseline-revalidation; batch_created, execution_paused, duplicate_publication, '
        'active_link_changed, successor_closed, predecessor_evidence_preserved, old_pr_closed, '
        'successor_needs_refinement, topology_allowed, preparation_valid, '
        'partial_tree_executable, and authoritative_view_executable are JSON booleans; dispatch is '
        'none or superreplan; resolution is '
        'pending, published, superseded, or declined; replay_action is resume-draft, '
        'resume-published, reassess, or block; propagation_stop is a stage ID or the string none; '
        'late_closeout_action is preserve-history or reconcile-delivery; pr_disposition is '
        'resume-existing, replace, or none; repair_shape is single-leaf or batch; '
        'completed_disposition is completed-history or none; revised_stages, '
        'retained_stages, completed_stages, retired_stages, and replacement_stages are JSON arrays '
        'of stage IDs. Scenario operation describes the selected action. The persisted '
        'planning_operation recovery hint remains refine, replan, or none: legacy plan and run '
        'selections persist none.',
    ]
    for name, facts, expected in cases:
        lines.extend(('', name + ': ' + facts,
                      'Return fields: reason, ' + ', '.join(expected.keys())))
    return '\n'.join(lines) + '\n'


def validate_answers(answers, cases):
    """Return human-readable validation errors for a decoded answer object."""
    if not isinstance(answers, dict):
        return ['top-level answer must be a JSON object']

    errors = []
    expected_names = {case[0] for case in cases}
    actual_names = set(answers)
    missing = sorted(expected_names - actual_names)
    unexpected = sorted(actual_names - expected_names)
    if missing:
        errors.append('missing case(s): ' + ', '.join(missing))
    if unexpected:
        errors.append('unexpected case(s): ' + ', '.join(unexpected))

    for name, _, expected in cases:
        if name not in answers:
            continue
        actual = answers[name]
        if not isinstance(actual, dict):
            errors.append(name + ': answer must be a JSON object')
            continue
        reason = actual.get('reason')
        if not isinstance(reason, str) or not reason.strip():
            errors.append(name + '.reason: must be a nonempty string')
        for key, value in expected.items():
            if key not in actual:
                errors.append(name + '.' + key + ': missing required field')
                continue
            observed = actual[key]
            if type(observed) is not type(value) or observed != value:  # bool is not integer here
                errors.append(name + '.' + key + ': expected ' + json.dumps(value) +
                              ', got ' + json.dumps(observed, sort_keys=True))
    return errors


def load_answers(path):
    """Decode an answers file and return (value, error), without leaking a traceback."""
    try:
        return json.loads(path.read_text(encoding='utf-8')), None
    except OSError as exc:
        return None, 'cannot read answers: ' + str(exc)
    except (UnicodeError, json.JSONDecodeError) as exc:
        return None, 'malformed answers JSON: ' + str(exc)


class ValidatorTests(unittest.TestCase):
    def valid_answers(self, cases=CASES):
        return {name: dict(expected, reason='Applied superstage evidence rule.')
                for name, _, expected in cases}

    def test_accepts_all_exact_cases_and_required_values(self):
        self.assertEqual(validate_answers(self.valid_answers(), CASES), [])

    def test_refinement_case_rejects_wrong_outcome(self):
        cases = select_cases(['scope_expansion_during_preparation'])
        answers = self.valid_answers(cases)
        answers['scope_expansion_during_preparation']['outcome'] = 'PREPARED'
        errors = validate_answers(answers, cases)
        self.assertTrue(any(error.startswith(
            'scope_expansion_during_preparation.outcome:') for error in errors))

    def test_supervisor_cases_pin_recovery_and_one_heavy_dispatch(self):
        cases = select_cases(['supervisor_stale_hints', 'supervisor_prepared_target',
                              'supervisor_missing_bridge_cli',
                              'supervisor_execution_replan_required',
                              'supervisor_cursor_native_refinement'])
        answers = self.valid_answers(cases)
        self.assertEqual(validate_answers(answers, cases), [])
        answers['supervisor_stale_hints']['target'] = 'S03'
        self.assertTrue(any(error.startswith('supervisor_stale_hints.target:')
                            for error in validate_answers(answers, cases)))
        answers = self.valid_answers(cases)
        answers['supervisor_prepared_target']['heavy_dispatches'] = 1
        self.assertTrue(any(error.startswith('supervisor_prepared_target.heavy_dispatches:')
                            for error in validate_answers(answers, cases)))
        answers = self.valid_answers(cases)
        answers['supervisor_missing_bridge_cli']['next_state'] = 'WAITING FOR INPUT'
        self.assertTrue(any(error.startswith('supervisor_missing_bridge_cli.next_state:')
                            for error in validate_answers(answers, cases)))
        answers = self.valid_answers(cases)
        answers['supervisor_execution_replan_required']['target'] = 'S02'
        self.assertTrue(any(error.startswith('supervisor_execution_replan_required.target:')
                            for error in validate_answers(answers, cases)))
        answers = self.valid_answers(cases)
        answers['supervisor_cursor_native_refinement']['dispatch_form'] = 'generic-child'
        self.assertTrue(any(error.startswith('supervisor_cursor_native_refinement.dispatch_form:')
                            for error in validate_answers(answers, cases)))

    def test_closeout_and_recovery_cases_require_delivery_identity_results(self):
        cases = select_cases(['manual_superrun_pending_batch',
                              'execution_snapshot_historical_digest',
                              'merged_lost_closeout_response',
                              'ci_pending_replan_request',
                              'replan_retained_preparation',
                              'replan_revised_preparation',
                              'discovery_completion_without_code_pr',
                              'discovery_execution_entry_without_code_changes',
                              'partial_closeout_open_pr',
                              'routine_closeout_finding',
                              'contract_contradiction_finding',
                              'stale_completed_ancestor_unsatisfied_dependency'])
        answers = self.valid_answers(cases)
        self.assertEqual(validate_answers(answers, cases), [])
        answers['ci_pending_replan_request']['merge_allowed'] = True
        self.assertTrue(any(error.startswith('ci_pending_replan_request.merge_allowed:')
                            for error in validate_answers(answers, cases)))
        answers = self.valid_answers(cases)
        answers['merged_lost_closeout_response']['duplicate_publication'] = True
        self.assertTrue(any(error.startswith('merged_lost_closeout_response.duplicate_publication:')
                            for error in validate_answers(answers, cases)))
        answers = self.valid_answers(cases)
        answers['discovery_completion_without_code_pr']['code_pr_required'] = True
        self.assertTrue(any(error.startswith(
            'discovery_completion_without_code_pr.code_pr_required:')
            for error in validate_answers(answers, cases)))
        answers = self.valid_answers(cases)
        answers['discovery_execution_entry_without_code_changes']['worktree_required'] = True
        self.assertTrue(any(error.startswith(
            'discovery_execution_entry_without_code_changes.worktree_required:')
            for error in validate_answers(answers, cases)))
        answers = self.valid_answers(cases)
        answers['partial_closeout_open_pr']['delivered'] = True
        self.assertTrue(any(error.startswith('partial_closeout_open_pr.delivered:')
                            for error in validate_answers(answers, cases)))

    def test_selected_cases_require_exact_selected_membership(self):
        cases = select_cases(['contract_break', 'legacy_default'])
        self.assertEqual([case[0] for case in cases], ['legacy_default', 'contract_break'])
        answers = self.valid_answers(cases)
        self.assertEqual(validate_answers(answers, cases), [])
        answers['bounded_unknown'] = {'reason': 'extra'}
        self.assertIn('unexpected case(s): bounded_unknown', validate_answers(answers, cases))

    def test_rejects_missing_case(self):
        answers = self.valid_answers()
        del answers['open_provider']
        self.assertIn('missing case(s): open_provider', validate_answers(answers, CASES))

    def test_rejects_unknown_case_selection(self):
        with self.assertRaisesRegex(ValueError, 'unknown case'):
            select_cases(['not-a-case'])

    def test_rejects_non_object_top_level_and_case_values(self):
        self.assertTrue(validate_answers([], CASES))
        answers = self.valid_answers()
        answers['legacy_default'] = 'incremental'
        self.assertIn('legacy_default: answer must be a JSON object',
                      validate_answers(answers, CASES))

    def test_rejects_missing_empty_and_non_string_reasons(self):
        for bad_reason in (None, '', '   ', True, 7, []):
            with self.subTest(reason=bad_reason):
                answers = self.valid_answers()
                if bad_reason is None:
                    del answers['legacy_default']['reason']
                else:
                    answers['legacy_default']['reason'] = bad_reason
                self.assertIn('legacy_default.reason: must be a nonempty string',
                              validate_answers(answers, CASES))

    def test_rejects_missing_wrong_and_bool_integer_types(self):
        answers = self.valid_answers()
        del answers['bounded_unknown']['executable']
        self.assertIn('bounded_unknown.executable: missing required field',
                      validate_answers(answers, CASES))
        answers = self.valid_answers()
        answers['bounded_unknown']['upfront_valid'] = 1
        errors = validate_answers(answers, CASES)
        self.assertTrue(any(error.startswith('bounded_unknown.upfront_valid:') for error in errors))
        answers = self.valid_answers()
        answers['legacy_default']['mode'] = False
        self.assertTrue(any(error.startswith('legacy_default.mode:')
                            for error in validate_answers(answers, CASES)))

    def test_prompt_has_facts_and_fields_without_expected_values(self):
        prompt = render_prompt(Path('skills'), select_cases(['legacy_default', 'bounded_unknown']))
        vocabulary_prefix = 'Global output vocabulary (not per-case answers):'
        self.assertEqual(prompt.count(vocabulary_prefix), 1)
        self.assertLess(prompt.index(vocabulary_prefix), prompt.index('legacy_default:'))
        self.assertIn('dispatch is none or superreplan', prompt)
        self.assertIn('revised_stages, retained_stages, completed_stages, retired_stages, and '
                      'replacement_stages are JSON arrays of stage IDs', prompt)
        self.assertIn('legacy_default:', prompt)
        self.assertIn('Return fields: reason, mode', prompt)
        self.assertIn('Return fields: reason, upfront_valid, executable', prompt)
        self.assertNotIn('mode: incremental', prompt)
        self.assertNotIn('upfront_valid: true', prompt.lower())
        self.assertNotIn('executable: false', prompt.lower())

    def test_supervisor_prompt_has_entry_phase_fields_without_answers(self):
        prompt = render_prompt(Path('skills'), select_cases(['supervisor_native_refinement',
                                                               'supervisor_prepared_target']))
        self.assertIn('Tick entry state is WAITING FOR PLAN', prompt)
        self.assertIn('selection and pre-dispatch state', prompt)
        self.assertIn('CURRENT superagent/superloop consumer rules', prompt)
        self.assertIn('/{superagent,superloop,superstage', prompt)
        self.assertIn('model_source and effort_source are', prompt)
        self.assertIn('Return fields: reason, selected_role, operation, model_source, effort_source, '
                      'target, next_state, heavy_dispatches', prompt)
        self.assertNotIn('selected_role: PLAN_REFINER', prompt)
        self.assertNotIn('heavy_dispatches: 1', prompt)

    def test_load_answers_reports_malformed_json_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            malformed = Path(directory) / 'bad.json'
            malformed.write_text('{', encoding='utf-8')
            value, error = load_answers(malformed)
            self.assertIsNone(value)
            self.assertIn('malformed answers JSON:', error)
            value, error = load_answers(Path(directory) / 'missing.json')
            self.assertIsNone(value)
            self.assertIn('cannot read answers:', error)


def run_self_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ValidatorTests)
    return unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prompt', action='store_true', help='print fresh-interpreter prompt')
    group.add_argument('--answers', type=Path, help='validate a JSON answer file')
    group.add_argument('--self-test', action='store_true', help='run validator unit tests')
    parser.add_argument('--skills', type=Path, default=Path('skills'),
                        help='canonical skill directory named in the prompt')
    parser.add_argument('--cases', nargs='+', choices=[case[0] for case in CASES],
                        help='include only these cases (default: all)')
    args = parser.parse_args(argv)
    cases = select_cases(args.cases)

    if args.self_test:
        return 0 if run_self_tests() else 1
    if args.prompt:
        sys.stdout.write(render_prompt(args.skills, cases))
        return 0

    answers, error = load_answers(args.answers)
    if error:
        print('plan-tree-regression: ' + error, file=sys.stderr)
        return 2
    errors = validate_answers(answers, cases)
    if errors:
        for item in errors:
            print('FAIL: ' + item, file=sys.stderr)
        return 1
    print('PASS: ' + str(len(cases)) + ' plan-tree scenario answer(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

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
    ('temporary_upfront_gate',
     'The current Task 1 build has a valid upfront-v1 graph and a stage with a documentation-valid '
     'PREPARED receipt. Tasks 3 and 5 have not yet installed preparation and operation-routing '
     'consumers. Classify a planning or execution selection attempt in this intermediate build.',
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
     'This fixture uses the dormant post-Task-5 C6 selection handler; its temporary transition gate '
     'does not apply. The highest DFS-priority upfront stage has satisfied dependencies and is '
     'unstarted, but its Preparation field is none. superrun is invoked directly on the root.',
     {'outcome': 'NEEDS-REFINEMENT', 'executable': False}),
    ('partially_executed_stage',
     'A stage has an execution closeout or open code PR showing that implementation already began, '
     'while its remaining work is unresolved. A caller asks the refiner to prepare it in place.',
     {'outcome': 'BLOCKED', 'in_place_overwrite': False}),
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
      'completed_stages': ['S01'], 'propagation_stop': 'S03'}),
    ('impact_foundational_change',
     'An upfront-v1 root is at Plan generation 7. S01 revision 3 is delivered. The unfinished stages '
     'are S02 revision 2 depending on S01, S03 revision 4 depending on S02, S04 revision 1 with '
     'Depends on none, and S05 revision 2 depending on S03. An adopted source-author decision changes '
     'the shared storage architecture named by the acceptance and chosen approach of every unfinished '
     'stage. Verified evidence says none of S02, S03, S04, or S05 can retain its current required '
     'outcome or shared contracts; no evidence changes delivered S01.',
     {'revised_stages': ['S02', 'S03', 'S04', 'S05'], 'retained_stages': [],
      'completed_stages': ['S01'], 'propagation_stop': 'none'}),
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
     'candidate closure, and PR/worktree dispositions. It has no draft paths yet.',
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
    ('replan_atomicity_violation',
     'An upfront-v1 root still says Plan generation 7 and Active replan D-216 pending. S01 revision 3 '
     'is delivered; S02 revision 2, S03 revision 4, S04 revision 1, and S05 revision 2 are unfinished. '
     'A working-tree edit exposes one S03 successor through an active Plan link, but the other '
     'authorized replacements, dependency rewrites, review, record publication fields, generation '
     'increment, and barrier clearing are absent and uncommitted.',
     {'outcome': 'BLOCKED', 'publication': 'none', 'execution_paused': True,
      'partial_tree_executable': False}),
    ('replan_internal_pr_not_merged',
     'An internal-vault upfront root on authoritative main is at Plan generation 7 with Active replan '
     'D-216b pending. S01 revision 3 is delivered; S02 revision 2, S03 revision 4, S04 revision 1, '
     'and S05 revision 2 are unfinished. A docs branch and open unmerged A7 PR contain a complete '
     'generation-8 candidate, a published-looking D-216b record, and a root with Active replan none. '
     'Authoritative main still contains the committed generation-7 pending barrier and has no '
     'publication decision marker.',
     {'outcome': 'continue', 'publication': 'none', 'execution_paused': True,
      'partial_tree_executable': False}),
    ('legacy_single_leaf_repair',
     'An unmarked legacy incremental root has one repair-requested leaf P0 and a tracked legacy C8 '
     'record with Decision ID D-217, adopted authority, predecessor/closeout/PR disposition, Successor '
     'pending, Disposition pending, and Resolution active. It has no upfront generation, stage IDs, '
     'or Active replan field. superreplan is invoked directly with that root and record; this case '
     'tests the new wrapper rather than the pre-Task-5 supervisor fallback.',
     {'operation': 'replan', 'role': 'REPLANNER', 'repair_shape': 'single-leaf',
      'batch_created': False}),
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
    skill_names = ['superstage', 'superauthor', 'supertraverse', 'superrefine', 'superrun',
                   'supergoal', 'superplan', 'supermeta', 'init']
    if (skills / 'superreplan' / 'SKILL.md').is_file():
        skill_names.insert(4, 'superreplan')
    lines = [
        'Read the supplied canonical skill contracts at ' + str(skills.resolve()) +
        '/{' + ','.join(skill_names) + '}/SKILL.md. '
        'Apply their rules to each independent '
        'fixture below. This is a read-only interpretation: do not dispatch, mutate files, call '
        'Git/network services, read implementation reports, or invent absent rules.',
        'Return one JSON object keyed by scenario id. Every result must be a JSON object with a '
        'nonempty string reason citing the governing rule/evidence, plus every requested field. '
        'Use JSON booleans where a field asks for a boolean and contract spellings for strings.',
        'For the Task 4 cases, outcome classifies the current artifact/replay handler, not C6 stage '
        'selection; the temporary C6 upfront BLOCKED gate remains until Task 5. dispatch names the '
        'next heavy skill authorized after durable request reconciliation, not a claim that the '
        'current supervisor already routes it. publication names the furthest coherent artifact '
        'form safe to resume: scratch for one unique draft/checkpoint even when it needs '
        'reassessment, vault only for a complete authoritative committed/integrated generation, and '
        'none when neither exists. A dirty active-tree edit or unmerged internal docs PR is none. '
        'execution_paused says whether this adopted decision/batch imposes its own whole-goal '
        'execution barrier, independent of the temporary C6 rollout gate and ordinary preparation '
        'or dependency readiness. '
        'replay_action names artifact reconciliation, not the later controller status. The '
        'propagation_stop value for no preserved stage boundary is the JSON string "none", never '
        'JSON null.',
        'Global output vocabulary (not per-case answers): mode is incremental, upfront-v1, or '
        'unsupported; outcome is BLOCKED, DRAFT-INCOMPLETE, NEEDS-REFINEMENT, PREPARED, '
        'REPLAN-REQUIRED, continue, or done; operation is refine, '
        'replan, or none; role is PLAN_REFINER, REPLANNER, or none; publication is none, scratch, '
        'or vault; draft_action describes scratch artifact handling only: resume, revise, or none; '
        'confirmation remains separately governed by the current gate; root_mode_marker is '
        'incremental, upfront-v1, or absent; upfront_valid, executable, '
        'done, code_execution, duplicate_stage_ids, duplicate_goal_folder, commitments_preserved, '
        'and in_place_overwrite are JSON booleans; stages and stage_revision are JSON '
        'integers; amendment_kind is none, content-amendment, or '
        'compatible-baseline-revalidation; batch_created, execution_paused, duplicate_publication, '
        'active_link_changed, successor_closed, predecessor_evidence_preserved, old_pr_closed, '
        'successor_needs_refinement, topology_allowed, preparation_valid, and '
        'partial_tree_executable are JSON booleans; dispatch is none or superreplan; resolution is '
        'pending, published, superseded, or declined; replay_action is resume-draft, '
        'resume-published, reassess, or block; propagation_stop is a stage ID or the string none; '
        'late_closeout_action is preserve-history or reconcile-delivery; pr_disposition is '
        'resume-existing, replace, or none; repair_shape is single-leaf or batch; revised_stages, '
        'retained_stages, completed_stages, retired_stages, and replacement_stages are JSON arrays '
        'of stage IDs.',
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

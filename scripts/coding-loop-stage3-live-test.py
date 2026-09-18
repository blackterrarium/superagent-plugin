#!/usr/bin/env python3
"""Offline tests; synthetic receipts and approval records never authorize live runs."""
import copy
import hashlib
import importlib.util
import json
import os
import signal
import shlex
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
PATH = SCRIPTS / 'coding-loop-stage3-live.py'
if PATH.exists():
    spec = importlib.util.spec_from_file_location('stage3_live', PATH)
    live = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(live)
else:
    class Missing:
        def __getattr__(self, name):
            raise AssertionError('bounded live driver not implemented: ' + name)
    live = Missing()


def digest(data):
    return hashlib.sha256(data).hexdigest()


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='stage3 live offline ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Offline fixture')
        self.git('config', 'user.email', 'offline@example.invalid')
        self.project = self.repo / 'vault/projects/example'
        self.project.mkdir(parents=True)
        for name in ('prd.md', 'evaluation.md', 'knowledge-base.md'):
            (self.project / name).write_text('# Approved offline ' + name + '\n')
        self.git('add', '.'); self.git('commit', '-qm', 'baseline')
        self.sha = self.git('rev-parse', 'HEAD')
        self.git('remote', 'add', 'origin', str(self.root / 'origin.git'))
        self.protocol = self.root / 'protocol.md'
        self.protocol.write_text('Offline fixture: round one must fail C1; no live authority.\n')
        self.manifest = {
            'protocol_version': 1,
            'protocol': {'path': str(self.protocol), 'sha256': digest(self.protocol.read_bytes())},
            'approval': {'receipt_path': str(self.root / 'approval.json'), 'author_ref': 'offline-author'},
            'baseline_sha': self.sha,
            'first_failure': {'mechanism': 'approved-baseline-defect', 'required_ids': ['C1']},
            'limits': {'max_rounds': 2, 'max_dispatches': 3, 'dispatch_seconds': 1,
                       'total_seconds': 3, 'retries': 0},
            'evidence_dir': str(self.root / 'evidence'),
            'harnesses': {},
        }
        for name in ('claude', 'codex', 'pi'):
            code = self.repo if name == 'codex' else self.root / name
            self.manifest['harnesses'][name] = {
                'code_root': str(code), 'vault_root': str(code / 'vault'),
                'project': str(code / 'vault/projects/example'),
                'remotes': {'code': {'origin': str(self.root / 'origin.git')}, 'vault': {}},
                'agreement_revision': 'a' * 64,
                'agreement': [{'path': str(code / 'vault/projects/example' / file),
                               'sha256': digest((self.project / file).read_bytes()),
                               'mode': 'prd-without-ledger' if file == 'prd.md' else 'bytes'}
                              for file in ('prd.md', 'evaluation.md', 'knowledge-base.md')],
                'binding_captures': [],
                'slug_prefixes': {'outer': name + '-outer-', 'inner': name + '-inner-'},
                'roles': {role: {'model': name + ':pinned-model', 'effort': 'high'}
                          for role in ('SUPERVISOR', 'META_PLANNER', 'PLANNER', 'EVALUATOR',
                                       'DIAGNOSER', 'IMPLEMENTER', 'TASK_REVIEWER', 'BRANCH_REVIEWER', 'EXECUTOR')},
                'packages': [{'path': str(self.protocol), 'sha256': digest(self.protocol.read_bytes()),
                              'version': '0.8.1'}],
                'auth_refs': ['env:OFFLINE_AUTH'],
                'cleanup': {'owner': name + '-test', 'registrations': [
                    {'slug': name + '-outer-1', 'supervisor': 'supercode'},
                    {'slug': name + '-inner-1', 'supervisor': 'superagent'}]},
            }
        self.path = self.root / 'manifest.json'
        self.save()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True,
                              text=True).stdout.strip()

    def save(self):
        self.path.write_text(json.dumps(self.manifest, indent=2) + '\n')

    def approve(self):
        record = self.root / 'author-record.txt'
        record.write_text('OFFLINE ONLY: approved manifest sha256 ' + digest(self.path.read_bytes()))
        receipt = {'manifest_sha256': digest(self.path.read_bytes()), 'author_ref': 'offline-author',
                   'decision': 'APPROVED', 'record': {'path': str(record), 'sha256': digest(record.read_bytes())}}
        (self.root / 'approval.json').write_text(json.dumps(receipt))

    def checked(self):
        self.approve()
        return live.load_manifest(self.path, approved=True)

    def request(self, **changes):
        request = dict(id='child-1', role='IMPLEMENTER', harness='codex', model='codex:pinned-model',
                       effort='high', round=1, operation='repair-1', code_root=str(self.repo),
                       vault_root=str(self.repo / 'vault'), slug='codex-inner-1')
        request.update(changes)
        return request

    def test_prepare_never_synthesizes_approval_and_preserves_attempts(self):
        first = live.prepare(self.path)
        second = live.prepare(self.path)
        self.assertEqual(first['status'], 'INCOMPLETE')
        self.assertNotEqual(first['attempt'], second['attempt'])
        self.assertFalse((self.root / 'approval.json').exists())
        self.assertTrue((Path(first['attempt']) / 'manifest.json').exists())

    def test_missing_approval_and_exact_byte_mismatch(self):
        self.assertEqual(live.execute('run', self.path, 'codex')['status'], 'INVALID')
        self.approve()
        self.path.write_bytes(self.path.read_bytes() + b' ')
        result = live.execute('run', self.path, 'codex')
        self.assertEqual(result['status'], 'INVALID')
        self.assertIn('manifest', result['reason'])

    def test_scope_rejects_unlisted_root_remote_and_wrong_harness(self):
        m = self.checked()
        live.check_scope(m, 'codex', baseline=True)
        self.git('remote', 'add', 'unlisted', 'https://example.invalid/unlisted.git')
        with self.assertRaises(live.Invalid): live.check_scope(m, 'codex', baseline=True)
        gate = live.Budget(m, 'codex', lambda event: None)
        for change in ({'code_root': str(self.root)}, {'harness': 'claude'}, {'slug': 'unowned'},
                       {'model': 'claude:foreign'}, {'effort': 'low'}):
            with self.subTest(change=change), self.assertRaises(live.Invalid): gate.authorize(self.request(**change))

    def test_manifest_schema_secrets_symlinks_and_bounds(self):
        for mutate in (lambda m: m['limits'].update(max_dispatches=0),
                       lambda m: m.update(api_key='secret'),
                       lambda m: m['harnesses']['codex']['roles']['SUPERVISOR'].update(model='claude:foreign')):
            original = copy.deepcopy(self.manifest)
            mutate(self.manifest); self.save()
            with self.assertRaises(live.Invalid): live.load_manifest(self.path)
            self.manifest = original
        self.save()
        alias = self.root / 'alias'; alias.symlink_to(self.repo, target_is_directory=True)
        self.manifest['harnesses']['codex']['code_root'] = str(alias); self.save()
        with self.assertRaises(live.Invalid): live.load_manifest(self.path)

    def test_native_runtime_gap_cannot_arm_or_accept_synthetic_receipt(self):
        self.approve()
        for name in ('codex',):
            result = live.execute('run', self.path, name)
            self.assertEqual(result['status'], 'INCOMPLETE')
            self.assertFalse(result['acceptance_passed'])
            self.assertIn('native', result['reason'])
        result = live.execute('collect', self.path, 'codex')
        self.assertEqual(result['status'], 'INCOMPLETE')

    def test_child_dispatch_cap_and_retry_cap_are_pre_dispatch(self):
        m = self.checked(); events = []
        gate = live.Budget(m, 'codex', events.append)
        gate.authorize(self.request())
        with self.assertRaises(live.Exhausted): gate.authorize(self.request(id='retry'))
        gate.authorize(self.request(id='child-2', operation='repair-2'))
        gate.authorize(self.request(id='child-3', operation='repair-3'))
        with self.assertRaises(live.Exhausted): gate.authorize(self.request(id='child-4', operation='repair-4'))
        self.assertEqual(len([e for e in events if e['kind'] == 'dispatch-permit']), 3)

    def test_total_deadline_is_independent_of_progress(self):
        m = self.checked(); m['limits']['total_seconds'] = 0.05
        gate = live.Budget(m, 'codex', lambda event: None)
        time.sleep(0.07)
        with self.assertRaises(live.Exhausted): gate.authorize(self.request())

    def test_bounded_fake_process_uses_argv_and_kills_timeout(self):
        m = self.checked(); m['limits']['dispatch_seconds'] = 0.08
        gate = live.Budget(m, 'codex', lambda event: None)
        permit = gate.authorize(self.request())
        start = time.monotonic()
        result = live.bounded_process([sys.executable, '-c', 'import time; time.sleep(20)'],
                                      self.repo, permit['seconds'], self.root / 'process')
        self.assertTrue(result['timed_out']); self.assertLess(time.monotonic() - start, 2)
        marker = 'literal;$(touch SHOULD_NOT_EXIST)'
        result = live.bounded_process([sys.executable, '-c', 'import sys; print(sys.argv[1])', marker],
                                      self.repo, 1, self.root / 'literal')
        self.assertEqual(result['returncode'], 0)
        self.assertIn(marker, (self.root / 'literal.stdout').read_text())
        self.assertFalse((self.repo / 'SHOULD_NOT_EXIST').exists())

    def test_cleanup_is_owned_and_failure_is_incomplete(self):
        m = self.checked()
        class Adapter:
            def __init__(self): self.stopped = []
            def stop(self, identity): self.stopped.append(identity['slug'])
            def active(self, identity): return identity['supervisor'] == 'superagent'
        adapter = Adapter()
        result = live.cleanup_owned(m, 'codex', adapter)
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertEqual(adapter.stopped, ['codex-outer-1', 'codex-inner-1'])
        self.assertFalse(result['acceptance_passed'])

    def test_changed_agreement_is_invalid(self):
        m = self.checked()
        (self.project / 'evaluation.md').write_text('weakened')
        with self.assertRaises(live.Invalid): live.check_agreement(m, 'codex', context=False)

    def test_unexpected_first_pass_is_invalid(self):
        result = live.verdict_sequence([{'round': 1, 'verdict': 'PASS'}], 2)
        self.assertEqual(result['status'], 'INVALID'); self.assertFalse(result['acceptance_passed'])

    def test_statuses_do_not_conflate_failure_missing_and_invalid(self):
        self.assertEqual(live.verdict_sequence([], 2)['status'], 'INCOMPLETE')
        self.assertEqual(live.verdict_sequence([{'round': 1, 'verdict': 'FAIL'}, {'round': 2, 'verdict': 'FAIL'}], 2)['status'], 'FAIL')
        result = live.verdict_sequence([{'round': 1, 'verdict': 'FAIL'}, {'round': 2, 'verdict': 'PASS'}], 2)
        self.assertEqual(result['status'], 'PASS'); self.assertFalse(result['acceptance_passed'])


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('transport_fixture', SCRIPTS / 'coding-loop-driver-test.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        cls.fixture = f = module.DriverTests()
        f.setUp(); cls.addClassCleanup(f.doCleanups)
        cls.agreement = f.full_loop_fixture('codex')
        cls.baseline = f.git('rev-parse', 'HEAD')
        f.full_tick('phase', 'META-PLANNING')
        f.full_tick('launch'); f.complete_fake_inner()
        f.full_tick('phase', 'EVALUATING'); f.full_tick('phase', 'DIAGNOSING')
        f.full_tick('phase', 'META-PLANNING'); f.full_tick('launch')
        f.git('switch', '-qc', 'normal-inner-repair')
        (f.repo / 'behavior.txt').write_text('repaired\n')
        f.git('add', 'behavior.txt'); f.git('commit', '-qm', 'implement approved repair')
        cls.reviewed = f.git('rev-parse', 'HEAD')
        f.git('switch', '-q', 'main'); f.git('merge', '--squash', 'normal-inner-repair')
        f.git('commit', '-qm', 'squash reviewed repair')
        cls.merged = f.git('rev-parse', 'HEAD')
        (f.project / 'closeout.md').write_text('Normal internal-vault bookkeeping after squash.\n')
        f.git('add', '.'); f.git('commit', '-qm', 'inner closeout')
        cls.integrated = f.git('rev-parse', 'HEAD')
        (f.project / 'retained-report.md').write_text('Retained inner bookkeeping.\n')
        f.git('add', '.'); f.git('commit', '-qm', 'retain report'); f.git('push', '-q')
        f.complete_fake_inner(); f.full_tick('phase', 'EVALUATING')
        cls.operations = [e['operation'] for e in f.full_events('worker')]
        # Internal-vault fixture planning commits precede its first EVAL. Select
        # that evaluated SHA for this synthetic collector fixture only.
        cls.baseline = next(op['code_commit'] for op in cls.operations if op['phase'] == 'EVALUATING')
        for action in ('implement', 'review', 'integrate'):
            path = f.project / (action + '-receipt.md')
            path.write_text('# ' + action + '\nRevision: ' + (cls.integrated if action == 'integrate' else cls.reviewed) + '\nVerdict: PASS\nOffline normal delivery artifact.\n')
        f.git('add', '.'); f.git('commit', '-qm', 'offline delivery receipts'); f.git('push', '-q')

    def setUp(self):
        f = self.fixture
        self.manifest = {'baseline_sha': self.baseline, 'limits': {'max_rounds': 2},
            'first_failure': {'required_ids': ['C1']},
            'harnesses': {'codex': {'code_root': str(f.repo), 'vault_root': str(f.repo / 'vault'),
                'project': str(f.project), 'agreement_revision': self.agreement, 'binding_captures': []}}}
        self.packet = {'operations': copy.deepcopy(self.operations), 'dispatches': [], 'changes': [],
                       'transitions': ['WAITING FOR EVAL', 'WAITING FOR DIAGNOSIS',
                           'WAITING FOR META-PLAN', 'WAITING FOR BUILD', 'BUILDING', 'WAITING FOR EVAL', 'DONE'],
                       'synthetic': True}
        for op in self.operations:
            role = {'META-PLANNING': 'META_PLANNER', 'EVALUATING': 'EVALUATOR', 'DIAGNOSING': 'DIAGNOSER'}[op['phase']]
            self.packet['dispatches'].append({'id': op['id'], 'operation_id': op['id'], 'role': role,
                'harness': 'codex', 'status': 'completed', 'source_commit': op['code_commit'],
                'round': op['round'], 'parent': 'supervisor', 'model': 'codex:pinned', 'effort': 'high'})
        sha = self.operations[-1]['code_commit']
        for role in ('IMPLEMENTER', 'BRANCH_REVIEWER', 'EXECUTOR'):
            self.packet['dispatches'].append({'id': role, 'role': role, 'harness': 'codex',
                'round': 2, 'status': 'completed', 'source_commit': self.integrated if role == 'EXECUTOR' else self.reviewed, 'parent': 'inner-supervisor',
                'model': 'codex:pinned', 'effort': 'high'})
        self.packet['changes'] = [dict(action=action, dispatch_id=role, code_commit=self.integrated if action == 'integrate' else self.reviewed,
            round=2, plan=self.operations[-2]['meta_plan']) for action, role in
            (('implement', 'IMPLEMENTER'), ('review', 'BRANCH_REVIEWER'), ('integrate', 'EXECUTOR'))]
        self.packet['changes'][-1].update(reviewed_commit=self.reviewed, merge_commit=self.merged,
            pr_url='https://github.com/offline/fixture/pull/1',
            pull_request={'url': 'https://github.com/offline/fixture/pull/1', 'state': 'MERGED',
                'baseRefName': 'main', 'headRefOid': self.reviewed, 'mergeCommit': {'oid': self.merged}})
        for change in self.packet['changes']:
            artifact = f.project / (change['action'] + '-receipt.md')
            change['artifact'] = {'path': str(artifact), 'sha256': digest(artifact.read_bytes())}

    def test_collector_validates_actual_integrated_fail_diagnosis_repair_pass(self):
        result = live.inspect_evidence(self.manifest, 'codex', self.packet)
        self.assertEqual(result['status'], 'PASS', result)
        self.assertFalse(result['acceptance_passed'])
        self.assertEqual(len(result['evaluations']), 2)

    def test_provenance_rejects_wrong_pr_head_and_unreviewed_later_code(self):
        self.packet['changes'][-1]['pull_request']['headRefOid'] = self.baseline
        result = live.inspect_evidence(self.manifest, 'codex', self.packet)
        self.assertEqual(result['status'], 'INVALID')
        self.assertIn('PR provenance', result['reason'])
        self.setUp()
        with tempfile.TemporaryDirectory() as folder:
            clone = Path(folder) / 'repo'
            subprocess.run(['git', 'clone', '-q', str(self.fixture.repo), str(clone)], check=True)
            def git(*args): return live.git(clone, *args)
            git('config', 'user.name', 'Offline'); git('config', 'user.email', 'offline@example.invalid')
            (clone / 'behavior.txt').write_text('unreviewed code\n')
            git('add', 'behavior.txt'); git('commit', '-qm', 'unreviewed later change')
            with self.assertRaisesRegex(live.Invalid, 'unreviewed code changed'):
                live.validate_integration(clone, clone / 'vault', git('rev-parse', 'HEAD'),
                    {row['action']: row for row in self.packet['changes']})

    def test_native_pr_query_supplies_git_verified_squash_provenance(self):
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('pr_native', SCRIPTS / '_coding_loop_live_native.py')
        native = importlib.util.module_from_spec(spec); spec.loader.exec_module(native)
        change = self.packet['changes'][-1]
        with tempfile.TemporaryDirectory() as folder:
            gh = Path(folder) / 'gh'
            gh.write_text('#!' + sys.executable + '\nimport json,sys\nassert sys.argv[1:3] == ["pr","view"]\nprint(' + repr(json.dumps(change['pull_request'])) + ')\n')
            gh.chmod(0o700)
            h = dict(self.manifest['harnesses']['codex'], remotes={'code': {'origin': 'https://github.com/offline/fixture.git'}})
            with patch.dict(os.environ, PATH=folder + ':' + os.environ['PATH']):
                change['pull_request'] = native.merged_pull_request(h, change)
                self.assertEqual(live.inspect_evidence(self.manifest, 'codex', self.packet)['status'], 'PASS')
                with self.assertRaisesRegex(native.live.Invalid, 'unlisted fixture remote'):
                    native.merged_pull_request(h, dict(change, pr_url='https://github.com/unlisted/fixture/pull/1'))

    def test_missing_normal_review_artifact_is_invalid(self):
        self.packet['changes'][1].pop('artifact')
        self.assertEqual(live.inspect_evidence(self.manifest, 'codex', self.packet)['status'], 'INVALID')

    def test_controller_written_repair_and_wrong_sha_are_invalid(self):
        self.packet['changes'][0]['dispatch_id'] = 'controller'
        self.assertEqual(live.inspect_evidence(self.manifest, 'codex', self.packet)['status'], 'INVALID')
        self.setUp(); self.packet['operations'][-1]['code_commit'] = 'f' * 40
        self.assertEqual(live.inspect_evidence(self.manifest, 'codex', self.packet)['status'], 'INVALID')

    def test_missing_runtime_role_review_and_full_report_are_incomplete_or_invalid(self):
        self.packet['dispatches'] = []
        self.assertEqual(live.inspect_evidence(self.manifest, 'codex', self.packet)['status'], 'INCOMPLETE')
        self.setUp(); self.packet['changes'] = self.packet['changes'][:1]
        self.assertEqual(live.inspect_evidence(self.manifest, 'codex', self.packet)['status'], 'INCOMPLETE')
        self.setUp(); self.packet['operations'][-1]['report'] = 'not-a-report.md'
        self.assertEqual(live.inspect_evidence(self.manifest, 'codex', self.packet)['status'], 'INVALID')


class NativeHookTests(unittest.TestCase):
    git = LiveTests.git
    save = LiveTests.save
    approve = LiveTests.approve
    checked = LiveTests.checked

    def setUp(self):
        LiveTests.setUp(self)
        native_path = SCRIPTS / '_coding_loop_live_native.py'
        if not native_path.exists(): self.fail('native admission adapter is not implemented')
        spec = importlib.util.spec_from_file_location('native_live', native_path)
        self.native = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.native)
        from unittest.mock import patch
        environment = patch.dict(os.environ, SUPERAGENT_SLUG='codex-inner-1')
        environment.start(); self.addCleanup(environment.stop)
        self.run = self.root / 'runtime.json'
        self.checked()
        self.native.initialize(self.path, 'codex', self.run)

    def event(self, tool='spawn_agent', number=1, role='IMPLEMENTER'):
        return {'hook_event_name': 'PreToolUse', 'session_id': 'parent', 'tool_use_id': str(number),
                'cwd': str(self.repo), 'model': 'pinned-model', 'tool_name': tool,
                'tool_input': {'message': 'STAGE3 role=' + role + ' operation=repair-' + str(number) + ' round=1\nDo work.',
                               'model': 'pinned-model', 'reasoning_effort': 'high'}}

    def claude_child(self):
        self.manifest['harnesses']['claude'], self.manifest['harnesses']['codex'] = self.manifest['harnesses']['codex'], self.manifest['harnesses']['claude']
        for name in ('claude', 'codex'):
            for pin in self.manifest['harnesses'][name]['roles'].values(): pin['model'] = name + ':pinned-model'
        self.save(); self.approve(); self.run = self.root / 'claude-runtime.json'
        self.native.initialize(self.path, 'claude', self.run)
        self.native.hook(self.run, self.event('Agent'))
        self.native.hook(self.run, dict(hook_event_name='PostToolUse', session_id='parent', tool_use_id='1',
            tool_name='Agent', tool_response={'agent_id': 'child'}))
        self.native.hook(self.run, dict(hook_event_name='SubagentStart', session_id='parent', agent_id='child', agent_type='stage3_IMPLEMENTER'))
        transcript = self.root / 'child-transcript.jsonl'
        transcript.write_text(json.dumps({'type': 'assistant', 'message': {'role': 'assistant', 'model': 'pinned-model'}}) + '\n')
        return dict(hook_event_name='SubagentStop', session_id='parent', agent_id='child', agent_type='stage3_IMPLEMENTER',
                    agent_transcript_path=str(transcript), last_assistant_message='Finished.')

    def test_claude_child_git_actor_uses_agent_id_in_shared_session(self):
        stop = self.claude_child()
        self.native.hook(self.run, dict(hook_event_name='PostToolUse', session_id='parent', agent_id='child',
            tool_use_id='git', tool_name='Bash', tool_input={'command': 'git rev-parse HEAD'}, tool_response={'stdout': self.sha}))
        self.native.hook(self.run, stop)
        data = json.loads(self.run.read_text())
        self.assertEqual(data['permits']['parent:1:0']['commits'], [self.sha])
        self.assertNotIn('parent', data['actions'])

    def test_claude_observed_effort_object_normalizes_without_trusting_request(self):
        stop = self.claude_child(); stop['effort'] = {'level': 'high'}
        self.native.hook(self.run, stop)
        data = json.loads(self.run.read_text())
        self.assertEqual(data['permits']['parent:1:0']['actual_effort'], 'high')
        self.assertEqual(data['problems'], [])
        for malformed in ({}, {'level': 3}, ['high']):
            with self.subTest(malformed=malformed), self.assertRaises(self.native.live.Invalid):
                self.native.hook(self.run, dict(stop, effort=malformed))
        with self.native.transaction(self.run) as data: data['permits']['parent:1:0']['status'] = 'permitted'
        self.native.hook(self.run, dict(stop, effort={'level': 'low'}))
        self.assertTrue(any('effort mismatch' in p for p in json.loads(self.run.read_text())['problems']))

    def test_standalone_cleanup_reaps_discovered_detached_groups_and_watchdog(self):
        self.cleanup_detached_fixture(check_bindings=False)

    def test_standalone_cleanup_rejects_tampered_binding_and_process_identity(self):
        self.cleanup_detached_fixture(check_bindings=True)

    def cleanup_detached_fixture(self, check_bindings):
        cli = self.root / 'fake-cli'; cli.write_text('offline')
        self.manifest['harnesses']['codex']['runtime'] = dict(cli=str(cli), cli_version='offline',
            scripts_root=str(SCRIPTS), config_root=str(self.root / 'config'), launchd_dir=str(self.root / 'LaunchAgents'),
            outer_loop=str(self.project / 'loop-status/outer.md'), interval_seconds=1)
        self.save(); self.approve()
        bin_dir = self.root / 'scheduler-bin'; bin_dir.mkdir()
        for name, code in (('launchctl', 113), ('systemctl', 3)):
            executable = bin_dir / name; executable.write_text('#!/bin/sh\nexit ' + str(code) + '\n'); executable.chmod(0o700)
        processes = [subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True) for _ in range(3)]
        def reap():
            for process in processes:
                if process.poll() is None: os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        self.addCleanup(reap)
        records = []
        for process in processes:
            observation = subprocess.run(['ps', '-p', str(process.pid), '-o', 'lstart='], text=True, capture_output=True, check=True)
            self.assertTrue(observation.stdout.strip())
            records.append(dict(pid=process.pid, start=observation.stdout.strip(), slug='codex-inner-1'))
        attempt = live.new_attempt(self.manifest, self.path, 'run', 'codex')
        runtime = attempt / 'native-runtime.json'; self.native.initialize(attempt / 'manifest.json', 'codex', runtime)
        with self.native.transaction(runtime) as data:
            data['processes'][str(processes[0].pid)] = records[0]
        second_attempt = live.new_attempt(self.manifest, self.path, 'run', 'codex')
        second_runtime = second_attempt / 'native-runtime.json'
        self.native.initialize(second_attempt / 'manifest.json', 'codex', second_runtime)
        with self.native.transaction(second_runtime) as data:
            data['watchdog'] = dict(records[1], slug='codex-outer-1')
        args = [sys.executable, str(PATH), 'cleanup', '--manifest', str(self.path), '--harness', 'codex']
        env = dict(os.environ, PATH=str(bin_dir) + ':' + os.environ['PATH'])
        if check_bindings:
            # Tampered binding is not process-kill authorization.
            with self.native.transaction(runtime) as data: data['manifest_sha256'] = '0' * 64
            rejected = subprocess.run(args, env=env, text=True, capture_output=True, timeout=10)
            self.assertNotEqual(rejected.returncode, 0, rejected.stdout)
            self.assertTrue(all(p.poll() is None for p in processes))
            with self.native.transaction(runtime) as data: data['manifest_sha256'] = digest(self.path.read_bytes())
            with self.native.transaction(runtime) as data: data['processes'][str(processes[0].pid)]['start'] = 'wrong process start'
            mismatched = subprocess.run(args, env=env, text=True, capture_output=True, timeout=10)
            self.assertEqual(json.loads(mismatched.stdout)['status'], 'INCOMPLETE')
            self.assertIsNone(processes[0].poll(), 'cleanup killed a group whose identity mismatched')
            self.assertIsNone(processes[2].poll())
            with self.native.transaction(runtime) as data: data['processes'][str(processes[0].pid)] = records[0]
        cleaned = subprocess.run(args, env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual(cleaned.returncode, 0, cleaned.stdout + cleaned.stderr)
        self.assertEqual(json.loads(cleaned.stdout)['status'], 'PASS')
        self.assertIsNotNone(processes[0].poll(), 'standalone cleanup left native detached worker alive')
        self.assertIsNotNone(processes[1].poll(), 'standalone cleanup left watchdog alive')
        self.assertIsNone(processes[2].poll(), 'cleanup killed an unrelated detached process')
        self.assertTrue(json.loads(runtime.read_text())['stopped'])
        self.assertTrue(json.loads(second_runtime.read_text())['stopped'])

    def test_native_hook_counts_followups_and_concurrent_reservations(self):
        for index, name in enumerate(('spawn_agent', 'followup_task', 'resume_agent'), 1):
            event = self.event(name, index)
            if name != 'spawn_agent': event['tool_input']['target'] = 'known-child'
            self.native.hook(self.run, event)
            if name == 'spawn_agent':
                self.native.hook(self.run, dict(hook_event_name='PostToolUse', session_id='parent', tool_use_id='1', tool_name=name, tool_response={'agent_id': 'known-child'}))
        with self.assertRaises(self.native.live.Exhausted): self.native.hook(self.run, self.event(number=4))
        self.assertEqual(json.loads(self.run.read_text())['used'], 3)

    def test_missing_role_and_foreign_pin_denied_before_spawn(self):
        event = self.event(); event['tool_input']['message'] = 'ordinary prompt with no role binding'
        with self.assertRaises(self.native.live.Invalid): self.native.hook(self.run, event)
        event = self.event(); event['tool_input']['model'] = 'foreign-model'
        with self.assertRaises(self.native.live.Invalid): self.native.hook(self.run, event)
        self.assertEqual(json.loads(self.run.read_text())['used'], 0)

    def test_hook_cli_denies_with_exit_two_and_preserves_receipt(self):
        event = self.event(); event['tool_input']['model'] = 'wrong'
        process = subprocess.run([sys.executable, str(SCRIPTS / '_coding_loop_live_native.py'), 'hook', str(self.run)],
                                 input=json.dumps(event), capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(json.loads(process.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertTrue(Path(str(self.run) + '.events.jsonl').exists())

    def test_runtime_actual_model_mismatch_invalidates_receipt(self):
        self.native.hook(self.run, self.event())
        self.native.hook(self.run, {'hook_event_name': 'SubagentStart', 'agent_id': 'child',
            'session_id': 'parent', 'cwd': str(self.repo), 'model': 'wrong', 'agent_type': 'general'})
        self.native.hook(self.run, {'hook_event_name': 'PostToolUse', 'tool_name': 'spawn_agent',
            'session_id': 'parent', 'tool_use_id': '1', 'tool_response': {'agent_id': 'child'}})
        problems = json.loads(self.run.read_text())['problems']
        self.assertTrue(any('model' in p for p in problems))

    def test_pi_parallel_children_consume_individual_budget_slots(self):
        self.manifest['harnesses']['codex']['roles']['IMPLEMENTER']['model'] = 'codex:pinned-model'
        event = self.event(); event['tool_name'] = 'subagent'
        event['tool_input'] = {'tasks': [{'task': 'STAGE3 role=IMPLEMENTER operation=one round=1', 'model': 'pinned-model'},
                                      {'task': 'STAGE3 role=IMPLEMENTER operation=two round=1', 'model': 'pinned-model'}]}
        # Test the native Pi cardinality parser with its own approved fixture root.
        m = copy.deepcopy(self.manifest)
        m['harnesses']['pi'], m['harnesses']['codex'] = m['harnesses']['codex'], m['harnesses']['pi']
        for name in ('pi', 'codex'):
            for pin in m['harnesses'][name]['roles'].values(): pin['model'] = name + ':pinned-model'
        self.path.write_text(json.dumps(m)); self.approve()
        self.run = self.root / 'pi-runtime.json'; self.native.initialize(self.path, 'pi', self.run)
        self.native.hook(self.run, event)
        self.assertEqual(json.loads(self.run.read_text())['used'], 2)

    def test_bridge_role_telemetry_is_supplied_without_altering_argv(self):
        bin_dir = self.root / 'bin'; bin_dir.mkdir()
        target = bin_dir / 'claude'
        output = self.root / 'bridge.json'
        target.write_text('#!' + sys.executable + '\nimport json,os,sys\nopen(' + repr(str(output)) +
                          ',"w").write(json.dumps({"role":os.environ.get("SUPERAGENT_ROLE"),"argv":sys.argv[1:]}))\nprint("ok")\n')
        target.chmod(0o700)
        prompt = self.root / 'prompt.txt'; prompt.write_text('offline')
        process = subprocess.run(['/bin/bash', str(SCRIPTS / 'role-bridge.sh'), '--harness', 'claude',
            '--role', 'implementer', '--cwd', str(self.repo), '--prompt-file', str(prompt)],
            env=dict(os.environ, PATH=str(bin_dir) + ':' + os.environ['PATH'], TMPDIR=str(self.root)),
            capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        receipt = json.loads(output.read_text())
        self.assertEqual(receipt['role'], 'implementer')
        self.assertEqual(receipt['argv'], ['-p', '--allowedTools', 'Read,Edit,Write,Bash,Grep,Glob'])

    def test_native_wrapper_caps_actual_process_and_clears_inherited_bridge_role(self):
        h, _response = self.package_cli_fixture()
        cli = Path(h['runtime']['cli'])
        output = self.root / 'native-process.json'
        cli.write_text(cli.read_text().replace("else: print(json.dumps", "elif 'exec' in sys.argv: open(" + repr(str(output)) + ", 'w').write(json.dumps({'role':os.environ.get('SUPERAGENT_ROLE'),'argv':sys.argv[1:]}))\nelse: print(json.dumps").replace('import sys,json', 'import sys,json,os'))
        h['runtime'].update(cli_version='offline', scripts_root=str(SCRIPTS),
            launchd_dir=str(self.root / 'LaunchAgents'), outer_loop=str(self.root / 'outer.md'), interval_seconds=1)
        for name in ('prd.md', 'evaluation.md', 'knowledge-base.md'):
            path = self.project / name
            path.write_text(path.read_text() + '**Date:** 2026-09-09 · **Status:** READY\n')
        self.git('add', '.'); self.git('commit', '-qm', 'ready offline agreement')
        h['agreement_revision'] = live.state.acceptance_context(self.repo, self.repo / 'vault', self.project)['agreement_revision']
        for ref in h['agreement']: ref['sha256'] = digest(Path(ref['path']).read_bytes())
        outer = {key: '' for key in live.state.REQUIRED_FIELDS}
        outer.update(supervisor='supercode', project=str(self.project.relative_to(self.repo)), status='BUILDING', driver='external',
            iteration=1, session_skill_count=0, round=1, agreement_revision=h['agreement_revision'], operation={key: '' for key in live.state.OPERATION_FIELDS})
        Path(h['runtime']['outer_loop']).write_bytes(live.state._serialize_state(outer))
        self.save(); self.approve()
        bin_dir = self.root / 'bin'; bin_dir.mkdir()
        ps = bin_dir / 'ps'; ps.write_text('#!/bin/sh\nprintf \'offline-process-start\\n\'\n'); ps.chmod(0o700)
        self.run = self.root / 'wrapper-runtime.json'; self.native.initialize(self.path, 'codex', self.run)
        process = subprocess.run([sys.executable, str(SCRIPTS / '_coding_loop_live_native.py'), 'wrapper', str(self.run),
            'exec', 'STAGE3 role=IMPLEMENTER operation=worker round=1', '-m', 'stale-model'],
            env=dict(os.environ, SUPERAGENT_ROLE='implementer', PATH=str(bin_dir) + ':' + os.environ['PATH']), capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        receipt = json.loads(output.read_text())
        self.assertIsNone(receipt['role'])
        self.assertIn('--dangerously-bypass-hook-trust', receipt['argv'])
        self.assertNotIn('stale-model', receipt['argv'])
        self.assertEqual(receipt['argv'].count('-m'), 1)
        self.assertEqual(json.loads(self.run.read_text())['used'], 1)
        # Loss of a child ownership receipt must reap the already-started group.
        cli.write_text(cli.read_text().replace("elif 'exec' in sys.argv: open(", "elif 'exec' in sys.argv: __import__('time').sleep(4); open("))
        ps.write_text('#!/bin/sh\nexit 1\n')
        self.run = self.root / 'unowned-runtime.json'; self.native.initialize(self.path, 'codex', self.run)
        started = time.monotonic()
        process = subprocess.run([sys.executable, str(SCRIPTS / '_coding_loop_live_native.py'), 'wrapper', str(self.run),
            'exec', 'STAGE3 role=IMPLEMENTER operation=worker round=1'],
            env=dict(os.environ, SUPERAGENT_ROLE='implementer', PATH=str(bin_dir) + ':' + os.environ['PATH']),
            capture_output=True, text=True, timeout=3)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('ownership receipt unavailable', process.stderr)
        self.assertLess(time.monotonic() - started, 3)

        # Read-only package selection may consume time, but cannot extend the
        # already reserved worker deadline or start a worker after it expires.
        output.unlink()
        ps.write_text('#!/bin/sh\nprintf "offline-process-start\\n"\n')
        cli.write_text(cli.read_text().replace("__import__('time').sleep(4); ", '').replace("if '--help' in sys.argv:", "if '--help' in sys.argv: __import__('time').sleep(1.2);"))
        self.run = self.root / 'expired-selection-runtime.json'; self.native.initialize(self.path, 'codex', self.run)
        process = subprocess.run([sys.executable, str(SCRIPTS / '_coding_loop_live_native.py'), 'wrapper', str(self.run),
            'exec', 'STAGE3 role=IMPLEMENTER operation=worker round=1'],
            env=dict(os.environ, SUPERAGENT_ROLE='implementer', PATH=str(bin_dir) + ':' + os.environ['PATH']),
            capture_output=True, text=True, timeout=3)
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse(output.exists(), 'expired reservation must not start a worker')

    def test_scheduler_path_augmentation_preserves_admission_wrapper(self):
        wrapper_dir = self.root / 'admission-bin'; wrapper_dir.mkdir()
        for name in ('claude', 'codex', 'pi', 'agent', 'cursor-agent'):
            target = wrapper_dir / name; target.write_text('#!/bin/sh\nexit 0\n'); target.chmod(0o700)
        env = dict(os.environ, PATH=self.native.admission_path(wrapper_dir), SUPERAGENT_CLI_PATH=str(wrapper_dir))
        command = '. "$1"; _superagent_augment_path; command -v codex; superagent_cli_path_dirs'
        process = subprocess.run(['/bin/bash', '-c', command, 'test', str(SCRIPTS / '_common.sh')], env=env,
                                 text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout.splitlines(), [str(wrapper_dir / 'codex'), str(wrapper_dir)])


    def test_independent_watchdog_stops_only_owned_outer_and_inner(self):
        scripts = self.root / 'fake-scheduler'; scripts.mkdir()
        calls = self.root / 'cleanup-calls.jsonl'
        stop = scripts / 'stop.sh'
        stop.write_text('#!/bin/sh\nexec ' + shlex.join([sys.executable, str(scripts / 'stop.py')]) + ' "$@"\n')
        (scripts / 'stop.py').write_text('import json,sys\nwith open(' + repr(str(calls)) + ',"a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n')
        cli = self.root / 'fake-native'; cli.write_text('unused')
        self.manifest['harnesses']['codex']['runtime'] = {'cli': str(cli), 'cli_version': 'offline',
            'scripts_root': str(scripts), 'config_root': str(self.root / 'config'),
            'launchd_dir': str(self.root / 'LaunchAgents'), 'outer_loop': str(self.root / 'outer.md'), 'interval_seconds': 1}
        self.manifest['harnesses']['codex']['runtime']['outer_loop'] = str(self.project / 'loop-status/outer.md')
        conf = self.root / 'config/superagent'; conf.mkdir(parents=True)
        for registration in self.manifest['harnesses']['codex']['cleanup']['registrations']:
            loop = self.project / ('loop-status/outer.md' if registration['supervisor'] == 'supercode' else 'loop-status/inner.md')
            (conf / (registration['slug'] + '.env')).write_text('REPO=' + str(self.repo) + '\nLOOP_FILE=' + str(loop) +
                '\nSUPERAGENT_SLUG=' + registration['slug'] + '\nSUPERAGENT_SUPERVISOR=' + registration['supervisor'] + '\n')
        self.save(); self.approve(); self.run = self.root / 'watchdog-runtime.json'
        self.native.initialize(self.path, 'codex', self.run)
        with self.native.transaction(self.run) as data: data['deadline'] = time.monotonic() + 0.15
        bin_dir = self.root / 'bin'; bin_dir.mkdir()
        for name in ('launchctl', 'systemctl'):
            p = bin_dir / name; p.write_text('#!/bin/sh\nexit ' + ('113' if name == 'launchctl' else '3') + '\n'); p.chmod(0o700)
        started = time.monotonic()
        process = subprocess.run([sys.executable, str(SCRIPTS / '_coding_loop_live_native.py'), 'watchdog', str(self.run)],
            env=dict(os.environ, PATH=str(bin_dir) + ':' + os.environ['PATH']), capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual([json.loads(line) for line in calls.read_text().splitlines()],
                         [['--slug', 'codex-outer-1', '--hard'], ['--slug', 'codex-inner-1', '--hard']])
        self.assertTrue(json.loads(self.run.read_text())['stopped'])


    def test_pi_extension_executes_tool_call_blocking_contract_offline(self):
        m = copy.deepcopy(self.manifest)
        m['harnesses']['pi'], m['harnesses']['codex'] = m['harnesses']['codex'], m['harnesses']['pi']
        for name in ('pi', 'codex'):
            for pin in m['harnesses'][name]['roles'].values(): pin['model'] = name + ':offline/pinned-model'
        self.path.write_text(json.dumps(m)); self.approve()
        self.run = self.root / 'extension-runtime.json'; self.native.initialize(self.path, 'pi', self.run)
        runner = self.root / 'extension-test.mjs'
        runner.write_text('import install from ' + json.dumps((SCRIPTS / 'coding-loop-stage3-pi.ts').as_uri()) + ';\n' +
            "const callbacks = {}; const pi = {on:(name,fn)=>callbacks[name]=fn,getThinkingLevel:()=> 'high'};\n" +
            'const ctx = {cwd:' + json.dumps(str(self.repo)) + ",model:{provider:'offline',id:'pinned-model'},sessionManager:{getSessionId:()=> 'parent',getBranch:()=>[]}};\n" +
            "install(pi); await callbacks.session_start({},ctx);\n" +
            "await callbacks.tool_result({toolName:'bash',toolCallId:'git',input:{command:'git rev-parse HEAD'},content:[{type:'text',text:'" + 'a' * 40 + "'}],details:{}},ctx);\n" +
            "const input={task:'STAGE3 role=IMPLEMENTER operation=work round=1',model:'offline/pinned-model',thinking:'high'};\n" +
            "await callbacks.tool_call({toolName:'subagent',toolCallId:'one',input},ctx);\n" +
            "const blocked=await callbacks.tool_call({toolName:'subagent',toolCallId:'two',input},ctx);\n" +
            "process.stdout.write(JSON.stringify({blocked,input}));\n")
        process = subprocess.run(['node', '--experimental-strip-types', '--no-warnings', str(runner)],
            env=dict(os.environ, SUPER_STAGE3_RUN=str(self.run), SUPER_STAGE3_PYTHON=sys.executable),
            capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertTrue(result['blocked']['block'])
        self.assertEqual(result['input']['thinking'], 'high')
        self.assertEqual(json.loads(self.run.read_text())['used'], 1)
        self.assertEqual(json.loads(self.run.read_text()).get('actions', {}).get('parent'), ['a' * 40])

    def package_cli_fixture(self, harness='codex'):
        package = self.root / ('selected-' + harness)
        manifest_dir = '.claude-plugin' if harness == 'claude' else '.codex-plugin'
        metadata = package / ('package.json' if harness == 'pi' else manifest_dir + '/plugin.json')
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text(json.dumps({'name': 'superagent', 'version': '0.8.1'}))
        skills = []
        for name in ('supercode', 'supermeta', 'supereval', 'superdiagnose', 'superrun', 'superagent', 'supergoal', 'superplan', 'superfinish'):
            path = package / 'skills' / name / 'SKILL.md'; path.parent.mkdir(parents=True)
            path.write_text('---\nname: ' + name + '\n---\nReviewed offline skill.\n')
            skills.append(dict(name=name, path=str(path), pluginId='superagent@offline', enabled=True, scope='user'))
        response = self.root / ('selection-' + harness + '.json')
        response.write_text(json.dumps({'installed': [dict(pluginId='superagent@offline', name='superagent', version='0.8.1', installed=True, enabled=True)], 'skills': skills}))
        cli = self.root / ('selection-cli-' + harness)
        cli.write_text('#!' + sys.executable + '\n' + """import sys,json
from pathlib import Path
record=json.loads(Path(RESPONSE).read_text())
if '--help' in sys.argv: print('--plugin-dir --settings --skill --no-skills --dangerously-bypass-hook-trust')
elif 'app-server' in sys.argv:
    for line in sys.stdin:
        request=json.loads(line)
        if 'id' not in request: continue
        result={} if request['method']=='initialize' else {'data':[{'cwd':request['params']['cwds'][0],'errors':[], 'skills':record['skills']}]}
        print(json.dumps({'id':request['id'],'result':result}),flush=True)
else: print(json.dumps(record['installed'] if HARNESS=='claude' else {'installed':record['installed']}))
""".replace('RESPONSE', repr(str(response))).replace('HARNESS', repr(harness)))
        cli.chmod(0o700)
        h = self.manifest['harnesses'][harness]
        h['runtime'] = dict(cli=str(cli), config_root=str(self.root / 'config'),
                            package_selection=dict(root=str(package), **({'plugin_id': 'superagent@offline'} if harness == 'codex' else {})))
        Path(h['code_root']).mkdir(exist_ok=True)
        h['packages'] = [dict(path=str(path), sha256=digest(path.read_bytes()), version='0.8.1') for path in package.rglob('*') if path.is_file()]
        if harness == 'claude': response.write_text(json.dumps({'installed': []}))
        return h, response

    def test_codex_selection_requires_actual_enabled_skill_paths_and_version(self):
        h, response = self.package_cli_fixture()
        good = json.loads(response.read_text())
        selected = self.native.selected_package(self.manifest, 'codex')
        self.assertEqual(selected['root'], h['runtime']['package_selection']['root'])
        variants = []
        missing = copy.deepcopy(good); missing['installed'] = []; variants.append(missing)
        disabled = copy.deepcopy(good); disabled['installed'][0]['enabled'] = False; variants.append(disabled)
        ambiguous = copy.deepcopy(good); ambiguous['installed'] *= 2; variants.append(ambiguous)
        wrong = copy.deepcopy(good); wrong['skills'][0]['path'] = str(self.protocol); variants.append(wrong)
        duplicate = copy.deepcopy(good); duplicate['skills'].append(dict(good['skills'][0], pluginId='another@market')); variants.append(duplicate)
        version = copy.deepcopy(good); version['installed'][0]['version'] = 'old'; variants.append(version)
        for variant in variants:
            response.write_text(json.dumps(variant))
            with self.assertRaises((self.native.live.Invalid, self.native.live.Incomplete)):
                self.native.selected_package(self.manifest, 'codex')
        response.write_text(json.dumps(good))
        Path(good['skills'][0]['path']).write_text('changed installed bytes')
        with self.assertRaises(self.native.live.Invalid): self.native.selected_package(self.manifest, 'codex')

    def test_explicit_claude_and_pi_selection_pins_loading_and_rejects_duplicates(self):
        for harness in ('claude', 'pi'):
            h, response = self.package_cli_fixture(harness)
            selected = self.native.selected_package(self.manifest, harness)
            self.assertEqual(selected['root'], h['runtime']['package_selection']['root'])
            self.save(); self.approve()
            argv = self.native.inject(harness, ['-p', 'offline'], self.run)
            self.assertIn('--plugin-dir' if harness == 'claude' else '--skill', argv)
            self.assertIn(selected['root'] if harness == 'claude' else selected['root'] + '/skills', argv)
            if harness == 'pi':
                argv = self.native.inject(harness, ['-p', '--skill', str(SCRIPTS.parent / 'pi/skills'), 'offline'], self.run)
                self.assertEqual(argv.count('--skill'), 1)
                with self.assertRaises(self.native.live.Invalid):
                    self.native.inject(harness, ['--skill', str(self.root / 'unlisted')], self.run)
            if harness == 'claude':
                response.write_text(json.dumps({'installed': [{'id': 'superagent@a', 'enabled': True}]}))
                argv = self.native.inject(harness, ['-p', 'offline'], self.run)
                self.assertEqual(json.loads(argv[argv.index('--settings') + 1])['enabledPlugins'], {'superagent@a': False})
                response.write_text(json.dumps({'installed': [{'id': 'superagent@a', 'enabled': True}, {'id': 'superagent@b', 'enabled': True}]}))
                with self.assertRaises(self.native.live.Invalid): self.native.selected_package(self.manifest, harness)

    def test_missing_selected_package_fails_preflight_before_scheduler(self):
        from unittest.mock import patch
        h, response = self.package_cli_fixture()
        cli = Path(h['runtime']['cli'])
        cli.write_text(cli.read_text().replace("if '--help' in sys.argv:", "if '--version' in sys.argv: print('offline-cli')\nelif '--help' in sys.argv:"))
        h['runtime'].update(cli_version='offline-cli', scripts_root=str(SCRIPTS), launchd_dir=str(self.root / 'LaunchAgents'),
            outer_loop=str(self.root / 'outer.md'), interval_seconds=1)
        for path in [cli, Path(self.native.__file__), PATH] + [SCRIPTS / name for name in
                ('launch.sh', 'stop.sh', 'install-timer.sh', 'uninstall-timer.sh', 'superagent-tick.sh', '_common.sh', 'role-bridge.sh')]:
            h['packages'].append(dict(path=str(path), sha256=digest(path.read_bytes()), version='0.8.1'))
        timeout = self.root / 'timeout'; timeout.write_text('#!/bin/sh\nprintf "GNU coreutils offline\\n"\n'); timeout.chmod(0o700)
        record = json.loads(response.read_text()); record['installed'] = []; response.write_text(json.dumps(record))
        with patch.object(self.native.shutil, 'which', return_value=str(timeout)):
            with self.assertRaisesRegex(self.native.live.Invalid, 'selected Codex plugin'):
                self.native.native_preflight(self.manifest, 'codex')
        self.assertFalse(Path(h['runtime']['config_root']).exists())
        self.assertFalse(Path(h['runtime']['outer_loop']).exists())

    def test_native_preflight_refuses_missing_gnu_timeout_before_arming(self):
        from unittest.mock import patch
        cli = self.root / 'fake-cli'
        cli.write_text('#!/bin/sh\nprintf \'offline-cli\\n\'\n'); cli.chmod(0o700)
        self.manifest['harnesses']['codex']['runtime'] = {'cli': str(cli), 'cli_version': 'offline-cli',
            'scripts_root': str(SCRIPTS), 'config_root': str(self.root / 'config'),
            'launchd_dir': str(self.root / 'LaunchAgents'), 'outer_loop': str(self.project / 'loop-status/outer.md'), 'interval_seconds': 1}
        with patch.object(self.native.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(self.native.live.Incomplete, 'GNU timeout'):
                self.native.native_preflight(self.manifest, 'codex')
        self.assertFalse((self.root / 'config').exists())


    def test_runtime_child_ids_decode_native_json_and_pi_session_headers(self):
        self.assertEqual(self.native.child_ids('{"agent_id":"child"}'), ['child'])
        self.assertEqual(self.native.child_ids('The child id is child; this is prose.'), [])
        paths = []
        for number in (0, 1):
            path = self.root / ('session-' + str(number) + '.jsonl')
            path.write_text(json.dumps({'type': 'session', 'id': 'child-' + str(number)}) + '\n')
            paths.append(str(path))
        receipt = {'details': {'results': [{'index': 1, 'sessionFile': paths[1]}, {'index': 0, 'sessionFile': paths[0]}]}}
        self.assertEqual(self.native.child_ids(receipt), ['child-0', 'child-1'])


    def test_codex_runtime_effort_and_usage_are_extracted_without_archiving_transcript(self):
        self.native.hook(self.run, self.event())
        self.native.hook(self.run, dict(hook_event_name='PostToolUse', session_id='parent', tool_use_id='1',
                                      tool_name='spawn_agent', tool_response={'agent_id': 'child'}))
        transcript = self.root / 'private-runtime.jsonl'
        transcript.write_text(json.dumps({'type': 'turn_context', 'payload': {'model': 'pinned-model', 'effort': 'high', 'private': 'not-archived'}}) + '\n' +
            json.dumps({'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {'total_token_usage': {'input_tokens': 10, 'output_tokens': 5}}}}) + '\n')
        self.native.hook(self.run, dict(hook_event_name='SubagentStop', session_id='parent', agent_id='child',
            cwd=str(self.repo), model='pinned-model', agent_transcript_path=str(transcript)))
        permit = next(iter(json.loads(self.run.read_text())['permits'].values()))
        self.assertEqual(permit['actual_effort'], 'high')
        self.assertEqual(permit['usage']['output_tokens'], 5)
        self.assertNotIn('not-archived', Path(str(self.run) + '.events.jsonl').read_text())


    def test_actual_native_final_result_retains_scrubbed_review_output(self):
        self.native.hook(self.run, self.event(role='BRANCH_REVIEWER'))
        self.native.hook(self.run, dict(hook_event_name='PostToolUse', session_id='parent', tool_use_id='1',
                                      tool_name='spawn_agent', tool_response={'agent_id': 'reviewer'}))
        reported = dict(action='review', round=1, code_commit=self.sha, plan='reviewed-plan.md',
                        artifact={'path': str(self.protocol), 'sha256': digest(self.protocol.read_bytes())}, verdict='PASS')
        message = 'Review completed. token=private-value\nSTAGE3_RESULT ' + json.dumps(reported)
        self.native.hook(self.run, dict(hook_event_name='SubagentStop', session_id='parent', agent_id='reviewer',
            cwd=str(self.repo), model='pinned-model', last_assistant_message=message))
        permit = next(iter(json.loads(self.run.read_text())['permits'].values()))
        self.assertEqual(permit['result'], reported)
        archived = Path(permit['final_response']['path']).read_text()
        self.assertIn('Review completed.', archived)
        self.assertNotIn('private-value', archived)
        self.assertEqual(digest(archived.encode()), permit['final_response']['sha256'])


    def test_native_observer_accepts_only_real_empty_operation_bootstrap(self):
        spec = importlib.util.spec_from_file_location('bootstrap_fixture', SCRIPTS / 'coding-loop-driver-test.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        f = module.DriverTests(); f.setUp(); self.addCleanup(f.doCleanups)
        agreement = f.full_loop_fixture('claude')
        snapshot = live.state.read_state(f.outer)
        self.assertEqual(snapshot['agreement_revision'], 'PENDING')
        h = self.manifest['harnesses']['codex']
        h.update(project=str(f.project), code_root=str(f.repo), vault_root=str(f.repo / 'vault'),
                 agreement_revision=agreement, runtime={'outer_loop': str(f.outer)})
        h['agreement'] = [dict(path=str(f.project / name), sha256=digest(live.evidence._without_iteration_ledger((f.project / name).read_bytes()) if name == 'prd.md' else (f.project / name).read_bytes()),
            mode='prd-without-ledger' if name == 'prd.md' else 'bytes')
            for name in ('prd.md', 'evaluation.md', 'knowledge-base.md')]
        with self.native.transaction(self.run) as data:
            deadline = data['deadline']
            self.native.observe_agreement(self.manifest, 'codex', snapshot)
            self.assertEqual(data['deadline'], deadline)
            request = self.native.pin_request(self.manifest, 'codex', self.event(), self.event()['tool_input'])
            with self.assertRaisesRegex(self.native.live.Invalid, 'fingerprint'):
                self.native.reserve(data, self.manifest, [request])
            self.assertEqual(data['used'], 0)
            frozen = dict(snapshot, agreement_revision=agreement)
            f.outer.write_bytes(live.state._serialize_state(frozen))
            self.native.reserve(data, self.manifest, [request])
            self.assertEqual(data['used'], 1)
            self.assertEqual(data['deadline'], deadline)
        for changes in ({'status': 'WAITING FOR EVAL'}, {'operation': {'phase': 'EVALUATING'}}, {'agreement_revision': 'wrong'}):
            with self.assertRaises(self.native.live.Invalid):
                self.native.observe_agreement(self.manifest, 'codex', dict(snapshot, **changes))
        (f.project / 'evaluation.md').write_text('changed')
        with self.assertRaises(self.native.live.Invalid):
            self.native.observe_agreement(self.manifest, 'codex', snapshot)

    def test_native_cli_argv_injection_has_no_shell_interpolation(self):
        for harness in ('codex', 'claude', 'pi'):
            self.package_cli_fixture(harness); self.save(); self.approve()
            argv = self.native.inject(harness, ['literal;$(touch NEVER)'], self.run)
            self.assertIn('literal;$(touch NEVER)', argv)
            self.assertTrue(all(isinstance(arg, str) for arg in argv))
            self.assertFalse((self.repo / 'NEVER').exists())


if __name__ == '__main__': unittest.main()

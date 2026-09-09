#!/usr/bin/env python3
"""Offline tests; synthetic receipts and approval records never authorize live runs."""
import copy
import hashlib
import importlib.util
import json
import os
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
        f.complete_fake_inner(repair=True); f.full_tick('phase', 'EVALUATING')
        cls.operations = [e['operation'] for e in f.full_events('worker')]
        # Internal-vault fixture planning commits precede its first EVAL. Select
        # that evaluated SHA for this synthetic collector fixture only.
        cls.baseline = next(op['code_commit'] for op in cls.operations if op['phase'] == 'EVALUATING')
        for action in ('implement', 'review', 'integrate'):
            path = f.project / (action + '-receipt.md')
            path.write_text('# ' + action + '\nRevision: ' + cls.operations[-1]['code_commit'] + '\nVerdict: PASS\nOffline normal delivery artifact.\n')
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
                'round': 2, 'status': 'completed', 'source_commit': sha, 'parent': 'inner-supervisor',
                'model': 'codex:pinned', 'effort': 'high'})
        self.packet['changes'] = [dict(action=action, dispatch_id=role, code_commit=sha,
            round=2, plan=self.operations[-2]['meta_plan']) for action, role in
            (('implement', 'IMPLEMENTER'), ('review', 'BRANCH_REVIEWER'), ('integrate', 'EXECUTOR'))]
        for change in self.packet['changes']:
            artifact = f.project / (change['action'] + '-receipt.md')
            change['artifact'] = {'path': str(artifact), 'sha256': digest(artifact.read_bytes())}

    def test_collector_validates_actual_integrated_fail_diagnosis_repair_pass(self):
        result = live.inspect_evidence(self.manifest, 'codex', self.packet)
        self.assertEqual(result['status'], 'PASS', result)
        self.assertFalse(result['acceptance_passed'])
        self.assertEqual(len(result['evaluations']), 2)

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
        cli = self.root / 'fake-native'
        output = self.root / 'native-process.json'
        cli.write_text('#!' + sys.executable + '\nimport json,os,sys\nopen(' + repr(str(output)) +
                       ',"w").write(json.dumps({"role":os.environ.get("SUPERAGENT_ROLE"),"argv":sys.argv[1:]}))\n')
        cli.chmod(0o700)
        self.manifest['harnesses']['codex']['runtime'] = {'cli': str(cli), 'cli_version': 'offline',
            'scripts_root': str(SCRIPTS), 'config_root': str(self.root / 'config'),
            'launchd_dir': str(self.root / 'LaunchAgents'), 'outer_loop': str(self.root / 'outer.md'), 'interval_seconds': 1}
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
        cli.write_text('#!' + sys.executable + '\nimport time\ntime.sleep(4)\n')
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


    def test_native_cli_argv_injection_has_no_shell_interpolation(self):
        for harness in ('codex', 'claude', 'pi'):
            argv = self.native.inject(harness, ['-p', 'literal;$(touch NEVER)'], self.run)
            self.assertIn('literal;$(touch NEVER)', argv)
            self.assertTrue(all(isinstance(arg, str) for arg in argv))
            self.assertFalse((self.repo / 'NEVER').exists())


if __name__ == '__main__': unittest.main()

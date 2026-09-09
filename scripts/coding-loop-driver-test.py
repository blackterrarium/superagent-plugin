#!/usr/bin/env python3
"""Offline real-driver tests: disposable Git roots and fake external executables."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import _coding_loop_state as state


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='coding driver ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 'driver@example.invalid')
        self.git('config', 'user.name', 'Driver Test')
        (self.repo / 'README.md').write_text('fixture\n')
        (self.repo / '.gitignore').write_text('loop-status/\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.project = self.repo / 'vault/projects/project with spaces'
        self.project.mkdir(parents=True)
        self.valid_project()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.calls = self.root / 'calls.jsonl'
        fake = '''#!PYTHON
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
with open(os.environ['FAKE_CALLS'], 'a') as out:
    out.write(json.dumps({'name': name, 'argv': sys.argv[1:], 'stdin': sys.stdin.read() if name == 'pi' else ''}) + '\\n')
if name == 'uname': print(os.environ.get('FAKE_OS', 'Linux'))
elif name == 'gh':
    if sys.argv[1:] == ['auth', 'token']: print('offline-fixture-token')
elif name == 'launchctl' and 'print' in sys.argv:
    value = os.environ.get('FAKE_JOB', 'waiting')
    if value == 'stopped': sys.exit(113)
    print('state = ' + value)
elif name == 'systemctl' and 'is-active' in sys.argv:
    service = any(a.endswith('.service') for a in sys.argv)
    active = os.environ.get('FAKE_JOB', 'waiting') == 'running' if service else os.environ.get('FAKE_JOB', 'waiting') != 'stopped'
    print('active' if active else 'inactive'); sys.exit(0 if active else 3)
'''.replace('PYTHON', sys.executable)
        for name in ('claude', 'codex', 'pi', 'agent', 'gh', 'systemctl', 'loginctl', 'launchctl', 'uname'):
            p = self.bin / name
            p.write_text(fake)
            p.chmod(0o755)
        self.env = dict(os.environ, REPO=str(self.repo), PATH=str(self.bin) + ':' + str(Path.home() / '.local/bin') + ':' + os.environ['PATH'], SUPERAGENT_CLI_PATH=str(self.bin),
                        XDG_CONFIG_HOME=str(self.root / 'config'), SUPERAGENT_LAUNCHD_DIR=str(self.root / 'LaunchAgents'),
                        FAKE_CALLS=str(self.calls), SUPER_MODEL_SUPERVISOR='inherit', SUPER_HARNESS='claude',
                        SUPER_GOAL_ROOT='vault', SUPER_NOTIFY_CMD='true', SUPER_AUTO_DISARM_ON_DONE='false',
                        LOG_FILE=str(self.root / 'tick.log'), GH_CONFIG_DIR=str(self.root / 'gh'), FAKE_JOB='waiting')
        for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'CURSOR_API_KEY', 'SUPERAGENT_SUPERVISOR', 'LOOP_FILE'):
            self.env.pop(key, None)
        self.outer = self.project / 'loop-status/outer.md'
        self.goal = self.repo / 'vault/goals/goal'
        self.plan = self.goal / 'master-plans/PLAN.md'
        self.plan.parent.mkdir(parents=True)
        self.plan.write_text('# Plan\n')
        self.running_inner = self.goal / 'loop-status/inner.md'
        self.running_inner.parent.mkdir()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, text=True, capture_output=True).stdout.strip()

    def valid_project(self):
        header = '**Date:** 2026-09-09 · **Status:** READY\n'
        (self.project / 'prd.md').write_text('# PRD\n' + header + '''\n## Objective
Demo.
## Success criteria
| Id | Criterion | Verified by (check ids) |
|---|---|---|
| SC1 | Works | C1 |
## Constraints and non-goals
None.
## Locked decisions
None.
## Iteration ledger
| Round | Meta-plan | Goal folder | Inner loop | Eval report | Verdict |
|---|---|---|---|---|---|
''')
        (self.project / 'knowledge-base.md').write_text('# Knowledge\n' + header + '\n| Id | Kind | Locator | Read for |\n|---|---|---|---|\n| K1 | `repo-file` | `README.md` | Fixture |\n')
        (self.project / 'evaluation.md').write_text('# Evaluation\n' + header + '''\n## Environment
- setup: `true`
- cwd: `.`
## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `true` | `.` | `exit 0` | 5 |
## Judged objectives
| Id | Objective | Criteria | Evidence to inspect |
|---|---|---|---|
None — command-only.
''')

    def invoke(self, script, *args, **env):
        return subprocess.run(['/bin/bash', str(SCRIPTS / script), *map(str, args)], env=dict(self.env, **env), cwd=self.repo, text=True, capture_output=True)

    def launch(self, **env):
        return self.invoke('launch.sh', self.project, '--supervisor', 'supercode', '--slug', 'outer', **env)

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def logs(self):
        return [json.loads(x) for x in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def model_invocations(self):
        return [x for x in self.logs() if x['name'] in ('claude', 'codex', 'pi', 'agent')]

    def write_outer(self, status='BUILDING', inner=None):
        self.outer.parent.mkdir(exist_ok=True)
        document = {k: '' for k in state.REQUIRED_FIELDS}
        document.update(supervisor='supercode', project=str(self.project.relative_to(self.repo)), status=status,
                        driver='external', iteration=0, session_skill_count=0, round=1, agreement_revision='a'*64,
                        inner_loop=str((inner or self.running_inner).relative_to(self.repo)), inner_slug='inner',
                        operation={k: '' for k in state.OPERATION_FIELDS})
        self.outer.write_bytes(state._serialize_state(document) + b'\n## Pending decision\n\n## Decisions\n\n## Iteration log\n')
        self.register('outer', self.outer, 'supercode')
        self.running_inner.write_text('---\nmaster_plan: ' + str(self.plan.relative_to(self.repo)) + '\nstatus: RUNNING\ndriver: external\n---\n')
        self.register('inner', self.running_inner, 'superagent')
        return document

    def register(self, slug, path, supervisor, repo=None):
        conf = Path(self.env['XDG_CONFIG_HOME']) / 'superagent'
        conf.mkdir(parents=True, exist_ok=True)
        (conf / (slug + '.env')).write_text(f'REPO={repo or self.repo}\nLOOP_FILE={path}\nSUPERAGENT_SLUG={slug}\nSUPERAGENT_SUPERVISOR={supervisor}\n')

    def invoke_tick(self, **env):
        return self.invoke('superagent-tick.sh', LOOP_FILE=str(self.outer), SUPERAGENT_SUPERVISOR='supercode', SUPERAGENT_SLUG='outer', **env)

    def outer_status(self):
        return state.read_state(self.outer)['status']

    def verified_build(self, inner_status='RUNNING'):
        import _coding_loop_evidence as evidence
        d = self.write_outer()
        remote = self.root / 'origin.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True)
        self.git('remote', 'add', 'origin', str(remote))
        self.git('add', '.')
        self.git('commit', '-qm', 'approved inputs')
        self.git('push', '-qu', 'origin', 'main')
        source = self.git('rev-parse', 'HEAD')
        d['agreement_revision'] = state.acceptance_context(self.repo, self.repo / 'vault', self.project)['agreement_revision']
        meta = self.project / 'meta-plans/frozen-r1.md'
        meta.parent.mkdir()
        meta_locator = str(meta.relative_to(self.repo))
        goal_locator = str(self.goal.relative_to(self.repo))
        op = dict(id='4'*32, phase='META-PLANNING', round=1, agreement_revision=d['agreement_revision'],
                  code_commit='', meta_plan=meta_locator, goal_folder=goal_locator, report='', source_vault_commit=source)
        identity = f"**Operation:** {op['id']} · **Round:** 1 · **Agreement revision:** {op['agreement_revision']} · **Source vault commit:** {source}"
        meta.write_text('# Meta\n**Status:** READY\n' + identity + '\n')
        self.plan.write_text('# Plan\n**Status:** READY\n' + identity + f'\n**Related:** [[{meta_locator[:-3]}]]\n')
        (self.goal / 'goal-directives.md').write_text('# Directives\n' + identity + f'\n**Source:** [[{meta_locator[:-3]}]]\n**Confirmation:** user-confirmed on 2026-09-09\n')
        for name in ('plans', 'findings', 'reports', 'handoff', 'todo'):
            (self.goal / name).mkdir()
            (self.goal / name / '.gitkeep').touch()
        with (self.project / 'prd.md').open('a') as out:
            out.write(f'| 1 | [[{meta_locator[:-3]}]] | [[{goal_locator}]] | - | - | - |\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'integrated meta scaffold and ledger')
        self.git('push', '-q')
        receipt = evidence.reconcile_operation(self.repo, self.repo / 'vault', op)
        self.assertTrue(receipt.get('worker_complete'), receipt)
        d.update(operation=op, meta_plan=meta_locator)
        self.outer.write_bytes(state._serialize_state(d) + b'\n## Pending decision\n\n## Decisions\n')
        self.running_inner.write_text(self.running_inner.read_text().replace('status: RUNNING', 'status: ' + inner_status))
        return d

    def helper(self, command, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / '_coding_loop_state.py'), command, *map(str, args)],
                              env=self.env, cwd=self.repo, text=True, capture_output=True)

    def full_loop_fixture(self, harness='codex'):
        """Real tick, copied package and native subprocesses; no model/scheduler."""
        package_source = SCRIPTS.parent / harness
        if harness == 'claude':
            package_source = SCRIPTS.parent
        elif harness == 'codex':
            package_source /= 'plugins/superagent'
        package = self.root / 'copied-package'
        for folder in ('scripts', 'skills', 'templates'):
            shutil.copytree(package_source / folder, package / folder)
        self.events = self.root / 'events.jsonl'
        self.env.update(FAKE_PACKAGE=str(package), FAKE_EVENTS=str(self.events),
                        FAKE_SCHEDULER_SCRIPTS=str(SCRIPTS), SUPER_HARNESS=harness,
                        SUPER_CODE_MAX_ITERATIONS='2', SUPER_AUTO_DISARM_ON_DONE='true')
        for cli in ('claude', 'codex', 'pi', 'agent'):
            target = self.bin / cli
            target.write_text('#!' + sys.executable + '\n' + (SCRIPTS / 'coding-loop-fake-worker.py').read_text())
            target.chmod(0o755)
        (self.repo / 'behavior.txt').write_text('broken\n')
        evaluation = self.project / 'evaluation.md'
        evaluation.write_text(evaluation.read_text().replace('| C1 | `true`', '| C1 | `test "$(cat behavior.txt)" = repaired`'))
        self.git('add', '.'); self.git('commit', '-qm', 'approved failing baseline')
        remote = self.root / 'origin.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True)
        self.git('remote', 'add', 'origin', str(remote)); self.git('push', '-qu', 'origin', 'main')
        self.assert_ok(self.launch())
        self.outer = next((self.project / 'loop-status').glob('*.md'))
        return state.acceptance_context(self.repo, self.repo / 'vault', self.project)['agreement_revision']

    def full_events(self, kind):
        return [e for e in map(json.loads, self.events.read_text().splitlines()) if e['kind'] == kind] if self.events.exists() else []

    def full_tick(self, action='reconcile', phase='', fault='', expected=None):
        result = self.invoke_tick(FAKE_ACTION=action, FAKE_PHASE=phase, FAKE_FAULT=fault)
        if fault:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            if result.returncode:
                self.fail(result.stdout + result.stderr + Path(self.env['LOG_FILE']).read_text()[-9000:])
        if expected:
            self.assertEqual(self.outer_status(), expected, self.outer.read_text() + result.stdout + result.stderr)
        return result

    def complete_fake_inner(self, repair=False):
        # The implementation transport is intentionally fake: this is NOT live
        # acceptance. It supplies an integrated change, then the exact child DONE.
        if repair:
            self.assertEqual(state.read_state(self.outer)['round'], 2)
            (self.repo / 'behavior.txt').write_text('repaired\n')
            self.git('add', 'behavior.txt'); self.git('commit', '-qm', 'fake inner implements approved repair'); self.git('push', '-q')
        child = self.repo / state.read_state(self.outer)['inner_loop']
        original = child.read_text()
        import re
        child.write_text(re.sub(r'(?m)^status:.*$', 'status: DONE', original))
        calls = len(self.full_events('invocation'))
        self.full_tick(expected='WAITING FOR EVAL')
        self.assertEqual(len(self.full_events('invocation')), calls, 'BUILDING must stay shell-only')

    def save_full_evidence(self, label):
        target = os.environ.get('CODING_LOOP_TEST_EVIDENCE_DIR')
        if not target:
            return
        folder = Path(target) / label
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.events, folder / 'events.jsonl')
        shutil.copyfile(self.outer, folder / 'outer.md')
        shutil.copyfile(Path(self.env['LOG_FILE']), folder / 'tick.log')
        (folder / 'commits.txt').write_text(self.git('log', '--all', '--format=%H %s') + '\n')
        for source, name in ((self.project, 'project'), (self.repo / 'vault/goals', 'goals'),
                             (Path(self.env['XDG_CONFIG_HOME']) / 'superagent', 'registrations')):
            shutil.copytree(source, folder / name, dirs_exist_ok=True)

    def assert_round_artifacts(self, rounds=2):
        import re
        self.assertEqual(len(list((self.project / 'meta-plans').glob('*.md'))), rounds)
        self.assertEqual(len(list((self.repo / 'vault/goals').glob('frozen-r*'))), rounds)
        self.assertEqual(len(list((self.project / 'eval-reports').glob('*.md'))), rounds)
        self.assertEqual(len(list((self.project / 'diagnoses').glob('*.md'))), 1)
        rows = re.findall(r'(?m)^\| ([0-9]+) \|.*$', (self.project / 'prd.md').read_text())
        self.assertEqual(rows, [str(n) for n in range(1, rounds + 1)])
        registrations = list((Path(self.env['XDG_CONFIG_HOME']) / 'superagent').glob('project-r*.env'))
        self.assertEqual(len(registrations), rounds)
        self.assertEqual([e['slug'] for e in self.full_events('registration')], ['project-r' + str(n) for n in range(1, rounds + 1)])
        workers = self.full_events('worker')
        ids = {e['operation']['id'] for e in workers}
        self.assertEqual(len(ids), 5)
        for entry in self.full_events('worker-receipt'):
            self.assertTrue(entry['receipt']['worker_complete'])
            self.assertEqual(entry['receipt']['outcome'], 'INTEGRATED')

    def test_real_ticks_copied_native_packages_fail_diagnose_repair_pass_replay(self):
        for harness in ('claude', 'codex', 'pi', 'cursor'):
            with self.subTest(harness=harness):
                if harness != 'claude':
                    self.temp.cleanup(); self.setUp()
                fingerprint = self.full_loop_fixture(harness)
                self.full_tick('phase', 'META-PLANNING', expected='WAITING FOR BUILD')
                self.full_tick('launch', expected='BUILDING')
                count = len(self.full_events('invocation'))
                self.full_tick(expected='BUILDING')
                self.assertEqual(len(self.full_events('invocation')), count)
                self.complete_fake_inner()
                self.full_tick('phase', 'EVALUATING', expected='WAITING FOR DIAGNOSIS')
                self.full_tick('phase', 'DIAGNOSING', expected='WAITING FOR META-PLAN')
                self.full_tick('phase', 'META-PLANNING', expected='WAITING FOR BUILD')
                self.full_tick('launch', expected='BUILDING')
                self.complete_fake_inner(repair=True)
                self.full_tick('phase', 'EVALUATING', expected='DONE')
                self.assertEqual(state.read_state(self.outer)['round'], 2)
                self.assertEqual(state.read_state(self.outer)['agreement_revision'], fingerprint)
                self.assertEqual([e['verdict'] for e in self.full_events('evaluation')], ['FAIL', 'PASS'])
                self.assertEqual([e['entry'] for e in self.full_events('meta-entry')], ['FIRST_ROUND', 'AUTONOMOUS_REPAIR'])
                workers = self.full_events('worker')
                self.assertEqual(len(workers), 5)
                self.assertEqual(len(self.full_events('invocation')), 12)  # 7 supervisor + 5 worker processes
                supervisors = [e for e in self.full_events('invocation') if e['role'] == 'supervisor']
                self.assertTrue(all('/skills/supercode/SKILL.md' in str(e) for e in supervisors))
                if harness == 'codex': self.assertIn('--dangerously-bypass-approvals-and-sandbox', supervisors[0]['argv'])
                if harness == 'cursor':
                    for flag in ('--trust', '--force', '--plugin-dir'): self.assertIn(flag, supervisors[0]['argv'])
                if harness == 'pi':
                    for flag in ('--approve', '--skill', '--thinking'): self.assertIn(flag, supervisors[0]['argv'])
                    self.assertNotIn('--tools', supervisors[0]['argv'])
                self.assert_round_artifacts()
                before = self.outer.read_bytes()
                events = {kind: self.full_events(kind) for kind in ('worker', 'commit', 'registration')}
                for _ in range(2): self.full_tick(expected='DONE')
                self.assertEqual(self.outer.read_bytes(), before)
                self.assertEqual({kind: self.full_events(kind) for kind in events}, events)
                self.assertEqual(len(self.full_events('invocation')), 14)  # two manually forced terminal reconciliation ticks
                disarms = [e for e in self.logs() if e['name'] == 'systemctl' and 'disable' in e['argv']]
                self.assertTrue(disarms)
                self.assertTrue(all('superagent-tick@outer.timer' in e['argv'] for e in disarms))
                self.assert_round_artifacts()
                self.save_full_evidence('full-' + harness)

    def test_real_tick_fault_boundaries_keep_exact_operations_and_registration(self):
        fingerprint = self.full_loop_fixture()

        def interrupted_phase(phase, expected, partial=False):
            before = len(self.full_events('worker'))
            self.full_tick('phase', phase, fault='before-worker')
            op = state.read_state(self.outer)['operation']
            self.assertEqual(len(self.full_events('worker')), before)
            self.assertNotEqual(self.outer_status(), 'DONE')
            self.full_tick(expected=state.RECOVER_READY[phase])
            self.assertEqual(state.read_state(self.outer)['operation'], op)
            self.full_tick('phase', phase, fault='before-commit')
            self.full_tick(expected=state.RECOVER_READY[phase])
            self.assertEqual(self.full_events('reconcile')[-1]['receipt']['outcome'], 'ABSENT')
            self.assertEqual(state.read_state(self.outer)['operation'], op)
            if partial:
                self.full_tick('phase', phase, fault='partial-meta')
                self.full_tick(expected=state.RECOVER_READY[phase])
                receipt = self.full_events('reconcile')[-1]['receipt']
                self.assertEqual(receipt['outcome'], 'INTEGRATED')
                self.assertFalse(receipt['worker_complete'])
                self.assertEqual(len(list((self.repo / 'vault/goals').glob('frozen-r*'))), 1)
                self.assertEqual(state.read_state(self.outer)['operation'], op)
            self.full_tick('phase', phase, fault='after-commit')
            workers = len(self.full_events('worker'))
            self.full_tick(expected=expected)
            self.assertEqual(len(self.full_events('worker')), workers, 'integrated output must reconcile without worker redispatch')
            self.assertTrue(self.full_events('reconcile')[-1]['receipt']['worker_complete'])
            attempts = [e['operation'] for e in self.full_events('worker') if e['operation']['id'] == op['id']]
            self.assertTrue(all(attempt == op for attempt in attempts))
            self.assertEqual(len(attempts), 3 if partial else 2)
            self.assertEqual(state.read_state(self.outer)['agreement_revision'], fingerprint)

        interrupted_phase('META-PLANNING', 'WAITING FOR BUILD', partial=True)
        self.full_tick('launch', fault='before-registration', expected='WAITING FOR BUILD')
        inner = {key: state.read_state(self.outer)[key] for key in ('inner_loop', 'inner_slug')}
        self.assertEqual(self.full_events('registration'), [])
        self.full_tick('launch', fault='after-registration', expected='WAITING FOR BUILD')
        self.assertEqual(len(self.full_events('registration')), 1)
        registration = Path(self.env['XDG_CONFIG_HOME']) / 'superagent' / (inner['inner_slug'] + '.env')
        registered_bytes = registration.read_bytes()
        scheduler_mutations = [e for e in self.logs() if e['name'] == 'systemctl' and 'enable' in e['argv']]
        self.full_tick('launch', expected='BUILDING')
        self.assertEqual(registration.read_bytes(), registered_bytes)
        self.assertEqual({key: state.read_state(self.outer)[key] for key in inner}, inner)
        self.assertEqual([e for e in self.logs() if e['name'] == 'systemctl' and 'enable' in e['argv']], scheduler_mutations)
        self.complete_fake_inner()
        interrupted_phase('EVALUATING', 'WAITING FOR DIAGNOSIS')
        interrupted_phase('DIAGNOSING', 'WAITING FOR META-PLAN')
        self.full_tick('phase', 'META-PLANNING', expected='WAITING FOR BUILD')
        self.full_tick('launch', expected='BUILDING'); self.complete_fake_inner(repair=True)
        self.full_tick('phase', 'EVALUATING', expected='DONE')
        self.assert_round_artifacts()
        self.assertEqual(len(self.full_events('worker')), 9)
        self.assertEqual(len(self.full_events('commit')), 6)  # partial META plus 5 complete phases
        self.assertEqual(len(self.full_events('fault')), 12)
        calls = len(self.full_events('invocation'))
        self.full_tick(expected='DONE'); self.full_tick(expected='DONE')
        self.assertEqual(len(self.full_events('invocation')), calls + 2)
        self.assertEqual(len(self.full_events('worker')), 9)
        self.assert_round_artifacts()
        self.save_full_evidence('fault-boundaries')

    def test_shell_gate_reloads_inner_and_preserves_new_input_after_lock(self):
        self.verified_build('DONE')
        # Real Bash gate sees DONE before acquire; the instrumented Python CLI
        # publishes an inner input and body answer immediately after acquisition.
        python = self.bin / 'python3'
        python.write_text('#!' + sys.executable + '\n' +
            'import os, pathlib, subprocess, sys\n' +
            'r=subprocess.run([' + repr(sys.executable) + ', *sys.argv[1:]])\n' +
            "if r.returncode == 0 and 'acquire-lock' in sys.argv:\n" +
            " p=pathlib.Path(os.environ['INNER']); p.write_text(p.read_text().replace('status: DONE', 'status: WAITING FOR INPUT') + '\\n## Pending decision\\nanswer: preserve-inner-answer\\n')\n" +
            'sys.exit(r.returncode)\n')
        python.chmod(0o755)
        self.assert_ok(self.invoke_tick(INNER=str(self.running_inner)))
        self.assertEqual(self.outer_status(), 'BUILDING')
        self.assertIn('answer: preserve-inner-answer', self.running_inner.read_text())
        self.assertEqual(self.model_invocations(), [])

    def test_generated_meta_worker_consumes_author_adoption_after_pass(self):
        self.full_loop_fixture('codex')
        # A valid command-only PASS baseline; author subsequently edits scope.
        (self.repo / 'behavior.txt').write_text('repaired\n')
        self.git('add', '.'); self.git('commit', '-qm', 'passing baseline'); self.git('push', '-q')
        self.full_tick('phase', 'META-PLANNING', expected='WAITING FOR BUILD')
        self.full_tick('launch', expected='BUILDING'); self.complete_fake_inner()
        self.full_tick('phase', 'EVALUATING', expected='DONE')
        prd = self.project / 'prd.md'; prd.write_text(prd.read_text().replace('Demo.', 'Author-approved changed scope.'))
        self.git('add', '.'); self.git('commit', '-qm', 'author agreement edit'); self.git('push', '-q')
        self.assert_ok(self.launch())
        self.assertEqual(self.outer_status(), 'WAITING FOR INPUT')
        before = len(self.full_events('worker'))
        self.assert_ok(self.invoke('answer.sh', '--no-kick', 'outer', 'retry'))
        self.full_tick(expected='WAITING FOR INPUT')
        self.assertIn('answer: retry', self.outer.read_text())
        self.assertEqual(len(self.full_events('worker')), before)
        answer = 'adopt-agreement ' + state.read_state(self.outer)['proposed_agreement_revision']
        self.assert_ok(self.invoke('answer.sh', '--replace', '--no-kick', 'outer', answer))
        self.full_tick(expected='WAITING FOR META-PLAN')
        self.full_tick('phase', 'META-PLANNING', expected='WAITING FOR BUILD')
        entry = self.full_events('meta-entry')[-1]
        self.assertEqual(entry['entry'], 'AUTHOR_APPROVED'); self.assertEqual(entry['answer'], answer)
        self.assertEqual(entry['operation_id'], state.read_state(self.outer)['operation']['id'])
        self.assertEqual(entry['round'], 2)
        self.assertNotEqual(entry['agreement_revision'], self.full_events('meta-entry')[0]['agreement_revision'])
        count = len(self.full_events('worker')); self.full_tick(expected='WAITING FOR BUILD')
        self.assertEqual(len(self.full_events('worker')), count)
        self.assertEqual(len(list((self.repo / 'vault/goals').glob('frozen-r*'))), 2)
        self.save_full_evidence('author-adoption')

    def test_outer_monitor_and_independent_stop_targets(self):
        self.write_outer()
        for adapter in ('Linux', 'Darwin'):
            with self.subTest(adapter=adapter):
                result = self.invoke('status.sh', '--json', 'outer', FAKE_OS=adapter)
                self.assert_ok(result)
                item = json.loads(result.stdout)[0]
                for field in ('supervisor', 'project', 'round', 'inner_slug', 'inner_status', 'last_verdict', 'pending_owner', 'iteration', 'timer_active'):
                    self.assertIn(field, item)
                self.assertEqual(item['supervisor'], 'supercode')
                self.assertEqual(item['inner_status'], 'RUNNING')
                before = self.running_inner.read_bytes()
                self.calls.unlink(missing_ok=True)
                result = self.invoke('stop.sh', self.project, FAKE_OS=adapter)
                self.assert_ok(result)
                self.assertIn('--slug inner', result.stdout)
                self.assertEqual(before, self.running_inner.read_bytes())
                self.assertFalse(any('inner' in str(c['argv']) for c in self.logs() if c['name'] in ('systemctl', 'launchctl')))
                self.calls.unlink(missing_ok=True)
                self.assert_ok(self.invoke('stop.sh', '--slug', 'inner', '--hard', FAKE_OS=adapter))
                self.assertFalse(any('outer' in str(c['argv']) for c in self.logs()))

    def test_lifecycle_identity_mismatch_refuses_before_scheduler(self):
        self.write_outer()
        for script, args in (('stop.sh', (self.project, '--slug', 'inner')),
                             ('force-stop.sh', (self.project, '--slug', 'inner', '--apply'))):
            result = self.invoke(script, *args)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.logs(), [])
        self.register('outer', self.outer, 'superagent')
        before = self.outer.read_bytes()
        for script, args in (('stop.sh', ('--slug', 'outer')),
                             ('force-stop.sh', ('--slug', 'outer', '--apply')),
                             ('answer.sh', ('--no-kick', 'outer', 'retry'))):
            self.assertNotEqual(self.invoke(script, *args).returncode, 0)
        self.assertEqual(self.outer.read_bytes(), before)
        self.assertEqual(self.logs(), [])

    def test_project_answer_uses_guard_and_preserves_replace(self):
        d = self.write_outer()
        d.update(status='WAITING FOR INPUT', prior_status='BUILDING')
        self.outer.write_bytes(state._serialize_state(d) + b'\n## Pending decision\nreason: stopped\nanswer:\n')
        lock = self.outer.parent / ('.' + self.outer.name + '.lockd')
        lock.mkdir(); (lock / 'owner').write_text('999999999')
        self.assert_ok(self.invoke('answer.sh', '--no-kick', 'outer', 'retry'))
        guard = Path(str(lock) + '.reclaim')
        self.assertTrue(guard.exists())
        inode = guard.stat().st_ino
        self.assert_ok(self.invoke('answer.sh', '--no-kick', 'outer', 'wrong'))
        self.assertIn('answer: retry', self.outer.read_text())
        self.assert_ok(self.invoke('answer.sh', '--replace', '--no-kick', 'outer', 'replacement'))
        self.assertIn('answer: replacement', self.outer.read_text())
        self.assertEqual(inode, guard.stat().st_ino)
        lock.mkdir(); (lock / 'owner').write_text(str(os.getpid()))
        self.assertEqual(self.invoke('answer.sh', '--replace', '--no-kick', 'outer', 'blocked').returncode, 4)
        self.assertNotIn('answer: blocked', self.outer.read_text())

    def test_outer_force_recovery_preserves_phase_and_live_peer_guard(self):
        d = self.verified_build()
        lock = self.outer.parent / ('.' + self.outer.name + '.lockd')
        for phase, ready in state.RECOVER_READY.items():
            d['status'] = phase; d['operation']['phase'] = phase
            d['operation']['code_commit'] = '' if phase == 'META-PLANNING' else self.git('rev-parse', 'HEAD')
            d['operation']['report'] = '' if phase == 'META-PLANNING' else str(self.project / 'eval-reports/missing.md')
            self.outer.write_bytes(state._serialize_state(d))
            lock.mkdir(); (lock / 'owner').write_text('999999999')
            before = self.outer.read_bytes()
            result = self.invoke('force-stop.sh', '--slug', 'outer', '--apply')
            self.assert_ok(result)
            self.assertIn(ready, result.stdout)
            self.assertEqual(before, self.outer.read_bytes())
            self.assertTrue(Path(str(lock) + '.reclaim').exists())
            self.assertFalse(lock.exists())
        lock.mkdir(); (lock / 'owner').write_text(str(os.getpid()))
        self.assertNotEqual(self.invoke('force-stop.sh', '--slug', 'outer', '--apply', '--no-kick').returncode, 0)
        self.assertEqual((lock / 'owner').read_text(), str(os.getpid()))

    def test_context_discovers_transitive_binding_and_refuses_missing(self):
        self.verified_build()
        (self.repo / 'README.md').write_text('Binding: [requirements](requirements.md)\n')
        (self.repo / 'requirements.md').write_text('Required assertion.\n')
        self.git('add', 'README.md', 'requirements.md'); self.git('commit', '-qm', 'binding'); self.git('push', '-q')
        args = ('--repo', self.repo, '--vault', self.repo / 'vault', '--project', self.project)
        result = self.helper('context', *args)
        self.assert_ok(result)
        packet = json.loads(result.stdout)
        self.assertEqual({m['locator'] for m in packet['manifest']}, {'README.md', 'requirements.md'})
        old = packet['agreement_revision']
        with (self.project / 'prd.md').open('a') as out: out.write('\n')
        self.assertEqual(json.loads(self.helper('context', *args).stdout)['agreement_revision'], old)
        (self.repo / 'requirements.md').unlink()
        self.assertNotEqual(self.helper('context', *args).returncode, 0)

    def evaluation_fixture(self, verdict='PASS', missing_j=False, wrong_sha=False):
        d = self.verified_build()
        if missing_j:
            p = self.project / 'evaluation.md'
            p.write_text(p.read_text().replace('None — command-only.', '| J1 | Required assertion | inspect | README.md |'))
            self.git('add', str(p.relative_to(self.repo))); self.git('commit', '-qm', 'judged agreement'); self.git('push', '-q')
        context = json.loads(self.helper('context', '--repo', self.repo, '--vault', self.repo / 'vault', '--project', self.project).stdout)
        sha = self.git('rev-parse', 'HEAD')
        report = self.project / 'eval-reports/frozen-r1.md'; report.parent.mkdir()
        op = dict(d['operation'], id='5'*32, phase='EVALUATING', agreement_revision=context['agreement_revision'],
                  code_commit=sha, source_vault_commit=sha, report=str(report.relative_to(self.repo)))
        report.write_text(f"""# Eval
**Date:** 2026-09-09 · **Status:** FINAL · **Round:** 1
**Operation:** {op['id']} · **Agreement revision:** {op['agreement_revision']} · **Source vault commit:** {sha}
## Environment
- commit: `{'0'*40 if wrong_sha else sha}` · worktree: `/tmp/work` · setup: `true` → ok
## Command checks
| Id | Result | Exit | Seconds | Evidence |
|---|---|---|---|---|
| C1 | {verdict} | 0 | 0 | README.md:1 |
## Judged objectives
none
## Verdict
**{verdict}** — observed result
**Inner loop:** none found
**Warnings:** none
""")
        prd = self.project / 'prd.md'
        prd.write_text(prd.read_text().replace('| - | - | - |', '| - | [[' + op['report'][:-3] + ']] | ' + verdict + ' |'))
        self.git('add', '.'); self.git('commit', '-qm', 'integrated evaluation'); self.git('push', '-q')
        d.update(status='EVALUATING', operation=op, agreement_revision=op['agreement_revision'])
        self.outer.write_bytes(state._serialize_state(d) + b'\n## Pending decision\nanswer:\n')
        return d

    def phase(self, maximum=1, consume=False):
        lock = self.outer.parent / ('.' + self.outer.name + '.lockd')
        self.assert_ok(self.helper('acquire-lock', lock, '--owner', os.getpid()))
        try:
            result = self.helper('reconcile-phase', self.outer, '--repo', self.repo, '--vault', self.repo / 'vault',
                                 '--max-rounds', maximum, '--write', '--owner', os.getpid(), *(['--consume-answer'] if consume else []))
            self.assert_ok(result)
            return json.loads(result.stdout)
        finally:
            shutil.rmtree(lock)

    def test_final_allowed_round_pass_and_negative_acceptance(self):
        self.evaluation_fixture()
        result = self.phase()
        self.assertEqual(result['state']['status'], 'DONE', result)
        self.assertEqual(result['state']['round'], 1)
        self.assertEqual(len(list((self.project / 'eval-reports').glob('*.md'))), 1)

    def test_missing_j_and_wrong_revision_never_done(self):
        # Separate fixtures preserve actual Git authority without test-side verdict injection.
        self.evaluation_fixture(missing_j=True)
        self.assertEqual(self.phase()['state']['status'], 'WAITING FOR INPUT')

    def test_wrong_evaluation_revision_never_done(self):
        self.evaluation_fixture(wrong_sha=True)
        self.assertEqual(self.phase()['state']['status'], 'WAITING FOR INPUT')

    def test_actual_adoption_answer_starts_new_round_without_old_pass(self):
        self.evaluation_fixture()
        self.phase()
        prd = self.project / 'prd.md'
        prd.write_text(prd.read_text().replace('Demo.', 'Changed approved scope.'))
        self.git('add', str(prd.relative_to(self.repo))); self.git('commit', '-qm', 'author changed scope'); self.git('push', '-q')
        self.assert_ok(self.launch())
        result = self.phase(2)
        self.assertEqual(result['state']['status'], 'WAITING FOR INPUT')
        # Explicit relaunch must expose adoption even after a previously terminal PASS.
        self.assert_ok(self.launch())
        self.assertEqual(self.outer_status(), 'WAITING FOR INPUT')
        old = result['state']['agreement_revision']
        new = result['state']['proposed_agreement_revision']
        self.assertNotEqual(old, new)
        self.assert_ok(self.invoke('answer.sh', '--no-kick', 'outer', 'retry'))
        self.assertEqual(self.phase(2, True)['state']['agreement_revision'], old)
        self.assert_ok(self.launch())
        self.assertIn('\nanswer: retry', self.outer.read_text())
        self.assert_ok(self.invoke('answer.sh', '--replace', '--no-kick', 'outer', 'adopt-agreement ' + new))
        result = self.phase(2, True)
        self.assertEqual(result['state']['status'], 'WAITING FOR META-PLAN', result)
        self.assertEqual(result['state']['round'], 2)
        self.assertEqual(result['state']['agreement_revision'], new)
        self.assertEqual(result['state']['operation']['phase'], '')
        self.assertNotIn('\nanswer: adopt-agreement', self.outer.read_text())

    def test_reservation_refuses_round_max_plus_one_and_pending_context(self):
        d = self.evaluation_fixture()
        d.update(status='WAITING FOR META-PLAN', round=2, operation={k: '' for k in state.OPERATION_FIELDS})
        self.outer.write_bytes(state._serialize_state(d))
        opfile = self.root / 'op.json'
        opfile.write_text(json.dumps(dict(d['operation'], phase='META-PLANNING', round=2, agreement_revision=d['agreement_revision'],
                                         meta_plan=str(self.project / 'meta-plans/new-r2.md'), goal_folder=str(self.repo / 'vault/goals/next'),
                                         source_vault_commit=self.git('rev-parse', 'HEAD'))))
        before = self.outer.read_bytes()
        result = self.helper('reserve', self.outer, '--repo', self.repo, '--vault', self.repo / 'vault', '--operation', opfile, '--max-rounds', 1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('round limit', result.stderr)
        self.assertEqual(before, self.outer.read_bytes())

    def diagnosis_fixture(self):
        self.evaluation_fixture(verdict='FAIL')
        self.assertEqual(self.phase()['state']['status'], 'WAITING FOR DIAGNOSIS')
        d = state.read_state(self.outer)
        report = self.project / 'diagnoses/frozen-r1.md'; report.parent.mkdir()
        source = self.git('rev-parse', 'HEAD')
        op = dict(d['operation'], id='6'*32, phase='DIAGNOSING', report=str(report.relative_to(self.repo)), source_vault_commit=source)
        report.write_text(f"""# Diagnosis
**Date:** 2026-09-09 · **Status:** FINAL · **Round:** 1
**Operation:** `{op['id']}`
**Eval report:** `{d['last_eval']}`
**Evaluated commit:** `{d['evaluated_commit']}`
**Agreement revision:** `{d['agreement_revision']}`
**Source vault commit:** `{source}`
## Inputs and limitations
Approved agreement and selected failed report inspected.
## Problems
| Problem | C/J IDs | AC IDs | Evidence | Cause | Confidence | Classification |
|---|---|---|---|---|---|---|
| P1 | C1 | none | README.md:1 | Required behavior absent | high | implementation defect |
## Repair guidance
P1: implement the approved behavior.
## Disposition
**REPAIR**
""")
        self.git('add', '.'); self.git('commit', '-qm', 'integrated diagnosis'); self.git('push', '-q')
        d.update(status='DIAGNOSING', operation=op)
        self.outer.write_bytes(state._serialize_state(d) + b'\n## Pending decision\nanswer:\n')
        return report

    def test_diagnosed_limit_requires_actual_explicit_raised_limit_answer(self):
        self.diagnosis_fixture()
        result = self.phase(1)
        self.assertEqual(result['state']['status'], 'WAITING FOR INPUT', result)
        self.assertEqual(result['state']['pending_kind'], 'limit')
        self.assertEqual(self.phase(2)['state']['status'], 'WAITING FOR INPUT')
        self.assert_ok(self.invoke('answer.sh', '--no-kick', 'outer', 'raise-limit 3'))
        self.assertEqual(self.phase(2, True)['state']['round'], 1)
        self.assert_ok(self.invoke('answer.sh', '--replace', '--no-kick', 'outer', 'raise-limit 2'))
        result = self.phase(2, True)
        self.assertEqual(result['state']['round'], 2)
        self.assertEqual(result['state']['status'], 'WAITING FOR META-PLAN')
        self.assertEqual(len(list((self.project / 'diagnoses').glob('*.md'))), 1)
        self.assertEqual(len(list((self.project / 'meta-plans').glob('*.md'))), 1)
        self.assertEqual(len(self.model_invocations()), 0)

    def test_diagnosis_wrong_selected_report_never_repairs(self):
        report = self.diagnosis_fixture()
        report.write_text(report.read_text().replace('eval-reports/frozen-r1.md', 'eval-reports/another-r1.md'))
        self.git('add', '.'); self.git('commit', '-qm', 'wrong report identity'); self.git('push', '-q')
        result = self.phase(2)
        self.assertEqual(result['state']['status'], 'WAITING FOR INPUT')
        self.assertEqual(result['state']['round'], 1)

    def test_absent_transient_reconciles_to_own_ready_phase(self):
        self.evaluation_fixture()
        original = state.read_state(self.outer)
        for phase, ready in state.RECOVER_READY.items():
            d = dict(original, status=phase, operation=dict(original['operation'], phase=phase, id='7'*32))
            d['operation']['goal_folder'] = 'vault/goals/absent'
            d['operation']['meta_plan'] = str((self.project / 'meta-plans/absent-r1.md').relative_to(self.repo))
            if phase == 'META-PLANNING':
                d['operation'].update(code_commit='', report='')
            else:
                d['operation']['report'] = str((self.project / ('diagnoses' if phase == 'DIAGNOSING' else 'eval-reports') / 'absent-r1.md').relative_to(self.repo))
            self.outer.write_bytes(state._serialize_state(d))
            result = self.phase(1)
            self.assertEqual(result['receipt']['outcome'], 'ABSENT', result)
            self.assertEqual(result['state']['status'], ready, result)
            self.assertEqual(result['state']['operation']['id'], '7'*32)

    def test_legacy_answer_retains_python_free_path(self):
        self.write_outer()
        self.running_inner.write_text(self.running_inner.read_text().replace('status: RUNNING', 'status: WAITING FOR INPUT') + '\n## Pending decision\nanswer:\n')
        python = self.bin / 'python3'; python.write_text('#!/bin/sh\nexit 99\n'); python.chmod(0o755)
        self.assert_ok(self.invoke('answer.sh', '--no-kick', 'inner', 'retry'))
        self.assertIn('answer: retry', self.running_inner.read_text())
        self.assert_ok(self.invoke('stop.sh', '--slug', 'inner', '--dry-run'))
        self.assert_ok(self.invoke('force-stop.sh', '--slug', 'inner'))

    def test_new_reservation_reuses_identity_and_requires_resolved_context(self):
        d = self.evaluation_fixture()
        context = d['agreement_revision']
        d.update(status='WAITING FOR META-PLAN', agreement_revision='PENDING', operation={k: '' for k in state.OPERATION_FIELDS})
        self.outer.write_bytes(state._serialize_state(d))
        op = dict(d['operation'], phase='META-PLANNING', round=1, agreement_revision=context,
                  meta_plan=str((self.project / 'meta-plans/reserved-r1.md').relative_to(self.repo)), goal_folder='vault/goals/reserved',
                  source_vault_commit=self.git('rev-parse', 'HEAD'))
        opfile = self.root / 'reserve.json'; opfile.write_text(json.dumps(op))
        lock = self.outer.parent / ('.' + self.outer.name + '.lockd')
        self.assert_ok(self.helper('acquire-lock', lock, '--owner', os.getpid()))
        args = (self.outer, '--repo', self.repo, '--vault', self.repo / 'vault', '--operation', opfile, '--max-rounds', 1, '--owner', os.getpid())
        try:
            result = self.helper('reserve', *args)
            self.assert_ok(result)
            reserved = json.loads(result.stdout)
            self.assertEqual(reserved['status'], 'META-PLANNING')
            operation_id = reserved['operation']['id']
            self.assertRegex(operation_id, '^[a-f0-9]{32}$')
            # Simulate interrupted absent worker: same durable reservation is reused.
            result = self.helper('reserve', *args)
            self.assert_ok(result)
            self.assertEqual(json.loads(result.stdout)['operation']['id'], operation_id)
            op['goal_folder'] += '-other'; opfile.write_text(json.dumps(op))
            self.assertNotEqual(self.helper('reserve', *args).returncode, 0)
            (self.repo / 'README.md').unlink()
            self.assertNotEqual(self.helper('reserve', *args).returncode, 0)
            self.assertEqual(state.read_state(self.outer)['operation']['id'], operation_id)
        finally:
            shutil.rmtree(lock)

    def test_legacy_adoption_rejects_unintegrated_raw_locators(self):
        d = self.evaluation_fixture()
        fingerprint = d['agreement_revision']
        d.update(status='WAITING FOR INPUT', prior_status='WAITING FOR META-PLAN', agreement_revision='PENDING',
                 adoption_goal_folder='[[vault/goals/missing]]', adoption_verdict='PASS',
                 operation={k: '' for k in state.OPERATION_FIELDS})
        self.outer.write_bytes(state._serialize_state(d) + b'\n## Pending decision\nanswer:\n')
        self.assert_ok(self.invoke('answer.sh', '--no-kick', 'outer', 'adopt-agreement ' + fingerprint))
        result = self.phase(2, True)
        self.assertEqual(result['state']['status'], 'WAITING FOR INPUT')
        self.assertEqual(result['state']['round'], 1)
        self.assertEqual(result['state']['agreement_revision'], 'PENDING')

    def test_changed_agreement_blocks_launcher_and_building_advancement(self):
        d = self.verified_build('DONE')
        prd = self.project / 'prd.md'; prd.write_text(prd.read_text().replace('Demo.', 'Changed obligation.'))
        self.git('add', '.'); self.git('commit', '-qm', 'changed agreement'); self.git('push', '-q')
        before = self.outer.read_bytes()
        self.assert_ok(self.invoke_tick())
        self.assertEqual(self.outer_status(), 'WAITING FOR INPUT')
        d.update(status='META-PLANNING', inner_loop='', inner_slug='')
        self.outer.write_bytes(state._serialize_state(d))
        self.assert_ok(self.launch())
        self.assertEqual(self.outer_status(), 'WAITING FOR INPUT')

    def test_answer_refuses_concurrent_reclaimer_without_lock_directory(self):
        import fcntl
        d = self.write_outer(); d.update(status='WAITING FOR INPUT', prior_status='BUILDING')
        self.outer.write_bytes(state._serialize_state(d) + b'\n## Pending decision\nanswer:\n')
        lock = self.outer.parent / ('.' + self.outer.name + '.lockd')
        guard = Path(str(lock) + '.reclaim')
        before = self.outer.read_bytes()
        with guard.open('a+b') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            self.assertEqual(self.invoke('answer.sh', '--no-kick', 'outer', 'retry').returncode, 4)
            self.assertEqual(before, self.outer.read_bytes())
            self.assertFalse(lock.exists())
        self.assertTrue(guard.exists())

    def test_remote_capture_persists_and_missing_capture_fails_closed(self):
        import hashlib
        d = self.evaluation_fixture()
        kb = self.project / 'knowledge-base.md'
        kb.write_text(kb.read_text() + '\nBinding [policy](https://example.invalid/policy).\n')
        self.git('add', '.'); self.git('commit', '-qm', 'binding policy'); self.git('push', '-q')
        capture = self.root / 'policy.txt'; capture.write_text('Required behavior remains approved.\n')
        entry = dict(locator='https://example.invalid/policy', path=str(capture), source_revision='policy-v1', sha256=hashlib.sha256(capture.read_bytes()).hexdigest())
        captures = self.root / 'captures.json'; captures.write_text(json.dumps([entry]))
        context_args = ('--repo', self.repo, '--vault', self.repo / 'vault', '--project', self.project)
        self.assertNotEqual(self.helper('context', *context_args).returncode, 0)
        context = self.helper('context', *context_args, '--captures', captures); self.assert_ok(context)
        d.update(status='WAITING FOR META-PLAN', agreement_revision='PENDING', operation={k: '' for k in state.OPERATION_FIELDS})
        self.outer.write_bytes(state._serialize_state(d))
        lock = self.outer.parent / ('.' + self.outer.name + '.lockd')
        self.assert_ok(self.helper('acquire-lock', lock, '--owner', os.getpid()))
        try:
            result = self.helper('reconcile-phase', self.outer, '--repo', self.repo, '--vault', self.repo / 'vault', '--write', '--owner', os.getpid(), '--captures', captures)
            self.assert_ok(result)
            self.assertEqual(json.loads(result.stdout)['state']['status'], 'WAITING FOR META-PLAN')
        finally:
            shutil.rmtree(lock)
        self.assertEqual(json.loads(state.read_state(self.outer)['binding_captures_json']), [entry])
        self.assertEqual(self.phase()['state']['status'], 'WAITING FOR META-PLAN')
        capture.unlink()
        self.assertEqual(self.phase()['state']['status'], 'WAITING FOR INPUT')

    def test_monitor_reports_disarmed_unfinished_child_as_stopped(self):
        self.write_outer()
        result = self.invoke('status.sh', '--json', 'outer', FAKE_JOB='stopped')
        self.assert_ok(result)
        self.assertEqual(json.loads(result.stdout)[0]['inner_status'], 'STOPPED')

    def test_partial_meta_requires_worker_complete_before_build(self):
        d = self.verified_build()
        prd = self.project / 'prd.md'
        prd.write_text('\n'.join(line for line in prd.read_text().splitlines() if not line.startswith('| 1 |')) + '\n')
        self.git('add', '.'); self.git('commit', '-qm', 'partial meta missing ledger'); self.git('push', '-q')
        d.update(status='META-PLANNING')
        self.outer.write_bytes(state._serialize_state(d))
        result = self.phase()
        self.assertEqual(result['receipt']['outcome'], 'INTEGRATED', result)
        self.assertFalse(result['receipt']['worker_complete'])
        self.assertEqual(result['state']['status'], 'WAITING FOR META-PLAN')
        self.assertEqual(result['state']['operation']['id'], d['operation']['id'])
        self.assertEqual(len(list((self.repo / 'vault/goals').iterdir())), 1)

    def test_repair_below_limit_advances_one_round_and_reconciliation_is_idempotent(self):
        self.diagnosis_fixture()
        result = self.phase(2)
        self.assertEqual(result['state']['status'], 'WAITING FOR META-PLAN')
        self.assertEqual(result['state']['round'], 2)
        self.assertEqual(self.phase(2)['state']['round'], 2)
        self.assertEqual(len(list((self.project / 'diagnoses').glob('*.md'))), 1)

    def test_relative_binding_names_are_resolved_per_source_before_deduplication(self):
        self.verified_build()
        for folder in ('a', 'b'):
            base = self.repo / folder; base.mkdir()
            (base / 'spec.md').write_text('[required](requirements.md)\n')
            (base / 'requirements.md').write_text(folder + ' required assertion\n')
        (self.repo / 'requirements.md').write_text('Unrelated root target must not shadow source-relative links.\n')
        kb = self.project / 'knowledge-base.md'
        kb.write_text(kb.read_text() + '| K2 | `repo-file` | `a/spec.md` | binding |\n| K3 | `repo-file` | `b/spec.md` | binding |\n')
        self.git('add', '.'); self.git('commit', '-qm', 'two scoped binding names'); self.git('push', '-q')
        args = ('--repo', self.repo, '--vault', self.repo / 'vault', '--project', self.project)
        result = self.helper('context', *args); self.assert_ok(result)
        packet = json.loads(result.stdout)
        self.assertIn('a/requirements.md', {m['locator'] for m in packet['manifest']})
        self.assertIn('b/requirements.md', {m['locator'] for m in packet['manifest']})
        (self.repo / 'b/requirements.md').write_text('Changed b obligation.\n')
        self.git('add', '.'); self.git('commit', '-qm', 'changed only b'); self.git('push', '-q')
        changed = self.helper('context', *args); self.assert_ok(changed)
        self.assertNotEqual(packet['agreement_revision'], json.loads(changed.stdout)['agreement_revision'])
        (self.repo / 'b/requirements.md').unlink()
        self.assertNotEqual(self.helper('context', *args).returncode, 0)

    def test_all_knowledge_base_kinds_resolve_and_nonfile_captures_are_required(self):
        import hashlib
        self.verified_build()
        source = self.repo / 'src'; source.mkdir()
        (source / 'entry.py').write_text('def required_symbol(): pass\n')
        (source / 'one.md').write_text('First required clause.\n')
        (source / 'two.md').write_text('Second required clause.\n')
        kb = self.project / 'knowledge-base.md'
        header = kb.read_text().split('| K1 |')[0]
        rows = [('instructions', 'README.md'), ('repo-file', 'README.md'), ('sample-code', 'src/entry.py'),
                ('repo-glob', 'src/*.md'), ('entry-point', 'src/entry.py:required_symbol'), ('entry-point', 'README.md:fixture'),
                ('doc-url', 'https://example.invalid/doc'), ('context7', '/org/library')]
        kb.write_text(header + ''.join(f'| K{i} | `{kind}` | `{locator}` | approved source |\n' for i, (kind, locator) in enumerate(rows, 1)))
        self.git('add', '.'); self.git('commit', '-qm', 'all valid source kinds'); self.git('push', '-q')
        self.assert_ok(self.invoke('prd-lint.sh', self.project, PRD_LINT_REPO_ROOT=str(self.repo)))
        captures = []
        for i, (_, locator) in enumerate(rows[-2:]):
            path = self.root / f'capture-{i}.txt'; path.write_text('Approved library text.\n')
            captures.append(dict(locator=locator, path=str(path), source_revision='v1', sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        capture_file = self.root / 'kb-captures.json'; capture_file.write_text(json.dumps(captures))
        args = ('--repo', self.repo, '--vault', self.repo / 'vault', '--project', self.project, '--captures', capture_file)
        result = self.helper('context', *args); self.assert_ok(result)
        locators = {m['locator'] for m in json.loads(result.stdout)['manifest']}
        self.assertTrue({'src/one.md', 'src/two.md', 'src/entry.py', '/org/library', 'https://example.invalid/doc'} <= locators)
        for missing in captures:
            capture_file.write_text(json.dumps([entry for entry in captures if entry != missing]))
            rejected = self.helper('context', *args)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn(missing['locator'], rejected.stderr)

    def reserve_next_meta_for_worker(self):
        d = state.read_state(self.outer)
        op = {k: '' for k in state.OPERATION_FIELDS}
        op.update(phase='META-PLANNING', round=d['round'], agreement_revision=d['agreement_revision'],
                  meta_plan=str((self.project / f"meta-plans/approved-r{d['round']}.md").relative_to(self.repo)),
                  goal_folder=f"vault/goals/approved-r{d['round']}", source_vault_commit=self.git('rev-parse', 'HEAD'))
        opfile = self.root / 'worker-operation.json'; opfile.write_text(json.dumps(op))
        lock = self.outer.parent / ('.' + self.outer.name + '.lockd')
        self.assert_ok(self.helper('acquire-lock', lock, '--owner', os.getpid()))
        try:
            result = self.helper('reserve', self.outer, '--repo', self.repo, '--vault', self.repo / 'vault',
                                 '--operation', opfile, '--owner', os.getpid(), '--max-rounds', 3)
            self.assert_ok(result)
        finally:
            shutil.rmtree(lock)
        opfile.write_text(json.dumps(json.loads(result.stdout)['operation']))
        return opfile

    def worker_meta_entry(self, opfile):
        return self.helper('meta-entry', self.outer, '--repo', self.repo, '--vault', self.repo / 'vault',
                           '--operation', opfile, '--conf', Path(self.env['XDG_CONFIG_HOME']) / 'superagent')

    def test_author_adopted_round_is_consumable_by_meta_worker_after_pass(self):
        self.evaluation_fixture(); self.phase()
        prd = self.project / 'prd.md'; prd.write_text(prd.read_text().replace('Demo.', 'Author adopted different scope.'))
        self.git('add', '.'); self.git('commit', '-qm', 'new author scope'); self.git('push', '-q')
        parked = self.phase(3)['state']
        command = 'adopt-agreement ' + parked['proposed_agreement_revision']
        self.assert_ok(self.invoke('answer.sh', '--no-kick', 'outer', command))
        self.phase(3, True)
        opfile = self.reserve_next_meta_for_worker()
        result = self.worker_meta_entry(opfile); self.assert_ok(result)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['entry'], 'AUTHOR_APPROVED')
        self.assertEqual(receipt['answer'], command)
        self.assertEqual(receipt['round'], 2)
        self.assertEqual(receipt['operation_id'], state.read_state(self.outer)['operation']['id'])
        self.assertEqual(self.worker_meta_entry(opfile).stdout, result.stdout)
        # A worker prompt or stale packet cannot authorize another operation.
        op = json.loads(opfile.read_text()); op['id'] = 'a'*32; opfile.write_text(json.dumps(op))
        self.assertNotEqual(self.worker_meta_entry(opfile).returncode, 0)

    def test_explicit_author_replan_is_worker_consumable_but_not_automatic_repair(self):
        report = self.diagnosis_fixture()
        report.write_text(report.read_text().replace('implementation defect', 'PRD/evaluation defect').replace('**REPAIR**', '**AUTHOR INPUT**'))
        self.git('add', '.'); self.git('commit', '-qm', 'author diagnosis'); self.git('push', '-q')
        self.assertEqual(self.phase(3)['state']['pending_kind'], 'author')
        self.assert_ok(self.invoke('answer.sh', '--no-kick', 'outer', 'replan'))
        self.phase(3, True)
        opfile = self.reserve_next_meta_for_worker()
        result = self.worker_meta_entry(opfile); self.assert_ok(result)
        self.assertEqual(json.loads(result.stdout)['entry'], 'AUTHOR_APPROVED')
        self.assertEqual(json.loads(result.stdout)['answer'], 'replan')
        original = self.outer.read_bytes()
        d, body = state._frontmatter_parts(self.outer)
        d['meta_authorization_json'] = ''
        self.outer.write_bytes(state._serialize_state(d) + body)
        self.assertNotEqual(self.worker_meta_entry(opfile).returncode, 0)
        self.outer.write_bytes(original)
        before = state.read_state(self.outer)['meta_authorization_json']
        retried = self.reserve_next_meta_for_worker()
        self.assertEqual(state.read_state(self.outer)['meta_authorization_json'], before)
        self.assertEqual(self.worker_meta_entry(retried).stdout, result.stdout)
        self.assertEqual(self.outer.read_text().count('\nauthor-meta: '), 1)

    def test_legacy_adoption_without_eval_or_diagnosis_is_worker_consumable(self):
        d = self.verified_build()
        fingerprint = d['agreement_revision']
        d.update(status='WAITING FOR INPUT', prior_status='WAITING FOR META-PLAN', agreement_revision='PENDING',
                 adoption_goal_folder='[[vault/goals/goal]]', adoption_verdict='-', last_eval='',
                 operation={k: '' for k in state.OPERATION_FIELDS})
        self.outer.write_bytes(state._serialize_state(d) + b'\n## Pending decision\nanswer:\n')
        self.assert_ok(self.invoke('answer.sh', '--no-kick', 'outer', 'adopt-agreement ' + fingerprint))
        self.phase(3, True)
        opfile = self.reserve_next_meta_for_worker()
        result = self.worker_meta_entry(opfile); self.assert_ok(result)
        self.assertEqual(json.loads(result.stdout)['entry'], 'AUTHOR_APPROVED')
        original = self.outer.read_bytes()
        self.outer.write_bytes(original.replace(b'author-meta: ', b'unverified-prompt-assertion: '))
        self.assertNotEqual(self.worker_meta_entry(opfile).returncode, 0)
        self.outer.write_bytes(original)
        for key, value in (('round', 3), ('agreement_revision', 'f'*64), ('operation_id', 'a'*32)):
            d, body = state._frontmatter_parts(self.outer)
            authorization = json.loads(d['meta_authorization_json']); authorization[key] = value
            d['meta_authorization_json'] = json.dumps(authorization)
            self.outer.write_bytes(state._serialize_state(d) + body)
            self.assertNotEqual(self.worker_meta_entry(opfile).returncode, 0)
            self.outer.write_bytes(original)

    def test_autonomous_worker_entry_keeps_exact_fail_repair_gate(self):
        self.diagnosis_fixture()
        self.phase(3)
        opfile = self.reserve_next_meta_for_worker()
        result = self.worker_meta_entry(opfile); self.assert_ok(result)
        self.assertEqual(json.loads(result.stdout)['entry'], 'AUTONOMOUS_REPAIR')
        original = self.outer.read_bytes()
        d, body = state._frontmatter_parts(self.outer)
        previous = json.loads(d['previous_round_json'])
        previous['last_diagnosis'] = str(self.project / 'diagnoses/unselected.md')
        d['previous_round_json'] = json.dumps(previous)
        self.outer.write_bytes(state._serialize_state(d) + body)
        self.assertNotEqual(self.worker_meta_entry(opfile).returncode, 0)
        self.outer.write_bytes(original)
        d, body = state._frontmatter_parts(self.outer)
        previous = json.loads(d['previous_round_json'])
        previous['agreement_revision'] = 'f'*64
        d['previous_round_json'] = json.dumps(previous)
        self.outer.write_bytes(state._serialize_state(d) + body)
        self.assertNotEqual(self.worker_meta_entry(opfile).returncode, 0)

    def test_raised_limit_round_is_consumable_as_strict_automatic_repair(self):
        self.diagnosis_fixture()
        self.phase(1)
        self.assert_ok(self.invoke('answer.sh', '--no-kick', 'outer', 'raise-limit 3'))
        self.phase(3, True)
        opfile = self.reserve_next_meta_for_worker()
        result = self.worker_meta_entry(opfile); self.assert_ok(result)
        self.assertEqual(json.loads(result.stdout)['entry'], 'AUTONOMOUS_REPAIR')

    def test_stale_capture_collision_cannot_mask_local_changed_or_missing_obligations(self):
        import hashlib
        self.verified_build()
        capture = self.root / 'stale-readme.txt'; capture.write_bytes((self.repo / 'README.md').read_bytes())
        entry = dict(locator='README.md', path=str(capture), source_revision='stale-v1', sha256=hashlib.sha256(capture.read_bytes()).hexdigest())
        captures = self.root / 'collision.json'; captures.write_text(json.dumps([entry]))
        args = ('--repo', self.repo, '--vault', self.repo / 'vault', '--project', self.project)
        for stage in ('original', 'changed-local', 'missing-transitive'):
            with self.subTest(stage=stage):
                if stage == 'changed-local':
                    (self.repo / 'README.md').write_text('[binding](requirements.md)\n')
                    (self.repo / 'requirements.md').write_text('A new required assertion.\n')
                elif stage == 'missing-transitive':
                    (self.repo / 'requirements.md').unlink()
                if stage != 'original':
                    self.git('add', '.'); self.git('commit', '-qm', stage); self.git('push', '-q')
                result = self.helper('context', *args, '--captures', captures)
                self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotEqual(self.helper('context', *args).returncode, 0)

    def test_absolute_capture_origin_cannot_suppress_local_transitive_scan(self):
        import hashlib
        self.verified_build()
        capture = self.root / 'stale-origin.txt'; capture.write_text('Old content without obligations.\n')
        entry = dict(locator=str(self.repo / 'README.md'), path=str(capture), source_revision='old-v1', sha256=hashlib.sha256(capture.read_bytes()).hexdigest())
        captures = self.root / 'origin-collision.json'; captures.write_text(json.dumps([entry]))
        args = ('--repo', self.repo, '--vault', self.repo / 'vault', '--project', self.project, '--captures', captures)
        (self.repo / 'README.md').write_text('[binding](requirements.md)\n')
        (self.repo / 'requirements.md').write_text('First required behavior.\n')
        self.git('add', '.'); self.git('commit', '-qm', 'actual local requirements'); self.git('push', '-q')
        result = self.helper('context', *args); self.assert_ok(result)
        original = json.loads(result.stdout)
        self.assertIn('requirements.md', {m['locator'] for m in original['manifest']})
        (self.repo / 'requirements.md').write_text('Changed required behavior.\n')
        self.git('add', '.'); self.git('commit', '-qm', 'changed transitive only'); self.git('push', '-q')
        changed = self.helper('context', *args); self.assert_ok(changed)
        self.assertNotEqual(original['agreement_revision'], json.loads(changed.stdout)['agreement_revision'])
        (self.repo / 'requirements.md').unlink()
        self.git('add', '.'); self.git('commit', '-qm', 'missing transitive'); self.git('push', '-q')
        self.assertNotEqual(self.helper('context', *args).returncode, 0)

    def test_verified_building_stays_pending_without_auth(self):
        self.verified_build()
        self.assert_ok(self.invoke_tick())
        self.assertEqual(self.outer_status(), 'BUILDING')
        self.assertEqual(self.model_invocations(), [])
        self.assertFalse(any(x['name'] == 'gh' for x in self.logs()))

    def test_all_inner_status_gate_outcomes(self):
        self.verified_build()
        original = self.outer.read_bytes()
        inner = self.running_inner.read_text()
        for status, job, expected in (
            ('RUNNING', 'running', 'BUILDING'), ('PLANNING', 'waiting', 'BUILDING'),
            ('WAITING FOR PLAN', 'waiting', 'BUILDING'), ('WAITING FOR RUN', 'waiting', 'BUILDING'),
            ('WAITING FOR CI', 'waiting', 'BUILDING'), ('WAITING FOR INPUT', 'waiting', 'BUILDING'),
            ('RUNNING', 'stopped', 'WAITING FOR INPUT'), ('garbage', 'waiting', 'WAITING FOR INPUT'),
            ('DONE', 'stopped', 'WAITING FOR EVAL')):
            for adapter in ('Linux', 'Darwin'):
                with self.subTest(status=status, job=job, adapter=adapter):
                    self.outer.write_bytes(original)
                    self.running_inner.write_text(inner.replace('status: RUNNING', 'status: ' + status))
                    self.assert_ok(self.invoke_tick(FAKE_JOB=job, FAKE_OS=adapter))
                    self.assertEqual(self.outer_status(), expected)
                    self.assertEqual(self.model_invocations(), [])
        self.assertFalse(any(x['name'] == 'gh' for x in self.logs()))

    def test_bad_inner_identities_never_evaluate(self):
        self.verified_build('DONE')
        original = self.outer.read_bytes()
        inner = self.running_inner.read_bytes()
        conf = Path(self.env['XDG_CONFIG_HOME']) / 'superagent/inner.env'
        registration = conf.read_bytes()
        for corruption in ('missing', 'malformed', 'wrong-plan', 'wrong-repo', 'wrong-registration', 'missing-registration', 'wrong-round'):
            with self.subTest(corruption=corruption):
                self.outer.write_bytes(original); self.running_inner.write_bytes(inner); conf.write_bytes(registration)
                if corruption == 'missing': self.running_inner.unlink()
                elif corruption == 'malformed': self.running_inner.write_text('status: DONE\n')
                elif corruption == 'wrong-plan': self.running_inner.write_text(inner.decode().replace('PLAN.md', 'OTHER.md'))
                elif corruption == 'wrong-repo': self.register('inner', self.running_inner, 'superagent', self.root)
                elif corruption == 'wrong-registration': self.register('inner', self.outer, 'superagent')
                elif corruption == 'missing-registration': conf.unlink()
                else:
                    data = state.read_state(self.outer); data['round'] = 2; data['operation']['round'] = 2
                    self.outer.write_bytes(state._serialize_state(data))
                self.assert_ok(self.invoke_tick())
                self.assertEqual(self.outer_status(), 'WAITING FOR INPUT')
                self.assertEqual(self.model_invocations(), [])

    def test_live_lock_blocks_gate_write_and_dead_lock_recovers(self):
        self.verified_build('DONE')
        before = self.outer.read_bytes()
        lock = self.outer.parent / ('.' + self.outer.name + '.lockd')
        lock.mkdir(); (lock / 'owner').write_text(str(os.getpid()))
        self.assert_ok(self.invoke_tick())
        self.assertEqual(self.outer.read_bytes(), before)
        self.assertEqual((lock / 'owner').read_text(), str(os.getpid()))
        (lock / 'owner').write_text('999999999')
        self.assert_ok(self.invoke_tick())
        self.assertEqual(self.outer_status(), 'WAITING FOR EVAL')
        self.assertFalse(lock.exists())

    def test_ready_lint_round_limit_and_own_vault_fail_before_registration(self):
        self.assertNotEqual(self.launch(SUPER_CODE_MAX_ITERATIONS='0').returncode, 0)
        self.assertNotEqual(self.launch(SUPER_CODE_MAX_ITERATIONS='one').returncode, 0)
        evaluation = self.project / 'evaluation.md'
        text = evaluation.read_text(); evaluation.write_text(text.replace('READY', 'DRAFT'))
        self.assertNotEqual(self.launch().returncode, 0)
        evaluation.write_text(text.replace('| C1 |', '| BAD |'))
        self.assertNotEqual(self.launch().returncode, 0)
        self.assertFalse((Path(self.env['XDG_CONFIG_HOME']) / 'superagent/outer.env').exists())

    def test_rendered_launchd_exec_preserves_literal_paths(self):
        import plistlib
        config = self.root / 'config & $literal `literal` \"quoted\" \'single\''
        self.env['XDG_CONFIG_HOME'] = str(config)
        self.assert_ok(self.launch(FAKE_OS='Darwin'))
        plist = Path(self.env['SUPERAGENT_LAUNCHD_DIR']) / 'com.superagent.tick.outer.plist'
        data = plistlib.loads(plist.read_bytes())
        result = subprocess.run(data['ProgramArguments'], env=self.env, text=True, capture_output=True)
        self.assert_ok(result)
        self.assertEqual(len(self.model_invocations()), 1)
        self.assertIn('/skills/supercode/SKILL.md', str(self.model_invocations()))
        self.assertIn(str(self.project), self.model_invocations()[-1]['argv'][1])

    def test_gate_rereads_after_acquiring_lock(self):
        self.verified_build('DONE')
        replacement = self.root / 'replacement.md'
        d = state.read_state(self.outer); d['status'] = 'WAITING FOR META-PLAN'
        replacement.write_bytes(state._serialize_state(d))
        python = self.bin / 'python3'
        python.write_text('#!' + sys.executable + "\nimport os, subprocess, sys, shutil\nr=subprocess.run([" + repr(sys.executable) + ", *sys.argv[1:]])\nif r.returncode == 0 and 'acquire-lock' in sys.argv: shutil.copyfile(os.environ['REPLACEMENT'], os.environ['LOOP_FILE'])\nsys.exit(r.returncode)\n")
        python.chmod(0o755)
        self.assert_ok(self.invoke_tick(REPLACEMENT=str(replacement)))
        self.assertEqual(self.outer.read_bytes(), replacement.read_bytes())
        self.assertEqual(self.model_invocations(), [])

    def test_incomplete_scaffold_done_is_not_evaluable(self):
        self.verified_build('DONE')
        self.git('rm', '-q', str((self.goal / 'goal-directives.md').relative_to(self.repo)))
        self.git('commit', '-qm', 'incomplete scaffold'); self.git('push', '-q')
        self.assert_ok(self.invoke_tick())
        self.assertEqual(self.outer_status(), 'WAITING FOR INPUT')

    def test_launcher_reconciles_completed_meta_cursor_under_lock(self):
        d = self.verified_build()
        d.update(status='META-PLANNING', inner_loop='', inner_slug='')
        self.outer.write_bytes(state._serialize_state(d))
        self.assert_ok(self.launch())
        self.assertEqual(self.outer_status(), 'WAITING FOR BUILD')
        self.assertEqual(state.read_state(self.outer)['round'], 1)
        self.assertEqual(len(list(self.outer.parent.glob('*.md'))), 1)

    def test_registered_project_reuses_slug_and_internal_primary_config(self):
        self.assert_ok(self.launch())
        self.assert_ok(self.invoke('launch.sh', self.project, '--supervisor', 'supercode'))
        conf = Path(self.env['XDG_CONFIG_HOME']) / 'superagent'
        self.assertEqual([x.name for x in conf.glob('*.env')], ['outer.env'])
        worktree = self.root / 'linked checkout'
        self.git('worktree', 'add', '-q', '-b', 'linked', str(worktree))
        (self.repo / '.superenv').write_text('SUPER_GOAL_ROOT=vault\n')
        env = self.env.pop('SUPER_GOAL_ROOT')
        try:
            self.assert_ok(self.launch(REPO=str(worktree)))
        finally:
            self.env['SUPER_GOAL_ROOT'] = env

    def test_bootstrap_pending_cannot_be_operation_evidence(self):
        d = self.verified_build()
        d['agreement_revision'] = 'PENDING'
        d['operation']['agreement_revision'] = 'PENDING'
        self.outer.write_bytes(state._serialize_state(d))
        self.assertNotEqual(self.invoke_tick().returncode, 0)
        self.assertEqual(self.model_invocations(), [])

    def test_selected_supervisor_skill_for_each_harness(self):
        self.write_outer(status='WAITING FOR META-PLAN')
        plugin = self.root / 'plugin'
        (plugin / 'scripts').mkdir(parents=True)
        for name in ('superagent-tick.sh', '_common.sh', '_coding_loop_state.py', '_coding_loop_evidence.py'):
            shutil.copyfile(SCRIPTS / name, plugin / 'scripts' / name)
        for path in ('skills/supercode', 'codex/plugins/superagent/skills/supercode', 'pi/skills/supercode', 'cursor/skills/supercode'):
            folder = plugin / path; folder.mkdir(parents=True); (folder / 'SKILL.md').write_text('# fixture skill availability\n')
        for harness, expected_cli in (('claude', 'claude'), ('codex', 'codex'), ('pi', 'pi'), ('cursor', 'agent')):
            with self.subTest(harness=harness):
                result = subprocess.run(['/bin/bash', str(plugin / 'scripts/superagent-tick.sh')],
                    env=dict(self.env, LOOP_FILE=str(self.outer), SUPERAGENT_SUPERVISOR='supercode', SUPER_HARNESS=harness),
                    text=True, capture_output=True)
                self.assert_ok(result)
                call = self.model_invocations()[-1]
                self.assertEqual(call['name'], expected_cli)
                self.assertIn('/skills/supercode/SKILL.md', str(call))

    def test_installer_conflict_and_invalid_supervisor_are_nonmutating(self):
        self.write_outer(status='WAITING FOR META-PLAN')
        conf = Path(self.env['XDG_CONFIG_HOME']) / 'superagent/outer.env'
        original = conf.read_bytes()
        for supervisor in ('superagent', 'bad'):
            result = self.invoke('install-timer.sh', 'outer', self.outer, '--supervisor', supervisor)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(conf.read_bytes(), original)
        self.assertEqual(self.logs(), [])

    def systemd_environment_contract(self, conf):
        """Interpret only generated directive/assignment syntax, not systemd itself.

        Directive contract: config_parse_unit_env_file expands specifiers and
        checks an absolute path; conf-parser passes a stripped raw rvalue.
        https://github.com/systemd/systemd/blob/main/src/core/load-fragment.c#L2496
        https://github.com/systemd/systemd/blob/main/src/shared/conf-parser.c#L237
        Assignment-value contract is separate: systemd.exec EnvironmentFile.
        """
        unit_dir = conf / 'systemd/user'
        unit = (unit_dir / 'superagent-tick@.service').read_text()
        fragments = [unit]
        fragments += [p.read_text() for p in sorted((unit_dir / 'superagent-tick@outer.service.d').glob('*.conf'))]
        paths = []
        for fragment in fragments:
            for line in fragment.splitlines():
                if not line.startswith('EnvironmentFile='):
                    continue
                value = line.partition('=')[2].strip()
                if not value:
                    paths.clear(); continue
                # Directive-specific parser: no unquoting or C-unescaping.
                # Invalid nonabsolute values are ignored by systemd, even
                # after a preceding empty assignment has cleared the list.
                import re
                value = re.sub(r'%(.)', lambda m: {'%': '%', 'i': 'outer', 'h': str(Path.home())}[m[1]], value)
                path = value[1:] if value.startswith('-') else value
                if not path.startswith('/'):
                    continue
                paths.append(Path(path))
        self.assertEqual(len(paths), 1, paths)
        self.assertTrue(paths[0].is_relative_to(conf), f'EnvironmentFile escapes installed XDG configuration: {paths[0]}')
        self.assertTrue(paths[0].is_file(), paths[0])
        result = {}
        for line in paths[0].read_text().splitlines():
            if not line or line.startswith(('#', ';')):
                continue
            key, _, value = line.partition('=')
            # Validate the documented double-quoted EnvironmentFile subset;
            # no variable/command expansion occurs in this format.
            self.assertTrue(value.startswith('"') and value.endswith('"'), line)
            value = value[1:-1]
            out = ''; index = 0
            while index < len(value):
                if value[index] == chr(92) and index + 1 < len(value) and value[index + 1] in ('"', chr(92), '`', '$'):
                    index += 1
                out += value[index]; index += 1
            result[key] = out
        return unit, result

    def test_systemd_path_serializer_is_raw_except_specifier_escaping(self):
        paths = ('/tmp/environment', '/tmp/with spaces/environment',
                 '/tmp/with \\backslash/"quotes"/%h %i %%/environment')
        for path in paths:
            with self.subTest(path=path):
                result = subprocess.run(['/bin/bash', '-c', 'source "$1"; superagent_systemd_path "$2"',
                    'path', str(SCRIPTS / '_common.sh'), path], env=self.env, capture_output=True, text=True)
                self.assert_ok(result)
                self.assertEqual(result.stdout, path.replace('%', '%%') + '\n')

    def test_systemd_ordinary_installed_path_survives_directive_parser(self):
        self.assert_ok(self.launch(FAKE_OS='Linux'))
        conf = Path(self.env['XDG_CONFIG_HOME'])
        _, registration = self.systemd_environment_contract(conf)
        self.assertEqual(registration, state._registration(conf / 'superagent/outer.env'))

    def test_systemd_installed_environment_path_and_literal_contract(self):
        self.env['XDG_CONFIG_HOME'] = str(self.root / 'config with spaces %h \\literal "quotes"')
        # Backslashes in actual runtime values exercise EnvironmentFile's
        # escaping, separately from the directive's path escaping.
        moved = self.project.with_name('project \\literal $dollar `backticks` "quotes"')
        self.project.rename(moved); self.project = moved
        self.assert_ok(self.launch(FAKE_OS='Linux'))
        conf = Path(self.env['XDG_CONFIG_HOME'])
        expected = state._registration(conf / 'superagent/outer.env')
        unit, registration = self.systemd_environment_contract(conf)
        self.assertEqual(registration, expected)
        self.assertEqual(registration.get('XDG_CONFIG_HOME'), str(conf), 'detached tick must retain the installed registry root')
        command = next(line.split('=', 1)[1] for line in unit.splitlines() if line.startswith('ExecStart='))
        import shlex
        # This executes the rendered ExecStart with the independently decoded
        # contract environment. It is NOT real systemd daemon/parser evidence.
        self.assert_ok(subprocess.run(shlex.split(command), env=dict(self.env, **registration), text=True, capture_output=True))
        self.assertEqual(len(self.model_invocations()), 1)
        self.assertIn(str(self.project), self.model_invocations()[-1]['argv'][1])

    def test_two_bash_stale_contenders_cannot_replace_live_owner(self):
        import time
        lock = self.root / '.race.lockd'
        lock.mkdir(); (lock / 'owner').write_text('999999999')
        # Force the old rm/recreate implementation to cache the dead owner in
        # BOTH Bash contenders. A reacquires first; B resumes its stale rm only
        # after A has published success and remains alive. New serialized code
        # need not call rm; simultaneous contenders still test actual ownership.
        rm = self.bin / 'rm'
        rm.write_text('#!' + sys.executable + "\n" + r"""import os, pathlib, subprocess, sys, time
root = pathlib.Path(os.environ['RACE_ROOT']); role = os.environ['RACE_ROLE']
if sys.argv[-1] == os.environ['RACE_LOCK']:
    (root / ('rm-' + role)).touch()
    deadline = time.monotonic() + 5
    while not all((root / ('rm-' + x)).exists() for x in ('A', 'B')):
        if time.monotonic() > deadline: sys.exit(90)
        time.sleep(.01)
    if role == 'B':
        while not (root / 'result-A').exists():
            if time.monotonic() > deadline: sys.exit(91)
            time.sleep(.01)
sys.exit(subprocess.run(['/bin/rm', *sys.argv[1:]]).returncode)
""")
        rm.chmod(0o755)
        script = 'source "$1"; if superagent_acquire_gate_lock "$RACE_LOCK"; then printf "acquired %s\n" "$$" > "$RACE_ROOT/result-$RACE_ROLE"; read -r release; else printf "busy\n" > "$RACE_ROOT/result-$RACE_ROLE"; fi'
        children = [subprocess.Popen(['/bin/bash', '-c', script, 'contender', str(SCRIPTS / '_common.sh')],
                    env=dict(self.env, RACE_ROOT=str(self.root), RACE_LOCK=str(lock), RACE_ROLE=role),
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for role in ('A', 'B')]
        try:
            deadline = time.monotonic() + 8
            while not all((self.root / ('result-' + role)).exists() for role in ('A', 'B')):
                if time.monotonic() > deadline: self.fail('contenders did not finish acquisition')
                time.sleep(.01)
            results = [(self.root / ('result-' + role)).read_text().strip() for role in ('A', 'B')]
            winners = [x.split()[1] for x in results if x.startswith('acquired ')]
            self.assertEqual(len(winners), 1, results)
            self.assertEqual((lock / 'owner').read_text().strip(), winners[0])
            os.kill(int(winners[0]), 0)
        finally:
            for child in children:
                if child.poll() is None: child.terminate()
                child.communicate(timeout=5)

    def test_killed_reclaimer_releases_persistent_guard(self):
        import select
        lock = self.root / '.crash.lockd'
        lock.mkdir(); (lock / 'owner').write_text('999999999')
        guard = lock.with_name(lock.name + '.reclaim')
        holder = subprocess.Popen([sys.executable, '-c',
            'import fcntl, sys; f=open(sys.argv[1], "a+b"); fcntl.flock(f, fcntl.LOCK_EX); print("locked", flush=True); sys.stdin.read()', str(guard)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([holder.stdout], [], [], 5)[0], 'reclaimer did not obtain guard')
            self.assertEqual(holder.stdout.readline().strip(), 'locked')
            inode = guard.stat().st_ino
            script = 'source "$1"; superagent_acquire_gate_lock "$2"'
            args = ['/bin/bash', '-c', script, 'lock', str(SCRIPTS / '_common.sh'), str(lock)]
            blocked = subprocess.run(args, env=self.env, capture_output=True, text=True)
            self.assertEqual(blocked.returncode, 1, blocked.stderr)
            self.assertEqual((lock / 'owner').read_text(), '999999999')
            holder.kill(); holder.communicate(timeout=5)
            self.assert_ok(subprocess.run(args, env=self.env, capture_output=True, text=True))
            self.assertNotEqual((lock / 'owner').read_text().strip(), '999999999')
            self.assertEqual(guard.stat().st_ino, inode, 'persistent guard inode must never be replaced')
        finally:
            if holder.poll() is None: holder.kill()
            holder.communicate(timeout=5)

    def test_killed_acquirer_before_owner_publication_recovers(self):
        lock = self.root / '.publication.lockd'
        code = """import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import _coding_loop_state as state
lock = Path(sys.argv[2]); mkdir = Path.mkdir
def interrupted_mkdir(path, *args, **kwargs):
    mkdir(path, *args, **kwargs)
    if path == lock: os._exit(23)
Path.mkdir = interrupted_mkdir
state.acquire_gate_lock(lock, os.getpid())
"""
        crash = subprocess.run([sys.executable, '-c', code, str(SCRIPTS), str(lock)], capture_output=True, text=True)
        self.assertEqual(crash.returncode, 23, crash.stderr)
        self.assertTrue(lock.exists()); self.assertFalse((lock / 'owner').exists())
        script = 'source "$1"; superagent_acquire_gate_lock "$2"'
        recovered = subprocess.run(['/bin/bash', '-c', script, 'lock', str(SCRIPTS / '_common.sh'), str(lock)],
            env=dict(self.env, SUPER_LOCK_STEAL_MIN='0'), capture_output=True, text=True)
        self.assert_ok(recovered)
        self.assertTrue((lock / 'owner').read_text().strip().isdigit())

    def test_systemd_purge_removes_generated_environment_only(self):
        self.assert_ok(self.launch(FAKE_OS='Linux'))
        conf = Path(self.env['XDG_CONFIG_HOME'])
        service = conf / 'systemd/user/superagent-tick@outer.service.d'
        user_dropin = service / 'operator.conf'
        user_dropin.write_text('[Service]\nNice=1\n')
        loop = next(self.outer.parent.glob('*.md'))
        saved = loop.read_bytes()
        guard = loop.parent / ('.' + loop.name + '.lockd.reclaim')
        guard_inode = guard.stat().st_ino
        self.assert_ok(self.invoke('uninstall-timer.sh', 'outer', FAKE_OS='Linux'))
        self.assertTrue((service / 'environment').exists())
        self.assertTrue((service / 'environment.conf').exists())
        self.assertTrue((conf / 'superagent/outer.env').exists())
        self.assert_ok(self.launch(FAKE_OS='Linux'))
        self.assert_ok(self.invoke('uninstall-timer.sh', 'outer', '--purge', FAKE_OS='Linux'))
        self.assertFalse((service / 'environment').exists())
        self.assertFalse((service / 'environment.conf').exists())
        self.assertFalse((conf / 'superagent/outer.env').exists())
        self.assertEqual(user_dropin.read_text(), '[Service]\nNice=1\n')
        self.assertEqual(loop.read_bytes(), saved)
        self.assertEqual(guard.stat().st_ino, guard_inode)
        self.assertEqual(self.model_invocations(), [])

    def test_ledger_ahead_of_saved_state_refuses_reset(self):
        self.assert_ok(self.launch())
        loop = next(self.outer.parent.glob('*.md')); before = loop.read_bytes()
        with (self.project / 'prd.md').open('a') as out:
            out.write('| 3 | meta3 | goal3 | inner3 | report3 | FAIL |\n')
        self.assertNotEqual(self.launch().returncode, 0)
        self.assertEqual(loop.read_bytes(), before)

    def test_unowned_external_vault_is_rejected(self):
        external = self.root / 'not a git vault'
        shutil.move(str(self.repo / 'vault'), external)
        self.project = external / 'projects/project with spaces'
        self.assertNotEqual(self.launch(SUPER_GOAL_ROOT=str(external)).returncode, 0)
        self.assertEqual(self.logs(), [])

    def test_old_unowned_lock_is_recovered_without_touching_live_peer(self):
        self.verified_build('DONE')
        lock = self.outer.parent / ('.' + self.outer.name + '.lockd')
        lock.mkdir(); (lock / 'acquired').write_text('2000-01-01T00:00:00Z\n')
        self.assert_ok(self.invoke_tick())
        self.assertEqual(self.outer_status(), 'WAITING FOR EVAL')
        self.assertFalse(lock.exists())

    def test_multiple_ledger_tables_never_become_empty_round_one(self):
        with (self.project / 'prd.md').open('a') as out:
            out.write('\nAdditional ledger\n\n| Round | Meta-plan | Goal folder | Inner loop | Eval report | Verdict |\n|---|---|---|---|---|---|\n| 4 | meta4 | goal4 | inner4 | eval4 | FAIL |\n')
        self.assertNotEqual(self.launch().returncode, 0)
        self.assertFalse(self.outer.parent.exists())

    def test_default_goal_launch_and_tick(self):
        result = self.invoke('launch.sh', self.plan, '--slug', 'legacy')
        self.assert_ok(result)
        conf = Path(self.env['XDG_CONFIG_HOME']) / 'superagent/legacy.env'
        self.assertIn('SUPERAGENT_SUPERVISOR=superagent', conf.read_text())
        loop = next(self.running_inner.parent.glob('*legacy.md'))
        self.assert_ok(self.invoke('superagent-tick.sh', LOOP_FILE=str(loop)))
        self.assertEqual(len(self.model_invocations()), 1)
        self.assertIn('/skills/superagent/SKILL.md', str(self.model_invocations()))

    def test_invalid_supervisor_refuses_without_side_effects(self):
        result = self.invoke('launch.sh', self.plan, '--supervisor', '../bad')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.logs(), [])

    def test_project_launch_and_relaunch_each_adapter(self):
        for adapter in ('Linux', 'Darwin'):
            with self.subTest(adapter=adapter):
                self.assert_ok(self.launch(FAKE_OS=adapter))
                loops = list((self.project / 'loop-status').glob('*.md'))
                self.assertEqual(len(loops), 1)
                data = loops[0].read_bytes()
                self.assertEqual(state.read_state(loops[0])['round'], 1)
                self.assertNotIn(b'master_plan:', data)
                self.assert_ok(self.launch(FAKE_OS=adapter, FAKE_JOB='running'))
                self.assertEqual(loops[0].read_bytes(), data)
        self.assertTrue(any(x['name'] == 'launchctl' for x in self.logs()))
        self.assertTrue(any(x['name'] == 'systemctl' for x in self.logs()))
        self.assertFalse(any(x['name'] == 'launchctl' and '-k' in x['argv'] for x in self.logs()))

    def test_slug_collision_does_not_mutate(self):
        self.register('outer', self.running_inner, 'superagent')
        conf = Path(self.env['XDG_CONFIG_HOME']) / 'superagent/outer.env'
        before = conf.read_bytes()
        self.assertNotEqual(self.launch().returncode, 0)
        self.assertEqual(conf.read_bytes(), before)
        self.assertFalse(self.outer.parent.exists())

    def test_identity_conflict_refuses_before_auth(self):
        self.write_outer(status='WAITING FOR META-PLAN')
        result = self.invoke('superagent-tick.sh', LOOP_FILE=str(self.outer), SUPERAGENT_SUPERVISOR='superagent')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.logs(), [])

    def test_building_does_not_start_model(self):
        self.verified_build()
        before = self.model_invocations()
        self.assert_ok(self.invoke_tick())
        self.assertEqual(self.model_invocations(), before)
        self.assertEqual(self.outer_status(), 'BUILDING')

    def test_outer_transients_return_ten_and_preserve_live_peer(self):
        for phase in state.RECOVER_READY:
            d = self.write_outer(status='WAITING FOR META-PLAN')
            d['status'] = phase
            d['operation'].update(id='1'*32, phase=phase, round=1, agreement_revision=d['agreement_revision'],
                                  meta_plan='meta.md', goal_folder='goal', source_vault_commit='b'*40,
                                  code_commit='' if phase == 'META-PLANNING' else 'c'*40,
                                  report='' if phase == 'META-PLANNING' else 'report.md')
            self.outer.write_bytes(state._serialize_state(d))
            self.assertEqual(self.invoke_tick().returncode, 10)
            lock = self.outer.parent / ('.' + self.outer.name + '.lockd')
            lock.mkdir(exist_ok=True)
            (lock / 'owner').write_text(str(os.getpid()))
            self.assert_ok(self.invoke_tick())
            self.assertTrue(lock.exists())
            shutil.rmtree(lock)

    def test_existing_ledger_is_not_reset(self):
        with (self.project / 'prd.md').open('a') as out:
            out.write('| 3 | [[meta-plans/r3]] | [[goals/g3]] | inner3 | [[eval-reports/r3]] | FAIL |\n')
        self.assert_ok(self.launch())
        loop = next((self.project / 'loop-status').glob('*.md'))
        d = state.read_state(loop)
        self.assertEqual(d['round'], 3)
        self.assertEqual(d['status'], 'WAITING FOR INPUT')
        self.assertIn('r3', d['last_eval'])

    def test_missing_python_fails_project_but_not_legacy(self):
        python = self.bin / 'python3'
        python.write_text('#!/bin/sh\nexit 127\n'); python.chmod(0o755)
        self.assertNotEqual(self.launch().returncode, 0)
        self.assert_ok(self.invoke('launch.sh', self.plan, '--slug', 'legacy'))
        loop = next(self.running_inner.parent.glob('*legacy.md'))
        self.assert_ok(self.invoke('superagent-tick.sh', LOOP_FILE=str(loop)))
        self.assertEqual(len(self.model_invocations()), 1)

    def test_external_vault_and_linked_checkout(self):
        external = self.root / 'external vault'
        shutil.move(str(self.repo / 'vault'), external)
        subprocess.run(['git', 'init', '-q', str(external)], check=True)
        (external / '.gitignore').write_text('loop-status/\n')
        self.project = external / 'projects/project with spaces'
        worktree = self.root / 'linked checkout'
        self.git('worktree', 'add', '-q', '-b', 'linked', str(worktree))
        self.assert_ok(self.launch(REPO=str(worktree), SUPER_GOAL_ROOT=str(external)))
        loop = next((self.project / 'loop-status').glob('*.md'))
        self.assertEqual(state.read_state(loop)['project'], str(self.project))
        conf = Path(self.env['XDG_CONFIG_HOME']) / 'superagent/outer.env'
        self.assertIn('REPO=' + str(self.repo), conf.read_text())


if __name__ == '__main__':
    unittest.main()

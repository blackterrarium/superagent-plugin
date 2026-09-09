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

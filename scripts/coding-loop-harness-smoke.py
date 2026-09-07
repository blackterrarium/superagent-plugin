#!/usr/bin/env python3
"""Live Stage 1/2 acceptance against copied Codex/Pi packages and disposable local repos.

Runs real model sessions (requires installed/authenticated harness, Pi requires pi-subagents).
No GitHub or scheduler mutations. The fixture supplies the inner loop's code commit; this tests
superprd's confirmation/reviewer, supermeta's planner/autoconfirm, and supereval's command AND
judged verdicts, not the existing inner scheduler. Logs and repos remain under --run-dir.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def command(args, cwd=None, **kwargs):
    return subprocess.run(args, cwd=cwd, check=True, text=True, **kwargs)


def dispatch_evidence(run, harness, phase):
    """Check runtime-produced dispatch records, independently of model-authored artifacts."""
    if harness == 'codex':
        thread = None
        for line in (run / (phase + '.jsonl')).read_text().splitlines():
            row = json.loads(line)
            if row.get('type') == 'thread.started':
                thread = row['thread_id']
        assert thread, f'{phase}: missing Codex thread receipt'
        sessions = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'sessions'
        logs = list(sessions.glob('**/*-' + thread + '.jsonl'))
        assert len(logs) == 1, f'{phase}: cannot locate Codex runtime transcript for {thread}'
        calls, outputs = {}, {}
        for line in logs[0].read_text().splitlines():
            event = json.loads(line).get('payload', {})
            if event.get('type') == 'function_call' and event.get('name', '').endswith('spawn_agent'):
                calls[event['call_id']] = json.loads(event['arguments'])
            if event.get('type') == 'function_call_output':
                outputs[event['call_id']] = event.get('output', '')
        evidence = []
        for call_id, call in calls.items():
            result = outputs.get(call_id, '')
            if call.get('fork_turns') == 'none' and call.get('model') == 'gpt-5.6-sol' and call.get('reasoning_effort') == 'high' and ('task_name' in result or 'agent_id' in result):
                try:
                    receipt = json.loads(result)
                except json.JSONDecodeError:
                    continue
                child_path = receipt.get('task_name')
                child_id = receipt.get('agent_id')
                completed = None
                for child_log in sessions.glob('**/*.jsonl'):
                    with child_log.open() as stream:
                        try:
                            first = json.loads(stream.readline()).get('payload', {})
                        except json.JSONDecodeError:
                            continue
                        source = first.get('source', {})
                        spawn = source.get('subagent', {}).get('thread_spawn', {}) if isinstance(source, dict) else {}
                        if spawn.get('parent_thread_id') != thread:
                            continue
                        if child_path and spawn.get('agent_path') != child_path:
                            continue
                        if child_id and first.get('id') != child_id:
                            continue
                        matched_pins = False
                        for line in stream:
                            try:
                                row = json.loads(line)
                                item = row.get('payload', {})
                            except json.JSONDecodeError:
                                continue
                            if row.get('type') == 'turn_context':
                                matched_pins = item.get('model') == 'gpt-5.6-sol' and item.get('effort') == 'high'
                            if matched_pins and item.get('type') == 'task_complete' and item.get('last_agent_message'):
                                completed = str(child_log)
                if completed:
                    evidence.append(dict({key: call[key] for key in ('task_name', 'fork_turns', 'model', 'reasoning_effort') if key in call}, completed_child=completed))
        assert evidence, f'{phase}: no successful isolated Codex role dispatch with expected pins'
        return evidence
    # The tool event supplies actual bridge log paths; do not accept unrelated successful runs.
    text = (run / (phase + '.jsonl')).read_text()
    paths = set(re.findall(r'/[^\s"\\]+/superagent-bridge/[^\s"\\]+\.log', text))
    wanted_tools = 'planner' if phase.startswith('meta') else 'evaluator'
    evidence = []
    for name in paths:
        path = Path(name)
        if not path.is_file():
            continue
        lines = path.read_text().splitlines()
        if not lines:
            continue
        header = lines[0]
        if all(word in header for word in ('harness=pi ', 'model=openai-codex/gpt-5.6-sol ', 'effort=high ', 'tools=' + wanted_tools + ' ')) and any('role-bridge: end=' in line and 'exit=0 ' in line for line in lines):
            evidence.append({'log': name, 'header': header})
    assert evidence, f'{phase}: no successful Pi {wanted_tools} bridge with expected pins'
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--harness', choices=['codex', 'pi'], required=True)
    parser.add_argument('--run-dir', type=Path, required=True, help='New directory; never overwritten')
    parser.add_argument('--continue-after-meta', action='store_true', help='Resume after successful first-round meta-planning')
    parser.add_argument('--continue-after-prd', action='store_true', help='Resume a retained fixture after successful draft and approval sessions')
    parser.add_argument('--timeout', type=int, default=1800, help='Per-session ceiling in seconds')
    args = parser.parse_args()
    if args.continue_after_meta:
        args.continue_after_prd = True
    run = args.run_dir.resolve()
    if not args.continue_after_prd:
        run.mkdir(parents=True, exist_ok=False)
    repo, vault, package = run / 'repo', run / 'vault', run / 'plugin'
    source = ROOT / ('codex/plugins/superagent' if args.harness == 'codex' else 'pi')
    if not args.continue_after_prd:
        shutil.copytree(source, package)
        (run / 'tmp').mkdir()
    env = dict(os.environ, TMPDIR=str(run / 'tmp') + '/', SUPER_HARNESS=args.harness,
               SUPERAGENT_PI_SKILLS=str(package / 'skills'))
    # Do not inherit a caller's vault or autoconfirm override into the fixture.
    for key in list(env):
        if key.startswith('SUPER_') and key != 'SUPER_HARNESS':
            del env[key]
    if not args.continue_after_prd:
        for path in (repo, vault):
            path.mkdir()
            command(['git', 'init', '-q', '-b', 'main'], path)
            command(['git', 'config', 'user.name', 'Harness acceptance'], path)
            command(['git', 'config', 'user.email', 'harness-test@example.invalid'], path)
        (repo / 'README.md').write_text('# Greeting\n\nRun `sh hello.sh` to print the greeting.\n')
        (repo / 'hello.sh').write_text('#!/bin/sh\nprintf "pending\\n"\n')
        (vault / 'README.md').write_text('# Disposable acceptance vault\n')
        model = 'codex:gpt-5.6-sol' if args.harness == 'codex' else 'pi:openai-codex/gpt-5.6-sol'
        (repo / '.superenv').write_text(
            f'SUPER_HARNESS={args.harness}\nSUPER_GOAL_ROOT={vault}\nSUPER_PI_SUBAGENTS=required\n'
            f'SUPER_MODEL_PLANNER={model}\nSUPER_EFFORT_PLANNER=high\n'
            f'SUPER_MODEL_PRD_REVIEWER={model}\nSUPER_EFFORT_PRD_REVIEWER=high\n'
            f'SUPER_MODEL_EVALUATOR={model}\nSUPER_EFFORT_EVALUATOR=high\n'
            'SUPER_GOAL_AUTOCONFIRM=false\n')
        (repo / 'AGENTS.md').write_text(
            '# Acceptance fixture\nUse only the supplied copied plugin at ' + str(package) + '.\n'
            'This is a disposable local code repo with a separate external vault. Their origins are\n'
            'local bare repositories. Apply external-vault A7 direct commits; do not create GitHub\n'
            'repositories or PRs. No implementation or scheduler is requested in these sessions.\n'
            'Pass this fixture policy and the copied plugin location to planner children.\n')
        for path in (repo, vault):
            command(['git', 'add', '.'], path)
            command(['git', 'commit', '-qm', 'acceptance fixture'], path)
            bare = run / (path.name + '.git')
            command(['git', 'clone', '-q', '--bare', str(path), str(bare)])
            command(['git', 'remote', 'add', 'origin', str(bare)], path)
            command(['git', 'push', '-qu', 'origin', 'main'], path)
    session = None
    if args.continue_after_prd:
        assert (run / 'approve.jsonl').is_file(), 'No retained approval session'
        receipt = dispatch_evidence(run, args.harness, 'draft')
        (run / 'draft.dispatch.json').write_text(json.dumps(receipt, indent=2) + '\n')

    def invoke(phase, prompt, resume=False):
        nonlocal session
        (run / (phase + '.prompt.txt')).write_text(prompt)
        if args.harness == 'codex':
            argv = ['codex', 'exec'] + (['resume', session] if resume else ['-C', str(repo)])
            argv += ['--dangerously-bypass-approvals-and-sandbox', '--skip-git-repo-check',
                     '-m', 'gpt-5.6-sol', '-c', 'model_reasoning_effort=medium', '--json',
                     '-o', str(run / (phase + '.last.txt')), '-']
        else:
            argv = ['pi', '-p', '--approve', '--mode', 'json', '--skill', str(package / 'skills'),
                    '--model', 'openai-codex/gpt-5.6-sol:medium', '--session',
                    str(run / ('prd.session.jsonl' if phase in ('draft', 'approve') else phase + '.session.jsonl'))]
        print(f'{args.harness}: {phase} started', flush=True)
        with (run / (phase + '.jsonl')).open('w') as out, (run / (phase + '.stderr')).open('w') as err:
            process = subprocess.Popen(argv, cwd=repo, env=env, stdin=subprocess.PIPE,
                                       stdout=out, stderr=err, text=True, start_new_session=True)
            try:
                process.communicate(prompt, timeout=args.timeout)
            except subprocess.TimeoutExpired:
                import signal
                os.killpg(process.pid, signal.SIGTERM)
                process.wait()
                raise RuntimeError(f'{phase} timed out; see {run}')
            if process.returncode:
                raise RuntimeError(f'{phase} exited {process.returncode}; see {run}')
        if args.harness == 'codex' and phase == 'draft':
            for line in (run / (phase + '.jsonl')).read_text().splitlines():
                row = json.loads(line)
                if row.get('type') == 'thread.started':
                    session = row['thread_id']
        if phase != 'approve':
            receipt = dispatch_evidence(run, args.harness, phase)
            (run / (phase + '.dispatch.json')).write_text(json.dumps(receipt, indent=2) + '\n')
        print(f'{args.harness}: {phase} session finished', flush=True)

    def skill(name):
        return f'Read and follow {package}/skills/{name}/SKILL.md. Resolve all plugin skills/helpers from {package}. '

    if not args.continue_after_prd:
        invoke('draft', skill('superprd') + '''Run superprd for this complete planning conversation:
    Objective: a POSIX shell script hello.sh prints exactly hello, world followed by a newline.
    Success S1: `sh hello.sh` stdout matches ^hello, world$ (C1), exit 0 (C2).
    Success S2: README.md visibly states the exact invocation `sh hello.sh` (J1, inspect README.md).
    Evaluation: setup `true`, cwd `.`, all command cwds `.`, timeout 1 minute.
    Knowledge base: README.md (repo-file), hello.sh (sample-code), AGENTS.md (instructions).
    Constraints: POSIX shell only, no network, no external dependencies, no CLI arguments required.
    Decision: use POSIX sh rather than Python to avoid an interpreter dependency beyond the shell.
    Non-goals: arguments, localization, installation. Name the project greeting-acceptance.
    Draft the inputs, run the real PRD reviewer, and stop at the confirmation gate. Do not implement.
    ''')
        assert not list(vault.glob('projects/*/prd.md')), 'superprd wrote before approval'
        invoke('approve', 'I approve the reviewed draft. Write this project folder to the external vault and commit it there under A7. Continue through the Final Report.', resume=True)
    projects = list(vault.glob('projects/*/prd.md'))
    assert len(projects) == 1, f'Expected one authored project, found {projects}'
    project = projects[0].parent
    for name in ('meta-plans', 'eval-reports', 'diagnoses'):
        assert (project / name / '.gitkeep').is_file(), f'Missing Stage 1 artifact folder: {name}'
    command([str(package / 'scripts/prd-lint.sh'), str(project)], repo, env=dict(env, PRD_LINT_REPO_ROOT=str(repo)))
    if args.continue_after_meta:
        receipt = dispatch_evidence(run, args.harness, 'meta')
        (run / 'meta.dispatch.json').write_text(json.dumps(receipt, indent=2) + '\n')
    else:
        invoke('meta', skill('supermeta') + f'Run supermeta {project}. Use the actual PLANNER child and return its result. Do not implement.')
    plans = list(vault.glob('*/master-plans/*.md'))
    assert len(plans) == 1, f'Expected one root plan, found {plans}'
    directives = (plans[0].parent.parent / 'goal-directives.md').read_text()
    assert 'auto-confirmed' in directives and '**Source:**' in directives
    assert 'SUPER_GOAL_AUTOCONFIRM=false' in (repo / '.superenv').read_text()
    # First round: broken implementation and broken judged evidence must both fail.
    (repo / 'README.md').write_text('# Greeting\n\nUsage is undocumented.\n')
    command(['git', 'add', 'README.md'], repo)
    command(['git', 'commit', '-qm', 'negative evaluation fixture'], repo)
    command(['git', 'push', '-q'], repo)
    invoke('eval-fail', skill('supereval') + f'Run supereval {project}. Run the real evaluator child for J1; do not repair anything.')
    reports = list(project.glob('eval-reports/*.md'))
    assert len(reports) == 1, f'Expected one report, found {reports}'
    failed = reports[0].read_text()
    assert '| J1 | FAIL |' in failed, 'Judged negative did not FAIL'
    assert '| C1 | FAIL |' in failed, 'Command negative did not FAIL'
    # Supply the commit normally delivered by the inner loop; scheduler is outside this probe.
    (repo / 'README.md').write_text('# Greeting\n\nRun `sh hello.sh` to print the greeting.\n')
    (repo / 'hello.sh').write_text('#!/bin/sh\nprintf "hello, world\\n"\n')
    command(['git', 'add', 'README.md', 'hello.sh'], repo)
    command(['git', 'commit', '-qm', 'passing implementation fixture'], repo)
    command(['git', 'push', '-q'], repo)
    invoke('meta-r2', skill('supermeta') + f'Run supermeta {project} for round 2. No diagnosis exists; use the failed evaluation as context. Do not implement.')
    assert len(list(vault.glob('*/master-plans/*.md'))) == 2, 'Round 2 root plan missing'
    invoke('eval-pass', skill('supereval') + f'Run supereval {project}. Run the real evaluator child for J1; do not repair anything.')
    reports = list(project.glob('eval-reports/*-r2.md'))
    assert len(reports) == 1, f'Expected round-2 report, found {reports}'
    passed = reports[0].read_text()
    for check in ('C1', 'C2', 'J1'):
        assert f'| {check} | PASS |' in passed, f'{check} did not PASS'
    ledger = projects[0].read_text()
    assert re.search(r'^\|\s*1\s*\|.*\|\s*FAIL\s*\|\s*$', ledger, re.M), 'Round 1 FAIL missing'
    assert re.search(r'^\|\s*2\s*\|.*\|\s*PASS\s*\|\s*$', ledger, re.M), 'Round 2 PASS missing'
    result = {'harness': args.harness, 'result': 'PASS', 'project': str(project),
              'coverage': ['superprd approval gate + reviewer', 'supermeta planner + autoconfirm',
                           'supereval command and judged FAIL/PASS', 'ledger rounds'],
              'excluded': ['inner scheduler', 'GitHub PR transport']}
    (run / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""TEST ONLY: explicit fake native CLI actions, never a product supervisor.

Driver tests select each action. Production CLIs own reservation/reconciliation;
this process writes controlled worker artifacts using the actual operation packet.
Not shipped in distributable packages and never used by production scripts.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def run(*args, ok=(0,)):
    result = subprocess.run(list(map(str, args)), text=True, capture_output=True)
    if result.returncode not in ok:
        raise RuntimeError(f'{args}: {result.returncode}\n{result.stdout}{result.stderr}')
    return result


def event(**values):
    with open(os.environ['FAKE_EVENTS'], 'a') as out:
        out.write(json.dumps(dict(pid=os.getpid(), **values)) + '\n')


def main():
    repo = Path(os.environ['REPO'])
    package = Path(os.environ['FAKE_PACKAGE'])
    scripts = package / 'scripts'
    source_scripts = Path(os.environ['FAKE_SCHEDULER_SCRIPTS'])
    loop = Path(os.environ['LOOP_FILE'])
    role = os.environ.get('FAKE_ROLE', 'supervisor')
    action = os.environ['FAKE_ACTION']
    fault = os.environ.get('FAKE_FAULT', '')
    sys.path.insert(0, str(scripts))
    import _coding_loop_state as state
    import _coding_loop_evidence as evidence
    document = state.read_state(loop)
    project = repo / document['project']
    vault = repo / 'vault'
    packet = loop.parent / 'worker-operation.json'
    conf = Path(os.environ['XDG_CONFIG_HOME']) / 'superagent'
    owner = int(os.environ.get('SUPERAGENT_TICK_PID', os.getpid()))
    lock = loop.parent / ('.' + loop.name + '.lockd')

    def helper(command, *args):
        return json.loads(run(sys.executable, scripts / '_coding_loop_state.py', command, *args).stdout)

    def reconcile():
        result = helper('reconcile-phase', loop, '--repo', repo, '--vault', vault,
                        '--max-rounds', os.environ['SUPER_CODE_MAX_ITERATIONS'],
                        '--consume-answer', '--write', '--owner', owner)
        event(kind='reconcile', **result)
        return result

    def git(*args):
        return run('git', '-C', repo, *args).stdout.strip()

    def integrate(label, paths=('vault',)):
        run('git', '-C', workrepo, 'add', *paths)
        run('git', '-C', workrepo, 'commit', '-qm', label)
        git('merge', '--ff-only', branch)
        # Disposable local bare remote only: production integration verifier
        # requires main and its upstream to agree.
        git('push', '-q', 'origin', 'main')
        event(kind='commit', label=label, commit=git('rev-parse', 'HEAD'))

    def boundary(name):
        if fault == name:
            event(kind='fault', boundary=name)
            raise SystemExit(23)

    def replace(updated):
        current = state.read_state(loop)
        state.replace_state(loop, current, dict(current, **updated))

    event(kind='invocation', role=role, action=action, argv=sys.argv[1:],
          stdin=sys.stdin.read() if Path(sys.argv[0]).name == 'pi' else '')
    if role == 'worker':
        op = evidence._load_json(packet, dict)
        document = state.read_state(loop)
        event(kind='worker', operation=op)
        phase = op['phase']
        skill = {'META-PLANNING': 'supermeta', 'EVALUATING': 'supereval', 'DIAGNOSING': 'superdiagnose'}[phase]
        text = (package / 'skills' / skill / 'SKILL.md').read_text()
        assert '--operation' in text
        branch = 'fake-worker-' + op['id']
        workrepo = Path(os.environ['FAKE_EVENTS']).parent / branch
        if not workrepo.exists():
            git('worktree', 'add', '-q', '-b', branch, str(workrepo))
        output_project = workrepo / document['project']
        identity = f"**Operation:** {op['id']} · **Round:** {op['round']} · **Agreement revision:** {op['agreement_revision']} · **Source vault commit:** {op['source_vault_commit']}"
        if phase == 'META-PLANNING':
            assert '_coding_loop_state.py meta-entry STATE' in text and 'AUTHOR_APPROVED' in text
            entry = helper('meta-entry', loop, '--repo', repo, '--vault', vault,
                           '--conf', conf, '--operation', packet)
            event(kind='meta-entry', **entry)
            goal = workrepo / op['goal_folder']
            meta = workrepo / op['meta_plan']
            meta.parent.mkdir(parents=True, exist_ok=True)
            meta.write_text('# Fake meta\n**Status:** READY\n' + identity + '\n')
            (goal / 'master-plans').mkdir(parents=True, exist_ok=True)
            (goal / 'master-plans/PLAN.md').write_text('# Fake plan\n**Status:** READY\n' + identity + f"\n**Related:** [[{op['meta_plan'][:-3]}]]\n")
            (goal / 'goal-directives.md').write_text('# Directives\n' + identity + f"\n**Source:** [[{op['meta_plan'][:-3]}]]\n**Confirmation:** user-confirmed on 2026-09-09\n")
            for name in ('plans', 'findings', 'reports', 'handoff', 'todo'):
                (goal / name).mkdir(exist_ok=True)
                (goal / name / '.gitkeep').touch()
            if fault == 'partial-meta':
                integrate('partial META before ledger', (op['meta_plan'], op['goal_folder']))
                boundary('partial-meta')
            prd = output_project / 'prd.md'
            row = f"| {op['round']} | [[{op['meta_plan'][:-3]}]] | [[{op['goal_folder']}]] | - | - | - |\n"
            if row not in prd.read_text():
                with prd.open('a') as out: out.write(row)
            helper('meta-entry', loop, '--repo', repo, '--vault', vault, '--conf', conf, '--operation', packet)
        elif phase == 'EVALUATING':
            results = loop.parent / 'commands.txt'
            execution = run('/bin/bash', scripts / 'supereval.sh', project, '--repo', repo,
                            '--commit', op['code_commit'], '--out', results, ok=(0, 1))
            verdict = 'PASS' if execution.returncode == 0 else 'FAIL'
            report = workrepo / op['report']; report.parent.mkdir(exist_ok=True)
            report.write_text('# Fake evaluation\n**Date:** 2026-09-09 · **Status:** FINAL\n' + identity + '\n' + results.read_text() + '\n## Judged objectives\nnone\n## Verdict\n**' + verdict + '** — actual command results\n**Inner loop:** ' + document['inner_loop'] + '\n**Warnings:** none\n')
            prd = output_project / 'prd.md'
            prd.write_text(re.sub(r'(?m)^\| ' + str(op['round']) + r' \|.*$',
                f"| {op['round']} | [[{op['meta_plan'][:-3]}]] | [[{op['goal_folder']}]] | {document['inner_loop']} | [[{op['report'][:-3]}]] | {verdict} |", prd.read_text()))
            event(kind='evaluation', verdict=verdict, code_commit=op['code_commit'])
        else:
            assert (package / 'templates/coding-loop-diagnosis.md').is_file()
            report = workrepo / op['report']; report.parent.mkdir(exist_ok=True)
            report.write_text(f"""# Fake diagnosis
**Date:** 2026-09-09 · **Status:** FINAL · **Round:** {op['round']}
**Operation:** `{op['id']}`
**Eval report:** `{document['last_eval']}`
**Evaluated commit:** `{op['code_commit']}`
**Agreement revision:** `{op['agreement_revision']}`
**Source vault commit:** `{op['source_vault_commit']}`
## Inputs and limitations
Deterministic transport fixture; actual command result inspected, no model judgment.
## Problems
| Problem | C/J IDs | AC IDs | Evidence | Cause | Confidence | Classification |
|---|---|---|---|---|---|---|
| P1 | C1 | none | behavior.txt:1 | Expected approved behavior missing | high | implementation defect |
## Repair guidance
P1: implement the approved behavior.
## Disposition
**REPAIR**
""")
        boundary('before-commit')
        integrate(phase + ' r' + str(op['round']))
        boundary('after-commit')
        receipt = json.loads(run(sys.executable, scripts / '_coding_loop_evidence.py', 'reconcile', repo, vault, '--operation', packet).stdout)
        event(kind='worker-receipt', receipt=receipt)
        assert receipt['worker_complete'], receipt
        return

    run(sys.executable, scripts / '_coding_loop_state.py', 'acquire-lock', lock, '--owner', owner)
    try:
        initial = document['status']
        result = reconcile()
        document = result['state']
        if action == 'reconcile' or document['status'] != initial:
            return
        if action == 'phase':
            phase = os.environ['FAKE_PHASE']
            op = document['operation']
            if op.get('phase') != phase:
                op = {key: '' for key in state.OPERATION_FIELDS}
                op.update(phase=phase, round=document['round'], agreement_revision=document['agreement_revision'],
                          source_vault_commit=git('rev-parse', 'main'))
                if phase == 'META-PLANNING':
                    op.update(meta_plan=str(project.relative_to(repo)) + f"/meta-plans/frozen-r{op['round']}.md",
                              goal_folder=f"vault/goals/frozen-r{op['round']}")
                else:
                    op.update(meta_plan=document['meta_plan'], goal_folder=document['operation']['goal_folder'],
                              code_commit=git('rev-parse', 'main') if phase == 'EVALUATING' else document['evaluated_commit'],
                              report=str(project.relative_to(repo)) + ('/eval-reports/' if phase == 'EVALUATING' else '/diagnoses/') + f"frozen-r{op['round']}.md")
            packet.write_text(json.dumps(op))
            reserved = helper('reserve', loop, '--repo', repo, '--vault', vault, '--operation', packet,
                              '--max-rounds', os.environ['SUPER_CODE_MAX_ITERATIONS'], '--owner', owner)
            packet.write_text(json.dumps(reserved['operation']))
            event(kind='reserved', operation=reserved['operation'])
            boundary('before-worker')
            worker = subprocess.run([sys.argv[0], '--operation', str(packet), '--supervisor-state', str(loop)],
                                    env=dict(os.environ, FAKE_ROLE='worker'), text=True, capture_output=True)
            if worker.returncode:
                raise RuntimeError(worker.stdout + worker.stderr)
            reconcile()
        elif action == 'launch':
            receipt = result['receipt']; assert receipt['worker_complete']
            slug = document['inner_slug'] or f"project-r{document['round']}"
            preview = run('/bin/bash', source_scripts / 'launch.sh', receipt['root_plan'], '--slug', slug, '--dry-run').stdout
            selected = re.search(r'  loop file:  (.*?)  \(', preview)[1]
            if document['inner_loop']:
                assert str(repo / document['inner_loop']) == selected
            replace(dict(inner_slug=slug, inner_loop=str(Path(selected).relative_to(repo))))
            boundary('before-registration')
            registration = conf / (slug + '.env')
            if not registration.exists():
                run('/bin/bash', source_scripts / 'launch.sh', receipt['root_plan'], '--slug', slug)
                event(kind='registration', slug=slug, loop=selected)
            boundary('after-registration')
            raw = state._registration(registration)
            assert raw['LOOP_FILE'] == selected and raw['REPO'] == str(repo)
            inner = state._inner_state(Path(selected))
            assert str(repo / inner['master_plan']) == receipt['root_plan']
            replace(dict(status='BUILDING'))
            decision = state.gate_snapshot(loop, repo, vault, conf, slug, True, False)
            assert decision['action'] == 'SKIP', decision
        else:
            raise ValueError('unknown explicit fixture action: ' + action)
    finally:
        if lock.exists() and (lock / 'owner').read_text().strip() == str(owner):
            shutil.rmtree(lock)


if __name__ == '__main__':
    main()

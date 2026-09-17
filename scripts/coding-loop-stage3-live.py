#!/usr/bin/env python3
"""Bounded Stage 3 acceptance with repo-owned native runtime adapters.

No CLI switch can enable a fake adapter. See README for the missing runtime hooks.
A manifest is data, never a shell script or a Python module to import.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import threading
import time
import uuid

import _coding_loop_evidence as evidence
import _coding_loop_state as state

HARNESSES = {'claude', 'codex', 'pi'}
ROLES = {'SUPERVISOR', 'META_PLANNER', 'PLANNER', 'EVALUATOR', 'DIAGNOSER', 'IMPLEMENTER', 'TASK_REVIEWER', 'BRANCH_REVIEWER', 'EXECUTOR'}
SHA256 = re.compile(r'[0-9a-f]{64}')
SHA = re.compile(r'[0-9a-f]{40}')
SLUG = re.compile(r'[a-z0-9][a-z0-9-]{0,99}')
RUNTIME_REQUIREMENTS = ('native execution requires reviewed CLI/package hashes, synchronous child hooks, '
                        'explicit native pins, GNU timeout, process ownership inspection, authentication, '
                        'a real scheduler and owned outer/inner cleanup')


class Invalid(ValueError): pass
class Incomplete(RuntimeError): pass
class Exhausted(RuntimeError): pass


def result(status, reason='', **fields):
    return dict(status=status, acceptance_passed=False, reason=reason, **fields)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition: raise Invalid(message)


def fields(value, required, optional=()):
    require(isinstance(value, dict), 'expected object')
    require(set(required) <= set(value) <= set(required) | set(optional),
            'missing or unknown fields: ' + ', '.join(sorted(set(required) ^ set(value))))


def absolute(value):
    require(isinstance(value, str) and value and Path(value).is_absolute(), 'absolute path required')
    path = Path(value)
    require(str(path.resolve()) == value, 'path must be physical/canonical (no symlink): ' + value)
    return path


def within(path, root):
    try: Path(path).relative_to(root); return True
    except ValueError: return False


def reference(value):
    fields(value, ('path', 'sha256'))
    absolute(value['path'])
    require(isinstance(value['sha256'], str) and SHA256.fullmatch(value['sha256']), 'invalid content hash')


def read_reference(value):
    reference(value)
    path = absolute(value['path'])
    try: data = path.read_bytes()
    except OSError as exc: raise Incomplete('required artifact unavailable: ' + str(path)) from exc
    require(sha256(data) == value['sha256'], 'artifact hash mismatch: ' + str(path))
    return data


def no_secrets(value):
    if isinstance(value, dict):
        for key, item in value.items():
            require(not re.search(r'password|secret|api.?key|access.?token|authorization', key, re.I),
                    'secret field forbidden; use auth_refs')
            no_secrets(item)
    elif isinstance(value, list):
        for item in value: no_secrets(item)
    elif isinstance(value, str):
        require(not re.search(r'-----BEGIN .*PRIVATE KEY|\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{12,}|https?://[^/\s]*@|[?&](?:token|key|auth)=', value, re.I),
                'credential-like value forbidden; use auth_refs')


def load_manifest(path, approved=False):
    raw = Path(path).read_bytes()
    try: m = json.loads(raw)
    except (ValueError, UnicodeError) as exc: raise Invalid('manifest must be JSON') from exc
    no_secrets(m)
    fields(m, ('protocol_version', 'protocol', 'approval', 'baseline_sha', 'first_failure',
               'limits', 'evidence_dir', 'harnesses'))
    require(type(m['protocol_version']) is int and m['protocol_version'] == 1, 'unsupported protocol version')
    reference(m['protocol'])
    fields(m['approval'], ('receipt_path', 'author_ref'))
    absolute(m['approval']['receipt_path'])
    require(isinstance(m['approval']['author_ref'], str) and m['approval']['author_ref'], 'author reference required')
    require(isinstance(m['baseline_sha'], str) and SHA.fullmatch(m['baseline_sha']), 'exact baseline SHA required')
    fields(m['first_failure'], ('mechanism', 'required_ids'))
    require(isinstance(m['first_failure']['mechanism'], str) and m['first_failure']['mechanism'].strip(), 'first failure mechanism required')
    require(isinstance(m['first_failure']['required_ids'], list) and m['first_failure']['required_ids'] and
            all(re.fullmatch(r'[CJ][1-9][0-9]*', item) for item in m['first_failure']['required_ids']), 'required failing C/J IDs needed')
    fields(m['limits'], ('max_rounds', 'max_dispatches', 'dispatch_seconds', 'total_seconds', 'retries'))
    for key, number in m['limits'].items():
        require(type(number) is int and number >= (0 if key == 'retries' else 1), 'invalid bound: ' + key)
    require(m['limits']['max_rounds'] >= 2, 'failed round and repair require at least two rounds')
    require(m['limits']['dispatch_seconds'] <= m['limits']['total_seconds'], 'dispatch cap exceeds total cap')
    archive = absolute(m['evidence_dir'])
    fields(m['harnesses'], HARNESSES)
    roots, slugs, owners = [], set(), set()
    for harness, h in m['harnesses'].items():
        fields(h, ('code_root', 'vault_root', 'project', 'remotes', 'agreement_revision', 'agreement',
                   'binding_captures', 'slug_prefixes', 'roles', 'packages', 'auth_refs', 'cleanup'), ('runtime',))
        code, vault, project = (absolute(h[key]) for key in ('code_root', 'vault_root', 'project'))
        require(within(project, vault) and project != vault, 'project must be within declared vault')
        require(not any(within(root, other) or within(other, root) for root in (code, vault) for other in roots),
                'harness roots must be isolated')
        roots.extend((code, vault))
        require(not any(within(archive, root) or within(root, archive) for root in (code, vault)), 'evidence must be outside fixture roots')
        fields(h['remotes'], ('code', 'vault'))
        for remotes in h['remotes'].values():
            require(isinstance(remotes, dict) and all(isinstance(k, str) and isinstance(v, str) and k and v for k, v in remotes.items()), 'remote name/URL mapping required')
        require(SHA256.fullmatch(h['agreement_revision'] or ''), 'agreement fingerprint required')
        require(isinstance(h['agreement'], list) and h['agreement'], 'agreement paths/hashes required')
        paths = set()
        for ref in h['agreement']:
            fields(ref, ('path', 'sha256', 'mode'))
            reference({key: ref[key] for key in ('path', 'sha256')})
            require(ref['mode'] in ('bytes', 'prd-without-ledger'), 'unknown agreement hash mode')
            require(ref['mode'] != 'prd-without-ledger' or Path(ref['path']) == project / 'prd.md', 'ledger exemption only for project PRD')
            require(ref['path'] not in paths and any(within(Path(ref['path']), root) for root in (code, vault)), 'unlisted or duplicate agreement path')
            paths.add(ref['path'])
        require({str(project / n) for n in ('prd.md', 'evaluation.md', 'knowledge-base.md')} <= paths, 'all three agreement documents required')
        require(isinstance(h['binding_captures'], list), 'binding captures must be an array')
        fields(h['slug_prefixes'], ('outer', 'inner'))
        for prefix in h['slug_prefixes'].values():
            require(isinstance(prefix, str) and SLUG.fullmatch(prefix) and prefix.endswith('-'), 'invalid slug prefix')
        require(isinstance(h['roles'], dict) and ROLES <= set(h['roles']), 'all supervisor/worker roles must be pinned')
        for role, pin in h['roles'].items():
            require(re.fullmatch(r'[A-Z][A-Z_]*', role), 'invalid role')
            fields(pin, ('model', 'effort'))
            require(isinstance(pin['model'], str) and pin['model'].startswith(harness + ':') and pin['model'] != harness + ':inherit', 'native exact model pin required')
            require(pin['model'][len(harness) + 1:].strip() and isinstance(pin['effort'], str) and pin['effort'] not in ('', 'inherit', 'default'), 'explicit model/effort required')
        require(isinstance(h['packages'], list) and h['packages'], 'installed package pins required')
        for package in h['packages']:
            fields(package, ('path', 'sha256', 'version'))
            reference({k: package[k] for k in ('path', 'sha256')})
            require(isinstance(package['version'], str) and package['version'], 'package version required')
        require(isinstance(h['auth_refs'], list) and h['auth_refs'] and all(isinstance(v, str) and re.fullmatch(r'(env|profile):[A-Za-z0-9_.:/-]+', v) for v in h['auth_refs']), 'auth references required')
        fields(h['cleanup'], ('owner', 'registrations'))
        require(isinstance(h['cleanup']['owner'], str) and h['cleanup']['owner'] and h['cleanup']['owner'] not in owners, 'unique cleanup owner required')
        owners.add(h['cleanup']['owner'])
        require(isinstance(h['cleanup']['registrations'], list) and h['cleanup']['registrations'], 'exact outer/inner cleanup registrations required')
        supervisors = set()
        for registration in h['cleanup']['registrations']:
            fields(registration, ('slug', 'supervisor'))
            require(registration['supervisor'] in ('supercode', 'superagent'), 'invalid supervisor')
            kind = 'outer' if registration['supervisor'] == 'supercode' else 'inner'
            slug = registration['slug']
            require(isinstance(slug, str) and SLUG.fullmatch(slug) and slug.startswith(h['slug_prefixes'][kind]) and slug not in slugs, 'unlisted/duplicate registration')
            slugs.add(slug); supervisors.add(registration['supervisor'])
        require(supervisors == {'supercode', 'superagent'}, 'cleanup must own outer and inner separately')
    if approved: verify_approval(m, raw)
    return m


def verify_approval(m, raw):
    try: receipt = json.loads(absolute(m['approval']['receipt_path']).read_bytes())
    except (OSError, ValueError) as exc: raise Invalid('actual author approval receipt missing or malformed') from exc
    fields(receipt, ('manifest_sha256', 'author_ref', 'decision', 'record'))
    require(receipt['manifest_sha256'] == sha256(raw), 'approved manifest byte hash mismatch')
    require(receipt['author_ref'] == m['approval']['author_ref'] and receipt['decision'] == 'APPROVED', 'author approval identity/decision mismatch')
    record = read_reference(receipt['record'])
    require(sha256(raw).encode() in record, 'author record does not name exact manifest digest')
    read_reference(m['protocol'])
    return receipt


def git(root, *args):
    try:
        return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True, timeout=10).stdout.strip()
    except (subprocess.SubprocessError, OSError) as exc: raise Incomplete('Git identity check failed') from exc


def check_scope(m, harness, baseline=False):
    require(harness in m['harnesses'], 'wrong harness')
    h = m['harnesses'][harness]
    code, vault = absolute(h['code_root']), absolute(h['vault_root'])
    require(git(code, 'rev-parse', '--show-toplevel') == str(code), 'unlisted code root')
    for root, kind in ((code, 'code'), (vault, 'vault')):
        if kind == 'vault' and within(vault, code):
            require(h['remotes']['vault'] == {}, 'internal vault remotes must be empty'); continue
        require(git(root, 'rev-parse', '--show-toplevel') == str(root), 'unlisted vault root')
        names = git(root, 'remote').splitlines()
        require(set(names) == set(h['remotes'][kind]), 'unlisted or missing remote')
        for name in names:
            for flag in ([], ['--push']):
                require(git(root, 'remote', 'get-url', *flag, '--all', name).splitlines() == [h['remotes'][kind][name]], 'unlisted remote URL')
    if baseline: require(git(code, 'rev-parse', 'HEAD') == m['baseline_sha'], 'selected baseline SHA mismatch')


def check_agreement(m, harness, context=True):
    h = m['harnesses'][harness]
    for ref in h['agreement']:
        try: data = absolute(ref['path']).read_bytes()
        except OSError as exc: raise Incomplete('agreement unavailable') from exc
        if ref['mode'] == 'prd-without-ledger': data = evidence._without_iteration_ledger(data)
        require(sha256(data) == ref['sha256'], 'changed agreement: ' + ref['path'])
    if context:
        current = state.acceptance_context(Path(h['code_root']), Path(h['vault_root']), Path(h['project']), h['binding_captures'])
        require(current['agreement_revision'] == h['agreement_revision'], 'changed binding agreement')


def scrub(text):
    text = re.sub(r'(?i)(?:Bearer\s+|(?:api[_-]?key|token|password|secret)\s*[=:]\s*)[^\s,;]+', '[REDACTED]', text)
    text = re.sub(r'\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]+', '[REDACTED]', text)
    return re.sub(r'-----BEGIN .*?PRIVATE KEY-----.*?-----END .*?PRIVATE KEY-----', '[REDACTED]', text, flags=re.S)


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as out:
        out.write(scrub(json.dumps(value, indent=2, sort_keys=True)) + '\n')


def new_attempt(m, path, action, harness=None):
    base = absolute(m['evidence_dir'])
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder = base / (time.strftime('%Y%m%dT%H%M%S') + '-' + action + '-' + uuid.uuid4().hex)
    folder.mkdir(mode=0o700)
    (folder / 'manifest.json').write_bytes(Path(path).read_bytes())
    write_json(folder / 'request.json', dict(action=action, harness=harness,
               manifest_sha256=sha256(Path(path).read_bytes()), created=time.time()))
    return folder


def prepare(path):
    m = load_manifest(path)
    folder = new_attempt(m, path, 'prepare')
    output = result('INCOMPLETE', 'review-only preparation; obtain author approval of exact manifest bytes before run',
                    attempt=str(folder), manifest_sha256=sha256(Path(path).read_bytes()), runtime_requirements=RUNTIME_REQUIREMENTS)
    write_json(folder / 'result.json', output)
    return output


class Budget:
    """Single owner pre-dispatch gate. Adapters must mediate *every* native spawn.

    Native tools must block until this gate grants a permit. Watching CLI logs after
    a spawn cannot satisfy this interface. Permits consume budget even on failure.
    """
    def __init__(self, manifest, harness, emit):
        self.m, self.harness, self.emit = manifest, harness, emit
        self.deadline = time.monotonic() + manifest['limits']['total_seconds']
        self.used, self.attempts, self.ids = 0, {}, set()
        self.lock = threading.Lock()

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0: raise Exhausted('total elapsed deadline exhausted')
        return remaining

    def authorize(self, request):
        with self.lock:
            left = self.remaining()
            h, limits = self.m['harnesses'][self.harness], self.m['limits']
            fields(request, ('id', 'role', 'harness', 'model', 'effort', 'round', 'operation', 'code_root', 'vault_root', 'slug'))
            require(request['harness'] == self.harness, 'wrong native harness')
            require(request['role'] in h['roles'], 'unlisted worker role')
            pin = h['roles'][request['role']]
            require(all(request[k] == pin[k] for k in ('model', 'effort')), 'wrong model/effort')
            require(all(request[k] == h[k] and str(absolute(request[k])) == h[k] for k in ('code_root', 'vault_root')), 'unlisted worker root')
            require(request['slug'] in {r['slug'] for r in h['cleanup']['registrations']}, 'unlisted scheduler identity')
            require(type(request['round']) is int and 1 <= request['round'] <= limits['max_rounds'], 'round bound exceeded')
            require(isinstance(request['id'], str) and request['id'] and request['id'] not in self.ids, 'duplicate/missing dispatch ID')
            require(isinstance(request['operation'], str) and request['operation'], 'operation ID required')
            key = (request['round'], request['operation'], request['role'])
            if self.used >= limits['max_dispatches']: raise Exhausted('native role dispatch ceiling exhausted')
            if self.attempts.get(key, 0) > limits['retries']: raise Exhausted('operation retry ceiling exhausted')
            self.used += 1; self.attempts[key] = self.attempts.get(key, 0) + 1; self.ids.add(request['id'])
            permit = dict(request, kind='dispatch-permit', sequence=self.used,
                          seconds=min(left, limits['dispatch_seconds']))
            self.emit(permit)
            return permit


def bounded_process(argv, cwd, seconds, output):
    """Owned process-group cap for adapter helpers; not a native child counter."""
    require(isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv), 'subprocess requires argv array')
    require(seconds > 0, 'positive subprocess deadline required')
    started, timed_out = time.monotonic(), False
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(argv, cwd=str(cwd), stdout=stdout, stderr=stderr, start_new_session=True)
        try: process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        finally:
            # Catch descendants retaining the group after the direct child exits.
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        for source, suffix in ((stdout, '.stdout'), (stderr, '.stderr')):
            source.seek(0)
            with Path(str(output) + suffix).open('x', encoding='utf-8') as target:
                target.write(scrub(source.read().decode('utf-8', errors='replace')))
    return dict(returncode=process.returncode, timed_out=timed_out, elapsed=time.monotonic() - started)


def cleanup_owned(m, harness, adapter):
    receipts, problems = [], []
    for identity in m['harnesses'][harness]['cleanup']['registrations']:
        try:
            adapter.stop(dict(identity))
            active = adapter.active(dict(identity))
            receipts.append(dict(identity, active=active))
            if active: problems.append(identity['slug'] + ' still has an active timer/process')
        except Exception as exc:
            problems.append(identity['slug'] + ': ' + scrub(str(exc)))
    return result('INCOMPLETE' if problems else 'PASS', '; '.join(problems), cleanup=receipts)


def verdict_sequence(evaluations, maximum):
    if not evaluations: return result('INCOMPLETE', 'missing first real evaluation')
    if evaluations[0]['round'] != 1 or evaluations[0]['verdict'] != 'FAIL':
        return result('INVALID', 'first evaluation unexpectedly PASS or not round one')
    if [e['round'] for e in evaluations] != list(range(1, len(evaluations) + 1)) or len(evaluations) > maximum:
        return result('INVALID', 'nonconsecutive evaluations or round ceiling exceeded')
    if any(e['verdict'] == 'PASS' for e in evaluations[:-1]): return result('INVALID', 'work continued after PASS')
    if evaluations[-1]['verdict'] == 'PASS': return result('PASS')
    return result('FAIL' if len(evaluations) == maximum else 'INCOMPLETE', 'no passing repair evaluation')


def validate_integration(repo, vault, evaluated, changes):
    """Preserve authentic actor SHAs; prove squash delivery and later bookkeeping."""
    integrated = changes['integrate']
    reviewed = changes['review']['code_commit']
    merged = integrated.get('merge_commit')
    integration_head = integrated['code_commit']
    require(changes['implement']['code_commit'] == reviewed == integrated.get('reviewed_commit'), 'implementation was not the reviewed head')
    require(evidence._commit_resolves(repo, merged), 'integrator did not record the merge revision')
    pr = integrated.get('pull_request', {})
    require(pr.get('url') == integrated.get('pr_url') and pr.get('state') == 'MERGED'
            and pr.get('baseRefName') == 'main' and pr.get('headRefOid') == reviewed
            and pr.get('mergeCommit', {}).get('oid') == merged, 'PR provenance does not match reviewed head and merge')
    parents = git(repo, 'rev-list', '--parents', '-n', '1', merged).split()
    require(len(parents) == 2, 'expected normal squash integration commit')
    # Reconstruct the actual Git merge tree, including concurrent changes on main.
    # This compares tree contents, not an unverifiable message or rebased receipt.
    expected_tree = git(repo, 'merge-tree', '--write-tree', parents[1], reviewed).splitlines()[0]
    require(expected_tree == git(repo, 'rev-parse', merged + '^{tree}'), 'squash tree differs from reviewed change')
    git(repo, 'merge-base', '--is-ancestor', merged, integration_head)
    git(repo, 'merge-base', '--is-ancestor', integration_head, evaluated)
    git(repo, 'merge-base', '--is-ancestor', evaluated, 'refs/heads/main')
    paths = ['.']
    if within(vault, repo): paths.append(':(exclude)' + vault.relative_to(repo).as_posix())
    require(not git(repo, 'diff', '--name-only', merged, evaluated, '--', *paths), 'unreviewed code changed after integration')


def inspect_evidence(m, harness, packet):
    """Validate actual revision-specific artifacts. PASS here is never live authority.

    Only a certified adapter can authenticate dispatch/change/state receipts. This
    function also serves offline callers and consequently never sets acceptance_passed.
    """
    try:
        h = m['harnesses'][harness]
        repo, vault, project = (Path(h[k]) for k in ('code_root', 'vault_root', 'project'))
        context = state.acceptance_context(repo, vault, project, h['binding_captures'])
        require(context['agreement_revision'] == h['agreement_revision'], 'changed agreement')
        operations = packet.get('operations', [])
        dispatches = packet.get('dispatches', [])
        if not operations or not dispatches: return result('INCOMPLETE', 'missing runtime operations/role receipts')
        require(len({d['id'] for d in dispatches}) == len(dispatches), 'duplicate runtime dispatch receipts')
        by_id = {d['id']: d for d in dispatches}
        evaluations, diagnoses, metas = [], {}, {}
        for op in operations:
            require(op['agreement_revision'] == h['agreement_revision'], 'operation agreement mismatch')
            role = {'META-PLANNING': 'META_PLANNER', 'EVALUATING': 'EVALUATOR', 'DIAGNOSING': 'DIAGNOSER'}.get(op['phase'])
            matches = [d for d in dispatches if d.get('operation_id') == op['id'] and d.get('role') == role and d.get('status') == 'completed']
            require(len(matches) == 1 and matches[0]['harness'] == harness and matches[0]['round'] == op['round'] and matches[0]['source_commit'] == op['code_commit'], 'wrong runtime role/round/SHA receipt')
            receipt = evidence.reconcile_operation(repo, vault, op)
            require(receipt.get('outcome') == 'INTEGRATED' and receipt.get('worker_complete'), 'unintegrated or invalid operation: ' + receipt.get('reason', receipt.get('completion_reason', 'missing')))
            if op['phase'] == 'META-PLANNING': metas[op['round']] = op; continue
            if op['phase'] == 'DIAGNOSING': diagnoses[op['round']] = op; continue
            report = evidence.validate_evaluation(Path(receipt['report']), project / 'evaluation.md', op)
            require(not report['errors'], 'invalid evaluation: ' + '; '.join(report['errors']))
            require(not report['missing_ids'], 'missing required command/judge results')
            evaluations.append(dict(round=op['round'], verdict=report['verdict'], operation=op, validation=report))
        evaluations.sort(key=lambda row: row['round'])
        outcome = verdict_sequence(evaluations, m['limits']['max_rounds'])
        if outcome['status'] == 'INVALID' or not evaluations: return outcome
        require(evaluations[0]['operation']['code_commit'] == m['baseline_sha'], 'first evaluation is not selected failing baseline SHA')
        require(set(m['first_failure']['required_ids']) <= set(evaluations[0]['validation']['failing_ids']), 'required initial defect was not observed')
        for failed, repaired in zip(evaluations, evaluations[1:]):
            number = failed['round']; op = failed['operation']
            if number not in diagnoses or repaired['round'] not in metas:
                return result('INCOMPLETE', 'missing diagnosis or planned repair')
            diagnosis = diagnoses[number]
            diagnosis_path = Path(diagnosis['report'])
            if not diagnosis_path.is_absolute(): diagnosis_path = repo / diagnosis_path
            checked = evidence.validate_diagnosis(diagnosis_path, dict(diagnosis,
                eval_report=op['report'], failing_ids=failed['validation']['failing_ids'],
                missing_ids=failed['validation']['missing_ids'],
                applicable_ac_ids=failed['validation']['required_ids']['AC'],
                allowed_ids=failed['validation']['required_ids']))
            require(checked['may_start_next_round'] and not checked['errors'], 'invalid repair diagnosis: ' + '; '.join(checked['errors']))
            sha = repaired['operation']['code_commit']
            require(sha != op['code_commit'], 'repair did not change selected revision')
            git(repo, 'merge-base', '--is-ancestor', op['code_commit'], sha)
            changes_by_action = {}
            for action, role in (('implement', 'IMPLEMENTER'), ('review', 'BRANCH_REVIEWER'), ('integrate', 'EXECUTOR')):
                changes = [c for c in packet.get('changes', []) if c.get('action') == action and c.get('round') == repaired['round']]
                if not changes: return result('INCOMPLETE', 'missing inner ' + action + ' receipt')
                require(len(changes) == 1, 'conflicting inner ' + action + ' receipts')
                change = changes[0]; worker = by_id.get(change.get('dispatch_id'), {})
                require(worker.get('role') == role and worker.get('parent') == 'inner-supervisor' and worker.get('status') == 'completed' and worker.get('harness') == harness and worker.get('round') == repaired['round'], 'controller-written repair or wrong inner role')
                source = change.get('code_commit')
                require(evidence._commit_resolves(repo, source), 'unresolved worker revision')
                require(worker.get('source_commit') == source and change.get('plan') == metas[repaired['round']]['meta_plan'], 'review/repair/integration SHA or plan mismatch')
                artifact = change.get('artifact')
                require(isinstance(artifact, dict), 'missing normal inner ' + action + ' artifact')
                body = read_reference(artifact).decode('utf-8')
                path = Path(artifact['path'])
                artifact_root = repo if within(path, repo) else vault
                require(within(path, artifact_root), 'unlisted inner delivery artifact')
                _, error = evidence._path_at_main(artifact_root, path)
                require(not error and source in body and re.search(r'\bPASS\b', body), 'unintegrated or revision-mismatched inner delivery/review artifact')
                changes_by_action[action] = change
            validate_integration(repo, vault, sha, changes_by_action)
        if outcome['status'] == 'PASS':
            history = packet.get('transitions', [])
            needed = ['WAITING FOR EVAL', 'WAITING FOR DIAGNOSIS', 'WAITING FOR META-PLAN', 'WAITING FOR BUILD', 'BUILDING', 'WAITING FOR EVAL', 'DONE']
            cursor = iter(history)
            require(all(any(event == wanted for event in cursor) for wanted in needed), 'missing scheduler/state transition evidence')
            require(history[-1] == 'DONE', 'work continued after terminal state')
        return dict(outcome, evaluations=evaluations, synthetic=packet.get('synthetic', True))
    except (Invalid, state.StateError, evidence.EvidenceError, KeyError, TypeError, ValueError) as exc:
        return result('INVALID', scrub(str(exc)))
    except (Incomplete, OSError) as exc: return result('INCOMPLETE', scrub(str(exc)))



def archive_scope(m, harness, attempt):
    """Retain full scoped agreement/evaluation/diagnosis/planning documents, scrubbed."""
    h = m['harnesses'][harness]; project = absolute(h['project'])
    paths = {absolute(ref['path']) for ref in h['agreement']}
    for folder in ('eval-reports', 'diagnoses', 'meta-plans'):
        root = project / folder
        if root.is_dir(): paths.update(root.rglob('*.md'))
    index = project / 'loop-status/stage3-evidence.json'
    if index.is_file():
        paths.add(index)
        try:
            packet = json.loads(index.read_text())
            for change in packet.get('changes', []):
                if isinstance(change.get('artifact'), dict): paths.add(Path(change['artifact']['path']))
            for operation in packet.get('operations', []):
                for key in ('report', 'meta_plan'):
                    if operation.get(key):
                        path = Path(operation[key]); paths.add(path if path.is_absolute() else Path(h['code_root']) / path)
                if operation.get('goal_folder'):
                    goal = Path(operation['goal_folder'])
                    if not goal.is_absolute(): goal = Path(h['code_root']) / goal
                    if any(within(goal.resolve(), Path(h[k])) for k in ('code_root', 'vault_root')):
                        paths.update(goal.rglob('*.md'))
        except (ValueError, KeyError, TypeError): pass
    folder = attempt / 'artifacts'; folder.mkdir()
    inventory = []
    for path in sorted(paths):
        path = absolute(str(path))
        require(any(within(path, Path(h[k])) for k in ('code_root', 'vault_root')), 'unlisted archive source')
        if not path.is_file(): continue
        original = path.read_bytes(); sanitized = scrub(original.decode('utf-8', errors='replace')).encode()
        target = folder / (str(len(inventory)) + '-' + path.name)
        target.write_bytes(sanitized)
        inventory.append(dict(source=str(path), original_sha256=sha256(original), archive=str(target), archived_sha256=sha256(sanitized)))
    write_json(attempt / 'artifacts.json', inventory)


def execute(action, path, harness):
    attempt = None
    approved = False
    try:
        if action == 'prepare': return prepare(path)
        m = load_manifest(path)
        require(harness in HARNESSES, 'wrong harness')
        attempt = new_attempt(m, path, action, harness)
        verify_approval(m, Path(path).read_bytes())
        approved = True
        from _coding_loop_live_native import NativeAdapter
        # An adapter addition is a reviewed product change. Required interface:
        # preflight(m,h) checks installed hashes/versions, CLI/auth, GNU timeout,
        # real scheduler, native scope and blocking role gates before any arm.
        # run(m,h,attempt,Budget) owns an independent watchdog + event IPC and
        # returns only after all owned native work is stopped. It cannot trust a
        # supervisor's self-report. collect authenticates raw runtime receipts.
        adapter = NativeAdapter(harness)
        if action == 'run': adapter.preflight(m, harness)
        else: adapter.configure(m, harness)
        if action != 'cleanup':
            check_scope(m, harness, baseline=action == 'run')
            check_agreement(m, harness)
        if action == 'cleanup':
            adapter.discover_owned(path)
            output = cleanup_owned(m, harness, adapter)
        else:
            if action == 'run':
                def emit(event):
                    with (attempt / 'events.jsonl').open('a') as out: out.write(scrub(json.dumps(event)) + '\n')
                    print(json.dumps({'event': event['kind'], 'sequence': event.get('sequence')}), flush=True)
                budget = Budget(m, harness, emit)
                try: adapter.run(m, harness, attempt, budget)
                finally:
                    cleanup = cleanup_owned(m, harness, adapter)
                    write_json(attempt / 'cleanup.json', cleanup)
                if cleanup['status'] != 'PASS': raise Incomplete(cleanup['reason'])
            packet = adapter.collect(m, harness)
            require(packet.get('synthetic') is False, 'synthetic runtime receipt cannot authorize live acceptance')
            output = inspect_evidence(m, harness, packet)
            cleanup = cleanup_owned(m, harness, adapter)
            check_scope(m, harness)
            check_agreement(m, harness)
            if cleanup['status'] != 'PASS': output = cleanup
            if output['status'] == 'PASS': output['acceptance_passed'] = True
        output['attempt'] = str(attempt)
    except (Invalid, state.StateError, evidence.EvidenceError, ValueError, TypeError, KeyError) as exc:
        output = result('INVALID', scrub(str(exc)))
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        output = result('INCOMPLETE', scrub(str(exc)))
    if attempt:
        if approved and action in ('run', 'collect'):
            try: archive_scope(m, harness, attempt)
            except (OSError, Invalid, ValueError) as exc:
                output = result('INCOMPLETE', 'evidence archive failed: ' + scrub(str(exc)))
        output['attempt'] = str(attempt)
        write_json(attempt / 'result.json', output)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'collect', 'cleanup'))
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--harness', choices=sorted(HARNESSES))
    args = parser.parse_args(argv)
    if args.action != 'prepare' and not args.harness: parser.error('--harness is required')
    output = execute(args.action, args.manifest, args.harness)
    print(json.dumps(output, indent=2, sort_keys=True))
    return {'PASS': 0, 'FAIL': 1, 'INVALID': 2, 'INCOMPLETE': 3}[output['status']]


if __name__ == '__main__': raise SystemExit(main())

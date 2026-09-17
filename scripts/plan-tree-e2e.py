#!/usr/bin/env python3
"""Validate retained upfront plan-tree evidence without running a lifecycle.

The manifest is an index of repositories and evidence artifacts.  Verdicts are
derived from those artifacts; a manifest-supplied PASS flag is never consulted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


PT_IDS = tuple('PT-%02d' % number for number in range(1, 12))
STATUS_RANK = {'PASS': 0, 'INCOMPLETE': 1, 'FAIL': 2}
FIELD_RE = re.compile(r'^\*\*([^*]+):\*\*\s*(.*?)\s*$')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*$')
HEADER_RE = re.compile(
    r'^role-bridge: start=(\S+) harness=(\S+) model=(\S+) effort=(\S+) '
    r'tools=(\S+) role=(\S+) cwd=(.*)$')
TRAILER_RE = re.compile(
    r'^role-bridge: end=(\S+) exit=(\d+) secs=(\d+) result_bytes=(\d+)$')
ROLE_LOG_NAMES = {'PLAN_REFINER': 'plan-refiner', 'REPLANNER': 'replanner',
                  'PLANNER': 'planner', 'EXECUTOR': 'executor'}


def result(status, message, facts=None):
    return {'status': status, 'message': message, 'facts': facts or {}}


def prepared_body(data):
    """Return exact bytes hashed by S5, preserving every non-pointer byte."""
    data.decode('utf-8')
    kept = []
    matches = 0
    for line in data.splitlines(keepends=True):
        content = line[:-2] if line.endswith(b'\r\n') else (
            line[:-1] if line.endswith((b'\n', b'\r')) else line)
        if content.startswith(b'**Preparation:**'):
            matches += 1
        else:
            kept.append(line)
    if matches != 1:
        raise ValueError('prepared plan must contain exactly one complete Preparation line')
    return b''.join(kept)


def resolve_path(value, base):
    if not isinstance(value, str) or not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def markdown_fields(data):
    text = data.decode('utf-8')
    fields = {}
    duplicates = set()
    for line in text.splitlines():
        match = FIELD_RE.match(line)
        if not match:
            continue
        key, value = match.group(1).strip(), match.group(2).strip()
        if key in fields and fields[key] != value:
            duplicates.add(key)
        fields[key] = value
    if duplicates:
        raise ValueError('conflicting duplicate field(s): ' + ', '.join(sorted(duplicates)))
    return fields


def markdown_sections(data):
    """Return nonempty Markdown section bodies keyed by heading text."""
    lines = data.decode('utf-8').splitlines()
    sections = {}
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        level = len(match.group(1))
        name = match.group(2).strip()
        body = []
        for following in lines[index + 1:]:
            next_heading = HEADING_RE.match(following)
            if next_heading and len(next_heading.group(1)) <= level:
                break
            body.append(following)
        value = '\n'.join(body).strip()
        if value:
            sections[name] = value
    return sections


def contract_value(fields, sections, name):
    return field(fields, name) or sections.get(name)


def dependency_ids(value):
    if not isinstance(value, str) or not value.strip():
        return None
    if value.strip().lower() == 'none':
        return []
    parts = [part for part in re.split(r'[\s,]+', value.strip()) if part]
    if any(not re.fullmatch(r'S\d+', part) for part in parts):
        return None
    return parts


def progress_plan_links(data):
    """Read Plan cells from the first Markdown table that has a Plan column."""
    lines = data.decode('utf-8').splitlines()
    for index, line in enumerate(lines):
        if '|' not in line:
            continue
        headers = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if 'Plan' not in headers or index + 1 >= len(lines):
            continue
        plan_index = headers.index('Plan')
        links = []
        for row in lines[index + 2:]:
            if '|' not in row:
                break
            cells = [cell.strip() for cell in row.strip().strip('|').split('|')]
            if plan_index >= len(cells):
                continue
            cell = cells[plan_index]
            wiki = re.search(r'\[\[([^]|]+)(?:\|[^]]+)?\]\]', cell)
            markdown = re.search(r'\[[^]]+\]\(([^)]+)\)', cell)
            if wiki:
                links.append(wiki.group(1))
            elif markdown:
                links.append(markdown.group(1))
            elif cell and cell.lower() != 'none':
                links.append(None)
        return links
    return None


def active_stage_map(repo, commit, root_rel):
    """Resolve active Plan links through root/sub-master tables to stage identities."""
    queue = [root_rel]
    visited = set()
    stages = {}
    while queue:
        relpath = queue.pop(0)
        if relpath in visited:
            return result('FAIL', 'active Plan links contain a cycle or duplicate path')
        visited.add(relpath)
        blob, error = git_blob(repo, commit, relpath)
        if error:
            return result('INCOMPLETE', 'active Plan link is missing: %s' % relpath)
        try:
            fields = markdown_fields(blob)
            stage_id = field(fields, 'Stage ID')
            if stage_id:
                if stage_id in stages:
                    return result('FAIL', 'active Plan links contain duplicate stage %s' % stage_id)
                stages[stage_id] = relpath
                continue
            links = progress_plan_links(blob)
        except (UnicodeError, ValueError) as exc:
            return result('FAIL', 'active Plan artifact is malformed: %s' % exc)
        if links is None or not links:
            return result('INCOMPLETE', 'active Plan links are absent from %s' % relpath)
        if any(link is None for link in links):
            return result('INCOMPLETE', 'an active Plan cell has no resolvable link')
        queue.extend(links)
    return result('PASS', 'active Plan links resolve the published stage graph', {'stages': stages})


def field(fields, *names):
    for name in names:
        if name in fields:
            return fields[name]
    return None


def reference_path(value):
    """Return the path carried by a plain or unlabelled wiki-link field."""
    if not isinstance(value, str):
        return None
    if value.startswith('[[') and value.endswith(']]'):
        return value[2:-2]
    return value


def git(repo, *args):
    try:
        proc = subprocess.run(['git', '-C', str(repo)] + list(args), text=False,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        return None, str(exc)
    if proc.returncode:
        message = proc.stderr.decode('utf-8', errors='replace').strip()
        return None, message or 'git exited %d' % proc.returncode
    return proc.stdout, None


def git_commit(repo, revision):
    output, error = git(repo, 'rev-parse', '--verify', str(revision) + '^{commit}')
    if error:
        return None
    return output.decode('ascii').strip()


def git_blob(repo, revision, relpath):
    return git(repo, 'show', str(revision) + ':' + str(relpath))


def check_artifact(path, label):
    if path is None or not path.is_file():
        return result('INCOMPLETE', '%s is missing' % label)
    try:
        data = path.read_bytes()
        data.decode('utf-8')
    except (OSError, UnicodeError) as exc:
        return result('FAIL', '%s is unreadable: %s' % (label, exc))
    return result('PASS', '%s is readable' % label, {'bytes': len(data)})


def check_role_log(path, expected):
    checked = check_artifact(path, 'role log')
    if checked['status'] != 'PASS':
        return checked
    lines = path.read_text(encoding='utf-8').splitlines()
    headers = [HEADER_RE.match(line) for line in lines if line.startswith('role-bridge: start=')]
    trailers = [TRAILER_RE.match(line) for line in lines if line.startswith('role-bridge: end=')]
    if len(headers) != 1 or headers[0] is None:
        return result('FAIL', 'role log does not contain exactly one valid start header')
    header = headers[0]
    facts = dict(zip(('start', 'harness', 'model', 'effort', 'tools', 'role', 'cwd'),
                     header.groups()))
    if not trailers:
        return result('INCOMPLETE', 'role log has no trailer; dispatch was interrupted', facts)
    if len(trailers) != 1 or trailers[0] is None:
        return result('FAIL', 'role log does not contain exactly one valid end trailer', facts)
    trailer = trailers[0]
    facts.update(dict(zip(('end', 'exit', 'secs', 'result_bytes'), trailer.groups())))
    for key in ('harness', 'model', 'effort'):
        wanted = expected.get(key)
        if wanted is not None and facts[key] != str(wanted):
            return result('FAIL', 'role log %s=%s, expected %s' %
                          (key, facts[key], wanted), facts)
    role = expected.get('role')
    wanted_role = ROLE_LOG_NAMES.get(role, str(role).lower().replace('_', '-'))
    if role and facts['role'] != wanted_role:
        return result('FAIL', 'role log role=%s, expected %s' %
                      (facts['role'], wanted_role), facts)
    if facts['exit'] != '0':
        return result('FAIL', 'role dispatch exited %s' % facts['exit'], facts)
    if int(facts['result_bytes']) <= 0:
        return result('FAIL', 'role dispatch returned an empty result', facts)
    return result('PASS', 'role log has a matching successful header and trailer', facts)


def load_trace(path):
    checked = check_artifact(path, 'operation trace')
    if checked['status'] != 'PASS':
        return checked
    records = []
    try:
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if line.strip():
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ValueError('line %d is not an object' % number)
                records.append(item)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return result('FAIL', 'operation trace is malformed: %s' % exc)
    headers = [item for item in records if item.get('type') == 'trace-header']
    trailers = [item for item in records if item.get('type') == 'trace-trailer']
    dispatches = [item for item in records if item.get('type') == 'dispatch']
    if len(headers) != 1:
        return result('FAIL', 'operation trace needs exactly one header')
    if not trailers:
        return result('INCOMPLETE', 'operation trace has no trailer; batch was interrupted',
                      {'header': headers[0], 'dispatches': dispatches})
    if len(trailers) != 1:
        return result('FAIL', 'operation trace needs exactly one trailer')
    run_id = headers[0].get('run_id')
    if not run_id or any(item.get('run_id') != run_id for item in dispatches + trailers):
        return result('FAIL', 'operation trace run identity is inconsistent')
    sequences = [item.get('sequence') for item in dispatches]
    if sequences != list(range(1, len(dispatches) + 1)):
        return result('FAIL', 'operation trace dispatch sequence is not complete and contiguous')
    if trailers[0].get('dispatch_count') != len(dispatches):
        return result('FAIL', 'operation trace trailer count disagrees with dispatch records')
    if not dispatches:
        return result('INCOMPLETE',
                      'operation trace has no dispatch records; it cannot prove zero operations',
                      {'header': headers[0], 'dispatches': [], 'trailer': trailers[0]})
    role_for_operation = {'plan': 'PLANNER', 'refine': 'PLAN_REFINER',
                          'replan': 'REPLANNER', 'run': 'EXECUTOR'}
    for item in dispatches:
        operation = item.get('operation')
        if operation not in role_for_operation or item.get('role') != role_for_operation[operation]:
            return result('FAIL', 'operation trace contains an invalid operation/role pair')
    return result('PASS', 'operation trace has complete attributable boundaries',
                  {'header': headers[0], 'dispatches': dispatches, 'trailer': trailers[0]})


def merge_status(current, incoming):
    return incoming if STATUS_RANK[incoming] > STATUS_RANK[current] else current


def validate_manifest(manifest, manifest_dir):
    """Return derived PT verdicts and inspected facts for one evidence manifest."""
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        raise ValueError('manifest schema_version must be 1')
    fixture = manifest.get('fixture')
    expected = manifest.get('expected')
    evidence = manifest.get('evidence')
    if not all(isinstance(item, dict) for item in (fixture, expected, evidence)):
        raise ValueError('fixture, expected, and evidence must be JSON objects')
    base = Path(manifest_dir)
    code_repo = resolve_path(fixture.get('code_repo'), base)
    vault_repo = resolve_path(fixture.get('vault_repo'), base)
    root_rel = fixture.get('root')
    checks = {pt: [] for pt in PT_IDS}
    facts = {'fixture_kind': fixture.get('kind', 'unspecified'), 'stages': {},
             'roles': {}, 'traces': {}}

    def add(pt_ids, checked):
        for pt in pt_ids:
            checks[pt].append({'status': checked['status'], 'message': checked['message']})

    if code_repo is None or not code_repo.is_dir():
        add(('PT-03', 'PT-08', 'PT-10'), result('INCOMPLETE', 'code repository is missing'))
    if vault_repo is None or not vault_repo.is_dir():
        add(PT_IDS, result('INCOMPLETE', 'vault repository is missing'))
    initial = evidence.get('initial_publication', {})
    initial_ref = initial.get('commit') if isinstance(initial, dict) else None
    initial_commit = git_commit(vault_repo, initial_ref) if vault_repo and initial_ref else None
    if not initial_ref or not initial_commit:
        add(('PT-01', 'PT-02', 'PT-10', 'PT-11'),
            result('INCOMPLETE', 'initial publication commit is absent from the vault repository'))
    else:
        facts['initial_publication_commit'] = initial_commit
        artifacts = initial.get('artifacts')
        if not isinstance(artifacts, list) or not artifacts:
            add(('PT-01', 'PT-10'), result('INCOMPLETE', 'initial publication artifact set is absent'))
        else:
            required_initial = {root_rel, initial.get('tree_review')}
            required_initial.update(stage.get('path') for stage in expected.get('stages', [])
                                    if isinstance(stage, dict))
            omitted = sorted(str(item) for item in required_initial if item and item not in artifacts)
            if omitted:
                add(('PT-01',), result('FAIL',
                    'initial publication manifest omits required artifacts: ' + ', '.join(omitted)))
            for relpath in artifacts:
                blob, error = git_blob(vault_repo, initial_commit, relpath)
                add(('PT-01', 'PT-10'), result('INCOMPLETE' if error else 'PASS',
                    'publication artifact %s %s' %
                    (relpath, 'is missing' if error else 'exists in the publication commit')))
        root_blob, root_error = git_blob(vault_repo, initial_commit, root_rel)
        if root_error:
            add(('PT-01', 'PT-09', 'PT-10'), result('INCOMPLETE', 'published root is missing'))
        else:
            try:
                root_fields = markdown_fields(root_blob)
                mode = field(root_fields, 'Planning mode')
                generation = field(root_fields, 'Plan generation')
                if mode != 'upfront-v1' or generation != str(expected.get('root_generation')):
                    add(('PT-01', 'PT-10'), result('FAIL',
                        'published root mode/generation disagrees with the manifest identity'))
                else:
                    add(('PT-01', 'PT-10'), result('PASS',
                        'published root mode and generation match'))
            except (UnicodeError, ValueError) as exc:
                add(('PT-01', 'PT-10'), result('FAIL', 'published root is malformed: %s' % exc))
        active_graph = active_stage_map(vault_repo, initial_commit, root_rel)
        add(('PT-01', 'PT-02'), active_graph)
        if active_graph['status'] == 'PASS':
            expected_stage_map = {
                stage.get('id'): stage.get('path') for stage in expected.get('stages', [])
                if isinstance(stage, dict) and stage.get('id') and stage.get('path')}
            actual_stage_map = active_graph.get('facts', {}).get('stages', {})
            if actual_stage_map != expected_stage_map:
                add(('PT-01', 'PT-02', 'PT-04'), result('FAIL',
                    'published active Plan links disagree with expected stage identities'))
            else:
                add(('PT-01', 'PT-02'), result('PASS',
                    'published active Plan links match expected stage identities'))
        review_rel = initial.get('tree_review')
        review_blob, review_error = git_blob(vault_repo, initial_commit, review_rel) \
            if review_rel else (None, 'absent')
        if review_error:
            add(('PT-01', 'PT-02'), result('INCOMPLETE', 'whole-tree review is missing'))
        else:
            try:
                review_fields = markdown_fields(review_blob)
                review_ok = (field(review_fields, 'Outcome') == 'PASS' and
                             field(review_fields, 'Plan generation') ==
                             str(expected.get('root_generation')))
                add(('PT-01', 'PT-02'), result('PASS' if review_ok else 'FAIL',
                    'whole-tree review passes for the expected generation' if review_ok else
                    'whole-tree review outcome or generation is inconsistent'))
            except (UnicodeError, ValueError) as exc:
                add(('PT-01', 'PT-02'), result('FAIL',
                    'whole-tree review is malformed: %s' % exc))
        for label in ('confirmation', 'supermeta'):
            relpath = initial.get(label)
            blob, error = git_blob(vault_repo, initial_commit, relpath) if relpath else (None, 'absent')
            if error:
                add(('PT-01',), result('INCOMPLETE', '%s evidence is missing' % label))
                continue
            try:
                fields = markdown_fields(blob)
                expected_outcome = 'CONFIRMED' if label == 'confirmation' else 'PUBLISHED'
                coherent = field(fields, 'Outcome') == expected_outcome
                if label == 'supermeta':
                    coherent = coherent and field(fields, 'Root plan') == root_rel
                add(('PT-01',), result('PASS' if coherent else 'FAIL',
                    '%s evidence is coherent' % label if coherent else
                    '%s evidence is inconsistent' % label))
            except (UnicodeError, ValueError) as exc:
                add(('PT-01',), result('FAIL', '%s evidence is malformed: %s' % (label, exc)))
        bounded_review_rel = initial.get('bounded_detail_review')
        if not bounded_review_rel:
            add(('PT-05',), result('INCOMPLETE',
                'tracked bounded-detail/no-replan assessment is absent'))
        else:
            bounded_blob, bounded_error = git_blob(
                vault_repo, initial_commit, bounded_review_rel)
            if bounded_error:
                add(('PT-05',), result('INCOMPLETE',
                    'tracked bounded-detail/no-replan assessment is missing'))
            else:
                try:
                    bounded_fields = markdown_fields(bounded_blob)
                    bounded_ok = (
                        field(bounded_fields, 'Outcome') == 'PASS' and
                        field(bounded_fields, 'Scenario') == 'bounded-detail' and
                        field(bounded_fields, 'Replan dispatches') == '0')
                    add(('PT-05',), result('PASS' if bounded_ok else 'FAIL',
                        'bounded-detail/no-replan assessment passes' if bounded_ok else
                        'bounded-detail/no-replan assessment is contradictory'))
                except (UnicodeError, ValueError) as exc:
                    add(('PT-05',), result('FAIL',
                        'bounded-detail/no-replan assessment is malformed: %s' % exc))

    stages = expected.get('stages')
    if not isinstance(stages, list) or not stages:
        add(('PT-01', 'PT-02', 'PT-03', 'PT-04', 'PT-10', 'PT-11'),
            result('INCOMPLETE', 'expected stage graph is absent'))
        stages = []
    stage_ids = set()
    delivered_ids = set()
    dependencies = {}
    stage_by_id = {}
    for stage in stages:
        if not isinstance(stage, dict) or not isinstance(stage.get('id'), str):
            add(('PT-01', 'PT-02'), result('FAIL', 'stage entry is malformed'))
            continue
        stage_id = stage['id']
        if stage_id in stage_ids:
            add(('PT-01', 'PT-02'), result('FAIL', 'duplicate stage ID %s' % stage_id))
            continue
        stage_ids.add(stage_id)
        stage_by_id[stage_id] = stage
        stage_facts = {}
        facts['stages'][stage_id] = stage_facts
        prepared_commit = git_commit(vault_repo, stage.get('prepared_vault_commit')) \
            if vault_repo and stage.get('prepared_vault_commit') else None
        if not prepared_commit:
            add(('PT-03', 'PT-04'), result('INCOMPLETE',
                '%s historical prepared vault commit is missing' % stage_id))
            continue
        stage_blob, stage_error = git_blob(vault_repo, prepared_commit, stage.get('path'))
        prep_blob, prep_error = git_blob(vault_repo, prepared_commit, stage.get('preparation'))
        if stage_error or prep_error:
            add(('PT-03', 'PT-04'), result('INCOMPLETE',
                '%s historical plan or preparation receipt is missing' % stage_id))
            continue
        try:
            stage_fields = markdown_fields(stage_blob)
            stage_sections = markdown_sections(stage_blob)
            prep_fields = markdown_fields(prep_blob)
            actual_digest = hashlib.sha256(prepared_body(stage_blob)).hexdigest()
        except (UnicodeError, ValueError) as exc:
            add(('PT-02', 'PT-03', 'PT-04'), result('FAIL',
                '%s preparation evidence is malformed: %s' % (stage_id, exc)))
            continue
        stage_facts['prepared_digest'] = actual_digest
        stage_facts['prepared_vault_commit'] = prepared_commit
        revision = str(stage.get('revision'))
        preparation_rel = stage.get('preparation')
        required_preparation = {
            'Outcome': field(prep_fields, 'Outcome'),
            'Root plan': field(prep_fields, 'Root plan'),
            'Root generation': field(prep_fields, 'Root generation'),
            'Stage ID': field(prep_fields, 'Stage ID'),
            'Stage revision': field(prep_fields, 'Stage revision'),
            'Prepared plan SHA-256': field(prep_fields, 'Prepared plan SHA-256',
                                          'Plan digest', 'Prepared-plan digest'),
            'Code commit': field(prep_fields, 'Code commit'),
        }
        missing_preparation = sorted(name for name, value in required_preparation.items()
                                     if not value)
        if missing_preparation:
            add(('PT-03', 'PT-04'), result('INCOMPLETE',
                '%s preparation receipt is missing: %s' %
                (stage_id, ', '.join(missing_preparation))))
        stage_pointer = reference_path(field(stage_fields, 'Preparation'))
        if stage_pointer != preparation_rel:
            add(('PT-03', 'PT-04'), result('FAIL',
                '%s stage Preparation pointer is inconsistent' % stage_id))
        else:
            add(('PT-03', 'PT-04'), result('PASS',
                '%s stage resolves the checked preparation receipt' % stage_id))
        historic_root_blob, historic_root_error = git_blob(
            vault_repo, prepared_commit, root_rel)
        historic_generation = None
        if historic_root_error:
            add(('PT-03', 'PT-04'), result('INCOMPLETE',
                '%s historical root is missing from its preparation commit' % stage_id))
        else:
            try:
                historic_root_fields = markdown_fields(historic_root_blob)
                historic_generation = field(historic_root_fields, 'Plan generation')
            except (UnicodeError, ValueError) as exc:
                add(('PT-03', 'PT-04'), result('FAIL',
                    '%s historical root is malformed: %s' % (stage_id, exc)))
            if not historic_generation:
                add(('PT-03', 'PT-04'), result('INCOMPLETE',
                    '%s historical root generation is missing' % stage_id))
        if not missing_preparation:
            identity_ok = (
                field(stage_fields, 'Stage ID') == stage_id and
                field(stage_fields, 'Stage revision') == revision and
                required_preparation['Outcome'] == 'PREPARED' and
                reference_path(required_preparation['Root plan']) == root_rel and
                required_preparation['Stage ID'] == stage_id and
                required_preparation['Stage revision'] == revision)
            if historic_generation is not None:
                identity_ok = (identity_ok and
                               required_preparation['Root generation'] == historic_generation)
            if not identity_ok:
                add(('PT-03', 'PT-04'), result('FAIL',
                    '%s preparation authority or identity is inconsistent' % stage_id))
            else:
                add(('PT-03', 'PT-04'), result('PASS',
                    '%s preparation authority and identity match historical context' % stage_id))
            if code_repo is not None and code_repo.is_dir():
                prepared_code_commit = git_commit(
                    code_repo, required_preparation['Code commit'])
                if not prepared_code_commit:
                    add(('PT-03', 'PT-04'), result('FAIL',
                        '%s preparation Code commit does not exist' % stage_id))
                else:
                    stage_facts['prepared_code_commit'] = prepared_code_commit
                    add(('PT-03', 'PT-04'), result('PASS',
                        '%s preparation Code commit exists' % stage_id))
        receipt_digest = field(prep_fields, 'Prepared plan SHA-256', 'Plan digest',
                               'Prepared-plan digest')
        if receipt_digest is None:
            pass
        elif receipt_digest != actual_digest:
            add(('PT-03', 'PT-04'), result('FAIL',
                '%s preparation digest does not match historical exact bytes' % stage_id))
        else:
            add(('PT-03', 'PT-04'), result('PASS',
                '%s preparation digest matches historical exact bytes' % stage_id))
        required_contract_fields = ('Stage ID', 'Stage revision', 'Stage kind', 'Depends on')
        required_contract_sections = ('Consumes', 'Produces', 'Acceptance',
                                      'Verification scenarios')
        missing_contract = [name for name in required_contract_fields
                            if not field(stage_fields, name)]
        missing_contract.extend(name for name in required_contract_sections
                                if not contract_value(stage_fields, stage_sections, name))
        add(('PT-02',), result('FAIL' if missing_contract else 'PASS',
            '%s %s' % (stage_id, ('is missing contract fields: ' + ', '.join(missing_contract))
                        if missing_contract else 'has the required upfront contract fields')))
        stage_kind = field(stage_fields, 'Stage kind')
        if stage_kind and stage_kind not in ('implementation', 'discovery'):
            add(('PT-01', 'PT-02'), result('FAIL',
                '%s has invalid Stage kind %s' % (stage_id, stage_kind)))
        actual_dependencies = dependency_ids(field(stage_fields, 'Depends on'))
        expected_dependencies = stage.get('depends_on')
        if actual_dependencies is None:
            add(('PT-01', 'PT-02', 'PT-04'), result('FAIL',
                '%s actual dependency field is malformed' % stage_id))
            dependencies[stage_id] = []
        else:
            dependencies[stage_id] = actual_dependencies
            stage_facts['depends_on'] = actual_dependencies
            if not isinstance(expected_dependencies, list):
                add(('PT-01', 'PT-02', 'PT-04'), result('INCOMPLETE',
                    '%s expected dependency inventory is absent' % stage_id))
            elif actual_dependencies != expected_dependencies:
                add(('PT-01', 'PT-02', 'PT-04'), result('FAIL',
                    '%s actual dependencies disagree with the manifest' % stage_id))
            else:
                add(('PT-01', 'PT-02', 'PT-04'), result('PASS',
                    '%s actual dependencies match the manifest' % stage_id))
        code_commit = git_commit(code_repo, stage.get('code_commit')) if code_repo else None
        integration_commit = git_commit(code_repo, stage.get('integration_commit')) if code_repo else None
        if not code_commit or not integration_commit:
            add(('PT-04', 'PT-10'), result('INCOMPLETE',
                '%s code or integration commit is absent' % stage_id))
            continue
        ancestor_out, ancestor_error = git(code_repo, 'merge-base', '--is-ancestor',
                                            code_commit, integration_commit)
        del ancestor_out
        if ancestor_error:
            add(('PT-04', 'PT-10'), result('FAIL',
                '%s code commit is not integrated in the claimed commit' % stage_id))
            continue
        delivery_commit = git_commit(vault_repo, stage.get('delivery_vault_commit')) \
            if vault_repo and stage.get('delivery_vault_commit') else None
        if not delivery_commit:
            add(('PT-04', 'PT-10'), result('INCOMPLETE',
                '%s delivery vault commit is missing' % stage_id))
            continue
        delivery_blob, delivery_error = git_blob(vault_repo, delivery_commit, stage.get('delivery'))
        if delivery_error:
            add(('PT-04', 'PT-10'), result('INCOMPLETE',
                '%s delivery receipt is absent from its vault commit' % stage_id))
            continue
        add(('PT-04', 'PT-10'), result('PASS',
            '%s delivery receipt is tracked in its vault commit' % stage_id))
        try:
            delivery_fields = markdown_fields(delivery_blob)
        except (UnicodeError, ValueError) as exc:
            add(('PT-04', 'PT-10'), result('FAIL',
                '%s delivery receipt is malformed: %s' % (stage_id, exc)))
            continue
        required_delivery = {
            'Stage ID': field(delivery_fields, 'Stage ID'),
            'Stage revision': field(delivery_fields, 'Stage revision'),
            'Root generation': field(delivery_fields, 'Root generation'),
            'Preparation': field(delivery_fields, 'Preparation'),
            'Prepared plan SHA-256': field(delivery_fields, 'Prepared plan SHA-256',
                                          'Plan digest'),
            'Code commit': field(delivery_fields, 'Code commit'),
            'Integration commit': field(delivery_fields, 'Integration commit'),
            'Delivered': field(delivery_fields, 'Delivered'),
            'Consumable': field(delivery_fields, 'Consumable'),
        }
        missing_delivery = sorted(name for name, value in required_delivery.items() if not value)
        if missing_delivery:
            add(('PT-04', 'PT-10'), result('INCOMPLETE',
                '%s delivery receipt is missing: %s' %
                (stage_id, ', '.join(missing_delivery))))
        else:
            delivery_ok = (
                required_delivery['Stage ID'] == stage_id and
                required_delivery['Stage revision'] == revision and
                required_delivery['Root generation'] == historic_generation and
                reference_path(required_delivery['Preparation']) == preparation_rel and
                required_delivery['Prepared plan SHA-256'] == actual_digest and
                required_delivery['Code commit'] == code_commit and
                required_delivery['Integration commit'] == integration_commit and
                required_delivery['Delivered'].lower() == 'true' and
                required_delivery['Consumable'].lower() == 'true')
            if delivery_ok:
                delivered_ids.add(stage_id)
            add(('PT-04', 'PT-10'), result('PASS' if delivery_ok else 'FAIL',
                '%s delivery identity %s' %
                (stage_id, 'matches' if delivery_ok else 'is inconsistent')))

    for stage_id, deps in dependencies.items():
        if not isinstance(deps, list) or any(dep not in stage_ids for dep in deps):
            add(('PT-01', 'PT-04'), result('FAIL',
                '%s dependency list is malformed or references an unknown stage' % stage_id))
        elif stage_id in delivered_ids and not set(deps).issubset(delivered_ids):
            add(('PT-04',), result('FAIL',
                '%s was delivered before all declared dependencies' % stage_id))
    visiting, visited = set(), set()
    def cyclic(node):
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        found = any(cyclic(dep) for dep in dependencies.get(node, []) if dep in dependencies)
        visiting.remove(node)
        visited.add(node)
        return found
    if any(cyclic(node) for node in dependencies):
        add(('PT-01', 'PT-04'), result('FAIL', 'stage dependency graph contains a cycle'))
    elif dependencies:
        add(('PT-01', 'PT-04'), result('PASS', 'stage dependency graph is acyclic'))

    role_pins = expected.get('role_pins', {})
    logs = evidence.get('dispatch_logs', [])
    required_planning_roles = {'PLAN_REFINER', 'REPLANNER'}
    if isinstance(role_pins, dict):
        for missing_role in sorted(required_planning_roles - set(role_pins)):
            add(('PT-08',), result('INCOMPLETE',
                'required planning role %s is absent' % missing_role))
    if not isinstance(role_pins, dict) or not role_pins or not isinstance(logs, list) or not logs:
        add(('PT-03', 'PT-05', 'PT-08'), result('INCOMPLETE',
            'expected role pins or dispatch logs are absent'))
    else:
        seen_roles = set()
        seen_recipes = set()
        for item in logs:
            if not isinstance(item, dict) or item.get('role') not in role_pins:
                add(('PT-08',), result('FAIL', 'dispatch log entry has an unexpected role'))
                continue
            role = item['role']
            recipe = item.get('recipe')
            if recipe is None:
                add(('PT-08',), result('INCOMPLETE',
                    '%s dispatch recipe is absent' % role))
            elif recipe not in ('native', 'bridged'):
                add(('PT-08',), result('FAIL',
                    '%s dispatch recipe is invalid' % role))
            else:
                seen_recipes.add(recipe)
            checked = check_role_log(resolve_path(item.get('path'), base),
                                     dict(role_pins[role], role=role))
            facts['roles'][role] = checked.get('facts', {})
            add(('PT-08',), checked)
            if role == 'PLAN_REFINER':
                add(('PT-03',), checked)
            if role == 'REPLANNER':
                add(('PT-05', 'PT-06'), checked)
            if checked['status'] == 'PASS':
                seen_roles.add(role)
        for role in role_pins:
            if role not in seen_roles:
                add(('PT-08',), result('INCOMPLETE', '%s has no successful dispatch log' % role))
        for recipe in ('native', 'bridged'):
            if recipe not in seen_recipes:
                add(('PT-08',), result('INCOMPLETE',
                    'required %s planning dispatch recipe is absent' % recipe))

    package_roots = evidence.get('packages')
    package_skills = expected.get('package_skills', ['superstage', 'superrefine', 'superreplan'])
    if not isinstance(package_skills, list) or not package_skills:
        add(('PT-08',), result('INCOMPLETE', 'required package skill inventory is empty'))
    elif not isinstance(package_roots, dict):
        add(('PT-08',), result('INCOMPLETE', 'copied-package inventory is absent'))
    else:
        for harness in ('canonical', 'codex', 'cursor', 'pi'):
            root = resolve_path(package_roots.get(harness), base)
            if root is None or not root.is_dir():
                add(('PT-08',), result('INCOMPLETE', '%s package skills root is missing' % harness))
                continue
            for skill in package_skills:
                skill_file = root / skill / 'SKILL.md'
                if not skill_file.is_file():
                    add(('PT-08',), result('INCOMPLETE',
                        '%s package lacks %s' % (harness, skill)))
                elif skill_file.is_symlink():
                    add(('PT-08',), result('FAIL',
                        '%s package uses a source fallback for %s' % (harness, skill)))
                else:
                    add(('PT-08',), result('PASS',
                        '%s package contains copied %s' % (harness, skill)))

    traces = evidence.get('traces', {})
    if not isinstance(traces, dict):
        traces = {}
    batch_resume_decision = None
    for name in ('normal', 'contract_break', 'batch_resume', 'legacy'):
        trace_spec = traces.get(name)
        if isinstance(trace_spec, dict):
            path = resolve_path(trace_spec.get('path'), base)
            trace_vault = resolve_path(trace_spec.get('vault_repo'), base) or vault_repo
            trace_code = resolve_path(trace_spec.get('code_repo'), base) or code_repo
            trace_root = trace_spec.get('root', root_rel)
            trace_initial_ref = trace_spec.get('initial_publication_commit')
        else:
            path = resolve_path(trace_spec, base)
            trace_vault, trace_code, trace_root = vault_repo, code_repo, root_rel
            trace_initial_ref = initial_commit
        checked = load_trace(path) if path else result('INCOMPLETE', '%s trace is missing' % name)
        trace_facts = checked.get('facts', {})
        trace_facts['context'] = {
            'vault_repo': str(trace_vault) if trace_vault else None,
            'code_repo': str(trace_code) if trace_code else None,
            'root': trace_root,
        }
        facts['traces'][name] = trace_facts
        pt_map = {'normal': ('PT-01', 'PT-03', 'PT-04', 'PT-11'),
                  'contract_break': ('PT-05', 'PT-06', 'PT-11'),
                  'batch_resume': ('PT-07',), 'legacy': ('PT-09',)}
        add(pt_map[name], checked)
        if checked['status'] != 'PASS':
            continue
        dispatches = checked['facts']['dispatches']
        header = checked['facts']['header']
        trailer = checked['facts']['trailer']
        if header.get('root') and trace_root and header.get('root') != trace_root:
            add(pt_map[name], result('FAIL', '%s trace root disagrees with its run context' % name))
        trace_initial_ref = trace_initial_ref or header.get('initial_publication_commit')
        trace_initial = git_commit(trace_vault, trace_initial_ref) if trace_vault else None
        final_ref = trailer.get('final_vault_commit')
        final_commit = git_commit(trace_vault, final_ref) if trace_vault and final_ref else None
        if trace_initial_ref and not trace_initial:
            add(pt_map[name], result('INCOMPLETE',
                '%s trace initial publication commit is absent from its run vault' % name))
        if final_ref and not final_commit:
            add(pt_map[name], result('INCOMPLETE',
                '%s trace final vault commit is absent from its run vault' % name))
        if trace_initial and final_commit:
            _, final_error = git(trace_vault, 'merge-base', '--is-ancestor',
                                 trace_initial, final_commit)
            if final_error:
                add(pt_map[name], result('FAIL',
                    '%s trace final commit does not descend from its publication' % name))
        for item in dispatches:
            role = item.get('role')
            if role in role_pins:
                log_path = resolve_path(item.get('log'), base)
                role_checked = check_role_log(log_path, dict(role_pins[role], role=role))
                add(pt_map[name], result(role_checked['status'],
                    'trace role log: ' + role_checked['message']))
        if name == 'normal':
            for item in dispatches:
                before = git_commit(trace_vault, item.get('vault_commit_before')) \
                    if trace_vault else None
                if not before:
                    add(('PT-01', 'PT-11'), result('INCOMPLETE',
                        'normal trace dispatch lacks a resolvable vault baseline'))
                    continue
                _, error = git(trace_vault, 'merge-base', '--is-ancestor', trace_initial, before) \
                    if trace_initial else (None, 'missing initial publication')
                if error:
                    add(('PT-01', 'PT-11'), result('FAIL',
                        'normal dispatch predates or diverges from initial publication'))
                if item.get('operation') in ('plan', 'replan'):
                    add(('PT-11',), result('FAIL',
                        'normal trace contains post-publication structural planning'))
            for stage_id in delivered_ids:
                stage_dispatches = [item for item in dispatches
                                    if item.get('stage_id') == stage_id]
                stage_ops = {item.get('operation') for item in stage_dispatches}
                add(('PT-03', 'PT-11'), result(
                    'PASS' if {'refine', 'run'}.issubset(stage_ops) else 'INCOMPLETE',
                    '%s has attributable refinement and execution' % stage_id if
                    {'refine', 'run'}.issubset(stage_ops) else
                    '%s lacks attributable refinement or execution' % stage_id))
                refine_sequences = [item.get('sequence') for item in stage_dispatches
                                    if item.get('operation') == 'refine']
                run_items = [item for item in stage_dispatches
                             if item.get('operation') == 'run']
                if refine_sequences and run_items:
                    first_run = min(item.get('sequence') for item in run_items)
                    first_refine = min(refine_sequences)
                    if first_run < first_refine:
                        add(('PT-03', 'PT-04', 'PT-11'), result('FAIL',
                            '%s execution occurs before refinement' % stage_id))
                    else:
                        add(('PT-03', 'PT-04', 'PT-11'), result('PASS',
                            '%s refinement precedes execution' % stage_id))
                for run_item in run_items:
                    for provider_id in dependencies.get(stage_id, []):
                        provider_runs = [item.get('sequence') for item in dispatches
                                         if item.get('stage_id') == provider_id and
                                         item.get('operation') == 'run']
                        if not provider_runs:
                            add(('PT-04', 'PT-11'), result('INCOMPLETE',
                                '%s execution lacks provider run witness for %s' %
                                (stage_id, provider_id)))
                        elif min(provider_runs) >= run_item.get('sequence'):
                            add(('PT-04', 'PT-11'), result('FAIL',
                                '%s executes before provider %s' % (stage_id, provider_id)))
                        before = git_commit(trace_vault, run_item.get('vault_commit_before')) \
                            if trace_vault else None
                        provider_stage = stage_by_id.get(provider_id, {})
                        if not before:
                            add(('PT-04', 'PT-11'), result('INCOMPLETE',
                                '%s execution has no resolvable dependency snapshot' % stage_id))
                        else:
                            _, delivery_error = git_blob(
                                trace_vault, before, provider_stage.get('delivery'))
                            add(('PT-04', 'PT-11'), result(
                                'FAIL' if delivery_error else 'PASS',
                                '%s provider %s delivery is absent at execution entry' %
                                (stage_id, provider_id) if delivery_error else
                                '%s provider %s was delivered before execution' %
                                (stage_id, provider_id)))
        elif name == 'contract_break':
            replans = [item for item in dispatches if item.get('operation') == 'replan']
            add(('PT-05', 'PT-06', 'PT-11'), result('PASS' if len(replans) == 1 else 'FAIL',
                'contract-break trace has exactly one replanning dispatch' if len(replans) == 1
                else 'contract-break trace does not have exactly one replanning dispatch'))
        elif name == 'batch_resume':
            replans = [item for item in dispatches if item.get('operation') == 'replan']
            if not replans:
                add(('PT-07',), result('FAIL',
                    'batch-resume trace contains no replanning'))
            elif len(replans) < 2:
                add(('PT-07',), result('INCOMPLETE',
                    'batch-resume trace has no interruption and resumed attempt witness'))
            else:
                required = ('decision_id', 'attempt', 'outcome')
                if any(not all(item.get(key) is not None for key in required)
                       for item in replans):
                    add(('PT-07',), result('INCOMPLETE',
                        'batch-resume attempt identity is incomplete'))
                else:
                    decisions = {item.get('decision_id') for item in replans}
                    attempts = [item.get('attempt') for item in replans]
                    outcomes = [item.get('outcome') for item in replans]
                    if len(decisions) != 1 or attempts != list(range(1, len(replans) + 1)):
                        add(('PT-07',), result('FAIL',
                            'batch-resume attempts do not share one contiguous decision identity'))
                    elif outcomes[0] != 'interrupted' or outcomes[-1] != 'published':
                        add(('PT-07',), result('FAIL',
                            'batch-resume outcomes contradict interruption and publication'))
                    else:
                        receipt_rel = replans[0].get('interruption_receipt')
                        if not receipt_rel:
                            add(('PT-07',), result('INCOMPLETE',
                                'batch interruption receipt is absent'))
                        elif not final_commit:
                            add(('PT-07',), result('INCOMPLETE',
                                'batch interruption receipt has no final tracked snapshot'))
                        else:
                            receipt_blob, receipt_error = git_blob(
                                trace_vault, final_commit, receipt_rel)
                            if receipt_error:
                                add(('PT-07',), result('INCOMPLETE',
                                    'batch interruption receipt is not tracked'))
                            else:
                                try:
                                    receipt_fields = markdown_fields(receipt_blob)
                                    receipt_ok = (
                                        field(receipt_fields, 'Decision ID') in decisions and
                                        field(receipt_fields, 'Outcome') == 'interrupted')
                                    add(('PT-07',), result('PASS' if receipt_ok else 'FAIL',
                                        'batch interruption receipt matches resumed decision' if
                                        receipt_ok else
                                        'batch interruption receipt contradicts resumed decision'))
                                    if receipt_ok:
                                        batch_resume_decision = next(iter(decisions))
                                except (UnicodeError, ValueError) as exc:
                                    add(('PT-07',), result('FAIL',
                                        'batch interruption receipt is malformed: %s' % exc))
        elif name == 'legacy':
            add(('PT-09',), result('PASS' if any(item.get('operation') == 'plan'
                                                for item in dispatches) else 'FAIL',
                'legacy trace uses incremental planning' if any(item.get('operation') == 'plan'
                                                                 for item in dispatches)
                else 'legacy trace does not exercise incremental planning'))

    replan = evidence.get('replan')
    if not isinstance(replan, dict):
        add(('PT-05', 'PT-06', 'PT-07'), result('INCOMPLETE',
            'coherent replan publication evidence is absent'))
        add(('PT-06',), result('INCOMPLETE',
            'tracked semantic impact assessment is absent'))
    else:
        replan_repo = resolve_path(replan.get('vault_repo'), base) or vault_repo
        replan_root = replan.get('root', root_rel)
        facts['replan'] = {'vault_repo': str(replan_repo) if replan_repo else None,
                           'root': replan_root}
        publication = git_commit(replan_repo, replan.get('publication_commit')) \
            if replan_repo else None
        record_rel = replan.get('record')
        report_rel = replan.get('report')
        impact_review_rel = replan.get('impact_review')
        if not impact_review_rel:
            add(('PT-06',), result('INCOMPLETE',
                'tracked semantic impact assessment is absent'))
        if not publication:
            add(('PT-05', 'PT-06', 'PT-07'), result('INCOMPLETE',
                'replan publication commit is absent'))
        else:
            blobs = []
            errors = []
            extra_artifacts = replan.get('artifacts')
            if not isinstance(extra_artifacts, list) or not extra_artifacts:
                add(('PT-05', 'PT-06', 'PT-07'), result('INCOMPLETE',
                    'replan publication artifact inventory is empty'))
                extra_artifacts = []
            core_paths = [replan_root, record_rel, report_rel]
            if impact_review_rel:
                core_paths.append(impact_review_rel)
            for relpath in core_paths + extra_artifacts:
                blob, error = git_blob(replan_repo, publication, relpath)
                blobs.append((relpath, blob))
                if error:
                    errors.append(relpath)
            if errors:
                add(('PT-05', 'PT-06', 'PT-07'), result('INCOMPLETE',
                    'replan publication is missing: ' + ', '.join(str(item) for item in errors)))
            else:
                try:
                    record_fields = markdown_fields(dict(blobs)[record_rel])
                    report_fields = markdown_fields(dict(blobs)[report_rel])
                    root_fields = markdown_fields(dict(blobs)[replan_root])
                    revised_value = replan.get('revised_stages')
                    retained_value = replan.get('retained_stages')
                    if not isinstance(revised_value, list) or not revised_value:
                        add(('PT-05', 'PT-06'), result('INCOMPLETE',
                            'replan revised-stage inventory is empty'))
                    if not isinstance(retained_value, list):
                        add(('PT-06',), result('INCOMPLETE',
                            'replan retained-stage inventory is absent'))
                    revised = sorted(revised_value if isinstance(revised_value, list) else [])
                    retained = sorted(retained_value if isinstance(retained_value, list) else [])
                    actual_revised = sorted(filter(None, re.split(r'[\s,]+',
                        field(report_fields, 'Revised stages') or '')))
                    actual_retained = sorted(filter(None, re.split(r'[\s,]+',
                        field(report_fields, 'Retained stages') or '')))
                    coherent = (
                        field(record_fields, 'Decision ID') == replan.get('decision_id') and
                        field(record_fields, 'Resolution') == 'published' and
                        field(report_fields, 'Decision ID') == replan.get('decision_id') and
                        field(root_fields, 'Plan generation') == str(replan.get('published_generation')) and
                        field(root_fields, 'Active replan') == 'none' and
                        actual_revised == revised and actual_retained == retained)
                    add(('PT-05', 'PT-06', 'PT-07'), result('PASS' if coherent else 'FAIL',
                        'replan publication identities and dispositions match' if coherent else
                        'replan publication identities or dispositions conflict'))
                    if batch_resume_decision is not None:
                        add(('PT-07',), result(
                            'PASS' if batch_resume_decision == replan.get('decision_id') else 'FAIL',
                            'batch recovery and publication decision identities match' if
                            batch_resume_decision == replan.get('decision_id') else
                            'batch recovery and publication decision identities conflict'))
                    if impact_review_rel:
                        impact_fields = markdown_fields(dict(blobs)[impact_review_rel])
                        impact_ok = (
                            field(impact_fields, 'Outcome') == 'PASS' and
                            field(impact_fields, 'Decision ID') == replan.get('decision_id') and
                            sorted(filter(None, re.split(r'[\s,]+',
                                field(impact_fields, 'Revised stages') or ''))) == revised and
                            sorted(filter(None, re.split(r'[\s,]+',
                                field(impact_fields, 'Retained stages') or ''))) == retained)
                        add(('PT-06',), result('PASS' if impact_ok else 'FAIL',
                            'semantic impact assessment matches publication' if impact_ok else
                            'semantic impact assessment contradicts publication'))
                except (UnicodeError, ValueError) as exc:
                    add(('PT-05', 'PT-06', 'PT-07'), result('FAIL',
                        'replan publication is malformed: %s' % exc))

    legacy = evidence.get('legacy')
    if not isinstance(legacy, dict):
        add(('PT-09',), result('INCOMPLETE', 'legacy root evidence is absent'))
    else:
        legacy_repo = resolve_path(legacy.get('vault_repo'), base)
        legacy_commit = git_commit(legacy_repo, legacy.get('commit')) if legacy_repo else None
        blob, error = git_blob(legacy_repo, legacy_commit, legacy.get('root')) \
            if legacy_commit else (None, 'missing')
        if error:
            add(('PT-09',), result('INCOMPLETE', 'legacy root snapshot is missing'))
        else:
            try:
                has_marker = field(markdown_fields(blob), 'Planning mode') is not None
                add(('PT-09',), result('FAIL' if has_marker else 'PASS',
                    'legacy root unexpectedly has a mode marker' if has_marker else
                    'legacy root remains unmarked'))
            except (UnicodeError, ValueError) as exc:
                add(('PT-09',), result('FAIL', 'legacy root is malformed: %s' % exc))

    publications = evidence.get('publications')
    if not isinstance(publications, dict) or not isinstance(publications.get('external'), dict):
        add(('PT-10',), result('INCOMPLETE', 'external-vault publication evidence is absent'))
    else:
        external = publications['external']
        repo = resolve_path(external.get('repo'), base)
        commit = git_commit(repo, external.get('commit')) if repo else None
        missing = []
        artifacts = external.get('artifacts')
        if not isinstance(artifacts, list) or not artifacts:
            add(('PT-10',), result('INCOMPLETE',
                'external publication artifact inventory is empty'))
            artifacts = []
        if not commit:
            missing.append('commit')
        else:
            for relpath in artifacts:
                _, error = git_blob(repo, commit, relpath)
                if error:
                    missing.append(str(relpath))
        add(('PT-10',), result('INCOMPLETE' if missing else 'PASS',
            'external publication is missing ' + ', '.join(missing) if missing else
            'external publication commit contains every named artifact'))

    if fixture.get('kind') != 'live':
        for pt in PT_IDS:
            add((pt,), result('INCOMPLETE',
                'fixture kind %s is synthetic/offline and cannot establish live acceptance' %
                fixture.get('kind', 'unspecified')))

    requirements = {}
    for pt in PT_IDS:
        verdict = 'PASS'
        if not checks[pt]:
            checks[pt].append({'status': 'INCOMPLETE', 'message': 'no evidence checks ran'})
        for checked in checks[pt]:
            verdict = merge_status(verdict, checked['status'])
        requirements[pt] = {'verdict': verdict, 'evidence': checks[pt]}
    summary = {status: sum(1 for item in requirements.values()
                           if item['verdict'] == status)
               for status in ('PASS', 'FAIL', 'INCOMPLETE')}
    return {'schema_version': 1, 'fixture_kind': fixture.get('kind', 'unspecified'),
            'requirements': requirements, 'summary': summary, 'facts': facts}


class EvidenceValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.code = self.base / 'code'
        self.vault = self.base / 'vault'
        self.code.mkdir()
        self.vault.mkdir()
        for repo in (self.code, self.vault):
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            subprocess.run(['git', '-C', str(repo), 'config', 'user.email',
                            'fixture@example.invalid'], check=True)
            subprocess.run(['git', '-C', str(repo), 'config', 'user.name',
                            'Offline Fixture'], check=True)
        (self.code / 'product.txt').write_text('delivered\n', encoding='utf-8')
        self.code_commit = self.commit(self.code, 'code delivery')
        self.stage_rel = 'goal/plans/s01.md'
        stage = (b'# Stage one\r\n**Stage ID:** S01\r\n**Stage revision:** 1\r\n'
                 b'**Stage kind:** implementation\r\n**Depends on:** none\r\n'
                 b'**Preparation:** [[goal/reports/prep-s01.md]]\r\n'
                 b'### Consumes\r\nnone\r\n### Produces\r\n- C-ONE@1: output\r\n'
                 b'### Acceptance\r\nA-ONE: accepted\r\n'
                 b'### Verification scenarios\r\nV-ONE: observe output\r\n')
        self.stage_bytes = stage
        self.write_bytes(self.vault / self.stage_rel, stage)
        expected_body = stage.replace(
            b'**Preparation:** [[goal/reports/prep-s01.md]]\r\n', b'')
        digest = hashlib.sha256(expected_body).hexdigest()
        prep_rel = 'goal/reports/prep-s01.md'
        self.write_text(self.vault / prep_rel,
                        '**Outcome:** PREPARED\n**Root plan:** goal/root.md\n'
                        '**Root generation:** 1\n'
                        '**Stage ID:** S01\n**Stage revision:** 1\n'
                        '**Prepared plan SHA-256:** %s\n'
                        '**Code commit:** %s\n' % (digest, self.code_commit))
        delivery_rel = 'goal/reports/delivery-s01.md'
        self.write_text(self.vault / delivery_rel,
                        '**Stage ID:** S01\n**Stage revision:** 1\n'
                        '**Root generation:** 1\n**Preparation:** %s\n'
                        '**Prepared plan SHA-256:** %s\n'
                        '**Code commit:** %s\n**Integration commit:** %s\n'
                        '**Delivered:** true\n**Consumable:** true\n' %
                        (prep_rel, digest, self.code_commit, self.code_commit))
        self.write_text(self.vault / 'goal/root.md',
                        '**Planning mode:** upfront-v1\n**Plan generation:** 1\n'
                        '**Active replan:** none\n**Tree review:** [[goal/reports/tree-review.md]]\n\n'
                        '## Progress Report\n\n| # | Plan | Status |\n'
                        '|---|---|---|\n| 1 | [[goal/plans/s01.md]] | READY |\n')
        self.write_text(self.vault / 'goal/reports/tree-review.md',
                        '**Outcome:** PASS\n**Plan generation:** 1\n')
        self.write_text(self.vault / 'goal/reports/confirmation.md',
                        '**Outcome:** CONFIRMED\n**Plan generation:** 1\n')
        self.write_text(self.vault / 'goal/reports/supermeta.md',
                        '**Outcome:** PUBLISHED\n**Root plan:** goal/root.md\n')
        self.initial_commit = self.commit(self.vault, 'initial publication')
        # A later closeout annotation must not change the historical digest basis.
        with (self.vault / self.stage_rel).open('ab') as handle:
            handle.write(b'**Closeout:** [[goal/reports/delivery-s01.md]]\r\n')
        self.final_vault_commit = self.commit(self.vault, 'closeout annotation')
        self.refiner_log = self.base / 'refiner.log'
        self.write_text(
            self.refiner_log,
            'role-bridge: start=20260916T120000Z harness=codex model=gpt-5.6-terra '
            'effort=medium tools=planner role=plan-refiner cwd=%s\n'
            'role-bridge: end=20260916T120002Z exit=0 secs=2 result_bytes=42\n' % self.code)
        self.trace = self.base / 'normal.jsonl'
        events = [
            {'type': 'trace-header', 'run_id': 'normal-1', 'scenario': 'normal',
             'root': 'goal/root.md', 'initial_publication_commit': self.initial_commit},
            {'type': 'dispatch', 'run_id': 'normal-1', 'sequence': 1,
             'operation': 'refine', 'role': 'PLAN_REFINER', 'stage_id': 'S01',
             'vault_commit_before': self.initial_commit,
             'log': str(self.refiner_log)},
            {'type': 'dispatch', 'run_id': 'normal-1', 'sequence': 2,
             'operation': 'run', 'role': 'EXECUTOR', 'stage_id': 'S01',
             'vault_commit_before': self.initial_commit},
            {'type': 'trace-trailer', 'run_id': 'normal-1', 'dispatch_count': 2,
             'final_vault_commit': self.final_vault_commit, 'outcome': 'complete'},
        ]
        self.trace.write_text(''.join(json.dumps(item) + '\n' for item in events),
                              encoding='utf-8')

    def tearDown(self):
        self.tempdir.cleanup()

    @staticmethod
    def write_text(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8')

    @staticmethod
    def write_bytes(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)

    @staticmethod
    def commit(repo, message):
        subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(repo), 'commit', '-q', '-m', message], check=True)
        return subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], check=True,
                              text=True, stdout=subprocess.PIPE).stdout.strip()

    def manifest(self):
        return {
            'schema_version': 1,
            'fixture': {'kind': 'synthetic-offline', 'code_repo': str(self.code),
                        'vault_repo': str(self.vault), 'root': 'goal/root.md'},
            'expected': {
                'root_generation': 1,
                'stages': [{'id': 'S01', 'revision': 1, 'path': self.stage_rel,
                            'depends_on': [], 'preparation': 'goal/reports/prep-s01.md',
                            'prepared_vault_commit': self.initial_commit,
                            'delivery': 'goal/reports/delivery-s01.md',
                            'delivery_vault_commit': self.final_vault_commit,
                            'code_commit': self.code_commit,
                            'integration_commit': self.code_commit}],
                'role_pins': {'PLAN_REFINER': {'harness': 'codex',
                                               'model': 'gpt-5.6-terra',
                                               'effort': 'medium'}},
            },
            'evidence': {
                'initial_publication': {
                    'commit': self.initial_commit,
                    'artifacts': ['goal/root.md', self.stage_rel,
                                  'goal/reports/tree-review.md'],
                    'tree_review': 'goal/reports/tree-review.md',
                    'confirmation': 'goal/reports/confirmation.md',
                    'supermeta': 'goal/reports/supermeta.md'},
                'dispatch_logs': [{'role': 'PLAN_REFINER', 'recipe': 'native',
                                   'path': str(self.refiner_log)}],
                'traces': {'normal': str(self.trace)},
            },
            'claimed_results': {pt: 'PASS' for pt in PT_IDS},
        }

    def verdict(self, manifest, pt):
        return validate_manifest(manifest, self.base)['requirements'][pt]['verdict']

    def test_historical_digest_uses_exact_crlf_blob_not_annotated_worktree(self):
        report = validate_manifest(self.manifest(), self.base)
        self.assertEqual(report['requirements']['PT-03']['verdict'], 'INCOMPLETE')
        self.assertFalse(any(item['status'] == 'FAIL'
                             for item in report['requirements']['PT-03']['evidence']))
        current = (self.vault / self.stage_rel).read_bytes()
        self.assertNotEqual(hashlib.sha256(prepared_body(current)).hexdigest(),
                            report['facts']['stages']['S01']['prepared_digest'])

    def test_exact_digest_removes_only_pointer_and_preserves_crlf(self):
        data = b'A\r\n**Preparation:** none\r\nB\r\n'
        self.assertEqual(prepared_body(data), b'A\r\nB\r\n')

    def test_coherent_role_log_passes_lower_level_check(self):
        checked = check_role_log(self.refiner_log, {
            'role': 'PLAN_REFINER', 'harness': 'codex',
            'model': 'gpt-5.6-terra', 'effort': 'medium'})
        self.assertEqual(checked['status'], 'PASS')

    def test_complete_trace_passes_lower_level_check(self):
        self.assertEqual(load_trace(self.trace)['status'], 'PASS')

    def test_corrupted_stage_revision_fails_identity(self):
        manifest = self.manifest()
        manifest['expected']['stages'][0]['revision'] = 2
        self.assertEqual(self.verdict(manifest, 'PT-03'), 'FAIL')

    def test_wrong_role_log_pin_fails_role_evidence(self):
        self.write_text(self.refiner_log, self.refiner_log.read_text().replace(
            'model=gpt-5.6-terra', 'model=gpt-5.6-sol'))
        self.assertEqual(self.verdict(self.manifest(), 'PT-08'), 'FAIL')

    def test_missing_role_log_trailer_is_incomplete_not_pass(self):
        first = self.refiner_log.read_text().splitlines()[0] + '\n'
        self.write_text(self.refiner_log, first)
        self.assertEqual(self.verdict(self.manifest(), 'PT-08'), 'INCOMPLETE')

    def test_missing_integration_object_is_incomplete(self):
        manifest = self.manifest()
        manifest['expected']['stages'][0]['integration_commit'] = '0' * 40
        self.assertEqual(self.verdict(manifest, 'PT-10'), 'INCOMPLETE')

    def test_interrupted_replay_trace_is_incomplete(self):
        lines = self.trace.read_text().splitlines()
        self.trace.write_text('\n'.join(lines[:-1]) + '\n', encoding='utf-8')
        self.assertEqual(self.verdict(self.manifest(), 'PT-07'), 'INCOMPLETE')

    def test_fake_publication_marker_without_stage_is_not_pass(self):
        manifest = self.manifest()
        manifest['evidence']['initial_publication']['commit'] = self.final_vault_commit
        manifest['evidence']['initial_publication']['artifacts'].append('goal/plans/missing.md')
        self.assertNotEqual(self.verdict(manifest, 'PT-01'), 'PASS')

    def test_manifest_pass_booleans_cannot_override_missing_evidence(self):
        manifest = self.manifest()
        manifest['evidence']['dispatch_logs'] = []
        self.assertEqual(self.verdict(manifest, 'PT-08'), 'INCOMPLETE')

    def test_synthetic_fixture_never_reports_pt_pass(self):
        report = validate_manifest(self.manifest(), self.base)
        self.assertEqual(report['summary']['PASS'], 0)

    def test_delivery_requires_a_tracked_vault_commit(self):
        manifest = self.manifest()
        del manifest['expected']['stages'][0]['delivery_vault_commit']
        report = validate_manifest(manifest, self.base)
        self.assertTrue(any('delivery vault commit is missing' in item['message']
                            for item in report['requirements']['PT-10']['evidence']))

    def test_present_tree_review_with_nonpass_outcome_fails(self):
        self.write_text(self.vault / 'goal/reports/tree-review.md',
                        '**Outcome:** FAIL\n**Plan generation:** 1\n')
        bad_commit = self.commit(self.vault, 'bad review')
        manifest = self.manifest()
        manifest['evidence']['initial_publication']['commit'] = bad_commit
        self.assertEqual(self.verdict(manifest, 'PT-01'), 'FAIL')

    def test_trace_refinement_log_must_exist(self):
        records = [json.loads(line) for line in self.trace.read_text().splitlines()]
        records[1]['log'] = str(self.base / 'missing-refiner.log')
        self.trace.write_text(''.join(json.dumps(item) + '\n' for item in records),
                              encoding='utf-8')
        report = validate_manifest(self.manifest(), self.base)
        self.assertTrue(any('trace role log' in item['message']
                            for item in report['requirements']['PT-03']['evidence']))

    def preparation_manifest(self, replacement):
        self.write_bytes(self.vault / self.stage_rel, self.stage_bytes)
        prep = (self.vault / 'goal/reports/prep-s01.md').read_text(encoding='utf-8')
        self.write_text(self.vault / 'goal/reports/prep-s01.md', replacement(prep))
        commit = self.commit(self.vault, 'corrupt preparation receipt')
        manifest = self.manifest()
        manifest['expected']['stages'][0]['prepared_vault_commit'] = commit
        manifest['expected']['stages'][0]['delivery_vault_commit'] = commit
        return manifest

    def commit_stage_bytes(self, stage_bytes, message='replace stage contract'):
        self.write_bytes(self.vault / self.stage_rel, stage_bytes)
        digest = hashlib.sha256(prepared_body(stage_bytes)).hexdigest()
        for relpath in ('goal/reports/prep-s01.md', 'goal/reports/delivery-s01.md'):
            path = self.vault / relpath
            value = re.sub(r'(\*\*Prepared plan SHA-256:\*\* )[0-9a-f]+',
                           r'\g<1>' + digest, path.read_text(encoding='utf-8'))
            self.write_text(path, value)
        return self.commit(self.vault, message)

    def canonical_stage_bytes(self, depends='none'):
        return (b'# Stage one\r\n**Stage ID:** S01\r\n'
                b'**Stage revision:** 1\r\n**Stage kind:** implementation\r\n'
                + ('**Depends on:** %s\r\n' % depends).encode('ascii') +
                b'**Preparation:** [[goal/reports/prep-s01.md]]\r\n'
                b'### Consumes\r\nnone\r\n### Produces\r\n- C-ONE@1: output\r\n'
                b'### Acceptance\r\nA-ONE: accepted\r\n'
                b'### Verification scenarios\r\nV-ONE: observe output\r\n')

    def trace_records(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()]

    def write_trace_records(self, records):
        self.trace.write_text(''.join(json.dumps(item) + '\n' for item in records),
                              encoding='utf-8')

    def test_canonical_section_stage_contract_is_accepted(self):
        commit = self.commit_stage_bytes(self.canonical_stage_bytes())
        manifest = self.manifest()
        stage = manifest['expected']['stages'][0]
        stage['prepared_vault_commit'] = commit
        stage['delivery_vault_commit'] = commit
        report = validate_manifest(manifest, self.base)
        self.assertFalse(any(item['status'] == 'FAIL'
                             for item in report['requirements']['PT-02']['evidence']))

    def test_missing_canonical_contract_section_fails_pt02(self):
        stage_bytes = self.canonical_stage_bytes().replace(
            b'### Verification scenarios\r\nV-ONE: observe output\r\n', b'')
        commit = self.commit_stage_bytes(stage_bytes)
        manifest = self.manifest()
        manifest['expected']['stages'][0]['prepared_vault_commit'] = commit
        self.assertEqual(self.verdict(manifest, 'PT-02'), 'FAIL')

    def test_missing_stage_kind_fails_pt02(self):
        stage_bytes = self.canonical_stage_bytes().replace(
            b'**Stage kind:** implementation\r\n', b'')
        commit = self.commit_stage_bytes(stage_bytes)
        manifest = self.manifest()
        manifest['expected']['stages'][0]['prepared_vault_commit'] = commit
        self.assertEqual(self.verdict(manifest, 'PT-02'), 'FAIL')

    def test_actual_unknown_dependency_fails_graph(self):
        commit = self.commit_stage_bytes(self.canonical_stage_bytes('S999'))
        manifest = self.manifest()
        stage = manifest['expected']['stages'][0]
        stage['prepared_vault_commit'] = commit
        stage['delivery_vault_commit'] = commit
        self.assertEqual(self.verdict(manifest, 'PT-01'), 'FAIL')
        self.assertEqual(self.verdict(manifest, 'PT-04'), 'FAIL')

    def test_missing_root_active_plan_link_is_incomplete(self):
        root = self.vault / 'goal/root.md'
        self.write_text(root, re.sub(r'^\| 1 \|.*\n', '',
                                     root.read_text(encoding='utf-8'),
                                     flags=re.MULTILINE))
        commit = self.commit(self.vault, 'remove active Plan row')
        manifest = self.manifest()
        manifest['evidence']['initial_publication']['commit'] = commit
        report = validate_manifest(manifest, self.base)
        evidence = report['requirements']['PT-01']['evidence']
        self.assertTrue(any(item['status'] == 'INCOMPLETE' and
                            'active Plan links' in item['message'] for item in evidence))

    def test_execution_before_refinement_fails(self):
        records = self.trace_records()
        records[1], records[2] = records[2], records[1]
        records[1]['sequence'], records[2]['sequence'] = 1, 2
        self.write_trace_records(records)
        report = validate_manifest(self.manifest(), self.base)
        for pt in ('PT-03', 'PT-04'):
            self.assertTrue(any(item['status'] == 'FAIL' and
                                'before refinement' in item['message']
                                for item in report['requirements'][pt]['evidence']))

    def test_single_uninterrupted_batch_is_incomplete(self):
        records = [
            {'type': 'trace-header', 'run_id': 'batch-1', 'scenario': 'batch_resume',
             'root': 'goal/root.md', 'initial_publication_commit': self.initial_commit},
            {'type': 'dispatch', 'run_id': 'batch-1', 'sequence': 1,
             'operation': 'replan', 'role': 'REPLANNER', 'decision_id': 'D1',
             'attempt': 1, 'outcome': 'published',
             'vault_commit_before': self.initial_commit},
            {'type': 'trace-trailer', 'run_id': 'batch-1', 'dispatch_count': 1,
             'final_vault_commit': self.final_vault_commit, 'outcome': 'complete'},
        ]
        batch = self.base / 'batch.jsonl'
        batch.write_text(''.join(json.dumps(item) + '\n' for item in records), encoding='utf-8')
        manifest = self.manifest()
        manifest['evidence']['traces']['batch_resume'] = str(batch)
        report = validate_manifest(manifest, self.base)
        self.assertTrue(any(item['status'] == 'INCOMPLETE' and 'interruption' in item['message']
                            for item in report['requirements']['PT-07']['evidence']))

    def test_missing_required_planning_role_is_incomplete(self):
        report = validate_manifest(self.manifest(), self.base)
        self.assertTrue(any(item['status'] == 'INCOMPLETE' and 'REPLANNER' in item['message']
                            for item in report['requirements']['PT-08']['evidence']))

    def test_missing_native_or_bridged_recipe_is_incomplete(self):
        replanner_log = self.base / 'replanner.log'
        self.write_text(
            replanner_log,
            'role-bridge: start=20260916T120000Z harness=codex model=gpt-5.6-terra '
            'effort=medium tools=planner role=replanner cwd=%s\n'
            'role-bridge: end=20260916T120002Z exit=0 secs=2 result_bytes=42\n' % self.code)
        manifest = self.manifest()
        manifest['expected']['role_pins']['REPLANNER'] = {
            'harness': 'codex', 'model': 'gpt-5.6-terra', 'effort': 'medium'}
        manifest['evidence']['dispatch_logs'].append(
            {'role': 'REPLANNER', 'path': str(replanner_log)})
        report = validate_manifest(manifest, self.base)
        self.assertTrue(any(item['status'] == 'INCOMPLETE' and 'recipe' in item['message']
                            for item in report['requirements']['PT-08']['evidence']))

    def two_stage_manifest(self, consumer_first=False):
        self.write_bytes(self.vault / self.stage_rel, self.stage_bytes)
        stage_one_delivery = (self.vault / 'goal/reports/delivery-s01.md').read_text(
            encoding='utf-8')
        (self.vault / 'goal/reports/delivery-s01.md').unlink()
        stage_two_rel = 'goal/plans/s02.md'
        stage_two = (b'# Stage two\n**Stage ID:** S02\n**Stage revision:** 1\n'
                     b'**Stage kind:** implementation\n**Depends on:** S01\n'
                     b'**Preparation:** [[goal/reports/prep-s02.md]]\n'
                     b'### Consumes\n- C-ONE@1 from S01: output\n'
                     b'### Produces\n- C-TWO@1: result\n'
                     b'### Acceptance\nA-TWO: accepted\n'
                     b'### Verification scenarios\nV-TWO: observe result\n')
        self.write_bytes(self.vault / stage_two_rel, stage_two)
        digest_two = hashlib.sha256(prepared_body(stage_two)).hexdigest()
        self.write_text(self.vault / 'goal/reports/prep-s02.md',
                        '**Outcome:** PREPARED\n**Root plan:** goal/root.md\n'
                        '**Root generation:** 1\n**Stage ID:** S02\n'
                        '**Stage revision:** 1\n**Prepared plan SHA-256:** %s\n'
                        '**Code commit:** %s\n' % (digest_two, self.code_commit))
        root = self.vault / 'goal/root.md'
        self.write_text(root, root.read_text(encoding='utf-8') +
                        '| 2 | [[goal/plans/s02.md]] | READY |\n')
        prepared = self.commit(self.vault, 'publish canonical two-stage graph')
        self.write_text(self.vault / 'goal/reports/delivery-s01.md', stage_one_delivery)
        provider_delivered = self.commit(self.vault, 'deliver provider')
        self.write_text(self.vault / 'goal/reports/delivery-s02.md',
                        '**Stage ID:** S02\n**Stage revision:** 1\n'
                        '**Root generation:** 1\n'
                        '**Preparation:** goal/reports/prep-s02.md\n'
                        '**Prepared plan SHA-256:** %s\n**Code commit:** %s\n'
                        '**Integration commit:** %s\n**Delivered:** true\n'
                        '**Consumable:** true\n' %
                        (digest_two, self.code_commit, self.code_commit))
        all_delivered = self.commit(self.vault, 'deliver consumer')
        manifest = self.manifest()
        manifest['evidence']['initial_publication']['commit'] = prepared
        manifest['evidence']['initial_publication']['artifacts'].append(stage_two_rel)
        stage_one = manifest['expected']['stages'][0]
        stage_one['prepared_vault_commit'] = prepared
        stage_one['delivery_vault_commit'] = provider_delivered
        stage_two_manifest = {
            'id': 'S02', 'revision': 1, 'path': stage_two_rel,
            'depends_on': ['S01'], 'preparation': 'goal/reports/prep-s02.md',
            'prepared_vault_commit': prepared,
            'delivery': 'goal/reports/delivery-s02.md',
            'delivery_vault_commit': all_delivered,
            'code_commit': self.code_commit, 'integration_commit': self.code_commit,
        }
        manifest['expected']['stages'].append(stage_two_manifest)
        ordered = [
            ('refine', 'PLAN_REFINER', 'S01', prepared),
            ('run', 'EXECUTOR', 'S01', prepared),
            ('refine', 'PLAN_REFINER', 'S02', provider_delivered),
            ('run', 'EXECUTOR', 'S02', provider_delivered),
        ]
        if consumer_first:
            ordered = [ordered[2], ordered[3], ordered[0], ordered[1]]
            ordered[0] = (ordered[0][0], ordered[0][1], ordered[0][2], prepared)
            ordered[1] = (ordered[1][0], ordered[1][1], ordered[1][2], prepared)
        records = [{'type': 'trace-header', 'run_id': 'normal-two', 'scenario': 'normal',
                    'root': 'goal/root.md', 'initial_publication_commit': prepared}]
        for sequence, (operation, role, stage_id, before) in enumerate(ordered, 1):
            item = {'type': 'dispatch', 'run_id': 'normal-two', 'sequence': sequence,
                    'operation': operation, 'role': role, 'stage_id': stage_id,
                    'vault_commit_before': before}
            if role == 'PLAN_REFINER':
                item['log'] = str(self.refiner_log)
            records.append(item)
        records.append({'type': 'trace-trailer', 'run_id': 'normal-two',
                        'dispatch_count': 4, 'final_vault_commit': all_delivered,
                        'outcome': 'complete'})
        self.write_trace_records(records)
        return manifest

    def test_canonical_two_stage_provider_order_has_no_ordering_failure(self):
        report = validate_manifest(self.two_stage_manifest(), self.base)
        for pt in ('PT-04', 'PT-11'):
            self.assertFalse(any(item['status'] == 'FAIL' and
                                 ('before provider' in item['message'] or
                                  'delivery is absent' in item['message'])
                                 for item in report['requirements'][pt]['evidence']))

    def test_consumer_before_provider_fails_order_and_snapshot(self):
        report = validate_manifest(self.two_stage_manifest(consumer_first=True), self.base)
        evidence = report['requirements']['PT-04']['evidence']
        self.assertTrue(any(item['status'] == 'FAIL' and
                            ('before provider' in item['message'] or
                             'delivery is absent' in item['message']) for item in evidence))

    def batch_resume_manifest(self, second_decision='D1'):
        receipt_rel = 'goal/reports/interruption-D1.md'
        self.write_text(self.vault / receipt_rel,
                        '**Decision ID:** D1\n**Outcome:** interrupted\n')
        final_commit = self.commit(self.vault, 'record interrupted batch')
        records = [
            {'type': 'trace-header', 'run_id': 'batch-2', 'scenario': 'batch_resume',
             'root': 'goal/root.md', 'initial_publication_commit': self.initial_commit},
            {'type': 'dispatch', 'run_id': 'batch-2', 'sequence': 1,
             'operation': 'replan', 'role': 'REPLANNER', 'decision_id': 'D1',
             'attempt': 1, 'outcome': 'interrupted',
             'interruption_receipt': receipt_rel,
             'vault_commit_before': self.initial_commit},
            {'type': 'dispatch', 'run_id': 'batch-2', 'sequence': 2,
             'operation': 'replan', 'role': 'REPLANNER', 'decision_id': second_decision,
             'attempt': 2, 'outcome': 'published',
             'vault_commit_before': self.initial_commit},
            {'type': 'trace-trailer', 'run_id': 'batch-2', 'dispatch_count': 2,
             'final_vault_commit': final_commit, 'outcome': 'complete'},
        ]
        batch = self.base / 'batch-resume.jsonl'
        batch.write_text(''.join(json.dumps(item) + '\n' for item in records), encoding='utf-8')
        manifest = self.manifest()
        manifest['evidence']['traces']['batch_resume'] = str(batch)
        return manifest

    def test_same_decision_interruption_and_resume_witness_is_coherent(self):
        report = validate_manifest(self.batch_resume_manifest(), self.base)
        self.assertTrue(any(item['status'] == 'PASS' and
                            'interruption receipt matches' in item['message']
                            for item in report['requirements']['PT-07']['evidence']))

    def test_mismatched_batch_decision_identity_fails(self):
        self.assertEqual(self.verdict(self.batch_resume_manifest('D2'), 'PT-07'), 'FAIL')

    def test_missing_semantic_assessments_are_explicitly_incomplete(self):
        report = validate_manifest(self.manifest(), self.base)
        self.assertTrue(any('bounded-detail/no-replan assessment is absent' in item['message']
                            for item in report['requirements']['PT-05']['evidence']))
        self.assertTrue(any('semantic impact assessment is absent' in item['message']
                            for item in report['requirements']['PT-06']['evidence']))

    def test_invalid_dispatch_recipe_is_fail(self):
        manifest = self.manifest()
        manifest['evidence']['dispatch_logs'][0]['recipe'] = 'claimed'
        self.assertEqual(self.verdict(manifest, 'PT-08'), 'FAIL')

    def test_contradictory_bounded_detail_assessment_fails(self):
        review_rel = 'goal/reports/bounded-detail-review.md'
        self.write_text(self.vault / review_rel,
                        '**Outcome:** FAIL\n**Scenario:** bounded-detail\n'
                        '**Replan dispatches:** 0\n')
        commit = self.commit(self.vault, 'contradict bounded detail assessment')
        manifest = self.manifest()
        initial = manifest['evidence']['initial_publication']
        initial['commit'] = commit
        initial['bounded_detail_review'] = review_rel
        self.assertEqual(self.verdict(manifest, 'PT-05'), 'FAIL')

    def test_contradictory_impact_assessment_fails(self):
        record_rel = 'goal/findings/D1.md'
        report_rel = 'goal/reports/replan-D1.md'
        impact_rel = 'goal/reports/impact-D1.md'
        self.write_text(self.vault / record_rel,
                        '**Decision ID:** D1\n**Resolution:** published\n')
        self.write_text(self.vault / report_rel,
                        '**Decision ID:** D1\n**Revised stages:** S01\n'
                        '**Retained stages:**\n')
        self.write_text(self.vault / impact_rel,
                        '**Outcome:** FAIL\n**Decision ID:** D1\n'
                        '**Revised stages:** S01\n**Retained stages:**\n')
        root = self.vault / 'goal/root.md'
        self.write_text(root, root.read_text(encoding='utf-8').replace(
            '**Plan generation:** 1', '**Plan generation:** 2'))
        publication = self.commit(self.vault, 'publish contradictory impact assessment')
        manifest = self.manifest()
        manifest['evidence']['replan'] = {
            'decision_id': 'D1', 'record': record_rel, 'report': report_rel,
            'impact_review': impact_rel, 'root': 'goal/root.md',
            'publication_commit': publication, 'published_generation': 2,
            'revised_stages': ['S01'], 'retained_stages': [],
            'artifacts': [self.stage_rel],
        }
        self.assertEqual(self.verdict(manifest, 'PT-06'), 'FAIL')

    def test_replan_required_preparation_outcome_fails_pt03(self):
        manifest = self.preparation_manifest(
            lambda value: value.replace('**Outcome:** PREPARED',
                                        '**Outcome:** REPLAN-REQUIRED'))
        self.assertEqual(self.verdict(manifest, 'PT-03'), 'FAIL')

    def test_wrong_preparation_root_generation_fails_pt03(self):
        manifest = self.preparation_manifest(
            lambda value: value.replace('**Root generation:** 1',
                                        '**Root generation:** 999'))
        self.assertEqual(self.verdict(manifest, 'PT-03'), 'FAIL')

    def test_nonexistent_preparation_code_commit_fails_pt03(self):
        manifest = self.preparation_manifest(
            lambda value: value.replace(self.code_commit, '0' * 40))
        self.assertEqual(self.verdict(manifest, 'PT-03'), 'FAIL')

    def test_wrong_preparation_root_path_fails_pt03(self):
        manifest = self.preparation_manifest(
            lambda value: value.replace('**Root plan:** goal/root.md',
                                        '**Root plan:** goal/other-root.md'))
        self.assertEqual(self.verdict(manifest, 'PT-03'), 'FAIL')

    def test_wrong_stage_preparation_pointer_fails_pt03(self):
        wrong = self.stage_bytes.replace(
            b'[[goal/reports/prep-s01.md]]', b'[[goal/reports/wrong.md]]')
        self.write_bytes(self.vault / self.stage_rel, wrong)
        commit = self.commit(self.vault, 'corrupt stage preparation pointer')
        manifest = self.manifest()
        manifest['expected']['stages'][0]['prepared_vault_commit'] = commit
        self.assertEqual(self.verdict(manifest, 'PT-03'), 'FAIL')

    def test_wrong_delivery_root_generation_fails_pt04(self):
        delivery = self.vault / 'goal/reports/delivery-s01.md'
        value = delivery.read_text(encoding='utf-8')
        value = value.replace('**Root generation:** 1', '**Root generation:** 998')
        self.write_text(delivery, value)
        commit = self.commit(self.vault, 'corrupt delivery generation')
        manifest = self.manifest()
        manifest['expected']['stages'][0]['delivery_vault_commit'] = commit
        self.assertEqual(self.verdict(manifest, 'PT-04'), 'FAIL')

    def test_wrong_delivery_preparation_pointer_fails_pt04(self):
        delivery = self.vault / 'goal/reports/delivery-s01.md'
        value = delivery.read_text(encoding='utf-8').replace(
            '**Preparation:** goal/reports/prep-s01.md',
            '**Preparation:** goal/reports/wrong.md')
        self.write_text(delivery, value)
        commit = self.commit(self.vault, 'corrupt delivery preparation pointer')
        manifest = self.manifest()
        manifest['expected']['stages'][0]['delivery_vault_commit'] = commit
        self.assertEqual(self.verdict(manifest, 'PT-04'), 'FAIL')

    def test_historical_revalidation_and_later_delivery_commit_are_distinct(self):
        self.write_bytes(self.vault / self.stage_rel, self.stage_bytes)
        self.write_text(self.vault / 'goal/root.md',
                        '**Planning mode:** upfront-v1\n**Plan generation:** 2\n'
                        '**Active replan:** none\n'
                        '**Tree review:** [[goal/reports/tree-review.md]]\n')
        prep = self.vault / 'goal/reports/prep-s01.md'
        self.write_text(prep, prep.read_text(encoding='utf-8').replace(
            '**Root generation:** 1', '**Root generation:** 2'))
        prepared_commit = self.commit(self.vault, 'revalidate preparation for generation two')
        self.write_text(self.code / 'product.txt', 'delivered later\n')
        delivered_code = self.commit(self.code, 'later stage delivery')
        delivery = self.vault / 'goal/reports/delivery-s01.md'
        value = delivery.read_text(encoding='utf-8')
        value = value.replace('**Root generation:** 1', '**Root generation:** 2')
        value = value.replace(self.code_commit, delivered_code)
        self.write_text(delivery, value)
        delivery_commit = self.commit(self.vault, 'later delivery receipt')
        manifest = self.manifest()
        stage = manifest['expected']['stages'][0]
        stage['prepared_vault_commit'] = prepared_commit
        stage['delivery_vault_commit'] = delivery_commit
        stage['code_commit'] = delivered_code
        stage['integration_commit'] = delivered_code
        report = validate_manifest(manifest, self.base)
        for pt in ('PT-03', 'PT-04'):
            self.assertFalse(any(item['status'] == 'FAIL'
                                 for item in report['requirements'][pt]['evidence']))

    def test_missing_historical_root_is_incomplete_not_fail(self):
        self.write_bytes(self.vault / self.stage_rel, self.stage_bytes)
        (self.vault / 'goal/root.md').unlink()
        commit = self.commit(self.vault, 'remove historical root evidence')
        manifest = self.manifest()
        manifest['expected']['stages'][0]['prepared_vault_commit'] = commit
        report = validate_manifest(manifest, self.base)
        evidence = report['requirements']['PT-03']['evidence']
        self.assertTrue(any('historical root is missing' in item['message']
                            for item in evidence))
        self.assertFalse(any(item['status'] == 'FAIL' for item in evidence))

    def test_missing_preparation_digest_is_incomplete_not_fail(self):
        manifest = self.preparation_manifest(
            lambda value: re.sub(r'^\*\*Prepared plan SHA-256:\*\*.*\n', '', value,
                                 flags=re.MULTILINE))
        report = validate_manifest(manifest, self.base)
        evidence = report['requirements']['PT-03']['evidence']
        self.assertTrue(any('preparation receipt is missing' in item['message']
                            for item in evidence))
        self.assertFalse(any(item['status'] == 'FAIL' for item in evidence))

    def test_missing_delivery_generation_is_incomplete_not_fail(self):
        delivery = self.vault / 'goal/reports/delivery-s01.md'
        self.write_text(delivery, re.sub(r'^\*\*Root generation:\*\*.*\n', '',
                                         delivery.read_text(encoding='utf-8'),
                                         flags=re.MULTILINE))
        commit = self.commit(self.vault, 'remove delivery generation evidence')
        manifest = self.manifest()
        manifest['expected']['stages'][0]['delivery_vault_commit'] = commit
        report = validate_manifest(manifest, self.base)
        evidence = report['requirements']['PT-04']['evidence']
        self.assertTrue(any('delivery receipt is missing' in item['message']
                            for item in evidence))
        self.assertFalse(any(item['status'] == 'FAIL' for item in evidence))

    def test_missing_code_repository_is_incomplete_not_fail(self):
        manifest = self.manifest()
        manifest['fixture']['code_repo'] = str(self.base / 'missing-code-repo')
        report = validate_manifest(manifest, self.base)
        evidence = report['requirements']['PT-03']['evidence']
        self.assertTrue(any('code repository is missing' in item['message']
                            for item in evidence))
        self.assertFalse(any(item['status'] == 'FAIL' for item in evidence))

    def test_trace_can_use_a_distinct_run_vault_context(self):
        other = self.base / 'other-vault'
        other.mkdir()
        subprocess.run(['git', 'init', '-q', str(other)], check=True)
        subprocess.run(['git', '-C', str(other), 'config', 'user.email',
                        'fixture@example.invalid'], check=True)
        subprocess.run(['git', '-C', str(other), 'config', 'user.name',
                        'Offline Fixture'], check=True)
        self.write_text(other / 'root.md', '**Planning mode:** upfront-v1\n')
        other_commit = self.commit(other, 'other run publication')
        records = [json.loads(line) for line in self.trace.read_text().splitlines()]
        records[0]['root'] = 'root.md'
        records[0]['initial_publication_commit'] = other_commit
        records[1]['vault_commit_before'] = other_commit
        records[2]['vault_commit_before'] = other_commit
        records[-1]['final_vault_commit'] = other_commit
        other_trace = self.base / 'other-normal.jsonl'
        other_trace.write_text(''.join(json.dumps(item) + '\n' for item in records),
                               encoding='utf-8')
        manifest = self.manifest()
        manifest['evidence']['traces']['normal'] = {
            'path': str(other_trace), 'vault_repo': str(other),
            'root': 'root.md', 'initial_publication_commit': other_commit}
        report = validate_manifest(manifest, self.base)
        messages = [item['message'] for item in report['requirements']['PT-11']['evidence']]
        self.assertFalse(any('lacks a resolvable vault baseline' in item for item in messages))
        self.assertEqual(report['facts']['traces']['normal']['context']['vault_repo'], str(other))

    def test_replan_can_use_a_distinct_run_vault_context(self):
        other = self.base / 'break-vault'
        other.mkdir()
        subprocess.run(['git', 'init', '-q', str(other)], check=True)
        subprocess.run(['git', '-C', str(other), 'config', 'user.email',
                        'fixture@example.invalid'], check=True)
        subprocess.run(['git', '-C', str(other), 'config', 'user.name',
                        'Offline Fixture'], check=True)
        self.write_text(other / 'root.md',
                        '**Planning mode:** upfront-v1\n**Plan generation:** 2\n'
                        '**Active replan:** none\n')
        self.write_text(other / 'record.md',
                        '**Decision ID:** D-OTHER\n**Resolution:** published\n')
        self.write_text(other / 'report.md',
                        '**Decision ID:** D-OTHER\n**Revised stages:** S02 S03\n'
                        '**Retained stages:** S04 S05\n')
        other_commit = self.commit(other, 'break publication')
        manifest = self.manifest()
        manifest['evidence']['replan'] = {
            'vault_repo': str(other), 'root': 'root.md', 'decision_id': 'D-OTHER',
            'record': 'record.md', 'report': 'report.md',
            'publication_commit': other_commit, 'published_generation': 2,
            'revised_stages': ['S02', 'S03'], 'retained_stages': ['S04', 'S05'],
            'artifacts': []}
        report = validate_manifest(manifest, self.base)
        messages = [item['message'] for item in report['requirements']['PT-06']['evidence']]
        self.assertFalse(any('replan publication commit is absent' in item for item in messages))
        self.assertEqual(report['facts']['replan']['vault_repo'], str(other))

    def test_empty_external_artifact_inventory_is_incomplete(self):
        manifest = self.manifest()
        manifest['evidence']['publications'] = {'external': {
            'repo': str(self.vault), 'commit': self.final_vault_commit, 'artifacts': []}}
        report = validate_manifest(manifest, self.base)
        self.assertTrue(any('artifact inventory is empty' in item['message']
                            for item in report['requirements']['PT-10']['evidence']))

    def test_empty_trace_is_incomplete_not_zero_operation_proof(self):
        empty_trace = self.base / 'empty.jsonl'
        empty_trace.write_text(
            json.dumps({'type': 'trace-header', 'run_id': 'empty'}) + '\n' +
            json.dumps({'type': 'trace-trailer', 'run_id': 'empty',
                        'dispatch_count': 0}) + '\n', encoding='utf-8')
        self.assertEqual(load_trace(empty_trace)['status'], 'INCOMPLETE')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--manifest', type=Path)
    group.add_argument('--self-test', action='store_true')
    args = parser.parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(EvidenceValidatorTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        report = validate_manifest(manifest, args.manifest.resolve().parent)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print('plan-tree-e2e: ' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if any(item['verdict'] == 'FAIL'
                    for item in report['requirements'].values()) else 0


if __name__ == '__main__':
    sys.exit(main())

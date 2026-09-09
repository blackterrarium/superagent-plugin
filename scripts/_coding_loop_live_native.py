#!/usr/bin/env python3
"""Repo-owned native admission hooks and runtime wrapper for Stage 3 acceptance.

Hook data is runtime input, never approval authority. Admission records contain no
prompts, credentials, or full private transcripts. The exact helper and extension
bytes must be bound by the approved manifest's package hashes.
"""
from __future__ import annotations

import contextlib
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('stage3_live_runtime', SCRIPTS / 'coding-loop-stage3-live.py')
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)

SPAWNS = {'spawn_agent', 'spawnAgent', 'Agent', 'Task'}
FOLLOWUPS = {'followup_task', 'followupTask', 'send_input', 'sendInput', 'resume_agent', 'resumeAgent'}
MARKER = re.compile(r'STAGE3 role=([A-Z_]+) operation=([A-Za-z0-9_-]+) round=([1-9][0-9]*)')


@contextlib.contextmanager
def transaction(path):
    """One persistent inode serializes all supervisor, native and bridge processes."""
    path = Path(path)
    with Path(str(path) + '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads(path.read_text())
        try: yield data
        finally:
            temporary = path.with_name(path.name + '.' + uuid.uuid4().hex)
            temporary.write_text(json.dumps(data, sort_keys=True))
            os.replace(temporary, path)


def initialize(manifest, harness, path):
    m = live.load_manifest(manifest, approved=True)
    now = time.monotonic()
    record = dict(manifest=str(Path(manifest).resolve()), manifest_sha256=live.sha256(Path(manifest).read_bytes()),
                  harness=harness, started=now, deadline=now + m['limits']['total_seconds'],
                  wall_deadline=time.time() + m['limits']['total_seconds'], used=0, attempts={},
                  permits={}, starts={}, processes={}, actions={}, problems=[], stopped=False, native_preflight=None, scheduler_armed=False)
    live.write_json(path, record)
    return record


def event_log(path, event):
    # Only normalized fields enter this archive. In particular do not persist
    # tool_input.message/prompt or model response bodies as generic hook logs.
    with Path(str(path) + '.events.jsonl').open('a') as out:
        out.write(live.scrub(json.dumps(dict(event, time=time.time()), sort_keys=True)) + '\n')


def normalize_name(name):
    return str(name).split('.')[-1].split('__')[-1]


def pin_request(m, harness, event, entry, index=0):
    prompt = entry.get('message', entry.get('prompt', entry.get('task', '')))
    marker = MARKER.search(prompt if isinstance(prompt, str) else '')
    live.require(marker is not None, 'native dispatch requires STAGE3 role/operation/round binding')
    role, operation, number = marker.groups()
    h = m['harnesses'][harness]
    live.require(role in h['roles'], 'unlisted native role')
    pin = h['roles'][role]
    model = entry.get('model', pin['model'].split(':', 1)[1])
    if ':' not in model: model = harness + ':' + model
    effort = entry.get('reasoning_effort', entry.get('thinking', pin['effort']))
    live.require(model == pin['model'] and effort == pin['effort'], 'wrong native model/effort pin')
    return dict(id=str(event['session_id']) + ':' + str(event['tool_use_id']) + ':' + str(index),
                role=role, operation=operation, round=int(number), model=model, effort=effort,
                source='native-tool', slug=os.environ.get('SUPERAGENT_SLUG'), session_id=event['session_id'], tool_use_id=event['tool_use_id'],
                tool=normalize_name(event['tool_name']), started=time.monotonic(), status='permitted')


def reserve(data, m, requests):
    now = time.monotonic()
    if data['stopped'] or now >= data['deadline'] or time.time() >= data['wall_deadline']:
        raise live.Exhausted('native run total deadline exhausted or stopped')
    # Reuse the driver's policy gate, with counters recovered under the persistent
    # process lock. Stage all batch reservations in memory before committing them.
    gate = live.Budget(m, data['harness'], lambda event: None)
    gate.deadline = data['deadline']; gate.used = data['used']; gate.ids = set(data['permits'])
    gate.attempts = {(int(parts[0]), parts[1], parts[2]): count
                     for key, count in data['attempts'].items() for parts in [key.split(':')]}
    h = m['harnesses'][data['harness']]
    for request in requests:
        permit = gate.authorize({key: request[key] for key in ('id', 'role', 'model', 'effort', 'round', 'operation', 'slug')} |
                                dict(harness=data['harness'], code_root=h['code_root'], vault_root=h['vault_root']))
        request['deadline'] = min(data['deadline'], now + permit['seconds'])
    for request in requests: data['permits'][request['id']] = request
    data['used'] = gate.used
    data['attempts'] = {str(key[0]) + ':' + key[1] + ':' + key[2]: count for key, count in gate.attempts.items()}


def child_ids(response):
    """Only documented identity fields, never arbitrary UUIDs in worker prose."""
    found = []
    if isinstance(response, dict):
        for key, value in response.items():
            if key in ('agent_id', 'agentId', 'thread_id', 'sessionId') and isinstance(value, str): found.append(value)
            elif key in ('receiverThreadIds', 'agent_ids') and isinstance(value, list): found.extend(v for v in value if isinstance(v, str))
            elif key == 'sessionFile' and isinstance(value, str):
                path = Path(value)
                if path.is_absolute() and path.is_file():
                    try:
                        with path.open() as stream: header = json.loads(stream.readline())
                        if header.get('type') == 'session' and isinstance(header.get('id'), str): found.append(header['id'])
                    except (OSError, ValueError): pass
            elif key in ('result', 'results', 'details', 'structuredContent', 'content'): found.extend(child_ids(value))
            elif key == 'text' and response.get('type') == 'text': found.extend(child_ids(value))
    elif isinstance(response, list):
        if response and all(isinstance(value, dict) and type(value.get('index')) is int for value in response):
            if len({value['index'] for value in response}) != len(response): return []
            response = sorted(response, key=lambda value: value['index'])
        for value in response: found.extend(child_ids(value))
    elif isinstance(response, str):
        try: decoded = json.loads(response)
        except ValueError: return []
        if isinstance(decoded, (dict, list)): found.extend(child_ids(decoded))
    return list(dict.fromkeys(found))


def correlate(data, harness):
    for permit in data['permits'].values():
        agent = permit.get('agent_id')
        if permit.get('status') == 'completed' and permit.get('actual_model'): continue
        if not agent or agent not in data['starts']: continue
        observed = data['starts'][agent]
        actual = observed.get('model')
        if actual:
            if ':' not in actual: actual = harness + ':' + actual
            permit['actual_model'] = actual
            if actual != permit['model']:
                problem = 'actual native model mismatch for ' + permit['id']
                if problem not in data['problems']: data['problems'].append(problem)
        permit['actual_effort'] = observed.get('effort')
        if observed.get('result'): permit['result'] = observed['result']
        if observed.get('final_response'): permit['final_response'] = observed['final_response']
        if observed.get('usage'):
            permit['usage'] = observed['usage']; permit['usage_scope'] = observed.get('usage_scope')
        if observed.get('effort') and observed['effort'] != permit['effort']:
            problem = 'actual native effort mismatch for ' + permit['id']
            if problem not in data['problems']: data['problems'].append(problem)
        if observed.get('stopped'): permit['status'] = 'completed'
        permit['commits'] = data.get('actions', {}).get(agent, [])


def hook(path, event):
    with transaction(path) as data:
        m = live.load_manifest(data['manifest'], approved=True)
        live.require(live.sha256(Path(data['manifest']).read_bytes()) == data['manifest_sha256'], 'runtime manifest changed')
        harness = data['harness']; h = m['harnesses'][harness]
        kind = event.get('hook_event_name')
        if event.get('cwd'):
            cwd = Path(event['cwd']).resolve()
            # Git worktrees are allowed only if their common repository matches.
            if not any(live.within(cwd, Path(h[k])) for k in ('code_root', 'vault_root')):
                common = live.git(cwd, 'rev-parse', '--git-common-dir')
                common = (cwd / common).resolve() if not Path(common).is_absolute() else Path(common).resolve()
                live.require(common == Path(h['code_root']) / '.git', 'observed unlisted native workspace')
        updated = None
        name = normalize_name(event.get('tool_name', ''))
        if kind == 'PreToolUse':
            if data['stopped'] or time.monotonic() >= data['deadline']: raise live.Exhausted('native deadline exhausted')
            if name in SPAWNS | FOLLOWUPS or (harness == 'pi' and name == 'subagent'):
                entry = event.get('tool_input', {})
                live.require(isinstance(entry, dict), 'native tool arguments must be object')
                if harness == 'pi':
                    live.require(not entry.get('chain'), 'Pi chain dispatch is unsupported; use independently metered subagents')
                    entries = entry.get('tasks', [entry])
                    live.require(isinstance(entries, list) and entries, 'missing Pi child dispatches')
                else: entries = [entry]
                requests = [pin_request(m, harness, event, child, i) for i, child in enumerate(entries)]
                if name in FOLLOWUPS:
                    target = entry.get('target', entry.get('id', entry.get('agent_id')))
                    known = [p for p in data['permits'].values() if p.get('agent_id') == target]
                    live.require(known and all(p['role'] == requests[0]['role'] and p['model'] == requests[0]['model'] and p['effort'] == requests[0]['effort'] for p in known), 'unlisted follow-up native identity/pin')
                    requests[0]['agent_id'] = target
                else:
                    updated = dict(entry)
                    if harness == 'codex':
                        updated.update(model=requests[0]['model'].split(':', 1)[1], reasoning_effort=requests[0]['effort'], fork_turns='none')
                    elif harness == 'claude':
                        updated['subagent_type'] = 'stage3_' + requests[0]['role']
                        updated.pop('model', None)
                    elif harness == 'pi':
                        revised = [dict(child, model=request['model'].split(':', 1)[1], thinking=request['effort']) for child, request in zip(entries, requests)]
                        updated = dict(entry, tasks=revised) if 'tasks' in entry else revised[0]
                if h.get('runtime') and Path(h['runtime']['outer_loop']).is_file():
                    outer = live.state.read_state(Path(h['runtime']['outer_loop']))
                    operation = outer.get('operation', {})
                    for request in requests:
                        if request['role'] in ('META_PLANNER', 'EVALUATOR', 'DIAGNOSER'):
                            live.require(request['operation'] == operation.get('id'), 'native phase worker operation mismatch')
                            request['operation_snapshot'] = operation
                reserve(data, m, requests)
                if name in FOLLOWUPS:
                    observed = data['starts'].setdefault(target, {})
                    observed['stopped'] = False; observed.pop('result', None); observed.pop('final_response', None)
                    data['actions'][target] = []
                for request in requests: event_log(path, dict(kind='dispatch-permit', **request))
            elif re.search(r'spawn|followup|resume.*agent|send.*input', name, re.I):
                raise live.Invalid('unknown native dispatch tool alias: ' + name)
        elif kind in ('SubagentStart', 'SubagentStop', 'Stop'):
            agent = event.get('agent_id', event.get('session_id'))
            live.require(isinstance(agent, str) and agent, 'missing runtime child identity')
            observed = data['starts'].setdefault(agent, {})
            for key in ('model', 'effort'):
                if event.get(key): observed[key] = event[key]
            observed.update(session_id=event.get('session_id'), stopped=kind in ('SubagentStop', 'Stop'))
            final = event.get('last_assistant_message') or ''
            matched = re.findall(r'(?m)^STAGE3_RESULT (\{[^\n]*\})$', final)
            if len(matched) == 1:
                reported = json.loads(matched[0])
                live.fields(reported, ('action', 'round', 'code_commit', 'plan', 'artifact', 'verdict'))
                live.require(reported['action'] in ('implement', 'review', 'integrate'), 'unknown native final action')
                live.reference(reported['artifact'])
                observed['result'] = reported
                final_path = Path(path).parent / ('native-final-' + uuid.uuid4().hex + '.txt')
                final_path.write_text(live.scrub(final))
                observed['final_response'] = dict(path=str(final_path), sha256=live.sha256(final_path.read_bytes()), original_sha256=live.sha256(final.encode()))
            elif len(matched) > 1: data['problems'].append('conflicting native final result receipts')
            if harness == 'claude' and kind == 'SubagentStop' and event.get('agent_transcript_path'):
                transcript = Path(event['agent_transcript_path'])
                if transcript.is_file():
                    models, usage = set(), {}
                    for line in transcript.read_text().splitlines():
                        try: row = json.loads(line)
                        except ValueError: continue
                        message = row.get('message', {})
                        if isinstance(message, dict) and message.get('role') == 'assistant' and message.get('model'):
                            models.add(message['model'])
                            usage = {k: v for k, v in message.get('usage', {}).items() if isinstance(v, (int, float))}
                    if len(models) == 1: observed['model'] = models.pop()
                    elif len(models) > 1: data['problems'].append('conflicting actual Claude child model receipts')
                    observed['usage'] = usage
                    observed['usage_scope'] = 'last_assistant_message'
            if harness == 'codex' and kind in ('SubagentStop', 'Stop'):
                transcript = Path(event.get('agent_transcript_path') or event.get('transcript_path') or '/nonexistent')
                if transcript.is_file():
                    models, efforts = set(), set()
                    for line in transcript.read_text().splitlines():
                        try: row = json.loads(line)
                        except ValueError: continue
                        payload = row.get('payload', {})
                        if row.get('type') == 'turn_context':
                            if payload.get('model'): models.add(payload['model'])
                            if payload.get('effort'): efforts.add(payload['effort'])
                        if payload.get('type') == 'token_count':
                            usage = payload.get('info', {}).get('total_token_usage', {})
                            observed['usage'] = {k: v for k, v in usage.items() if isinstance(v, (int, float))}
                            observed['usage_scope'] = 'runtime_total'
                    if len(models) == 1: observed['model'] = models.pop()
                    if len(efforts) == 1: observed['effort'] = efforts.pop()
                    if len(models) > 1 or len(efforts) > 1: data['problems'].append('conflicting actual Codex model/effort receipts')
            event_log(path, dict(kind=kind, agent_id=agent, model=observed.get('model'), effort=observed.get('effort')))

        elif kind == 'PostToolUse' and (name in SPAWNS | FOLLOWUPS or name == 'subagent'):
            permits = [p for p in data['permits'].values() if p['session_id'] == event.get('session_id') and p['tool_use_id'] == event.get('tool_use_id')]
            ids = child_ids(event.get('tool_response'))
            if name in FOLLOWUPS and not ids: ids = [p['agent_id'] for p in permits if p.get('agent_id')]
            if len(ids) != len(permits): data['problems'].append('missing or ambiguous runtime child IDs for ' + str(event.get('tool_use_id')))
            else:
                for permit, agent in zip(permits, ids): permit['agent_id'] = agent
        elif kind == 'PostToolUse' and name in ('Bash', 'bash', 'exec_command'):
            command = event.get('tool_input', {}).get('command', event.get('tool_input', {}).get('cmd', ''))
            if re.search(r'(?:^|&&|;)\s*git(?:\s+-C\s+[^ ]+)?\s+(?:commit|rev-parse|merge|pull)\b', command):
                # Preserve only exact revision tokens produced by Git operations.
                output = json.dumps(event.get('tool_response', {}))
                commits = re.findall(r'(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])', output)
                for short in re.findall(r'\[[^]\n]*? ([0-9a-f]{7,40})\]', output):
                    try: commits.append(live.git(Path(h['code_root']), 'rev-parse', short + '^{commit}'))
                    except live.Incomplete: pass
                owner = event.get('session_id')
                process_id = os.environ.get('SUPER_STAGE3_PROCESS_PERMIT')
                if process_id in data['permits'] and data['permits'][process_id].get('agent_id') == owner:
                    owner = data['permits'][process_id]['agent_id']
                for commit in commits:
                    if re.fullmatch(r'[0-9a-f]{40}', commit): data.setdefault('actions', {}).setdefault(owner, []).append(commit)
        elif kind == 'SessionStart':
            session_id = event.get('session_id')
            data['starts'].setdefault(session_id, {}).update(model=event.get('model'), effort=event.get('effort'), stopped=False)
            process_id = os.environ.get('SUPER_STAGE3_PROCESS_PERMIT')
            if process_id in data['permits']:
                permit = data['permits'][process_id]
                permit['agent_id'] = event.get('session_id')
                actual = event.get('model')
                if actual:
                    permit['actual_model'] = actual if ':' in actual else harness + ':' + actual
                    if permit['actual_model'] != permit['model']: data['problems'].append('actual CLI model mismatch')
                permit['actual_effort'] = event.get('effort')
            event_log(path, dict(kind=kind, session_id=event.get('session_id'), model=event.get('model')))
        correlate(data, harness)
        if updated is not None: return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'allow', 'updatedInput': updated}}
        return {'hookSpecificOutput': {'hookEventName': kind, 'additionalContext': routing_instructions(h)}} if kind == 'SessionStart' else {}


def routing_instructions(h):
    return ('This is a bounded Stage 3 acceptance run. For every native child start and follow-up, '
            'begin its prompt with STAGE3 role=ROLE operation=IDENTITY round=N, using its actual '
            'configured role and stable operation identity. Retry the same operation identity. '
            'Use only declared native model/effort pins: ' + json.dumps(h['roles'], sort_keys=True) +
            '. For CLI bridges always pass --role with the exact role name (such as meta_planner, evaluator, diagnoser or executor). '
            'Use isolated Codex contexts with fork_turns=none. Review/integration evidence must include '
            'the exact Git source revision observed with git rev-parse HEAD and the native dispatch ID. '
            '. No alternate model APIs, unmetered subprocess binaries, chain dispatches, or worker '
            'output claimed as runtime authority. Use only the declared fixture code/vault/remotes '
            'and exact outer/inner registration slugs: ' + json.dumps(h['cleanup']['registrations']) +
            '. Never edit approval/agreement inputs or fabricate first-failure/inner-DONE evidence. '
            'Before a DONE or WAITING FOR INPUT supervisor exits, write loop-status/stage3-evidence.json under the project. '
            'This is an artifact index only. Use {operations:[exact reserved operation objects], '
            'dispatches:[{id: exact native permit id, operation_id: reserved operation id for phase workers, '
            'role: configured role, round: N, source_commit: exact evaluated/reviewed SHA}], '
            'changes:[{action: implement|review|integrate, dispatch_id: exact native permit id, '
            'round: repaired round, code_commit: exact SHA, plan: exact meta-plan locator}]}. '
            'Read actual permit IDs from the SUPER_STAGE3_RUN JSON path and its .events.jsonl; never invent IDs. '
            'Every IMPLEMENTER, BRANCH_REVIEWER and integrating EXECUTOR must run git rev-parse HEAD '
            'on the exact reviewed/integrated code checkout at completion so the native hook captures the '
            'revision; retain its normal implementation/review/integration artifacts and links. '
            'Each such worker must end its actual final response with one single line STAGE3_RESULT '
            '{"action":"implement|review|integrate","round":N,"code_commit":"SHA","plan":"meta-plan locator",'
            '"artifact":{"path":"absolute normal delivery/report path","sha256":"artifact hash"},"verdict":"PASS|FAIL"}. '
            'The normal artifact must include the exact reviewed code SHA and its verdict and be integrated '
            'through the normal inner delivery workflow. The supervisor copies that artifact reference into changes. '
            'Copy exact operation objects from runtime operation_snapshot records. Do not alter runtime files. '
            'The collector replaces index dispatch identity/parent/transition claims with authenticated runtime data.')


def toml(value):
    if isinstance(value, str): return json.dumps(value)
    if isinstance(value, list): return '[' + ','.join(toml(item) for item in value) + ']'
    if isinstance(value, dict): return '{' + ','.join(json.dumps(k) + '=' + toml(v) for k, v in value.items()) + '}'
    return str(value).lower()


def inject(harness, args, path):
    # Hook engines accept shell command strings. The command contains only this
    # repo-owned helper's literal path; manifest data travels through environment.
    command = shlex.join([sys.executable, str(Path(__file__).resolve()), 'hook'])
    definitions = {kind: [{'matcher': '.*', 'hooks': [{'type': 'command', 'command': command, 'timeout': 5}]}]
                   for kind in ('SessionStart', 'PreToolUse', 'PostToolUse', 'SubagentStart', 'SubagentStop', 'Stop')}
    if harness == 'codex':
        return list(args) + ['--dangerously-bypass-hook-trust'] + [part for key, value in definitions.items() for part in ('-c', 'hooks.' + key + '=' + toml(value))]
    if harness == 'claude':
        data = json.loads(Path(path).read_text())
        m = live.load_manifest(data['manifest'], approved=True)
        agents = {'stage3_' + role: dict(description='Bounded Stage 3 ' + role, prompt='Execute only the supplied ' + role + ' task.',
                  model=pin['model'].split(':', 1)[1], effort=pin['effort']) for role, pin in m['harnesses']['claude']['roles'].items()}
        return list(args) + ['--settings', json.dumps({'hooks': definitions}), '--agents', json.dumps(agents)]
    if harness == 'pi': return list(args) + ['--extension', str(SCRIPTS / 'coding-loop-stage3-pi.ts')]
    raise live.Invalid('unsupported native harness')


def native_argv(runtime, args):
    return ([runtime['node']] if runtime.get('node') else []) + [runtime['cli'], *args]


def admission_path(bin_dir):
    # _common.sh prepends common CLI directories unless ~/.local/bin is already
    # present. Include them after our wrapper so its ordinary augmentation keeps
    # admission first, and inventory foreign Cursor names in the same directory.
    entries = [str(bin_dir), str(Path.home() / '.local/bin'), '/opt/homebrew/bin', '/usr/local/bin']
    entries.extend(os.environ['PATH'].split(':'))
    return ':'.join(dict.fromkeys(entries))


def native_preflight(m, harness):
    h = m['harnesses'][harness]; runtime = h.get('runtime')
    if not runtime: raise live.Incomplete('native adapter requires exact reviewed runtime CLI/version, scheduler/config and outer-loop identities')
    live.fields(runtime, ('cli', 'cli_version', 'scripts_root', 'config_root', 'launchd_dir', 'outer_loop', 'interval_seconds'), ('node',))
    for key in ('cli', 'scripts_root', 'config_root', 'launchd_dir', 'outer_loop'): live.absolute(runtime[key])
    live.require(type(runtime['interval_seconds']) is int and runtime['interval_seconds'] > 0, 'positive scheduler interval required')
    cli = Path(runtime['cli'])
    if runtime.get('node'): live.absolute(runtime['node'])
    if not cli.is_file(): raise live.Incomplete('native CLI unavailable')
    if b'/usr/bin/env node' in cli.read_bytes()[:100] and not runtime.get('node'):
        raise live.Incomplete('native JS CLI requires an approved absolute node interpreter')
    version = subprocess.run(native_argv(runtime, ['--version']), capture_output=True, text=True, timeout=10)
    if version.returncode or version.stdout.strip() != runtime['cli_version']:
        raise live.Incomplete('native CLI exact version mismatch')
    timeout = shutil.which('timeout') or shutil.which('gtimeout')
    if not timeout: raise live.Incomplete('GNU timeout/gtimeout unavailable; bounded run cannot arm')
    check = subprocess.run([timeout, '--version'], capture_output=True, text=True, timeout=5)
    if check.returncode or 'GNU coreutils' not in check.stdout: raise live.Incomplete('timeout is not GNU coreutils')
    required = {str(Path(__file__).resolve()), str(SCRIPTS / 'coding-loop-stage3-live.py'), str(cli),
                *(str(SCRIPTS / name) for name in ('launch.sh', 'stop.sh', 'install-timer.sh', 'uninstall-timer.sh', 'superagent-tick.sh', '_common.sh', 'role-bridge.sh'))}
    if harness == 'pi': required.add(str(SCRIPTS / 'coding-loop-stage3-pi.ts'))
    if runtime.get('node'): required.add(runtime['node'])
    pinned = {p['path'] for p in h['packages']}
    live.require(required <= pinned, 'approved manifest does not bind native helper/extension bytes')
    versions = []
    for pin in h['packages']:
        content = live.read_reference({k: pin[k] for k in ('path', 'sha256')})
        if Path(pin['path']).suffix == '.json':
            try: metadata = json.loads(content)
            except ValueError: continue
            if isinstance(metadata, dict) and 'version' in metadata:
                live.require(metadata['version'] == pin['version'], 'installed package version mismatch')
                versions.append(metadata['version'])
    if not versions: raise live.Incomplete('installed package manifest version receipt missing')
    live.require(runtime['scripts_root'] == str(SCRIPTS), 'native adapter requires this reviewed scheduler script root')
    for ref in h['auth_refs']:
        kind, value = ref.split(':', 1)
        if kind == 'env' and not os.environ.get(value): raise live.Incomplete('missing authentication reference: ' + ref)
        if kind == 'profile' and not Path(value).is_file(): raise live.Incomplete('missing native auth profile reference')
    if harness == 'codex':
        help_text = subprocess.run(native_argv(runtime, ['--help']), capture_output=True, text=True, timeout=10).stdout
        if '--dangerously-bypass-hook-trust' not in help_text: raise live.Incomplete('Codex native CLI lacks reviewed hook-trust interface')
    try:
        identity = subprocess.run(['ps', '-p', str(os.getpid()), '-o', 'lstart='], capture_output=True, text=True, timeout=5)
        if identity.returncode or not identity.stdout.strip(): raise live.Incomplete('native process ownership inspection unavailable')
    except OSError as exc: raise live.Incomplete('native process ownership inspection unavailable') from exc
    scheduler = ['launchctl', 'print', 'gui/' + str(os.getuid())] if sys.platform == 'darwin' else ['systemctl', '--user', 'show-environment']
    # This query can contain environment secrets. Do not archive its output.
    if subprocess.run(scheduler, capture_output=True, timeout=10).returncode:
        raise live.Incomplete('real user scheduler unavailable')
    if subprocess.run(['gh', 'auth', 'status'], capture_output=True, timeout=10).returncode:
        raise live.Incomplete('GitHub authentication unavailable')
    return runtime



def pinned_args(harness, args, pin):
    """Replace incoming pins; duplicate --model options are rejected by some CLIs."""
    output = []; index = 0
    while index < len(args):
        arg = args[index]
        if arg in ('-m', '--model', '--effort', '--thinking'):
            live.require(index + 1 < len(args), 'missing CLI pin argument')
            index += 2; continue
        if any(arg.startswith(prefix) for prefix in ('--model=', '--effort=', '--thinking=')):
            index += 1; continue
        if arg in ('-c', '--config') and index + 1 < len(args) and args[index + 1].split('=', 1)[0] == 'model_reasoning_effort':
            index += 2; continue
        if arg.startswith('--config=model_reasoning_effort='):
            index += 1; continue
        output.append(arg); index += 1
    model = pin['model'].split(':', 1)[1]
    if harness == 'codex': return output + ['-m', model, '-c', 'model_reasoning_effort=' + pin['effort']]
    if harness == 'claude': return output + ['--model', model, '--effort', pin['effort']]
    return output + ['--model', model, '--thinking', pin['effort']]

def wrapper(path, args):
    path = Path(path)
    stdin_data = None if sys.stdin.isatty() else sys.stdin.buffer.read()
    with transaction(path) as data:
        m = live.load_manifest(data['manifest'], approved=True); harness = data['harness']; h = m['harnesses'][harness]
        runtime = h['runtime']
        # CLI utility probes are read-only and do not start model contexts.
        if args in (['--version'], ['--help']):
            command = native_argv(runtime, args)
            os.execv(command[0], command)
        role = os.environ.get('SUPERAGENT_ROLE', 'SUPERVISOR').upper().replace('-', '_')
        prompt = ' '.join(args) + '\n' + (stdin_data or b'').decode('utf-8', errors='replace')
        marker = MARKER.search(prompt)
        if marker:
            requested_role, operation, number = marker.groups()
            if os.environ.get('SUPERAGENT_ROLE'): live.require(requested_role == role, 'bridge role and prompt identity conflict')
            role = requested_role
        else:
            live.require(os.environ.get('SUPERAGENT_SLUG') in {r['slug'] for r in h['cleanup']['registrations']}, 'unbound bridge/native CLI process')
            outer = live.state.read_state(Path(runtime['outer_loop']))
            number = str(outer['round'])
            operation = outer.get('operation', {}).get('id') if role != 'SUPERVISOR' else None
            operation = operation or 'tick-' + os.environ['SUPERAGENT_SLUG'] + '-' + str(outer['iteration'])
        pin = h['roles'][role]
        entry = {'message': f'STAGE3 role={role} operation={operation} round={number}', 'model': pin['model'].split(':', 1)[1], 'reasoning_effort': pin['effort']}
        event = dict(session_id='process-' + str(os.getpid()), tool_use_id=uuid.uuid4().hex, tool_name='native-cli')
        request = pin_request(m, harness, event, entry)
        request.update(source='native-cli', pid=os.getpid(), slug=os.environ.get('SUPERAGENT_SLUG'))
        if role in ('META_PLANNER', 'EVALUATOR', 'DIAGNOSER'):
            outer = live.state.read_state(Path(runtime['outer_loop']))
            request['operation_snapshot'] = outer['operation']
            live.require(request['operation'] == outer['operation'].get('id'), 'native bridge operation mismatch')
        reserve(data, m, [request])
        event_log(path, dict(kind='dispatch-permit', **request))
        seconds = request['deadline'] - time.monotonic()
    env = dict(os.environ, SUPER_STAGE3_RUN=str(path), SUPER_STAGE3_PROCESS_PERMIT=request['id'], SUPER_STAGE3_PYTHON=sys.executable)
    env.pop('SUPERAGENT_ROLE', None)
    env.pop('CLAUDE_CODE_EFFORT_LEVEL', None)
    env.update(XDG_CONFIG_HOME=runtime['config_root'], SUPERAGENT_LAUNCHD_DIR=runtime['launchd_dir'],
               SUPERAGENT_CLI_PATH=str(path.parent / 'bin'), SUPER_CODE_MAX_ITERATIONS=str(m['limits']['max_rounds']))
    for name, configured in h['roles'].items():
        env['SUPER_MODEL_' + name] = configured['model']; env['SUPER_EFFORT_' + name] = configured['effort']
    if harness == 'pi': env['PI_SUBAGENT_PI_BINARY'] = str(path.parent / 'bin/pi')
    args = pinned_args(harness, args, pin)
    process = subprocess.Popen(native_argv(runtime, inject(harness, args, path)), env=env, start_new_session=True,
                               stdin=subprocess.PIPE if stdin_data is not None else None)
    try:
        ownership = subprocess.run(['ps', '-p', str(process.pid), '-o', 'lstart='], capture_output=True, text=True, timeout=5)
        identity = ownership.stdout.strip()
        if ownership.returncode or not identity: raise live.Incomplete('native child process ownership receipt unavailable')
        with transaction(path) as data:
            data['processes'][str(process.pid)] = dict(id=request['id'], slug=os.environ.get('SUPERAGENT_SLUG'), start=identity)
    except Exception:
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait(); raise
    try:
        process.communicate(input=stdin_data, timeout=seconds)
        code = process.returncode
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL); code = process.wait(); event_log(path, {'kind': 'dispatch-timeout', 'id': request['id']})
    finally:
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        with transaction(path) as data:
            data['processes'].pop(str(process.pid), None)
            data['permits'][request['id']]['status'] = 'completed' if process.returncode == 0 else 'failed'
    return code



class NativeAdapter:
    """Native CLI/hook transport around the existing external scheduler."""
    def __init__(self, harness):
        self.harness = harness

    def configure(self, manifest, harness):
        self.m = manifest; self.h = manifest['harnesses'][harness]
        self.runtime = self.h.get('runtime')
        if not self.runtime: raise live.Incomplete('native adapter requires reviewed runtime identities')
        self.env = dict(os.environ, REPO=self.h['code_root'], XDG_CONFIG_HOME=self.runtime['config_root'],
                        SUPERAGENT_LAUNCHD_DIR=self.runtime['launchd_dir'], SUPER_HARNESS=harness)
        for registration in self.h['cleanup']['registrations']:
            self.registration(registration, optional=True)

    def preflight(self, manifest, harness):
        native_preflight(manifest, harness)
        self.configure(manifest, harness)
        self.verified = dict(cli_sha256=live.sha256(Path(self.runtime['cli']).read_bytes()), cli_version=self.runtime['cli_version'], platform=sys.platform)

    def registration(self, identity, optional=False):
        path = Path(self.runtime['config_root']) / 'superagent' / (identity['slug'] + '.env')
        if optional and not path.exists(): return None
        if not path.is_file(): raise live.Incomplete('missing owned registration: ' + identity['slug'])
        fields = {}
        for line in path.read_text().splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                live.require(key not in fields, 'duplicate registration field')
                fields[key] = value
        live.require(fields.get('REPO') == self.h['code_root'] and fields.get('SUPERAGENT_SLUG') == identity['slug'] and
                     fields.get('SUPERAGENT_SUPERVISOR') == identity['supervisor'], 'owned registration identity conflict')
        loop = live.absolute(fields.get('LOOP_FILE', ''))
        live.require(any(live.within(loop, Path(self.h[k])) for k in ('code_root', 'vault_root')), 'unlisted registered loop path')
        if identity['supervisor'] == 'supercode': live.require(str(loop) == self.runtime['outer_loop'], 'outer loop identity changed')
        return fields

    def command(self, argv, timeout=10):
        process = subprocess.Popen(argv, env=self.env, cwd=self.h['code_root'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL); process.communicate()
            raise
        finally:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass

    def stop(self, identity):
        registered = self.registration(identity, optional=True)
        if registered is None:
            if self.active(identity): raise live.Incomplete('active scheduler identity lacks owned registration proof')
            return
        # No glob, pkill, killall, global systemctl action or unowned scheduler ID.
        if hasattr(self, 'path'):
            with transaction(self.path) as data:
                for pid, item in list(data['processes'].items()):
                    process = item if isinstance(item, dict) else {}
                    if process.get('slug') != identity['slug']: continue
                    current = subprocess.run(['ps', '-p', pid, '-o', 'lstart='], capture_output=True, text=True).stdout.strip()
                    if current and current == process.get('start'):
                        try: os.killpg(int(pid), signal.SIGKILL)
                        except ProcessLookupError: pass
        stopped = self.command(['/bin/bash', str(Path(self.runtime['scripts_root']) / 'stop.sh'), '--slug', identity['slug'], '--hard'])
        if stopped.returncode: raise live.Incomplete('owned stop failed: ' + identity['slug'])

    def active(self, identity):
        self.registration(identity, optional=True)
        if sys.platform == 'darwin':
            query = self.command(['launchctl', 'print', 'gui/' + str(os.getuid()) + '/com.superagent.tick.' + identity['slug']])
            if query.returncode not in (0, 113): raise live.Incomplete('cannot verify owned launchd cleanup')
            active = query.returncode == 0
        else:
            active = False
            for suffix in ('timer', 'service'):
                query = self.command(['systemctl', '--user', 'is-active', 'superagent-tick@' + identity['slug'] + '.' + suffix])
                if query.returncode not in (0, 3, 4): raise live.Incomplete('cannot verify owned systemd cleanup')
                active |= query.stdout.strip() in ('active', 'activating', 'reloading', 'deactivating')
        if hasattr(self, 'path'):
            with transaction(self.path) as data:
                for pid, item in data['processes'].items():
                    if isinstance(item, dict) and item.get('slug') == identity['slug']:
                        query = subprocess.run(['ps', '-p', pid, '-o', 'lstart='], capture_output=True, text=True)
                        active |= bool(query.stdout.strip()) and query.stdout.strip() == item.get('start')
        return active

    def run(self, manifest, harness, attempt, budget):
        self.path = attempt / 'native-runtime.json'
        if not getattr(self, 'verified', None): raise live.Incomplete('native run lacks successful real runtime preflight')
        initialize(attempt / 'manifest.json', harness, self.path)
        with transaction(self.path) as data: data['native_preflight'] = self.verified
        # Reserve and retain the attempt before any native work. A subsequent run
        # needs another explicitly allowed attempt or a newly approved manifest.
        attempts_file = Path(manifest['evidence_dir']) / ('attempts-' + harness + '.json')
        lockfile = Path(str(attempts_file) + '.lock')
        with lockfile.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            attempts = json.loads(attempts_file.read_text()) if attempts_file.exists() else []
            digest = live.sha256((attempt / 'manifest.json').read_bytes())
            if sum(entry['manifest_sha256'] == digest for entry in attempts) > manifest['limits']['retries']:
                raise live.Exhausted('approved native run attempt ceiling exhausted')
            attempts.append(dict(manifest_sha256=digest, runtime=str(self.path)))
            attempts_file.write_text(json.dumps(attempts))
        bin_dir = attempt / 'bin'; bin_dir.mkdir()
        # Python wrapper files contain JSON string literals, never shell code.
        for name in ('claude', 'codex', 'pi', 'agent', 'cursor-agent'):
            wrapper_file = bin_dir / name
            if name != harness:
                wrapper_file.write_text('#!' + sys.executable + '\nraise SystemExit(\"foreign native harness refused by Stage 3 manifest\")\n')
                wrapper_file.chmod(0o700)
                continue
            wrapper_file.write_text('#!' + sys.executable + '\nimport runpy,sys\nsys.path.insert(0,' +
                repr(str(SCRIPTS)) + ')\nfrom _coding_loop_live_native import wrapper\nraise SystemExit(wrapper(' +
                repr(str(self.path)) + ',sys.argv[1:]))\n')
            wrapper_file.chmod(0o700)
        self.env.update(PATH=admission_path(bin_dir), SUPERAGENT_CLI_PATH=str(bin_dir),
                        SUPER_STAGE3_RUN=str(self.path), SUPER_CODE_MAX_ITERATIONS=str(manifest['limits']['max_rounds']))
        for role, pin in self.h['roles'].items():
            self.env['SUPER_MODEL_' + role] = pin['model']
            self.env['SUPER_EFFORT_' + role] = pin['effort']
        outer = next(item for item in self.h['cleanup']['registrations'] if item['supervisor'] == 'supercode')
        watcher = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'watchdog', str(self.path)],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   env=self.env, start_new_session=True)
        try:
            launched = self.command(['/bin/bash', str(Path(self.runtime['scripts_root']) / 'launch.sh'),
                self.h['project'], '--supervisor', 'supercode', '--slug', outer['slug'],
                '--interval', str(self.runtime['interval_seconds']) + 's',
                '--timeout', str(manifest['limits']['dispatch_seconds'])], timeout=min(30, budget.remaining()))
            live.write_json(attempt / 'launch.json', dict(returncode=launched.returncode,
                            stdout=live.scrub(launched.stdout), stderr=live.scrub(launched.stderr)))
            if launched.returncode: raise live.Incomplete('native scheduler launch failed')
            with transaction(self.path) as data: data['scheduler_armed'] = True
            last = None
            while True:
                budget.remaining()
                with transaction(self.path) as data:
                    if data['problems']: raise live.Incomplete('; '.join(data['problems']))
                    if data['stopped']: raise live.Exhausted('native watchdog stopped run')
                self.registration(outer)
                snapshot = live.state.read_state(Path(self.runtime['outer_loop']))
                live.require(snapshot['round'] <= manifest['limits']['max_rounds'], 'observed project round ceiling exceeded')
                live.require(snapshot['agreement_revision'] == self.h['agreement_revision'], 'observed agreement revision changed')
                live.check_agreement(manifest, harness, context=False)
                identity = json.dumps(snapshot, sort_keys=True)
                if identity != last:
                    event_log(self.path, dict(kind='state', state=snapshot))
                    print(json.dumps(dict(event='state', harness=harness, status=snapshot['status'], round=snapshot['round'])), flush=True)
                    last = identity
                if snapshot['status'] in ('DONE', 'WAITING FOR INPUT'):
                    with transaction(self.path) as data:
                        if not data['processes'] and not any(p['status'] == 'permitted' for p in data['permits'].values()): break
                time.sleep(min(0.25, budget.remaining()))
        finally:
            with transaction(self.path) as data: data['stopped'] = True
            live.cleanup_owned(manifest, harness, self)
            try: watcher.wait(timeout=12)
            except subprocess.TimeoutExpired:
                watcher.kill(); watcher.wait()

    def collect(self, manifest, harness):
        digest = live.sha256(json.dumps(manifest, sort_keys=True).encode())
        candidates = []
        for path in Path(manifest['evidence_dir']).glob('*-run-*/native-runtime.json'):
            data = json.loads(path.read_text())
            saved = live.load_manifest(data['manifest'], approved=True)
            if data['harness'] == harness and live.sha256(json.dumps(saved, sort_keys=True).encode()) == digest:
                candidates.append(path)
        if not candidates: raise live.Incomplete('missing native runtime receipts')
        self.path = max(candidates, key=lambda p: p.parent.name)
        with transaction(self.path) as data:
            if not data.get('native_preflight') or not data.get('scheduler_armed'): raise live.Incomplete('synthetic/unarmed receipts are not live acceptance authority')
            if data['problems']: raise live.Incomplete('; '.join(data['problems']))
            permits = list(data['permits'].values())
        for permit in permits:
            operation = permit.get('operation_snapshot', {})
            if operation.get('phase') == 'EVALUATING' and operation.get('round') == 1 and permit.get('actual_model') and permit.get('status') == 'completed':
                receipt = live.evidence.reconcile_operation(Path(self.h['code_root']), Path(self.h['vault_root']), operation)
                if receipt.get('outcome') == 'INTEGRATED' and receipt.get('worker_complete'):
                    report = live.evidence.validate_evaluation(Path(receipt['report']), Path(self.h['project']) / 'evaluation.md', operation)
                    if report['declared_verdict'] == 'PASS': raise live.Invalid('first native evaluation unexpectedly PASS')
        index = Path(self.h['project']) / 'loop-status/stage3-evidence.json'
        if not index.is_file(): raise live.Incomplete('missing revision-specific native review/integration evidence index')
        packet = json.loads(index.read_text())
        snapshots = {}
        for permit in permits:
            if permit.get('operation_snapshot'): snapshots[permit['operation_snapshot']['id']] = permit['operation_snapshot']
        if snapshots: packet['operations'] = list(snapshots.values())
        history = [json.loads(line) for line in Path(str(self.path) + '.events.jsonl').read_text().splitlines()]
        packet['transitions'] = [event['state']['status'] for event in history if event.get('kind') == 'state']
        # A worker-authored index only supplies artifact links. Its dispatches and
        # synthetic flag cannot manufacture native runtime authority.
        authenticated = {p['id']: p for p in permits if p.get('actual_model') and p.get('status') == 'completed'}
        for claim in packet.get('dispatches', []):
            observed = authenticated.get(claim.get('id'))
            if observed is None: raise live.Incomplete('missing completed native runtime identity')
            live.require(claim.get('role') == observed['role'] and claim.get('round') == observed['round'], 'native role receipt mismatch')
            if claim.get('operation_id'):
                live.require(claim['operation_id'] == observed['operation'], 'runtime operation ID mismatch')
                live.require(claim.get('source_commit') == observed.get('operation_snapshot', {}).get('code_commit'), 'runtime operation SHA mismatch')
            registration = next((r for r in self.h['cleanup']['registrations'] if r['slug'] == observed.get('slug')), None)
            live.require(registration is not None, 'runtime dispatch has no declared scheduler parent')
            parent = 'inner-supervisor' if registration['supervisor'] == 'superagent' else 'outer-supervisor'
            claim.update(harness=harness, model=observed['actual_model'], effort=observed.get('actual_effort'), status='completed', parent=parent)
            if observed.get('usage'): claim.update(usage=observed['usage'], usage_scope=observed.get('usage_scope'))
            if observed.get('final_response'): claim['final_response'] = observed['final_response']
        for change in packet.get('changes', []):
            live.require(change.get('dispatch_id') in authenticated, 'controller-written change has no native worker receipt')
            # Git transport proof is collected by a PostToolUse commit observation,
            # not by the controller or worker index asserting an actor name.
            proof = authenticated[change['dispatch_id']].get('commits', [])
            live.require(change.get('code_commit') in proof, 'missing runtime-attributed commit/review receipt')
            worker = authenticated[change['dispatch_id']]
            final_response = worker.get('final_response')
            live.require(isinstance(final_response, dict), 'missing full native reviewer/worker final output')
            live.read_reference({k: final_response[k] for k in ('path', 'sha256')})
            reported = worker.get('result')
            live.require(isinstance(reported, dict), 'missing actual native worker/reviewer final result')
            live.require(all(reported.get(key) == change.get(key) for key in ('action', 'round', 'code_commit', 'plan', 'artifact')) and reported.get('verdict') == 'PASS', 'native reviewer output disagrees with evidence index')
        packet['synthetic'] = False
        return packet


def watchdog(path):
    data = json.loads(Path(path).read_text())
    m = live.load_manifest(data['manifest'], approved=True)
    adapter = NativeAdapter(data['harness']); adapter.m = m; adapter.h = m['harnesses'][data['harness']]
    adapter.runtime = adapter.h['runtime']; adapter.path = Path(path)
    adapter.env = dict(os.environ, REPO=adapter.h['code_root'], XDG_CONFIG_HOME=adapter.runtime['config_root'],
                       SUPERAGENT_LAUNCHD_DIR=adapter.runtime['launchd_dir'])
    while True:
        with transaction(path) as current:
            if current['stopped']: return 0
            now = time.monotonic()
            timed_out = bool(current['problems']) or now >= current['deadline'] or time.time() >= current['wall_deadline'] or any(
                p.get('status') == 'permitted' and now >= p['deadline'] for p in current['permits'].values())
            if timed_out:
                current['stopped'] = True; current['problems'].append('independent native dispatch/total deadline exhausted')
        if timed_out:
            receipt = live.cleanup_owned(m, data['harness'], adapter)
            event_log(path, dict(kind='watchdog-cleanup', receipt=receipt)); return 0
        time.sleep(0.1)

def main():
    action = sys.argv[1]
    path = Path(sys.argv[2] if len(sys.argv) > 2 else os.environ['SUPER_STAGE3_RUN'])
    if action == 'hook':
        try: output = hook(path, json.load(sys.stdin))
        except Exception as exc:
            event_log(path, {'kind': 'hook-denied', 'reason': str(exc)})
            with transaction(path) as data: data['problems'].append('native hook rejected: ' + str(exc))
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': str(exc)}}))
            return 2
        print(json.dumps(output)); return 0
    if action == 'wrapper': return wrapper(path, sys.argv[3:])
    if action == 'watchdog': return watchdog(path)
    raise SystemExit('unknown native helper action')


if __name__ == '__main__': raise SystemExit(main())

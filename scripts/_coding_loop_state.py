#!/usr/bin/env python3
"""Strict, atomic state handling for the Stage 3 coding-loop supervisor."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid


class StateError(ValueError):
    """The state file or a requested transition is invalid."""


RECOVER_READY = {
    "META-PLANNING": "WAITING FOR META-PLAN",
    "EVALUATING": "WAITING FOR EVAL",
    "DIAGNOSING": "WAITING FOR DIAGNOSIS",
}

STATUSES = {
    "WAITING FOR META-PLAN",
    "META-PLANNING",
    "WAITING FOR BUILD",
    "BUILDING",
    "WAITING FOR EVAL",
    "EVALUATING",
    "WAITING FOR DIAGNOSIS",
    "DIAGNOSING",
    "WAITING FOR INPUT",
    "DONE",
}

REQUIRED_FIELDS = {
    "supervisor",
    "project",
    "status",
    "prior_status",
    "driver",
    "cron_id",
    "created",
    "iteration",
    "session_skill_count",
    "round",
    "meta_plan",
    "inner_loop",
    "inner_slug",
    "last_eval",
    "last_diagnosis",
    "evaluated_commit",
    "agreement_revision",
    "operation",
}

OPERATION_FIELDS = (
    "id",
    "phase",
    "round",
    "agreement_revision",
    "code_commit",
    "meta_plan",
    "goal_folder",
    "report",
    "source_vault_commit",
)

INTEGER_FIELDS = {"iteration", "session_skill_count", "round"}
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
OPERATION_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _frontmatter_parts(path: Path) -> tuple[dict, bytes]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise StateError(f"cannot read state {path}: {exc}") from exc

    lines = data.splitlines(keepends=True)
    if not lines or lines[0].rstrip(b"\r\n") != b"---":
        raise StateError("state must begin with a frontmatter delimiter")

    closing = None
    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip(b"\r\n") == b"---":
            closing = index
            break
    if closing is None:
        raise StateError("state frontmatter has no closing delimiter")

    try:
        source = b"".join(lines[1:closing]).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StateError("state frontmatter is not valid UTF-8") from exc
    body = b"".join(lines[closing + 1 :])
    return _parse_frontmatter(source), body


def _parse_scalar(key: str, value: str):
    if "\n" in value or "\r" in value:
        raise StateError(f"invalid multiline value for {key}")
    if key in INTEGER_FIELDS or key == "round":
        if not re.fullmatch(r"-?[0-9]+", value):
            return value
        return int(value)
    return value


def _parse_frontmatter(source: str) -> dict:
    result: dict = {}
    operation: dict | None = None
    in_operation = False

    for number, raw_line in enumerate(source.splitlines(), start=2):
        if not raw_line.strip():
            raise StateError(f"blank line in frontmatter at line {number}")
        if raw_line.startswith(("\t", "   ")):
            raise StateError(f"unsupported indentation at line {number}")

        if raw_line.startswith("  "):
            if not in_operation or operation is None:
                raise StateError(f"nested field outside operation at line {number}")
            nested = raw_line[2:]
            if ":" not in nested:
                raise StateError(f"malformed operation field at line {number}")
            key, value = nested.split(":", 1)
            if not KEY_RE.fullmatch(key) or (value and not value.startswith(" ")):
                raise StateError(f"malformed operation field at line {number}")
            if key in operation:
                raise StateError(f"duplicate operation key: {key}")
            scalar = value[1:] if value.startswith(" ") else ""
            operation[key] = _parse_scalar(key, scalar) if key == "round" else scalar
            continue

        in_operation = False
        if ":" not in raw_line:
            raise StateError(f"malformed frontmatter field at line {number}")
        key, value = raw_line.split(":", 1)
        if not KEY_RE.fullmatch(key) or (value and not value.startswith(" ")):
            raise StateError(f"malformed frontmatter field at line {number}")
        if key in result:
            raise StateError(f"duplicate frontmatter key: {key}")
        scalar = value[1:] if value.startswith(" ") else ""
        if key == "operation":
            if scalar:
                raise StateError("operation must be a mapping")
            operation = {}
            result[key] = operation
            in_operation = True
        else:
            result[key] = _parse_scalar(key, scalar)

    return result


def _require_string(mapping: dict, key: str, *, empty: bool = True) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or (not empty and not value):
        qualifier = "nonempty string" if not empty else "string"
        raise StateError(f"{key} must be a {qualifier}")
    if "\n" in value or "\r" in value:
        raise StateError(f"{key} must be a single-line string")
    return value


def _validate_operation(document: dict) -> None:
    operation = document["operation"]
    if not isinstance(operation, dict):
        raise StateError("operation must be a mapping")
    missing = set(OPERATION_FIELDS) - set(operation)
    extra = set(operation) - set(OPERATION_FIELDS)
    if missing:
        raise StateError(f"operation is missing fields: {', '.join(sorted(missing))}")
    if extra:
        raise StateError(f"operation has unknown fields: {', '.join(sorted(extra))}")

    for key in OPERATION_FIELDS:
        if key == "round":
            continue
        _require_string(operation, key)

    status = document["status"]
    populated = any(value != "" for value in operation.values())
    if not populated:
        if status in RECOVER_READY:
            raise StateError(f"operation record is required for transient status {status}")
        return

    if document['agreement_revision'] == 'PENDING':
        raise StateError('bootstrap PENDING agreement must be adopted before reserving an operation')
    phase = operation["phase"]
    if phase not in RECOVER_READY:
        raise StateError(f"unknown operation phase: {phase or '<empty>'}")
    operation_id = operation["id"]
    if not OPERATION_ID_RE.fullmatch(operation_id):
        raise StateError("operation id must be 32 lowercase hexadecimal characters")
    operation_round = operation["round"]
    if not isinstance(operation_round, int) or isinstance(operation_round, bool) or operation_round <= 0:
        raise StateError("operation round must be a positive integer")
    if operation_round != document["round"]:
        raise StateError("operation round does not match project round")
    if operation["agreement_revision"] != document["agreement_revision"]:
        raise StateError("operation agreement_revision does not match project state")

    for key in ("agreement_revision", "meta_plan", "goal_folder", "source_vault_commit"):
        if not operation[key]:
            raise StateError(f"operation {key} is required for {phase}")
    if phase == "META-PLANNING":
        if operation["code_commit"]:
            raise StateError("operation code_commit must be empty for META-PLANNING")
        if operation["report"]:
            raise StateError("operation report must be empty for META-PLANNING")
    else:
        for key in ("code_commit", "report"):
            if not operation[key]:
                raise StateError(f"operation {key} is required for {phase}")

    if status in RECOVER_READY and phase != status:
        raise StateError(f"operation phase {phase} does not match transient status {status}")


def _validate_state(document: dict) -> None:
    if not isinstance(document, dict):
        raise StateError("state must be a mapping")
    missing = REQUIRED_FIELDS - set(document)
    if missing:
        raise StateError(f"state is missing required fields: {', '.join(sorted(missing))}")

    supervisor = _require_string(document, "supervisor", empty=False)
    if supervisor not in {"superagent", "supercode"}:
        raise StateError(f"unknown supervisor: {supervisor}")
    _require_string(document, "project", empty=False)
    _require_string(document, "agreement_revision", empty=False)
    for key in (
        "status",
        "prior_status",
        "driver",
        "cron_id",
        "created",
        "meta_plan",
        "inner_loop",
        "inner_slug",
        "last_eval",
        "last_diagnosis",
        "evaluated_commit",
    ):
        _require_string(document, key)

    status = document["status"]
    if status not in STATUSES:
        raise StateError(f"unknown status: {status}")
    prior_status = document["prior_status"]
    if prior_status and prior_status not in STATUSES - {"WAITING FOR INPUT"}:
        raise StateError(f"unknown prior_status: {prior_status}")
    if status == "WAITING FOR INPUT" and not prior_status:
        raise StateError("WAITING FOR INPUT requires prior_status")
    if status != "WAITING FOR INPUT" and prior_status:
        raise StateError("prior_status is valid only while WAITING FOR INPUT")

    round_value = document["round"]
    if not isinstance(round_value, int) or isinstance(round_value, bool) or round_value <= 0:
        raise StateError("round must be a positive integer")
    for key in ("iteration", "session_skill_count"):
        value = document[key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise StateError(f"{key} must be a nonnegative integer")

    _validate_operation(document)


def read_state(path: Path) -> dict:
    """Read and validate one coding-loop state file."""
    document, _body = _frontmatter_parts(Path(path))
    _validate_state(document)
    return document


def _git_output(path: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise StateError(f"cannot resolve Git identity for {path}") from exc
    return result.stdout.strip()


def _physical_directory(path: Path, label: str) -> Path:
    try:
        physical = Path(path).expanduser().resolve(strict=True)
    except OSError as exc:
        raise StateError(f"{label} does not resolve to an existing directory: {path}") from exc
    if not physical.is_dir():
        raise StateError(f"{label} is not a directory: {physical}")
    return physical


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def project_identity(repo: Path, vault: Path, project: Path) -> dict:
    """Resolve physical project roots and the canonical stored project locator."""
    repo_input = _physical_directory(Path(repo), "repo")
    common_dir = Path(
        _git_output(repo_input, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve(strict=True)
    physical_repo = common_dir.parent
    physical_vault = _physical_directory(Path(vault), "vault")
    physical_project = _physical_directory(Path(project), "project")

    if physical_project == physical_vault or not _is_within(physical_project, physical_vault):
        raise StateError(f"project must be contained in configured vault {physical_vault}")

    if _is_within(physical_vault, physical_repo):
        stored_project = physical_project.relative_to(physical_repo).as_posix()
    else:
        try:
            vault_git_root = Path(
                _git_output(physical_vault, "rev-parse", "--show-toplevel")
            ).resolve(strict=True)
        except StateError as exc:
            raise StateError("external vault must be its own Git repository") from exc
        if vault_git_root != physical_vault:
            raise StateError("external vault must be its own Git repository")
        stored_project = str(physical_project)

    return {
        "repo": str(physical_repo),
        "vault": str(physical_vault),
        "project": str(physical_project),
        "stored_project": stored_project,
    }


def _operation_with_identity(current: dict, updated: dict) -> dict:
    prepared = dict(updated)
    operation = prepared.get("operation")
    if not isinstance(operation, dict):
        return prepared
    operation = dict(operation)
    prepared["operation"] = operation
    phase = operation.get("phase")
    if not phase:
        return prepared

    previous = current.get("operation")
    same_phase = (
        isinstance(previous, dict)
        and previous.get("phase") == phase
        and previous.get("round") == operation.get("round")
    )
    if same_phase and previous.get("id"):
        supplied = operation.get("id")
        if supplied and supplied != previous["id"]:
            raise StateError("operation id cannot change during a phase retry")
        operation["id"] = previous["id"]
    elif operation.get("id"):
        raise StateError("new operation id must be generated by the state helper")
    else:
        operation["id"] = uuid.uuid4().hex
    if phase == 'META-PLANNING' and prepared.get('meta_authorization_json'):
        authorization = json.loads(prepared['meta_authorization_json'])
        if not isinstance(authorization, dict): raise StateError('author META authorization must be an object')
        if (authorization.get('project') != prepared['project'] or authorization.get('round') != operation['round'] or
                authorization.get('agreement_revision') != operation['agreement_revision']):
            raise StateError('author META authorization does not match reserved project/round/agreement')
        if authorization.get('operation_id') not in {'', operation['id']}:
            raise StateError('author META authorization is already bound to another operation')
        authorization['operation_id'] = operation['id']
        prepared['meta_authorization_json'] = json.dumps(authorization, sort_keys=True, separators=(',', ':'))
    return prepared


def _serialize_state(document: dict) -> bytes:
    lines = ["---"]
    for key, value in document.items():
        if not KEY_RE.fullmatch(key):
            raise StateError(f"invalid frontmatter key: {key}")
        if key == "operation":
            lines.append("operation:")
            for operation_key in OPERATION_FIELDS:
                operation_value = value[operation_key]
                lines.append(f"  {operation_key}: {operation_value}")
        else:
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                raise StateError(f"unsupported scalar value for {key}")
            if isinstance(value, str) and ("\n" in value or "\r" in value):
                raise StateError(f"unsupported multiline value for {key}")
            lines.append(f"{key}: {value}")
    lines.extend(("---", ""))
    return "\n".join(lines).encode("utf-8")


def replace_state(path: Path, expected: dict, updated: dict, *, pending_decision: str | None = None, decision_receipt: str | None = None) -> None:
    """Atomically replace matching state frontmatter while preserving its body."""
    state_path = Path(path)
    current, body = _frontmatter_parts(state_path)
    _validate_state(current)
    _validate_state(expected)
    if current != expected:
        raise StateError("stale state: current frontmatter does not match expected state")

    if not isinstance(updated, dict):
        raise StateError("updated state must be a mapping")
    missing = REQUIRED_FIELDS - set(updated)
    if missing:
        raise StateError(f"updated state is missing required fields: {', '.join(sorted(missing))}")
    merged = dict(current)
    merged.update(updated)
    prepared = _operation_with_identity(current, merged)
    _validate_state(prepared)
    frontmatter = _serialize_state(prepared)
    if pending_decision is not None:
        text = body.decode('utf-8')
        section = re.compile(r'(?ms)^## Pending decision[^\n]*\n.*?(?=^## |\Z)')
        replacement = '## Pending decision\n\n' + pending_decision + '\n\n'
        text = section.sub(lambda _: replacement, text, count=1) if section.search(text) else replacement + text
        body = text.encode('utf-8')
    if decision_receipt is not None:
        text = body.decode('utf-8')
        section = re.compile(r'(?ms)^## Decisions[^\n]*\n.*?(?=^## |\Z)')
        if section.search(text):
            text = section.sub(lambda match: match[0].rstrip() + '\n' + decision_receipt + '\n\n', text, count=1)
        else:
            text += '\n## Decisions\n\n' + decision_receipt + '\n'
        body = text.encode('utf-8')
    try:
        mode = state_path.stat().st_mode & 0o7777
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{state_path.name}.", suffix=".tmp", dir=state_path.parent
        )
        try:
            os.fchmod(descriptor, mode)
            with os.fdopen(descriptor, "wb") as temporary:
                descriptor = -1
                temporary.write(frontmatter)
                temporary.write(body)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, state_path)
        except BaseException:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
    except OSError as exc:
        raise StateError(f"cannot atomically replace state {state_path}: {exc}") from exc


def recover_ready(status: str) -> str:
    """Map a persisted transient status to its retry-ready status."""
    return RECOVER_READY.get(status, status)


def _load_json(path: Path) -> dict:
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise StateError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        with Path(path).open(encoding="utf-8") as source:
            value = json.load(source, object_pairs_hook=reject_duplicates)
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot read JSON state {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StateError(f"JSON state {path} must contain an object")
    return value


def acquire_gate_lock(lock_dir: Path, owner: int, steal_min: str = '90') -> bool:
    """Acquire project L3 under a crash-released, persistent reclamation guard.

    The sibling <lock-dir>.reclaim is an advisory-lock inode, never unlinked.
    Its fcntl lock covers fresh mkdir too, plus stale re-read/removal and owner
    publication. A delayed contender therefore cannot remove a new live owner.
    Only project callers use this helper; legacy goal ticks remain Python-free.
    """
    import datetime
    import fcntl
    import shutil

    if owner <= 0:
        raise StateError('lock owner must be a positive process ID')
    lock_dir = Path(lock_dir)
    guard = lock_dir.with_name(lock_dir.name + '.reclaim')
    descriptor = os.open(guard, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, 'a+b') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        try:
            lock_dir.mkdir()
        except FileExistsError:
            try:
                previous = (lock_dir / 'owner').read_text().strip()
            except (OSError, UnicodeError):
                previous = ''
            stale = False
            if re.fullmatch(r'[0-9]+', previous):
                try:
                    os.kill(int(previous), 0)
                except ProcessLookupError:
                    stale = True
                except (PermissionError, OverflowError):
                    return False
                else:
                    return False
            if not stale:
                try:
                    try:
                        acquired = datetime.datetime.fromisoformat((lock_dir / 'acquired').read_text().strip().replace('Z', '+00:00'))
                        if acquired.tzinfo is None:
                            return False
                    except FileNotFoundError:
                        # A killed acquirer may have created the directory but
                        # not published either file yet. Age this incomplete
                        # acquisition from its directory, never from a cached
                        # pre-guard observation.
                        acquired = datetime.datetime.fromtimestamp(lock_dir.stat().st_mtime, datetime.timezone.utc)
                    minutes = int(steal_min) if re.fullmatch(r'[0-9]+', steal_min) else 90
                    age = (datetime.datetime.now(datetime.timezone.utc) - acquired).total_seconds()
                    if age <= minutes * 60:
                        return False
                except (OSError, ValueError, UnicodeError):
                    return False
            shutil.rmtree(lock_dir)
            lock_dir.mkdir()
        (lock_dir / 'owner').write_text(str(owner) + '\n')
        (lock_dir / 'acquired').write_text(datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ') + '\n')
        return True


def _registration(path: Path) -> dict:
    """Read literal scheduler EnvironmentFile values; never evaluate shell code."""
    result = {}
    try:
        for line in path.read_text().splitlines():
            if not line or line.startswith('#'):
                continue
            key, sep, value = line.partition('=')
            if not sep or not KEY_RE.fullmatch(key) or key in result:
                raise StateError(f'malformed registration: {path}')
            result[key] = value
    except OSError as exc:
        raise StateError(f'missing registration: {path}') from exc
    return result


def _locator(repo: Path, value: str) -> str:
    return str((repo / value).resolve()) if value else ''


def _inner_state(path: Path) -> dict:
    # Legacy inner state can contain ci_wait mappings. Only scalar identities are
    # consumed; duplicate top-level fields and malformed framing fail closed.
    lines = path.read_text().splitlines()
    if not lines or lines[0] != '---' or '---' not in lines[1:]:
        raise StateError('malformed inner frontmatter')
    result = {}
    for line in lines[1:lines[1:].index('---') + 1]:
        if line.startswith((' ', '\t')) or not line:
            continue
        key, sep, value = line.partition(':')
        if not sep or not KEY_RE.fullmatch(key) or key in result:
            raise StateError('malformed or duplicate inner field')
        result[key] = value.strip()
    if not result.get('status') or not result.get('master_plan'):
        raise StateError('inner status/master_plan missing')
    return result


def building_gate(state: dict, inner: dict, registration: dict) -> dict:
    """Pure decision over normalized identities and verified META receipts.

    registration includes repo/expected_repo, loop_file/expected_loop,
    root_plan/expected_root_plan, goal_folder/expected_goal_folder, round,
    slug, supervisor, worker_complete, armed and active. Receipt fields are
    populated by gate_snapshot, never inferred from an inner DONE string.
    """
    result = {'action': 'INPUT', 'reason': '', 'identities': {}}
    def reject(reason):
        return dict(result, reason=reason)
    if state.get('status') != 'BUILDING':
        return dict(result, action='SKIP', reason='outer state changed; re-read next tick')
    if registration.get('error'):
        return reject(registration['error'])
    if not registration.get('worker_complete'):
        return reject('recorded META operation is not verified complete')
    if registration.get('supervisor', 'superagent') != 'superagent' or inner.get('supervisor', 'superagent') != 'superagent':
        return reject('inner supervisor identity mismatch')
    for actual, expected in (('repo', 'expected_repo'), ('loop_file', 'expected_loop'),
                             ('root_plan', 'expected_root_plan'), ('goal_folder', 'expected_goal_folder')):
        if not registration.get(actual) or registration[actual] != registration.get(expected):
            return reject(f'inner {actual} identity mismatch')
    if registration.get('slug') != state.get('inner_slug') or registration.get('round') != state.get('round'):
        return reject('inner slug/round identity mismatch')
    result['identities'] = {k: registration[k] for k in ('repo', 'loop_file', 'root_plan', 'goal_folder', 'round', 'slug')}
    status = inner.get('status')
    if status == 'DONE':
        return dict(result, action='EVALUATE', reason='verified inner DONE')
    known = {'WAITING FOR PLAN', 'PLANNING', 'WAITING FOR RUN', 'RUNNING', 'WAITING FOR CI', 'WAITING FOR INPUT'}
    if status not in known:
        return reject('unknown inner status')
    if registration.get('armed') is not True and registration.get('active') is not True:
        return reject('inner is stopped or scheduler state is unavailable; explicitly resume the inner registration')
    if status == 'WAITING FOR INPUT':
        return dict(result, action='SKIP', reason='inner WAITING FOR INPUT; answer the inner decision')
    return dict(result, action='SKIP', reason=f'inner {status}; build remains pending')


def gate_snapshot(path: Path, repo: Path, vault: Path, conf: Path, slug: str,
                  armed: bool, active: bool, write: bool = False) -> dict:
    """Re-read all state/registration/evidence; caller holds L3 when write=True."""
    from _coding_loop_evidence import reconcile_operation
    current = read_state(path)
    registration = {}
    inner = {}
    if current['status'] != 'BUILDING':
        return building_gate(current, inner, registration)
    try:
        identity = project_identity(repo, vault, repo / current['project'])
        repo = Path(identity['repo'])
        context = acceptance_context(repo, Path(identity['vault']), Path(identity['project']),
                                     json.loads(current.get('binding_captures_json', '[]')))
        if context['agreement_revision'] != current['agreement_revision']:
            raise StateError('Agreement changed; author adoption required before BUILDING advancement')
        operation = current['operation']
        validate_operation_locations(operation, repo, Path(identity['vault']), Path(identity['project']))
        if operation.get('phase') != 'META-PLANNING' or current['agreement_revision'] == 'PENDING':
            raise StateError('BUILDING requires the recorded completed META operation and adopted agreement')
        receipt = reconcile_operation(repo, Path(identity['vault']), operation)
        if receipt.get('outcome') != 'INTEGRATED' or not receipt.get('worker_complete'):
            raise StateError('META completion not verified: ' + receipt.get('completion_reason', receipt.get('reason', 'missing receipts')))
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', current['inner_slug']) or slug != current['inner_slug']:
            raise StateError('inner slug changed or is invalid; retry from fresh scheduler observation')
        raw = _registration(conf / (slug + '.env'))
        inner_path = Path(_locator(repo, current['inner_loop']))
        inner = _inner_state(inner_path)
        root_plan = _locator(repo, inner['master_plan'])
        registration.update(repo=_locator(repo, raw.get('REPO', '')), expected_repo=str(repo),
                            loop_file=_locator(repo, raw.get('LOOP_FILE', '')), expected_loop=str(inner_path),
                            root_plan=root_plan, expected_root_plan=receipt['root_plan'],
                            goal_folder=str(Path(root_plan).parent.parent), expected_goal_folder=receipt['goal_folder'],
                            round=operation['round'], slug=raw.get('SUPERAGENT_SLUG', ''),
                            supervisor=raw.get('SUPERAGENT_SUPERVISOR', 'superagent'),
                            worker_complete=True, armed=armed, active=active)
        if current['meta_plan'] != operation['meta_plan']:
            raise StateError('state meta_plan does not match recorded operation')
    except (ValueError, OSError, KeyError) as exc:
        registration['error'] = str(exc)
    decision = building_gate(current, inner, registration)
    if write and decision['action'] in {'EVALUATE', 'INPUT'}:
        updated = dict(current)
        updated['status'] = 'WAITING FOR EVAL' if decision['action'] == 'EVALUATE' else 'WAITING FOR INPUT'
        updated['prior_status'] = '' if decision['action'] == 'EVALUATE' else 'BUILDING'
        updated['gate_reason'] = decision['reason']
        updated['pending_decision_owner'] = 'outer' if decision['action'] == 'INPUT' else ''
        pending = None
        if decision['action'] == 'INPUT':
            pending = f"owner: outer\nreason: {decision['reason']}\ninner: {current['inner_slug']}\nanswer:"
        replace_state(path, current, updated, pending_decision=pending)
    return decision


def prepare_project(repo: Path, vault: Path, project: Path, conf: Path, slug: str,
                    max_rounds: str, dirname: str, write: bool = False) -> dict:
    """Validate bootstrap/resume; evidence reconciliation remains supervisor-owned."""
    from _coding_loop_evidence import _section, _tables
    from datetime import date
    if not re.fullmatch(r'[1-9][0-9]*', max_rounds):
        raise StateError('SUPER_CODE_MAX_ITERATIONS must be a positive integer')
    identity = project_identity(repo, vault, project)
    if any('\n' in value or '\r' in value for value in identity.values()):
        raise StateError('multiline paths are unsupported')
    repo, project = Path(identity['repo']), Path(identity['project'])
    for name in ('prd.md', 'evaluation.md', 'knowledge-base.md'):
        if not re.search(r'^\*\*Date:\*\* .*\*\*Status:\*\* READY(?:\s|$)', '\n'.join((project / name).read_text().splitlines()[:3]), re.M):
            raise StateError(f'{name} is not READY')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', slug):
        raise StateError('slug must contain only letters, digits, dots, underscores or hyphens')
    if not dirname or Path(dirname).name != dirname or dirname in {'.', '..'}:
        raise StateError('loop-status dirname must be a single directory name')
    loop_dir = project / dirname
    if loop_dir.resolve().parent != project:
        raise StateError('loop-status directory must remain within the project')
    # State is local runtime data, and must already be ignored by the vault repo.
    ignored = subprocess.run(['git', '-C', str(project), 'check-ignore', '-q', '--', str(loop_dir / 'supercode.md')])
    if ignored.returncode:
        raise StateError('project loop-status directory must be Git-ignored (run init)')
    matches = []
    for path in sorted(loop_dir.glob('*.md')):
        current = read_state(path)
        if current['project'] == identity['stored_project']:
            if current['supervisor'] != 'supercode':
                raise StateError('state supervisor identity conflict')
            matches.append((path, current))
    if len(matches) > 1:
        raise StateError('multiple states name this project')
    loop_file = matches[0][0] if matches else loop_dir / 'supercode.md'
    registered_slugs = []
    for registration_file in sorted(conf.glob('*.env')):
        registration = _registration(registration_file)
        same_loop = _locator(repo, registration.get('LOOP_FILE', '')) == str(loop_file)
        selected_slug = registration_file.stem == slug
        if same_loop:
            registered_slugs.append(registration_file.stem)
        if (selected_slug or same_loop) and (not same_loop or _locator(repo, registration.get('REPO', '')) != str(repo)
                              or registration.get('SUPERAGENT_SUPERVISOR', 'superagent') != 'supercode'):
            raise StateError(f'registration collision for slug {slug}')
    if len(registered_slugs) > 1:
        raise StateError('project has multiple registered slugs')
    if registered_slugs:
        slug = registered_slugs[0]
    tables = _tables(_section((project / 'prd.md').read_text(), 'Iteration ledger'))
    if len(tables) != 1 or tables[0][0] != ['Round', 'Meta-plan', 'Goal folder', 'Inner loop', 'Eval report', 'Verdict']:
        raise StateError('project must have exactly one canonical iteration ledger table')
    rows = tables[0][1]
    rounds = []
    for row in rows:
        if len(row) != 6 or not re.fullmatch(r'[1-9][0-9]*', row[0].strip()):
            raise StateError('malformed project iteration ledger')
        rounds.append(int(row[0]))
    if len(set(rounds)) != len(rounds):
        raise StateError('duplicate ledger round')
    if matches:
        current = matches[0][1]
        if current['round'] < max(rounds, default=1):
            raise StateError('ledger is ahead of saved state; reconcile/adopt the current round before launch')
        # Bootstrap is intentionally deferred to the native supervisor's first tick.
        if current['agreement_revision'] == 'PENDING' and not current['operation'].get('phase'):
            return dict(identity, loop_file=str(loop_file), slug=slug, existing=True)
        # Recover only durable operation identities; legacy ledger rows cannot
        # substitute for them. Do not adopt a changed agreement here.
        try:
            context = acceptance_context(repo, Path(identity['vault']), project,
                                         json.loads(current.get('binding_captures_json', '[]')))
            updated, receipt = reconcile_phase(current, repo, Path(identity['vault']), context, int(max_rounds))
        except (ValueError, OSError) as exc:
            updated = _park(current, str(exc))
        if write and updated != current:
            pending = pending_with_answer(loop_file, updated['gate_reason']) if updated['status'] == 'WAITING FOR INPUT' else None
            replace_state(loop_file, current, updated, pending_decision=pending)
        return dict(identity, loop_file=str(loop_file), slug=slug, existing=True)
    current = {key: '' for key in REQUIRED_FIELDS}
    current.update(supervisor='supercode', project=identity['stored_project'], status='WAITING FOR META-PLAN',
                   driver='external', created=date.today().isoformat(), iteration=0, session_skill_count=0,
                   round=max(rounds, default=1), agreement_revision='PENDING',
                   operation={key: '' for key in OPERATION_FIELDS})
    if rows:
        row = rows[rounds.index(max(rounds))]
        current.update(status='WAITING FOR INPUT', prior_status='WAITING FOR META-PLAN',
                       meta_plan=row[1], inner_loop=row[3], last_eval=row[4],
                       adoption_goal_folder=row[2], adoption_verdict=row[5],
                       gate_reason='Existing ledger requires author adoption: no durable operation/agreement identity; reconcile recorded artifacts before resume',
                       pending_decision_owner='outer')
    if write:
        loop_dir.mkdir(parents=True, exist_ok=True)
        _validate_state(current)
        try:
            with loop_file.open('xb') as output:
                pending = ('owner: outer\nreason: ' + current['gate_reason'] + '\nanswer:\n') if rows else ''
                output.write(_serialize_state(current) + ('\n## Pending decision\n\n' + pending + '\n## Decisions\n\n## Iteration log\n').encode())
        except FileExistsError:
            raise StateError('state appeared during launch; retry without overwriting it')
    return dict(identity, loop_file=str(loop_file), slug=slug, existing=False)


def acceptance_context(repo: Path, vault: Path, project: Path, captures: list | None = None) -> dict:
    """Resolve typed KB sources and source-relative binding links before deduplication."""
    import hashlib
    from urllib.parse import urljoin
    from _coding_loop_evidence import agreement_fingerprint, _without_iteration_ledger, _tables, _path_at_main
    identity = project_identity(repo, vault, project)
    repo, vault, project = (Path(identity[k]) for k in ('repo', 'vault', 'project'))
    if captures is not None and not isinstance(captures, list):
        raise StateError('binding captures must be an array')
    supplied = {}
    for entry in captures or []:
        if not isinstance(entry, dict) or entry.get('locator') in supplied:
            raise StateError('invalid or duplicate binding capture')
        agreement_fingerprint(project, [entry])
        supplied[entry['locator']] = entry
    manifest, seen, scanned = [], set(), set()
    roots = {project / n for n in ('prd.md', 'evaluation.md', 'knowledge-base.md')}
    queue = []
    for path in sorted(roots):
        header = '\n'.join(path.read_text().splitlines()[:3])
        if not re.search(r'^\*\*Date:\*\* .*\*\*Status:\*\* READY(?:\s|$)', header, re.M):
            raise StateError(path.name + ' is not READY')
        queue.append((path, path.read_bytes(), str(path)))

    def add_capture(locator):
        entry = supplied.get(locator)
        if not entry: raise StateError(f'unresolved binding source: {locator}')
        if locator in seen: return
        path = Path(entry.get('path', entry.get('resolved_path', '')))
        manifest.append(entry); seen.add(locator)
        queue.append((path, path.read_bytes(), locator))

    def add_local(path):
        path = path.resolve()
        if not path.is_file(): raise StateError(f'missing binding source: {path}')
        if path in roots: return
        if not _is_within(path, repo) and not _is_within(path, vault):
            raise StateError(f'local binding is outside the configured repositories: {path}')
        canonical = str(path.relative_to(repo)) if _is_within(path, repo) else str(path)
        # Only fully resolved identities are deduplicated. Raw requirements.md is
        # not an identity: every referring directory must resolve its own target.
        if canonical in seen: return
        git_root = repo if _is_within(path, repo) else vault
        _, error = _path_at_main(git_root, path)
        if error: raise StateError(f'binding {canonical}: {error}')
        content = path.read_bytes()
        revision = _git_output(git_root, 'rev-parse', 'main:' + str(path.relative_to(git_root)))
        manifest.append(dict(locator=canonical, path=str(path), source_revision=revision,
                             sha256=hashlib.sha256(content).hexdigest()))
        seen.add(canonical)
        queue.append((path, content, str(path)))

    # Explicit prose-discovered captures supplement, never exempt, discovered sources.
    for locator in supplied: add_capture(locator)
    while queue:
        source, data, origin = queue.pop(0)
        if origin in scanned: continue
        scanned.add(origin)
        if source.name == 'prd.md' and source in roots:
            data = _without_iteration_ledger(data)
        try:
            text = data.decode('utf-8')
        except UnicodeError as exc:
            raise StateError(f'binding text needs a readable capture: {source}') from exc
        references = []
        generic = text
        if source == project / 'knowledge-base.md':
            for header, rows in _tables(text):
                if 'Locator' not in header: continue
                if 'Kind' not in header: raise StateError('knowledge-base locator table needs Kind')
                ki, li = header.index('Kind'), header.index('Locator')
                for row in rows:
                    if len(row) <= max(ki, li): raise StateError('malformed knowledge-base locator row')
                    kind, locator = row[ki].strip('` '), row[li].strip('` ')
                    references.append((kind, locator))
                    # Typed Locator cells must not also become untyped Markdown paths.
                    generic = generic.replace(row[li], '')
        references += [('link', x) for x in re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)', generic)]
        references += [('wiki', x.split('|', 1)[0]) for x in re.findall(r'\[\[([^\]\n]+)\]\]', generic)]
        references += [('file-token', x) for x in re.findall(r'`([^`\n]+\.(?:md|txt|pdf|docx))`', generic)]
        for kind, raw in references:
            locator = raw.strip().strip('<>')
            if not locator or locator.startswith('#'): continue
            locator = locator.split('#', 1)[0]
            if kind in {'doc-url', 'context7'} or (kind in {'link', 'wiki', 'file-token'} and re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', locator)):
                add_capture(locator)
            elif kind == 'repo-glob':
                if Path(locator).is_absolute() or '..' in Path(locator).parts:
                    raise StateError('repo-glob must remain within the primary repository')
                matches = sorted(p for p in repo.glob(locator) if p.is_file())
                if not matches: raise StateError(f'repo-glob matches no file: {locator}')
                for path in matches: add_local(path)
            elif kind == 'entry-point':
                filename, sep, symbol = locator.partition(':')
                if not sep or not symbol: raise StateError('entry-point needs path:symbol')
                path = repo / filename
                if Path(filename).is_absolute() or not _is_within(path.resolve(), repo):
                    raise StateError('entry-point must remain within the primary repository')
                if not path.is_file() or symbol not in path.read_text():
                    raise StateError(f'entry-point not found: {locator}')
                add_local(path)
            elif kind in {'instructions', 'repo-file', 'sample-code'}:
                if Path(locator).is_absolute() or not _is_within((repo / locator).resolve(), repo):
                    raise StateError(kind + ' must remain within the primary repository')
                add_local(repo / locator)
            elif kind in {'link', 'wiki', 'file-token'}:
                if re.match(r'^https?://', origin) and kind == 'link':
                    add_capture(urljoin(origin, locator))
                    continue
                if kind == 'link':
                    # Markdown links are relative to the source document, even if a
                    # same-named target happens to exist elsewhere in the repository.
                    path = source.parent / locator
                else:
                    candidates = []
                    for base in (source.parent, repo, vault):
                        candidate = (base / locator).resolve()
                        if not candidate.exists() and not candidate.suffix: candidate = candidate.with_suffix('.md')
                        if candidate.is_file() and candidate not in candidates: candidates.append(candidate)
                    if len(candidates) != 1: raise StateError(f'missing or ambiguous binding source: {locator}')
                    path = candidates[0]
                add_local(path)
            else:
                raise StateError(f'unknown knowledge-base kind: {kind}')
    return dict(identity, manifest=manifest, agreement_revision=agreement_fingerprint(project, manifest))


def _park(document: dict, reason: str, kind: str = 'retry') -> dict:
    prior = document['prior_status'] if document['status'] == 'WAITING FOR INPUT' else recover_ready(document['status'])
    return dict(document, status='WAITING FOR INPUT', prior_status=prior, gate_reason=reason,
                pending_decision_owner='outer', pending_kind=kind)


def _next_round(document: dict) -> dict:
    history = {key: document[key] for key in REQUIRED_FIELDS | {'eval_operation_id', 'eval_source_vault_commit', 'last_verdict'} if key in document}
    return dict(document, previous_round_json=json.dumps(history, sort_keys=True, separators=(',', ':')), meta_authorization_json='', round=document['round'] + 1, status='WAITING FOR META-PLAN', prior_status='',
                meta_plan='', inner_loop='', inner_slug='', operation={k: '' for k in OPERATION_FIELDS},
                pending_decision_owner='', pending_kind='', gate_reason='')


def validate_operation_locations(operation: dict, repo: Path, vault: Path, project: Path) -> None:
    """Bind all output locators to this project and its physical configured vault."""
    for field in ('meta_plan', 'goal_folder', 'report'):
        value = operation.get(field)
        if not value: continue
        physical = Path(_locator(repo, value))
        if not _is_within(physical, vault): raise StateError(field + ' is outside the configured vault')
        canonical = str(physical.relative_to(repo)) if _is_within(physical, repo) else str(physical)
        if value != canonical: raise StateError(field + ' must use its canonical stored locator')
        if field == 'meta_plan' and not _is_within(physical, project / 'meta-plans'):
            raise StateError('meta-plan belongs to a different project')
        if field == 'report':
            folder = 'diagnoses' if operation['phase'] == 'DIAGNOSING' else 'eval-reports'
            if not _is_within(physical, project / folder): raise StateError('report belongs to a different project/phase')


def reconcile_phase(document: dict, repo: Path, vault: Path, context: dict, maximum: int) -> tuple[dict, dict]:
    """Validate/reconcile one persisted phase, without dispatching any worker."""
    from _coding_loop_evidence import reconcile_operation, validate_evaluation, validate_diagnosis, _sync_error
    if maximum < 1: raise StateError('SUPER_CODE_MAX_ITERATIONS must be positive')
    project = Path(context['project'])
    for root, remote in ((repo, True), (vault, False)):
        error = _sync_error(root, remote_required=remote)
        if error: return _park(document, error), {'outcome': 'CONFLICT', 'reason': error}
        if root == repo and _is_within(vault, repo): break
    from _coding_loop_evidence import _path_at_main
    artifact_repo = vault if not _is_within(vault, repo) else repo
    for name in ('prd.md', 'evaluation.md', 'knowledge-base.md'):
        _, error = _path_at_main(artifact_repo, project / name)
        if error: return _park(document, name + ': ' + error), {'outcome': 'CONFLICT', 'reason': error}
    fingerprint = context['agreement_revision']
    if document['agreement_revision'] == 'PENDING' and not document.get('adoption_goal_folder'):
        document = dict(document, agreement_revision=fingerprint)
    elif fingerprint != document['agreement_revision']:
        result = _park(document, 'Agreement changed; author must record adopt-agreement ' + fingerprint, 'agreement')
        result['proposed_agreement_revision'] = fingerprint
        return result, {'outcome': 'CONFLICT', 'reason': result['gate_reason']}
    operation = document['operation']
    if document['status'] in {'DONE', 'WAITING FOR INPUT'}:
        return document, {'outcome': 'PARKED'}
    if document['round'] > maximum:
        return dict(_park(document, 'Round exceeds configured limit; explicit raise-limit answer required', 'limit'), pending_limit_action='resume'), {'outcome': 'PARKED'}
    if not operation.get('phase'):
        return document, {'outcome': 'ABSENT'}
    try:
        validate_operation_locations(operation, repo, vault, project)
    except StateError as exc:
        return _park(document, str(exc)), {'outcome': 'CONFLICT', 'reason': str(exc)}
    receipt = reconcile_operation(repo, vault, operation)
    if receipt['outcome'] == 'CONFLICT':
        return _park(document, receipt['reason']), receipt
    if receipt['outcome'] == 'ABSENT' or not receipt.get('worker_complete'):
        return dict(document, status=recover_ready(document['status'])), receipt
    phase = operation['phase']
    if phase == 'META-PLANNING':
        if document['status'] in {'META-PLANNING', 'WAITING FOR META-PLAN'}:
            document = dict(document, status='WAITING FOR BUILD', meta_plan=operation['meta_plan'])
        return document, receipt
    if phase == 'EVALUATING':
        result = validate_evaluation(Path(receipt['report']), project / 'evaluation.md', operation)
        if result['errors'] or (result['declared_verdict'] == 'PASS' and result['verdict'] != 'PASS'):
            return _park(document, 'Evaluation evidence invalid: ' + '; '.join(result['errors'])), receipt
        document = dict(document, last_eval=operation['report'], evaluated_commit=operation['code_commit'],
                        last_verdict=result['verdict'], status='DONE' if result['verdict'] == 'PASS' else 'WAITING FOR DIAGNOSIS')
        return document, receipt
    if phase == 'DIAGNOSING':
        # Keep the selected FAIL evaluation's independent operation/source identity.
        eval_path = Path(_locator(repo, document['last_eval']))
        expected = dict(round=document['round'], code_commit=operation['code_commit'],
                        agreement_revision=document['agreement_revision'],
                        operation_id=document.get('eval_operation_id', ''),
                        source_vault_commit=document.get('eval_source_vault_commit', ''))
        if not expected['operation_id'] or not expected['source_vault_commit']:
            return _park(document, 'Selected FAIL evaluation operation/source receipt is missing'), receipt
        eval_operation = dict(operation, phase='EVALUATING', id=expected['operation_id'],
                              source_vault_commit=expected['source_vault_commit'], report=document['last_eval'])
        eval_receipt = reconcile_operation(repo, vault, eval_operation)
        if eval_receipt.get('outcome') != 'INTEGRATED' or not eval_receipt.get('worker_complete'):
            return _park(document, 'Selected FAIL evaluation is no longer integrated'), receipt
        evaluated = validate_evaluation(eval_path, project / 'evaluation.md', expected)
        if evaluated['errors'] or evaluated['declared_verdict'] != 'FAIL':
            return _park(document, 'Selected FAIL evaluation is invalid'), receipt
        diagnosis = validate_diagnosis(Path(receipt['report']), dict(
            round=document['round'], operation_id=operation['id'], eval_report=document['last_eval'],
            evaluated_commit=operation['code_commit'], agreement_revision=document['agreement_revision'],
            source_vault_commit=operation['source_vault_commit'], failing_ids=evaluated['failing_ids'], missing_ids=evaluated['missing_ids']))
        document = dict(document, last_diagnosis=operation['report'])
        if diagnosis.get('errors') or not diagnosis.get('may_start_next_round'):
            return _park(document, 'Diagnosis requires author input: ' + '; '.join(diagnosis.get('errors', [])), 'author'), receipt
        if document['round'] >= maximum:
            return dict(_park(document, 'Repair diagnosed at round limit; record raise-limit N after raising configuration', 'limit'), pending_limit_action='next-round'), receipt
        return _next_round(document), receipt
    raise StateError('unknown operation phase')


def validate_legacy_adoption(document: dict, repo: Path, vault: Path) -> dict:
    """Resolve raw ledger cells as history only; never promote a legacy PASS."""
    from _coding_loop_evidence import _path_at_main
    artifact_repo = vault if not _is_within(vault, repo) else repo
    adopted = {}
    for field in ('meta_plan', 'adoption_goal_folder', 'last_eval'):
        value = document.get(field, '').strip()
        if value in {'', '-', '—', 'none'}:
            if field == 'last_eval': continue
            raise StateError('legacy adoption is missing ' + field)
        if value.startswith('[[') and value.endswith(']]'): value = value[2:-2].split('|', 1)[0]
        value = value.strip('`')
        path = Path(_locator(repo, value))
        if field == 'adoption_goal_folder':
            roots = sorted((path / 'master-plans').glob('*.md'))
            if len(roots) != 1: raise StateError('legacy goal must have exactly one integrated root plan')
            path = roots[0]
        elif not path.suffix: path = path.with_suffix('.md')
        if not _is_within(path, vault): raise StateError('legacy artifact is outside the configured vault')
        _, error = _path_at_main(artifact_repo, path)
        if error: raise StateError('legacy ' + field + ': ' + error)
        adopted['adopted_legacy_' + field] = str(path.relative_to(repo)) if _is_within(path, repo) else str(path)
    return adopted


def consume_answer(document: dict, answer: str, context: dict, maximum: int) -> dict:
    """Only explicit recorded answers may adopt agreement or raise a parked limit."""
    if document['status'] != 'WAITING FOR INPUT' or not answer.strip(): return document
    answer = answer.strip()
    from_round = document['round']
    kind = document.get('pending_kind', 'adoption' if document.get('adoption_goal_folder') else 'retry')
    if kind in {'agreement', 'adoption'}:
        fingerprint = context['agreement_revision']
        if answer != 'adopt-agreement ' + fingerprint:
            raise StateError('author adoption must name the exact newly resolved fingerprint')
        if document['round'] >= maximum: raise StateError('adoption requires room for a new round; raise configured limit first')
        document = _next_round(document)
        document.update(agreement_revision=fingerprint, adopted_agreement_revision=fingerprint)
    elif kind == 'limit':
        match = re.fullmatch(r'raise-limit ([1-9][0-9]*)', answer)
        if not match or int(match[1]) != maximum or maximum <= document['round']:
            raise StateError('raise-limit answer must match a configured limit above the current round')
        if document.get('pending_limit_action') == 'resume':
            document = dict(document, status=recover_ready(document['prior_status']), prior_status='', pending_decision_owner='', pending_kind='', gate_reason='')
        else:
            document = _next_round(document)
        document['adopted_max_rounds'] = str(maximum)
    elif kind == 'author':
        if answer != 'replan' or maximum <= document['round']:
            raise StateError('author must explicitly record replan with room for a new round, or adopt changed agreement')
        document = _next_round(document)
    elif answer == 'retry':
        document = dict(document, status=recover_ready(document['prior_status']), prior_status='', pending_decision_owner='', pending_kind='', gate_reason='')
    else:
        raise StateError('record retry for an operational retry; specification changes require author adoption')
    if kind in {'agreement', 'adoption', 'author'} and document['round'] == from_round + 1:
        authorization = dict(decision_id=uuid.uuid4().hex, project=document['project'], from_round=from_round,
                             round=document['round'], agreement_revision=document['agreement_revision'], answer=answer, operation_id='')
        document['meta_authorization_json'] = json.dumps(authorization, sort_keys=True, separators=(',', ':'))
    return dict(document, last_operator_answer=answer)


def pending_with_answer(path: Path, reason: str) -> str:
    body = _frontmatter_parts(path)[1].decode()
    block = re.search(r'(?ms)^## Pending decision[^\n]*\n(.*?)(?=^## |\Z)', body)
    answers = re.findall(r'(?m)^answer:[^\n]*$', block[1]) if block else []
    return 'owner: outer\nreason: ' + reason + '\n' + ('\n'.join(answers) if answers else 'answer:')


def phase_snapshot(path: Path, repo: Path, vault: Path, captures: list, maximum: int,
                   write: bool = False, owner: int = 0, answer: bool = False) -> dict:
    """Atomic validation seam for the native supervisor; never launches a model."""
    current = read_state(path)
    identity = project_identity(repo, vault, repo / current['project'])
    repo, vault = Path(identity['repo']), Path(identity['vault'])
    if write:
        lock = path.parent / ('.' + path.name + '.lockd')
        if owner <= 0 or (lock / 'owner').read_text().strip() != str(owner):
            raise StateError('write requires the caller-owned project L3 lock')
        os.kill(owner, 0)
    try:
        captures = captures if captures is not None else json.loads(current.get('binding_captures_json', '[]'))
        context = acceptance_context(repo, vault, Path(identity['project']), captures)
        working = dict(current, binding_captures_json=json.dumps(captures, separators=(',', ':')))
        if answer and current['status'] == 'WAITING FOR INPUT':
            body = _frontmatter_parts(path)[1].decode()
            block = re.search(r'(?ms)^## Pending decision[^\n]*\n(.*?)(?=^## |\Z)', body)
            answers = re.findall(r'(?m)^answer:\s*(\S[^\n]*)$', block[1]) if block else []
            if len(answers) > 1: raise StateError('multiple operator answers')
            if answers:
                # Detect changed agreement before interpreting an operational retry.
                if context['agreement_revision'] != current['agreement_revision'] and current['agreement_revision'] != 'PENDING':
                    working = dict(current, pending_kind='agreement')
                history = {}
                if current.get('adoption_goal_folder') and current['agreement_revision'] == 'PENDING':
                    history = validate_legacy_adoption(current, repo, vault)
                working = dict(consume_answer(working, answers[0], context, maximum), **history,
                               binding_captures_json=json.dumps(captures, separators=(',', ':')))
        updated, receipt = reconcile_phase(working, repo, vault, context, maximum)
    except (ValueError, OSError) as exc:
        updated, receipt = _park(current, str(exc)), {'outcome': 'CONFLICT', 'reason': str(exc)}
        # Invalid answers retain the original restriction and pending answer.
        updated['pending_kind'] = current.get('pending_kind', updated['pending_kind'])
    if updated['operation'].get('phase') == 'EVALUATING' and updated.get('last_eval') == updated['operation']['report']:
        updated = dict(updated, eval_operation_id=updated['operation']['id'], eval_source_vault_commit=updated['operation']['source_vault_commit'])
    if write and updated != current:
        pending = None
        authorization = updated.get('meta_authorization_json', '')
        decision_receipt = None
        if authorization and authorization != current.get('meta_authorization_json', ''):
            receipt_record = json.loads(authorization)
            receipt_record.pop('operation_id')
            decision_receipt = 'author-meta: ' + json.dumps(receipt_record, sort_keys=True, separators=(',', ':'))
        if updated['status'] == 'WAITING FOR INPUT':
            # Preserve a rejected answer for correction with answer.sh --replace.
            pending = pending_with_answer(path, updated['gate_reason']) if decision_receipt is None else 'owner: outer\nreason: ' + updated['gate_reason'] + '\nanswer:'
        elif current['status'] == 'WAITING FOR INPUT': pending = ''
        replace_state(path, current, updated, pending_decision=pending, decision_receipt=decision_receipt)
    return dict(state=updated, receipt=receipt)


def reserve_operation(path: Path, repo: Path, vault: Path, operation: dict,
                      maximum: int, owner: int, captures: list) -> dict:
    current = read_state(path)
    if maximum < 1 or current['round'] > maximum:
        raise StateError('round limit refuses operation reservation')
    lock = path.parent / ('.' + path.name + '.lockd')
    if owner <= 0 or (lock / 'owner').read_text().strip() != str(owner):
        raise StateError('reservation requires caller-owned project L3 lock')
    os.kill(owner, 0)
    captures = captures if captures is not None else json.loads(current.get('binding_captures_json', '[]'))
    context = acceptance_context(repo, vault, repo / current['project'], captures)
    repo, vault = Path(context['repo']), Path(context['vault'])
    prepared, receipt = reconcile_phase(current, repo, vault, context, maximum)
    if prepared['status'] not in {'WAITING FOR META-PLAN', 'WAITING FOR EVAL', 'WAITING FOR DIAGNOSIS'}:
        raise StateError('current phase is not ready for reservation: ' + prepared['status'])
    phase = {'WAITING FOR META-PLAN': 'META-PLANNING', 'WAITING FOR EVAL': 'EVALUATING',
             'WAITING FOR DIAGNOSIS': 'DIAGNOSING'}[prepared['status']]
    if operation.get('phase') != phase: raise StateError('reserved phase does not match ready state')
    if operation.get('agreement_revision') != context['agreement_revision']:
        raise StateError('operation agreement is not the resolved current fingerprint')
    previous = current['operation']
    if previous.get('phase') == phase and any(previous.get(k) != operation.get(k) for k in OPERATION_FIELDS if k != 'id'):
        raise StateError('retry must preserve all original operation identities and paths')
    project = Path(context['project'])
    validate_operation_locations(operation, repo, vault, project)
    if phase != 'META-PLANNING' and (operation['meta_plan'] != current['meta_plan'] or
                                   operation['goal_folder'] != previous['goal_folder']):
        raise StateError('later phase must retain the selected META/goal identities')
    artifact_repo = vault if not _is_within(vault, repo) else repo
    if previous.get('phase') != phase:
        if operation.get('source_vault_commit') != _git_output(artifact_repo, 'rev-parse', 'main'):
            raise StateError('new operation must freeze the current vault main SHA')
        if phase == 'EVALUATING' and operation.get('code_commit') != _git_output(repo, 'rev-parse', 'main'):
            raise StateError('evaluation must freeze the current code main SHA')
        if phase == 'DIAGNOSING' and operation.get('code_commit') != current['evaluated_commit']:
            raise StateError('diagnosis must retain the failed evaluation code SHA')
    updated = dict(prepared, status=phase, operation=operation, binding_captures_json=json.dumps(captures, separators=(',', ':')))
    replace_state(path, current, updated)
    return read_state(path)


def meta_entry(path: Path, repo: Path, vault: Path, conf: Path, operation: dict) -> dict:
    """Worker entry contract: verify registered state and durable author/repair authority.

    A prompt, an arbitrary authorization JSON packet, or a prior round's answer is
    insufficient. The worker reads this state and its Decisions receipt itself.
    """
    current = read_state(path)
    context = acceptance_context(repo, vault, repo / current['project'],
                                 json.loads(current.get('binding_captures_json', '[]')))
    repo, vault, project = (Path(context[key]) for key in ('repo', 'vault', 'project'))
    if current['supervisor'] != 'supercode' or path.resolve().parent.parent != project:
        raise StateError('META entry state is not the project supervisor state')
    matches = []
    for registration_path in conf.glob('*.env'):
        registration = _registration(registration_path)
        if _locator(repo, registration.get('LOOP_FILE', '')) != str(path.resolve()): continue
        if (registration.get('SUPERAGENT_SUPERVISOR') != 'supercode' or
                _locator(repo, registration.get('REPO', '')) != str(repo) or
                registration.get('SUPERAGENT_SLUG') != registration_path.stem):
            raise StateError('META entry registration identity mismatch')
        matches.append(registration_path)
    if len(matches) != 1: raise StateError('META entry needs exactly one matching registered supervisor')
    if current['operation'] != operation or operation.get('phase') != 'META-PLANNING':
        raise StateError('worker operation does not match reserved supervisor META operation')
    if current['status'] not in {'META-PLANNING', 'WAITING FOR META-PLAN'}:
        raise StateError('supervisor no longer authorizes this META worker phase')
    if context['agreement_revision'] != current['agreement_revision']:
        raise StateError('META entry agreement has changed')
    validate_operation_locations(operation, repo, vault, project)
    from _coding_loop_evidence import _commit_on_main, _sync_error
    for root, required in ((repo, True), (vault, False)):
        error = _sync_error(root, remote_required=required)
        if error: raise StateError('META entry sync gate: ' + error)
        if root == repo and _is_within(vault, repo): break
    artifact_repo = vault if not _is_within(vault, repo) else repo
    if not _commit_on_main(artifact_repo, operation['source_vault_commit']):
        raise StateError('META entry source-vault commit is not integrated')
    result = dict(project=current['project'], round=current['round'], agreement_revision=current['agreement_revision'],
                  operation_id=operation['id'])
    raw = current.get('meta_authorization_json')
    if raw:
        authorization = json.loads(raw)
        required = {'decision_id', 'project', 'from_round', 'round', 'agreement_revision', 'answer', 'operation_id'}
        if not isinstance(authorization, dict) or set(authorization) != required:
            raise StateError('malformed author META authorization')
        if not OPERATION_ID_RE.fullmatch(authorization['decision_id']): raise StateError('invalid author decision id')
        if any(authorization[key] != result[key] for key in ('project', 'round', 'agreement_revision', 'operation_id')):
            raise StateError('author META authorization identity mismatch')
        if authorization['from_round'] != current['round'] - 1:
            raise StateError('author META authorization is from a different round')
        if authorization['answer'] not in {'replan', 'adopt-agreement ' + current['agreement_revision']}:
            raise StateError('author META authorization has no explicit adoption/replan answer')
        expected = dict(authorization); expected.pop('operation_id')
        body = _frontmatter_parts(path)[1].decode()
        block = re.search(r'(?ms)^## Decisions[^\n]*\n(.*?)(?=^## |\Z)', body)
        records = []
        for line in block[1].splitlines() if block else []:
            if line.startswith('author-meta: '):
                record = json.loads(line[len('author-meta: '):])
                if record.get('decision_id') == authorization['decision_id']: records.append(record)
        if records != [expected]:
            raise StateError('author META entry lacks the exact consumed-answer Decisions receipt')
        return dict(result, entry='AUTHOR_APPROVED', answer=authorization['answer'], decision_id=authorization['decision_id'])
    if current['round'] == 1:
        return dict(result, entry='FIRST_ROUND')
    previous = json.loads(current.get('previous_round_json', '{}'))
    if (previous.get('round') != current['round'] - 1 or previous.get('agreement_revision') != current['agreement_revision'] or
            previous.get('operation', {}).get('phase') != 'DIAGNOSING'):
        raise StateError('autonomous META entry requires the previous exact FAIL and current-agreement REPAIR')
    _validate_state(previous)
    if (previous['last_diagnosis'] != previous['operation']['report'] or
            previous['evaluated_commit'] != previous['operation']['code_commit']):
        raise StateError('autonomous META predecessor summary does not match its selected diagnosis/code identity')
    # A diagnosed round may have been parked at its limit before an explicit
    # raised-limit answer. Revalidate its recorded diagnosis, not its parked tag.
    previous = dict(previous, status='DIAGNOSING', prior_status='')
    checked, receipt = reconcile_phase(previous, repo, vault, context, current['round'])
    if (checked['status'] != 'WAITING FOR META-PLAN' or checked['round'] != current['round'] or
            not receipt.get('worker_complete')):
        raise StateError('autonomous META entry refused: ' + checked.get('gate_reason', 'previous FAIL/REPAIR not verified'))
    return dict(result, entry='AUTONOMOUS_REPAIR', diagnosis=previous['last_diagnosis'], eval_report=previous['last_eval'])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    read_parser = subparsers.add_parser("read")
    read_parser.add_argument("state", type=Path)
    replace_parser = subparsers.add_parser("replace")
    replace_parser.add_argument("state", type=Path)
    replace_parser.add_argument("--expected", required=True, type=Path)
    replace_parser.add_argument("--updated", required=True, type=Path)
    lock_parser = subparsers.add_parser('acquire-lock')
    lock_parser.add_argument('lock_dir', type=Path)
    lock_parser.add_argument('--owner', type=int, required=True)
    lock_parser.add_argument('--steal-min', default='90')
    prepare_parser = subparsers.add_parser('prepare-project')
    for name in ('repo', 'vault', 'project', 'conf'):
        prepare_parser.add_argument('--' + name, type=Path, required=True)
    prepare_parser.add_argument('--slug', required=True)
    prepare_parser.add_argument('--max-rounds', default='10')
    prepare_parser.add_argument('--dirname', default='loop-status')
    prepare_parser.add_argument('--write', action='store_true')
    gate_parser = subparsers.add_parser('building-gate')
    gate_parser.add_argument('state', type=Path)
    for name in ('repo', 'vault', 'conf'):
        gate_parser.add_argument('--' + name, type=Path, required=True)
    gate_parser.add_argument('--slug', required=True)
    gate_parser.add_argument('--armed', choices=('true', 'false'), required=True)
    gate_parser.add_argument('--active', choices=('true', 'false'), required=True)
    gate_parser.add_argument('--write', action='store_true')
    context_parser = subparsers.add_parser('context')
    phase_parser = subparsers.add_parser('reconcile-phase')
    reserve_parser = subparsers.add_parser('reserve')
    reserve_parser.add_argument('state', type=Path)
    reserve_parser.add_argument('--operation', type=Path, required=True)
    reserve_parser.add_argument('--owner', type=int, default=0)
    reserve_parser.add_argument('--max-rounds', type=int, default=10)
    for item in (context_parser, phase_parser, reserve_parser):
        item.add_argument('--repo', type=Path, required=True)
        item.add_argument('--vault', type=Path, required=True)
        item.add_argument('--captures', type=Path)
    context_parser.add_argument('--project', type=Path, required=True)
    phase_parser.add_argument('state', type=Path)
    phase_parser.add_argument('--max-rounds', type=int, default=10)
    phase_parser.add_argument('--consume-answer', action='store_true')
    phase_parser.add_argument('--write', action='store_true')
    phase_parser.add_argument('--owner', type=int, default=0)
    meta_parser = subparsers.add_parser('meta-entry')
    meta_parser.add_argument('state', type=Path)
    for name in ('repo', 'vault', 'conf', 'operation'):
        meta_parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == 'meta-entry':
            print(json.dumps(meta_entry(args.state, args.repo, args.vault, args.conf, _load_json(args.operation)), sort_keys=True))
            return 0
        if args.command in {'context', 'reconcile-phase', 'reserve'}:
            captures = json.loads(args.captures.read_text()) if args.captures else None
            if captures is not None and not isinstance(captures, list): raise StateError('captures must be an array')
            if args.command == 'context':
                result = acceptance_context(args.repo, args.vault, args.project, captures)
            elif args.command == 'reserve':
                result = reserve_operation(args.state, args.repo, args.vault, _load_json(args.operation), args.max_rounds, args.owner, captures)
            else:
                result = phase_snapshot(args.state, args.repo, args.vault, captures, args.max_rounds,
                                        args.write, args.owner, args.consume_answer)
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.command == 'acquire-lock':
            return 0 if acquire_gate_lock(args.lock_dir, args.owner, args.steal_min) else 1
        if args.command == "read":
            json.dump(read_state(args.state), sys.stdout, sort_keys=True)
            sys.stdout.write("\n")
        elif args.command == 'prepare-project':
            result = prepare_project(args.repo, args.vault, args.project, args.conf, args.slug,
                                     args.max_rounds, args.dirname, args.write)
            for key in ('repo', 'project', 'stored_project', 'loop_file', 'slug'):
                if '\n' in result[key] or '\r' in result[key]:
                    raise StateError('multiline paths are unsupported')
                print(result[key])
        elif args.command == 'building-gate':
            result = gate_snapshot(args.state, args.repo, args.vault, args.conf, args.slug,
                                   args.armed == 'true', args.active == 'true', args.write)
            print(result['action'])
            print(result['reason'])
        else:
            replace_state(args.state, _load_json(args.expected), _load_json(args.updated))
    except (StateError, TypeError, OSError, ValueError) as exc:
        print(f"coding-loop-state: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

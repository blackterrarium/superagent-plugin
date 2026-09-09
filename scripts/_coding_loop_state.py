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


def replace_state(path: Path, expected: dict, updated: dict, *, pending_decision: str | None = None) -> None:
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
        operation = current['operation']
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
        # Recover only durable operation identities; legacy ledger rows cannot
        # substitute for them. Do not adopt a changed agreement here.
        if current['status'] in {'META-PLANNING', 'WAITING FOR META-PLAN'} and current['operation'].get('phase') == 'META-PLANNING':
            from _coding_loop_evidence import reconcile_operation
            receipt = reconcile_operation(repo, Path(identity['vault']), current['operation'])
            if receipt.get('outcome') == 'INTEGRATED' and receipt.get('worker_complete') and write:
                updated = dict(current, status='WAITING FOR BUILD', meta_plan=current['operation']['meta_plan'])
                replace_state(loop_file, current, updated)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    read_parser = subparsers.add_parser("read")
    read_parser.add_argument("state", type=Path)
    replace_parser = subparsers.add_parser("replace")
    replace_parser.add_argument("state", type=Path)
    replace_parser.add_argument("--expected", required=True, type=Path)
    replace_parser.add_argument("--updated", required=True, type=Path)
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
    args = parser.parse_args(argv)

    try:
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

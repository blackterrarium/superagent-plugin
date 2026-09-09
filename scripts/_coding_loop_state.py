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

    populated = any(value != "" for value in operation.values())
    if not populated:
        return

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

    status = document["status"]
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


def replace_state(path: Path, expected: dict, updated: dict) -> None:
    """Atomically replace matching state frontmatter while preserving its body."""
    state_path = Path(path)
    current, body = _frontmatter_parts(state_path)
    _validate_state(current)
    _validate_state(expected)
    if current != expected:
        raise StateError("stale state: current frontmatter does not match expected state")

    prepared = _operation_with_identity(current, updated)
    _validate_state(prepared)
    frontmatter = _serialize_state(prepared)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    read_parser = subparsers.add_parser("read")
    read_parser.add_argument("state", type=Path)
    replace_parser = subparsers.add_parser("replace")
    replace_parser.add_argument("state", type=Path)
    replace_parser.add_argument("--expected", required=True, type=Path)
    replace_parser.add_argument("--updated", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "read":
            json.dump(read_state(args.state), sys.stdout, sort_keys=True)
            sys.stdout.write("\n")
        else:
            replace_state(args.state, _load_json(args.expected), _load_json(args.updated))
    except (StateError, TypeError) as exc:
        print(f"coding-loop-state: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

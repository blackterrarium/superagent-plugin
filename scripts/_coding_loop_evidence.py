#!/usr/bin/env python3
"""Agreement fingerprints and committed evidence checks for coding-loop rounds."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable


class EvidenceError(ValueError):
    """Agreement or round evidence cannot be trusted."""


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
OPERATION_ID_RE = re.compile(r"^[0-9a-f]{32}$")
RESULTS = {"PASS", "FAIL"}
OPERATION_FIELDS = {
    "id",
    "phase",
    "round",
    "agreement_revision",
    "code_commit",
    "meta_plan",
    "goal_folder",
    "report",
    "source_vault_commit",
}


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        resolved = Path(path).expanduser().resolve(strict=True)
        if not resolved.is_file():
            raise OSError("not a regular file")
        return resolved.read_bytes()
    except OSError as exc:
        raise EvidenceError(f"cannot read {label} {path}: {exc}") from exc


def _without_iteration_ledger(data: bytes) -> bytes:
    ledger = re.search(
        br"(?m)^##[ \t]+Iteration ledger[ \t]*(?:\r?\n|$)", data
    )
    if ledger is None:
        return data
    following = re.search(br"(?m)^##[ \t]+", data[ledger.end() :])
    end = len(data) if following is None else ledger.end() + following.start()
    return data[: ledger.start()] + data[end:]


def agreement_fingerprint(project: Path, binding_manifest: list) -> str:
    """Hash the immutable agreement text and revision-labeled binding captures."""
    try:
        project_path = Path(project).expanduser().resolve(strict=True)
    except OSError as exc:
        raise EvidenceError(f"project does not resolve: {project}") from exc
    if not project_path.is_dir():
        raise EvidenceError(f"project is not a directory: {project_path}")
    if not isinstance(binding_manifest, list):
        raise EvidenceError("binding manifest must be an array")

    inputs = []
    for name in ("prd.md", "evaluation.md", "knowledge-base.md"):
        content = _read_bytes(project_path / name, name)
        if name == "prd.md":
            content = _without_iteration_ledger(content)
        inputs.append(
            {"locator": f"project:{name}", "sha256": hashlib.sha256(content).hexdigest()}
        )

    seen = {item["locator"] for item in inputs}
    for number, entry in enumerate(binding_manifest, start=1):
        if not isinstance(entry, dict):
            raise EvidenceError(f"binding {number} must be an object")
        missing = {
            key for key in ("locator", "source_revision", "sha256") if not entry.get(key)
        }
        captured = entry.get("path", entry.get("resolved_path"))
        if not captured:
            missing.add("path")
        if missing:
            raise EvidenceError(
                f"binding {number} is missing: {', '.join(sorted(missing))}"
            )
        locator = entry["locator"]
        revision = entry["source_revision"]
        digest = entry["sha256"]
        if not all(isinstance(value, str) for value in (locator, revision, digest, captured)):
            raise EvidenceError(f"binding {number} fields must be strings")
        if locator in seen:
            raise EvidenceError(f"duplicate binding locator: {locator}")
        if not SHA256_RE.fullmatch(digest):
            raise EvidenceError(f"binding {locator} has an invalid sha256 digest")
        captured_path = Path(captured).expanduser()
        if not captured_path.is_absolute():
            raise EvidenceError(f"binding {locator} path must be absolute")
        content = _read_bytes(captured_path, f"binding {locator}")
        if not content:
            raise EvidenceError(f"binding {locator} has no captured text")
        actual = hashlib.sha256(content).hexdigest()
        if actual != digest:
            raise EvidenceError(
                f"binding {locator} digest does not match captured text"
            )
        inputs.append(
            {
                "locator": locator,
                "source_revision": revision,
                "sha256": actual,
            }
        )
        seen.add(locator)

    canonical = json.dumps(
        sorted(inputs, key=lambda item: item["locator"]),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _decode(path: Path, label: str) -> str:
    data = _read_bytes(path, label)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceError(f"{label} is not valid UTF-8: {path}") from exc


def _section(text: str, name: str) -> str | None:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == f"## {name}":
            start = index + 1
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end])


def _split_markdown_row(line: str) -> list[str]:
    source = line.strip()
    if not source.startswith("|"):
        return []
    if source.endswith("|"):
        source = source[1:-1]
    else:
        source = source[1:]
    cells = []
    current = []
    escaped = False
    for character in source:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "|":
            cells.append("".join(current).strip().strip("`"))
            current = []
        else:
            current.append(character)
    if escaped:
        current.append("\\")
    cells.append("".join(current).strip().strip("`"))
    return cells


def _tables(section: str | None) -> list[tuple[list[str], list[list[str]]]]:
    if section is None:
        return []
    groups: list[list[str]] = []
    current: list[str] = []
    for line in section.splitlines():
        if line.lstrip().startswith("|"):
            current.append(line)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    parsed = []
    for group in groups:
        if len(group) < 2:
            continue
        header = _split_markdown_row(group[0])
        separator = _split_markdown_row(group[1])
        if not separator or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator):
            continue
        parsed.append((header, [_split_markdown_row(row) for row in group[2:]]))
    return parsed


def _evaluation_ids(text: str) -> tuple[dict[str, list[str]], list[str]]:
    found = {"C": [], "J": [], "AC": []}
    errors = []
    sections = {
        "C": "Command checks",
        "J": "Judged objectives",
        "AC": "Acceptance checklist",
    }
    for prefix, section_name in sections.items():
        tables = _tables(_section(text, section_name))
        if not tables:
            if prefix == "C":
                errors.append("evaluation is missing the Command checks table")
            continue
        header, rows = tables[0]
        if not header or header[0] != "Id":
            errors.append(f"evaluation {section_name} table has no Id column")
            continue
        for row in rows:
            if not row or not row[0]:
                continue
            identifier = row[0]
            if not re.fullmatch(rf"{prefix}[1-9][0-9]*", identifier):
                errors.append(f"invalid {prefix} id in evaluation: {identifier}")
                continue
            if identifier in found[prefix]:
                errors.append(f"duplicate evaluation id: {identifier}")
                continue
            found[prefix].append(identifier)
    return found, errors


def _report_results(text: str) -> tuple[dict[str, dict[str, str]], list[str]]:
    results = {"C": {}, "J": {}, "AC": {}}
    errors = []
    sections = {
        "C": "Command checks",
        "J": "Judged objectives",
    }
    for section_prefix, section_name in sections.items():
        for header, rows in _tables(_section(text, section_name)):
            if not header:
                continue
            first = header[0]
            prefix = "AC" if first == "AC" else section_prefix if first == "Id" else ""
            if not prefix:
                continue
            try:
                result_index = header.index("Result")
            except ValueError:
                errors.append(f"report {section_name} table has no Result column")
                continue
            for row in rows:
                if not row or not row[0]:
                    continue
                identifier = row[0]
                if not re.fullmatch(rf"{prefix}[1-9][0-9]*", identifier):
                    errors.append(f"invalid {prefix} id in report: {identifier}")
                    continue
                if identifier in results[prefix]:
                    errors.append(f"duplicate report result: {identifier}")
                    continue
                result = row[result_index] if result_index < len(row) else ""
                if result not in RESULTS:
                    errors.append(f"invalid result for {identifier}: {result or '<empty>'}")
                    continue
                results[prefix][identifier] = result
    return results, errors


def _label_values(text: str, label: str) -> list[str]:
    pattern = re.compile(
        rf"\*\*{re.escape(label)}:\*\*\s*`?([^`·\r\n]+?)`?\s*(?=·|\r?$)",
        re.MULTILINE | re.IGNORECASE,
    )
    return [match.group(1).strip() for match in pattern.finditer(text)]


def _single_label(text: str, label: str, errors: list[str]) -> str:
    values = _label_values(text, label)
    unique = list(dict.fromkeys(values))
    if len(unique) > 1:
        errors.append(f"conflicting {label.lower()} values in report")
    return unique[0] if len(unique) == 1 else ""


def _report_identity(text: str) -> tuple[dict[str, object], list[str]]:
    errors: list[str] = []
    round_text = _single_label(text, "Round", errors)
    code_commit = _single_label(text, "Commit evaluated", errors)
    if not code_commit:
        environment = _section(text, "Environment") or ""
        commits = re.findall(r"(?mi)^-\s*commit:\s*`([^`]+)`", environment)
        unique = list(dict.fromkeys(commits))
        if len(unique) > 1:
            errors.append("conflicting code_commit values in report")
        elif unique:
            code_commit = unique[0]
    identity: dict[str, object] = {
        "status": _single_label(text, "Status", errors),
        "round": int(round_text) if round_text.isdigit() else None,
        "code_commit": code_commit,
        "agreement_revision": _single_label(text, "Agreement revision", errors),
        "operation_id": _single_label(text, "Operation", errors),
        "source_vault_commit": _single_label(text, "Source vault commit", errors),
    }
    if round_text and not round_text.isdigit():
        errors.append(f"invalid round in report: {round_text}")
    return identity, errors


def validate_evaluation(report: Path, evaluation: Path, expected: dict) -> dict:
    """Validate report completeness, declared verdict, and revision identity."""
    errors: list[str] = []
    missing_ids: list[str] = []
    failing_ids: list[str] = []
    try:
        report_text = _decode(Path(report), "evaluation report")
        evaluation_text = _decode(Path(evaluation), "evaluation")
    except EvidenceError as exc:
        return {
            "verdict": "FAIL",
            "declared_verdict": "",
            "missing_ids": [],
            "failing_ids": [],
            "errors": [str(exc)],
            "identity": {},
        }
    if not isinstance(expected, dict):
        errors.append("expected identity must be an object")
        expected = {}

    identities, identity_errors = _report_identity(report_text)
    errors.extend(identity_errors)
    if identities.get("status") != "FINAL":
        errors.append("report status must be FINAL")
    if _section(evaluation_text, "Judged objectives") is None:
        errors.append("evaluation is missing the Judged objectives section")
    if _section(report_text, "Judged objectives") is None:
        errors.append("report is missing the Judged objectives section")
    expected_fields = {
        "round": ("round",),
        "code_commit": ("code_commit", "evaluated_commit"),
        "agreement_revision": ("agreement_revision",),
        "operation_id": ("operation_id", "id"),
        "source_vault_commit": ("source_vault_commit",),
    }
    for report_field, aliases in expected_fields.items():
        supplied = next((expected[key] for key in aliases if key in expected), None)
        if supplied in (None, ""):
            continue
        observed = identities.get(report_field)
        if observed in (None, ""):
            errors.append(f"report is missing {report_field}")
        elif observed != supplied:
            errors.append(
                f"{report_field} mismatch: expected {supplied}, found {observed}"
            )

    required, evaluation_errors = _evaluation_ids(evaluation_text)
    errors.extend(evaluation_errors)
    results, result_errors = _report_results(report_text)
    errors.extend(result_errors)
    for prefix in ("C", "J", "AC"):
        required_set = set(required[prefix])
        reported_set = set(results[prefix])
        missing_ids.extend(sorted(required_set - reported_set))
        extras = sorted(reported_set - required_set)
        if extras:
            errors.append(f"undeclared {prefix} results: {', '.join(extras)}")
        failing_ids.extend(
            identifier
            for identifier in required[prefix]
            if results[prefix].get(identifier) == "FAIL"
        )

    verdict_section = _section(report_text, "Verdict") or ""
    verdicts = re.findall(r"(?m)^\*\*(PASS|FAIL)\*\*", verdict_section)
    declared = verdicts[0] if len(verdicts) == 1 else ""
    if len(verdicts) != 1:
        errors.append("report must declare exactly one PASS or FAIL verdict")
    checks_pass = not errors and not missing_ids and not failing_ids
    computed = "PASS" if checks_pass else "FAIL"
    if declared and declared != computed:
        errors.append(
            f"declared verdict {declared} conflicts with validated verdict {computed}"
        )
        computed = "FAIL"
    return {
        "verdict": computed,
        "declared_verdict": declared,
        "missing_ids": sorted(set(missing_ids)),
        "failing_ids": sorted(set(failing_ids)),
        "errors": errors,
        "identity": identities,
        "required_ids": required,
    }


def _git(path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", str(path), *args],
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EvidenceError(f"Git check failed in {path}: {' '.join(args)}") from exc


def _git_text(path: Path, *args: str) -> str:
    return _git(path, *args).stdout.strip()


def _git_bytes(path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", str(path), *args],
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EvidenceError(f"Git check failed in {path}: {' '.join(args)}") from exc


def _primary_root(repo: Path) -> Path:
    common = Path(
        _git_text(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve(strict=True)
    return common.parent


def _within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_artifact(repo: Path, vault: Path, locator: str) -> Path:
    path = Path(locator).expanduser()
    if path.is_absolute():
        return path.resolve()
    if not _within(vault, repo):
        raise EvidenceError("external-vault artifact paths must be absolute")
    return (repo / path).resolve()


def _sync_error(git_root: Path, *, remote_required: bool) -> str:
    main = _git(git_root, "rev-parse", "--verify", "refs/heads/main", check=False)
    if main.returncode:
        return "repository has no local main ref"
    remotes = [line for line in _git_text(git_root, "remote").splitlines() if line]
    if not remotes and not remote_required:
        return ""
    upstream = _git_text(
        git_root, "for-each-ref", "--format=%(upstream)", "refs/heads/main"
    )
    if not upstream:
        return "main has no configured remote ref"
    remote_sha = _git(git_root, "rev-parse", "--verify", upstream, check=False)
    if remote_sha.returncode:
        return f"configured remote ref {upstream} is missing"
    if main.stdout.strip() != remote_sha.stdout.strip():
        return f"main is not synchronized with {upstream}"
    return ""


def _commit_resolves(git_root: Path, commit: str) -> bool:
    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
        return False
    return _git(
        git_root, "cat-file", "-e", f"{commit}^{{commit}}", check=False
    ).returncode == 0


def _commit_on_main(git_root: Path, commit: str) -> bool:
    return _git(
        git_root,
        "merge-base",
        "--is-ancestor",
        commit,
        "refs/heads/main",
        check=False,
    ).returncode == 0


def _path_at_main(git_root: Path, artifact: Path) -> tuple[str, str]:
    try:
        relative = artifact.relative_to(git_root).as_posix()
    except ValueError:
        return "", "artifact is outside its Git repository"
    dirty = _git_text(git_root, "status", "--porcelain", "--", relative)
    if dirty:
        return "", "artifact has uncommitted or untracked changes"
    tracked = _git(
        git_root, "cat-file", "-e", f"refs/heads/main:{relative}", check=False
    )
    if tracked.returncode:
        return "", "artifact is not tracked on main"
    commit = _git_text(
        git_root, "log", "-1", "--format=%H", "refs/heads/main", "--", relative
    )
    if not commit:
        return "", "artifact has no commit on main"
    return commit, ""


def _main_blob(git_root: Path, relative: str) -> bytes | None:
    result = _git_bytes(
        git_root, "show", f"refs/heads/main:{relative}", check=False
    )
    return result.stdout if result.returncode == 0 else None


def _decode_blob(data: bytes, label: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceError(f"{label} on main is not valid UTF-8") from exc


def _identity_matches(identity: dict[str, object], operation: dict) -> bool:
    if identity.get("status") != "FINAL":
        return False
    required = {
        "round": operation["round"],
        "agreement_revision": operation["agreement_revision"],
        "operation_id": operation["id"],
    }
    if operation["phase"] != "META-PLANNING":
        required["code_commit"] = operation["code_commit"]
    for field, expected in required.items():
        if identity.get(field) != expected:
            return False
    source = identity.get("source_vault_commit")
    return not source or source == operation["source_vault_commit"]


def _ledger_error(
    git_root: Path, report: Path, round_number: int, verdict: str
) -> str:
    project = report.parent.parent
    prd = project / "prd.md"
    try:
        relative = prd.relative_to(git_root).as_posix()
    except ValueError:
        return "project ledger is outside its Git repository"
    blob = _main_blob(git_root, relative)
    if blob is None:
        return "project ledger prd.md is missing on main"
    section = _section(_decode_blob(blob, "project ledger"), "Iteration ledger")
    tables = _tables(section)
    if not tables:
        return "project iteration ledger table is missing"
    header, rows = tables[0]
    try:
        round_index = header.index("Round")
        report_index = header.index("Eval report")
        verdict_index = header.index("Verdict")
    except ValueError:
        return "project iteration ledger has incompatible columns"
    matches = [
        row
        for row in rows
        if round_index < len(row) and row[round_index] == str(round_number)
    ]
    if len(matches) != 1:
        return f"project iteration ledger has {len(matches)} rows for round {round_number}"
    row = matches[0]
    if report_index >= len(row) or report.stem not in row[report_index]:
        return "project iteration ledger does not link the report"
    if verdict_index >= len(row) or row[verdict_index] != verdict:
        return "project iteration ledger verdict disagrees with the report"
    return ""


def reconcile_operation(repo: Path, vault: Path, operation: dict) -> dict:
    """Classify a recorded operation artifact using identity and Git integration."""
    try:
        if not isinstance(operation, dict) or set(operation) != OPERATION_FIELDS:
            raise EvidenceError("operation does not have the required state fields")
        if operation["phase"] not in {"META-PLANNING", "EVALUATING", "DIAGNOSING"}:
            raise EvidenceError(f"unknown operation phase: {operation['phase']}")
        if not isinstance(operation["round"], int) or operation["round"] <= 0:
            raise EvidenceError("operation round must be a positive integer")
        if not isinstance(operation["id"], str) or not OPERATION_ID_RE.fullmatch(operation["id"]):
            raise EvidenceError("operation id must be 32 lowercase hexadecimal characters")
        for field in ("agreement_revision", "meta_plan", "goal_folder", "source_vault_commit"):
            if not isinstance(operation[field], str) or not operation[field]:
                raise EvidenceError(f"operation {field} must be a nonempty string")
        if operation["phase"] != "META-PLANNING":
            for field in ("code_commit", "report"):
                if not isinstance(operation[field], str) or not operation[field]:
                    raise EvidenceError(f"operation {field} must be a nonempty string")
        repo_root = _primary_root(Path(repo).resolve(strict=True))
        vault_root = Path(vault).resolve(strict=True)
        external = not _within(vault_root, repo_root)
        artifact_repo = vault_root if external else repo_root
        if external:
            vault_git = Path(_git_text(vault_root, "rev-parse", "--show-toplevel")).resolve()
            if vault_git != vault_root:
                raise EvidenceError("external vault must be its own Git repository")
        sync_error = _sync_error(repo_root, remote_required=True)
        if sync_error:
            return {"outcome": "CONFLICT", "artifacts": [], "reason": sync_error}
        if external:
            sync_error = _sync_error(artifact_repo, remote_required=False)
            if sync_error:
                return {"outcome": "CONFLICT", "artifacts": [], "reason": sync_error}
        if operation["code_commit"] and not _commit_resolves(
            repo_root, operation["code_commit"]
        ):
            return {
                "outcome": "CONFLICT",
                "artifacts": [],
                "reason": "selected code_commit is not resolvable",
            }
        if operation["code_commit"] and not _commit_on_main(
            repo_root, operation["code_commit"]
        ):
            return {
                "outcome": "CONFLICT",
                "artifacts": [],
                "reason": "selected code_commit is not integrated on main",
            }
        if operation["source_vault_commit"] and not _commit_resolves(
            artifact_repo, operation["source_vault_commit"]
        ):
            return {
                "outcome": "CONFLICT",
                "artifacts": [],
                "reason": "source_vault_commit is not resolvable",
            }
        if operation["source_vault_commit"] and not _commit_on_main(
            artifact_repo, operation["source_vault_commit"]
        ):
            return {
                "outcome": "CONFLICT",
                "artifacts": [],
                "reason": "source_vault_commit is not integrated on main",
            }

        locator = (
            operation["goal_folder"]
            if operation["phase"] == "META-PLANNING"
            else operation["report"]
        )
        artifact = _resolve_artifact(repo_root, vault_root, locator)
        if operation["phase"] == "META-PLANNING":
            if not artifact.exists():
                return {"outcome": "ABSENT", "artifacts": [], "reason": "recorded artifact is absent"}
            if not artifact.is_dir():
                return {"outcome": "CONFLICT", "artifacts": [], "reason": "goal artifact is not a directory"}
            candidates = list((artifact / "master-plans").glob("*.md"))
            matching = []
            for candidate in candidates:
                text = _decode(candidate, "goal master plan")
                identity, _ = _report_identity(text)
                if identity["round"] == operation["round"] and Path(operation["meta_plan"]).stem in text:
                    matching.append(candidate)
            if len(matching) != 1:
                noun = "no" if not matching else "multiple"
                return {"outcome": "CONFLICT", "artifacts": [], "reason": f"{noun} matching goal master plans"}
            artifact = matching[0]
        else:
            try:
                relative = artifact.relative_to(artifact_repo).as_posix()
                relative_parent = artifact.parent.relative_to(artifact_repo).as_posix()
            except ValueError:
                return {"outcome": "CONFLICT", "artifacts": [], "reason": "recorded report is outside its Git repository"}
            dirty = _git_text(
                artifact_repo, "status", "--porcelain", "--", relative_parent
            )
            if dirty:
                return {"outcome": "CONFLICT", "artifacts": [], "reason": "report output has uncommitted or untracked changes"}
            integrated_paths = _git_text(
                artifact_repo,
                "ls-tree",
                "-r",
                "--name-only",
                "refs/heads/main",
                "--",
                relative_parent,
            ).splitlines()
            matching = []
            for candidate_relative in integrated_paths:
                candidate_path = Path(candidate_relative)
                if candidate_path.parent.as_posix() != relative_parent or candidate_path.suffix != ".md":
                    continue
                try:
                    blob = _main_blob(artifact_repo, candidate_relative)
                    if blob is None:
                        continue
                    identity, parse_errors = _report_identity(
                        _decode_blob(blob, "operation report")
                    )
                except EvidenceError:
                    continue
                if not parse_errors and _identity_matches(identity, operation):
                    matching.append((artifact_repo / candidate_relative).resolve())
            if len(matching) != 1:
                if not matching and _main_blob(artifact_repo, relative) is None and not artifact.exists():
                    return {"outcome": "ABSENT", "artifacts": [], "reason": "recorded artifact is absent"}
                noun = "no" if not matching else "multiple"
                return {"outcome": "CONFLICT", "artifacts": [], "reason": f"{noun} matching operation reports on main"}
            if matching[0] != artifact.resolve():
                return {"outcome": "CONFLICT", "artifacts": [], "reason": "matching report is not at the recorded path"}

        commit, reason = _path_at_main(artifact_repo, artifact)
        if reason:
            return {"outcome": "CONFLICT", "artifacts": [], "reason": reason}
        artifacts = [{"path": str(artifact.resolve()), "commit": commit}]
        if operation["phase"] == "EVALUATING":
            report_relative = artifact.relative_to(artifact_repo).as_posix()
            report_blob = _main_blob(artifact_repo, report_relative)
            if report_blob is None:
                return {"outcome": "CONFLICT", "artifacts": artifacts, "reason": "report is missing on main"}
            text = _decode_blob(report_blob, "evaluation report")
            verdict_section = _section(text, "Verdict") or ""
            verdicts = re.findall(r"(?m)^\*\*(PASS|FAIL)\*\*", verdict_section)
            if len(verdicts) != 1:
                return {"outcome": "CONFLICT", "artifacts": artifacts, "reason": "report has no unique verdict"}
            ledger_reason = _ledger_error(
                artifact_repo, artifact, operation["round"], verdicts[0]
            )
            if ledger_reason:
                return {"outcome": "CONFLICT", "artifacts": artifacts, "reason": ledger_reason}
            ledger = artifact.parent.parent / "prd.md"
            ledger_commit, ledger_git_error = _path_at_main(artifact_repo, ledger)
            if ledger_git_error:
                return {"outcome": "CONFLICT", "artifacts": artifacts, "reason": ledger_git_error}
            artifacts.append({"path": str(ledger.resolve()), "commit": ledger_commit})
        return {"outcome": "INTEGRATED", "artifacts": artifacts, "reason": ""}
    except (EvidenceError, OSError, KeyError, TypeError) as exc:
        return {"outcome": "CONFLICT", "artifacts": [], "reason": str(exc)}


def _load_json(path: Path, expected_type: type):
    def reject_duplicates(pairs: Iterable[tuple[str, object]]):
        result = {}
        for key, value in pairs:
            if key in result:
                raise EvidenceError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        with Path(path).open(encoding="utf-8") as source:
            value = json.load(source, object_pairs_hook=reject_duplicates)
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"cannot read JSON input {path}: {exc}") from exc
    if not isinstance(value, expected_type):
        raise EvidenceError(f"JSON input {path} must contain a {expected_type.__name__}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    fingerprint = commands.add_parser("fingerprint")
    fingerprint.add_argument("project", type=Path)
    fingerprint.add_argument("--bindings", required=True, type=Path)
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("repo", type=Path)
    reconcile.add_argument("vault", type=Path)
    reconcile.add_argument("--operation", required=True, type=Path)
    validation = commands.add_parser("validate-evaluation")
    validation.add_argument("report", type=Path)
    validation.add_argument("evaluation", type=Path)
    validation.add_argument("--expected", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "fingerprint":
            print(agreement_fingerprint(args.project, _load_json(args.bindings, list)))
        elif args.command == "reconcile":
            json.dump(
                reconcile_operation(
                    args.repo, args.vault, _load_json(args.operation, dict)
                ),
                sys.stdout,
                sort_keys=True,
            )
            sys.stdout.write("\n")
        else:
            json.dump(
                validate_evaluation(
                    args.report, args.evaluation, _load_json(args.expected, dict)
                ),
                sys.stdout,
                sort_keys=True,
            )
            sys.stdout.write("\n")
    except EvidenceError as exc:
        print(f"coding-loop-evidence: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Behavior tests for the coding-loop project state helper."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import types
import unittest


SCRIPTS = Path(__file__).resolve().parent
MODULE_PATH = SCRIPTS / "_coding_loop_state.py"


def load_state_module():
    if not MODULE_PATH.exists():
        def missing(*_args, **_kwargs):
            raise AssertionError("_coding_loop_state.py is not implemented")

        return types.SimpleNamespace(
            StateError=ValueError,
            read_state=missing,
            project_identity=missing,
            replace_state=missing,
            recover_ready=missing,
        )
    spec = importlib.util.spec_from_file_location("_coding_loop_state", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


state = load_state_module()


def run_git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


class CodingLoopStateTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q")
        run_git(self.repo, "config", "user.email", "state-test@example.invalid")
        run_git(self.repo, "config", "user.name", "State Test")
        (self.repo / "README.md").write_text("fixture\n")
        run_git(self.repo, "add", "README.md")
        run_git(self.repo, "commit", "-q", "-m", "fixture")

        self.vault = self.repo / "vault"
        self.project = self.vault / "projects" / "sample"
        self.project.mkdir(parents=True)
        self.state_path = self.project / "loop-status" / "sample.md"
        self.state_path.parent.mkdir()
        self.state_path.write_text(self.valid_document())

    def tearDown(self):
        self.temp.cleanup()

    def valid_operation(self, **changes):
        operation = {
            "id": "",
            "phase": "",
            "round": "",
            "agreement_revision": "",
            "code_commit": "",
            "meta_plan": "",
            "goal_folder": "",
            "report": "",
            "source_vault_commit": "",
        }
        operation.update(changes)
        return operation

    def valid_document(self, *, overrides=None, operation=None, body=None):
        fields = {
            "supervisor": "supercode",
            "project": "vault/projects/sample",
            "status": "WAITING FOR META-PLAN",
            "prior_status": "",
            "driver": "external",
            "cron_id": "",
            "created": "2026-09-09",
            "iteration": 0,
            "session_skill_count": 0,
            "round": 1,
            "meta_plan": "",
            "inner_loop": "",
            "inner_slug": "",
            "last_eval": "",
            "last_diagnosis": "",
            "evaluated_commit": "",
            "agreement_revision": "agreement-r1",
        }
        fields.update(overrides or {})
        lines = ["---", *(f"{key}: {value}" for key, value in fields.items()), "operation:"]
        lines.extend(
            f"  {key}: {value}" for key, value in (operation or self.valid_operation()).items()
        )
        pending = body if body is not None else (
            "## Pending decision\n"
            "Choose exactly one:\n"
            "- keep: preserve `code: value` and  two spaces  \n"
            "answer:\n\n"
            "## Decisions\n\n"
            "## Iteration log\n"
        )
        return "\n".join([*lines, "---", "", pending])

    def test_read_state_parses_valid_frontmatter(self):
        parsed = state.read_state(self.state_path)
        self.assertEqual("supercode", parsed["supervisor"])
        self.assertEqual(1, parsed["round"])
        self.assertEqual(0, parsed["iteration"])
        self.assertEqual(self.valid_operation(), parsed["operation"])

    def test_project_identity_uses_repo_relative_locator_for_internal_vault(self):
        identity = state.project_identity(self.repo, self.vault, self.project)
        self.assertEqual(
            {
                "repo": str(self.repo.resolve()),
                "vault": str(self.vault.resolve()),
                "project": str(self.project.resolve()),
                "stored_project": "vault/projects/sample",
            },
            identity,
        )

    def test_project_identity_uses_primary_checkout_from_linked_worktree(self):
        worktree = self.root / "linked"
        run_git(self.repo, "worktree", "add", "-q", "-b", "linked-state-test", str(worktree))
        identity = state.project_identity(worktree, self.vault, self.project)
        self.assertEqual(str(self.repo.resolve()), identity["repo"])
        self.assertEqual("vault/projects/sample", identity["stored_project"])

    def test_project_identity_requires_external_vault_to_be_its_own_repository(self):
        external = self.root / "external-vault"
        project = external / "projects" / "sample"
        project.mkdir(parents=True)
        with self.assertRaisesRegex(state.StateError, "external vault.*Git repository"):
            state.project_identity(self.repo, external, project)

        run_git(external, "init", "-q")
        identity = state.project_identity(self.repo, external, project)
        self.assertEqual(str(external.resolve()), identity["vault"])
        self.assertEqual(str(project.resolve()), identity["stored_project"])

    def test_project_symlink_cannot_escape_vault(self):
        outside = self.root / "outside-project"
        outside.mkdir()
        symlink = self.vault / "projects" / "escape"
        symlink.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(state.StateError, "contained in.*vault"):
            state.project_identity(self.repo, self.vault, symlink)

    def test_duplicate_identity_key_is_rejected(self):
        document = self.valid_document().replace(
            "project: vault/projects/sample\n",
            "project: vault/projects/sample\nproject: vault/projects/other\n",
        )
        self.state_path.write_text(document)
        with self.assertRaisesRegex(state.StateError, "duplicate.*project"):
            state.read_state(self.state_path)

    def test_duplicate_operation_identity_key_is_rejected(self):
        document = self.valid_document().replace(
            "  id: \n", "  id: \n  id: duplicate\n"
        )
        self.state_path.write_text(document)
        with self.assertRaisesRegex(state.StateError, "duplicate.*id"):
            state.read_state(self.state_path)

    def test_missing_project_identity_is_rejected(self):
        document = self.valid_document().replace("project: vault/projects/sample\n", "")
        self.state_path.write_text(document)
        with self.assertRaisesRegex(state.StateError, "missing required fields: project"):
            state.read_state(self.state_path)

    def test_round_must_be_a_positive_integer(self):
        for invalid in (0, -1, "1.5", "one"):
            with self.subTest(round=invalid):
                self.state_path.write_text(self.valid_document(overrides={"round": invalid}))
                with self.assertRaisesRegex(state.StateError, "round.*positive integer"):
                    state.read_state(self.state_path)

    def test_unknown_supervisor_is_rejected(self):
        self.state_path.write_text(
            self.valid_document(overrides={"supervisor": "surprise"})
        )
        with self.assertRaisesRegex(state.StateError, "unknown supervisor"):
            state.read_state(self.state_path)

    def test_unknown_status_is_rejected(self):
        self.state_path.write_text(
            self.valid_document(overrides={"status": "SOMEWHERE"})
        )
        with self.assertRaisesRegex(state.StateError, "unknown status"):
            state.read_state(self.state_path)

    def test_transient_status_requires_matching_operation_phase(self):
        operation = self.valid_operation(
            id="0" * 32,
            phase="DIAGNOSING",
            round=1,
            agreement_revision="agreement-r1",
            code_commit="a" * 40,
            meta_plan="meta-plans/r1.md",
            goal_folder="goals/r1",
            report="eval-reports/r1.md",
            source_vault_commit="b" * 40,
        )
        self.state_path.write_text(
            self.valid_document(overrides={"status": "EVALUATING"}, operation=operation)
        )
        with self.assertRaisesRegex(state.StateError, "operation phase.*status"):
            state.read_state(self.state_path)

    def test_operation_id_is_generated_once_and_preserved_across_retry(self):
        original = state.read_state(self.state_path)
        operation = self.valid_operation(
            phase="META-PLANNING",
            round=1,
            agreement_revision="agreement-r1",
            meta_plan="meta-plans/r1.md",
            goal_folder="goals/r1",
            source_vault_commit="c" * 40,
        )
        state.replace_state(
            self.state_path,
            original,
            dict(original, status="META-PLANNING", operation=operation),
        )
        active = state.read_state(self.state_path)
        self.assertRegex(active["operation"]["id"], re.compile(r"^[0-9a-f]{32}$"))

        retry = dict(active, status="WAITING FOR META-PLAN")
        retry["operation"] = dict(active["operation"])
        state.replace_state(self.state_path, active, retry)
        recovered = state.read_state(self.state_path)
        self.assertEqual(active["operation"]["id"], recovered["operation"]["id"])

    def test_new_operation_id_is_owned_by_state_helper(self):
        original = state.read_state(self.state_path)
        operation = self.valid_operation(
            id="0" * 32,
            phase="META-PLANNING",
            round=1,
            agreement_revision="agreement-r1",
            meta_plan="meta-plans/r1.md",
            goal_folder="goals/r1",
            source_vault_commit="c" * 40,
        )
        with self.assertRaisesRegex(state.StateError, "new operation id"):
            state.replace_state(
                self.state_path,
                original,
                dict(original, status="META-PLANNING", operation=operation),
            )

    def test_code_commit_is_forbidden_during_meta_planning(self):
        operation = self.valid_operation(
            id="0" * 32,
            phase="META-PLANNING",
            round=1,
            agreement_revision="agreement-r1",
            code_commit="a" * 40,
            meta_plan="meta-plans/r1.md",
            goal_folder="goals/r1",
            source_vault_commit="b" * 40,
        )
        self.state_path.write_text(
            self.valid_document(overrides={"status": "META-PLANNING"}, operation=operation)
        )
        with self.assertRaisesRegex(state.StateError, "code_commit.*META-PLANNING"):
            state.read_state(self.state_path)

    def test_active_operation_requires_each_source_and_path(self):
        operation = self.valid_operation(
            id="0" * 32,
            phase="EVALUATING",
            round=1,
            agreement_revision="agreement-r1",
            code_commit="a" * 40,
            meta_plan="meta-plans/r1.md",
            goal_folder="goals/r1",
            report="eval-reports/r1.md",
            source_vault_commit="b" * 40,
        )
        for key in (
            "agreement_revision",
            "code_commit",
            "meta_plan",
            "goal_folder",
            "report",
            "source_vault_commit",
        ):
            with self.subTest(field=key):
                invalid = dict(operation, **{key: ""})
                self.state_path.write_text(
                    self.valid_document(
                        overrides={"status": "EVALUATING"}, operation=invalid
                    )
                )
                with self.assertRaisesRegex(state.StateError, key):
                    state.read_state(self.state_path)

    def test_stale_state_does_not_overwrite_decision(self):
        original_bytes = self.state_path.read_bytes()
        mode = stat.S_IMODE(self.state_path.stat().st_mode)
        original = state.read_state(self.state_path)
        updated = dict(original, status="WAITING FOR BUILD")
        self.state_path.write_text(self.state_path.read_text() + "\noperator note\n")

        state.replace_state(self.state_path, original, updated)

        replaced = self.state_path.read_bytes()
        original_body = original_bytes.split(b"---\n", 2)[2]
        replaced_body = replaced.split(b"---\n", 2)[2]
        self.assertEqual(original_body + b"\noperator note\n", replaced_body)
        self.assertEqual(mode, stat.S_IMODE(self.state_path.stat().st_mode))
        with self.assertRaises(state.StateError):
            state.replace_state(self.state_path, original, updated)

    def test_replace_preserves_unrelated_frontmatter_fields(self):
        self.state_path.write_text(
            self.valid_document().replace("driver: external\n", "driver: external\ncustom: keep-me\n")
        )
        original = state.read_state(self.state_path)
        state.replace_state(
            self.state_path, original, dict(original, status="WAITING FOR BUILD")
        )
        self.assertEqual("keep-me", state.read_state(self.state_path)["custom"])

    def test_recovery_mapping_changes_only_transient_phases(self):
        expected = {
            "META-PLANNING": "WAITING FOR META-PLAN",
            "EVALUATING": "WAITING FOR EVAL",
            "DIAGNOSING": "WAITING FOR DIAGNOSIS",
            "WAITING FOR BUILD": "WAITING FOR BUILD",
        }
        self.assertEqual(expected, {value: state.recover_ready(value) for value in expected})

    def test_cli_reads_json_and_rejects_a_stale_replace(self):
        read = subprocess.run(
            [sys.executable, str(MODULE_PATH), "read", str(self.state_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(0, read.returncode, read.stderr)
        parsed = json.loads(read.stdout)
        expected_path = self.root / "expected.json"
        updated_path = self.root / "updated.json"
        expected_path.write_text(json.dumps(parsed))
        updated_path.write_text(json.dumps(dict(parsed, status="WAITING FOR BUILD")))
        changed = dict(parsed, iteration=1)
        state.replace_state(self.state_path, parsed, changed)

        replace = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "replace",
                str(self.state_path),
                "--expected",
                str(expected_path),
                "--updated",
                str(updated_path),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(2, replace.returncode)
        self.assertIn("stale", replace.stderr.lower())


if __name__ == "__main__":
    unittest.main()

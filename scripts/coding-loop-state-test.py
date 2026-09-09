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
EVIDENCE_MODULE_PATH = SCRIPTS / "_coding_loop_evidence.py"


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


def load_evidence_module():
    if not EVIDENCE_MODULE_PATH.exists():
        def missing(*_args, **_kwargs):
            raise AssertionError("_coding_loop_evidence.py is not implemented")

        return types.SimpleNamespace(
            EvidenceError=ValueError,
            agreement_fingerprint=missing,
            reconcile_operation=missing,
            validate_evaluation=missing,
        )
    spec = importlib.util.spec_from_file_location(
        "_coding_loop_evidence", EVIDENCE_MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


evidence = load_evidence_module()


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

    def test_transient_status_requires_operation_record(self):
        for status in ("META-PLANNING", "EVALUATING", "DIAGNOSING"):
            with self.subTest(status=status):
                self.state_path.write_text(
                    self.valid_document(overrides={"status": status})
                )
                with self.assertRaisesRegex(state.StateError, "operation.*required"):
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

    def test_replace_preserves_unrelated_frontmatter_fields_omitted_by_caller(self):
        self.state_path.write_text(
            self.valid_document().replace("driver: external\n", "driver: external\ncustom: keep-me\n")
        )
        original = state.read_state(self.state_path)
        updated = {
            key: value
            for key, value in dict(original, status="WAITING FOR BUILD").items()
            if key != "custom"
        }
        state.replace_state(self.state_path, original, updated)
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
        self.assertEqual(0, replace.returncode, replace.stderr)
        self.assertEqual("WAITING FOR BUILD", state.read_state(self.state_path)["status"])

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

    def test_cli_rejects_malformed_state(self):
        self.state_path.write_text("---\nround: nope\n---\n")
        read = subprocess.run(
            [sys.executable, str(MODULE_PATH), "read", str(self.state_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(2, read.returncode)
        self.assertIn("missing required fields", read.stderr)


class CodingLoopEvidenceTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.prd = self.project / "prd.md"
        self.evaluation = self.project / "evaluation.md"
        self.knowledge = self.project / "knowledge-base.md"
        self.binding = self.root / "requirements.md"
        self.prd.write_text(
            "# PRD\n\n## Requirements\nkeep this\n\n"
            "## Iteration ledger\n| Round | Verdict |\n|---|---|\n| 1 | - |\n"
        )
        self.evaluation.write_text(self.evaluation_text())
        self.knowledge.write_text("# Knowledge\n\nbinding notes\n")
        self.binding.write_text("approved requirement\n")

    def tearDown(self):
        self.temp.cleanup()

    def evaluation_text(self, *, judged=True, duplicate_command=False):
        command_rows = "| C1 | `true` | `.` | `exit 0` | 1 |\n"
        if duplicate_command:
            command_rows += "| C1 | `false` | `.` | `exit 1` | 1 |\n"
        judged_section = (
            "## Judged objectives\n"
            "| Id | Objective | Criteria | Evidence to inspect |\n"
            "|---|---|---|---|\n"
            "| J1 | behavior | required assertion | product.py |\n\n"
            "## Acceptance checklist\n"
            "| Id | Source | Required case or rule | Expected result | Verification and check ids |\n"
            "|---|---|---|---|---|\n"
            "| AC1 | prd | required assertion | preserved | C1, J1 |\n"
            if judged
            else "## Judged objectives\nnone\n"
        )
        return (
            "# Evaluation\n\n## Command checks\n"
            "| Id | Command | Cwd | Pass when | Timeout |\n"
            "|---|---|---|---|---|\n"
            f"{command_rows}\n{judged_section}"
        )

    def manifest(self):
        import hashlib

        return [
            {
                "locator": "requirements.md",
                "source_revision": "source-r1",
                "sha256": hashlib.sha256(self.binding.read_bytes()).hexdigest(),
                "path": str(self.binding),
            }
        ]

    def report_text(
        self,
        *,
        round_number=1,
        code_commit="a" * 40,
        agreement="agreement-r1",
        operation_id="1" * 32,
        source_vault_commit="b" * 40,
        command_result="PASS",
        judgment_result="PASS",
        ac_result="PASS",
        verdict="PASS",
        include_judgment=True,
        include_ac=True,
    ):
        judged = (
            "| Id | Result | Rationale |\n|---|---|---|\n"
            f"| J1 | {judgment_result} | inspected |\n"
            if include_judgment
            else "none\n"
        )
        ac = (
            "\n| AC | Result | Item-to-evidence |\n|---|---|---|\n"
            f"| AC1 | {ac_result} | product.py:1 |\n"
            if include_ac
            else ""
        )
        return (
            f"# Demo — eval report round {round_number}\n"
            f"**Date:** 2026-09-09 · **Status:** FINAL · **Round:** {round_number}\n"
            f"**Operation:** {operation_id} · **Agreement revision:** {agreement} · "
            f"**Source vault commit:** {source_vault_commit}\n\n"
            "## Environment\n"
            f"- commit: `{code_commit}` · worktree: `/tmp/work` · setup: `true` → ok\n\n"
            "## Command checks\n"
            "| Id | Result | Exit | Seconds | Evidence |\n|---|---|---|---|---|\n"
            f"| C1 | {command_result} | 0 | 0 | ok |\n\n"
            f"## Judged objectives\n{judged}{ac}\n"
            "## Verdict\n"
            f"**{verdict}** — {'all checks passed' if verdict == 'PASS' else 'failed'}\n"
            "**Inner loop:** none found\n**Warnings:** none\n"
        )

    def expected_identity(self):
        return {
            "round": 1,
            "code_commit": "a" * 40,
            "agreement_revision": "agreement-r1",
            "operation_id": "1" * 32,
            "source_vault_commit": "b" * 40,
        }

    def test_ledger_only_update_preserves_fingerprint(self):
        before = evidence.agreement_fingerprint(self.project, self.manifest())
        self.prd.write_text(
            self.prd.read_text().replace("| 1 | - |", "| 1 | PASS |\n| 2 | - |")
        )
        self.assertEqual(before, evidence.agreement_fingerprint(self.project, self.manifest()))

    def test_requirement_evaluation_and_binding_changes_alter_fingerprint(self):
        for changed in ("prd", "evaluation", "binding"):
            with self.subTest(changed=changed):
                original_prd = self.prd.read_text()
                original_evaluation = self.evaluation.read_text()
                original_binding = self.binding.read_text()
                manifest = self.manifest()
                before = evidence.agreement_fingerprint(self.project, manifest)
                if changed == "prd":
                    self.prd.write_text(original_prd.replace("keep this", "changed"))
                elif changed == "evaluation":
                    self.evaluation.write_text(original_evaluation + "binding change\n")
                else:
                    self.binding.write_text("changed binding\n")
                    import hashlib
                    manifest[0]["sha256"] = hashlib.sha256(
                        self.binding.read_bytes()
                    ).hexdigest()
                self.assertNotEqual(
                    before, evidence.agreement_fingerprint(self.project, manifest)
                )
                self.prd.write_text(original_prd)
                self.evaluation.write_text(original_evaluation)
                self.binding.write_text(original_binding)

    def test_missing_duplicate_or_unverified_binding_is_rejected(self):
        manifest = self.manifest()
        for invalid, message in (
            (manifest + manifest, "duplicate"),
            ([dict(manifest[0], path=str(self.root / "missing.md"))], "cannot read"),
            ([dict(manifest[0], sha256="0" * 64)], "digest"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(evidence.EvidenceError, message):
                    evidence.agreement_fingerprint(self.project, invalid)

    def test_wrong_round_code_or_agreement_refuses_evaluation(self):
        report = self.root / "report.md"
        mutations = {
            "round": {"round_number": 2},
            "code_commit": {"code_commit": "c" * 40},
            "agreement_revision": {"agreement": "agreement-r2"},
        }
        for field, arguments in mutations.items():
            with self.subTest(field=field):
                report.write_text(self.report_text(**arguments))
                result = evidence.validate_evaluation(
                    report, self.evaluation, self.expected_identity()
                )
                self.assertEqual("FAIL", result["verdict"])
                self.assertTrue(any(field in item for item in result["errors"]))

    def test_missing_judgment_is_not_pass(self):
        report = self.root / "report.md"
        report.write_text(self.report_text(include_judgment=False))
        result = evidence.validate_evaluation(
            report, self.evaluation, self.expected_identity()
        )
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("J1", result["missing_ids"])

    def test_missing_acceptance_evidence_is_not_pass(self):
        report = self.root / "report.md"
        report.write_text(self.report_text(include_ac=False))
        result = evidence.validate_evaluation(
            report, self.evaluation, self.expected_identity()
        )
        self.assertEqual("FAIL", result["verdict"])
        self.assertIn("AC1", result["missing_ids"])

    def test_duplicate_evaluation_ids_and_invalid_results_are_rejected(self):
        report = self.root / "report.md"
        report.write_text(self.report_text(command_result="OK"))
        invalid_result = evidence.validate_evaluation(
            report, self.evaluation, self.expected_identity()
        )
        self.assertEqual("FAIL", invalid_result["verdict"])
        self.assertTrue(any("invalid result" in item for item in invalid_result["errors"]))

        self.evaluation.write_text(self.evaluation_text(duplicate_command=True))
        duplicate = evidence.validate_evaluation(
            report, self.evaluation, self.expected_identity()
        )
        self.assertEqual("FAIL", duplicate["verdict"])
        self.assertTrue(any("duplicate" in item for item in duplicate["errors"]))

    def test_command_only_legacy_report_can_pass_without_judgments(self):
        self.evaluation.write_text(self.evaluation_text(judged=False))
        report = self.root / "report.md"
        report.write_text(
            self.report_text(include_judgment=False, include_ac=False)
        )
        expected = {"round": 1, "code_commit": "a" * 40}
        result = evidence.validate_evaluation(report, self.evaluation, expected)
        self.assertEqual("PASS", result["verdict"])
        self.assertEqual([], result["missing_ids"])

    def test_nonfinal_report_is_not_accepted(self):
        report = self.root / "report.md"
        report.write_text(self.report_text().replace("**Status:** FINAL", "**Status:** DRAFT"))
        result = evidence.validate_evaluation(
            report, self.evaluation, self.expected_identity()
        )
        self.assertEqual("FAIL", result["verdict"])
        self.assertTrue(any("FINAL" in item for item in result["errors"]))

    def test_command_only_report_still_requires_judged_section(self):
        self.evaluation.write_text(self.evaluation_text(judged=False))
        report = self.root / "report.md"
        report.write_text(
            self.report_text(include_judgment=False, include_ac=False).replace(
                "## Judged objectives\nnone\n\n", ""
            )
        )
        result = evidence.validate_evaluation(
            report, self.evaluation, {"round": 1, "code_commit": "a" * 40}
        )
        self.assertEqual("FAIL", result["verdict"])
        self.assertTrue(any("Judged objectives" in item for item in result["errors"]))

    def make_reconcile_fixture(self):
        repo = self.root / "repo"
        remote = self.root / "remote.git"
        run_git(self.root, "init", "-q", "--bare", str(remote))
        repo.mkdir()
        run_git(repo, "init", "-q", "-b", "main")
        run_git(repo, "config", "user.email", "evidence-test@example.invalid")
        run_git(repo, "config", "user.name", "Evidence Test")
        run_git(repo, "remote", "add", "origin", str(remote))
        project = repo / "vault" / "projects" / "sample"
        reports = project / "eval-reports"
        reports.mkdir(parents=True)
        (project / "prd.md").write_text(
            "# PRD\n\n## Iteration ledger\n"
            "| Round | Meta-plan | Goal folder | Inner loop | Eval report | Verdict |\n"
            "|---|---|---|---|---|---|\n"
            "| 1 | meta | goal | - | [[vault/projects/sample/eval-reports/r1]] | PASS |\n"
        )
        report = reports / "r1.md"
        report.write_text(self.report_text())
        run_git(repo, "add", "vault")
        run_git(repo, "commit", "-q", "-m", "integrated report")
        run_git(repo, "push", "-q", "-u", "origin", "main")
        source_vault_commit = run_git(repo, "rev-parse", "HEAD")
        operation = {
            "id": "1" * 32,
            "phase": "EVALUATING",
            "round": 1,
            "agreement_revision": "agreement-r1",
            "code_commit": run_git(repo, "rev-parse", "HEAD"),
            "meta_plan": "vault/projects/sample/meta-plans/r1.md",
            "goal_folder": "vault/goals/r1",
            "report": "vault/projects/sample/eval-reports/r1.md",
            "source_vault_commit": source_vault_commit,
        }
        report.write_text(
            self.report_text(
                code_commit=operation["code_commit"],
                source_vault_commit=source_vault_commit,
            )
        )
        run_git(repo, "add", str(report.relative_to(repo)))
        run_git(repo, "commit", "-q", "-m", "record selected code")
        run_git(repo, "push", "-q")
        return repo, repo / "vault", project, report, operation

    def make_external_reconcile_fixture(self):
        repo = self.root / "repo"
        remote = self.root / "remote.git"
        run_git(self.root, "init", "-q", "--bare", str(remote))
        repo.mkdir()
        run_git(repo, "init", "-q", "-b", "main")
        run_git(repo, "config", "user.email", "evidence-test@example.invalid")
        run_git(repo, "config", "user.name", "Evidence Test")
        run_git(repo, "remote", "add", "origin", str(remote))
        (repo / "README.md").write_text("code\n")
        run_git(repo, "add", "README.md")
        run_git(repo, "commit", "-q", "-m", "code")
        run_git(repo, "push", "-q", "-u", "origin", "main")

        vault = self.root / "vault"
        project = vault / "projects" / "sample"
        reports = project / "eval-reports"
        reports.mkdir(parents=True)
        run_git(vault, "init", "-q", "-b", "main")
        run_git(vault, "config", "user.email", "evidence-test@example.invalid")
        run_git(vault, "config", "user.name", "Evidence Test")
        (project / "prd.md").write_text(
            "# PRD\n\n## Iteration ledger\n"
            "| Round | Meta-plan | Goal folder | Inner loop | Eval report | Verdict |\n"
            "|---|---|---|---|---|---|\n"
            f"| 1 | meta | goal | - | [[{reports / 'r1'}]] | PASS |\n"
        )
        report = reports / "r1.md"
        report.write_text(self.report_text())
        run_git(vault, "add", "projects")
        run_git(vault, "commit", "-q", "-m", "agreement")
        source_vault_commit = run_git(vault, "rev-parse", "HEAD")
        operation = {
            "id": "1" * 32,
            "phase": "EVALUATING",
            "round": 1,
            "agreement_revision": "agreement-r1",
            "code_commit": run_git(repo, "rev-parse", "HEAD"),
            "meta_plan": str(project / "meta-plans" / "r1.md"),
            "goal_folder": str(vault / "goals" / "r1"),
            "report": str(report),
            "source_vault_commit": source_vault_commit,
        }
        report.write_text(
            self.report_text(
                code_commit=operation["code_commit"],
                source_vault_commit=source_vault_commit,
            )
        )
        run_git(vault, "add", str(report.relative_to(vault)))
        run_git(vault, "commit", "-q", "-m", "evaluation")
        return repo, vault, report, operation

    def test_tracked_integrated_matching_result_is_reusable(self):
        repo, vault, _project, report, operation = self.make_reconcile_fixture()
        result = evidence.reconcile_operation(repo, vault, operation)
        self.assertEqual("INTEGRATED", result["outcome"])
        self.assertEqual(str(report.resolve()), result["artifacts"][0]["path"])
        self.assertEqual(run_git(repo, "rev-parse", "main"), result["artifacts"][0]["commit"])

    def test_synced_main_is_authority_from_a_clean_older_branch(self):
        repo, vault, _project, _report, operation = self.make_reconcile_fixture()
        run_git(
            repo,
            "switch",
            "-q",
            "-c",
            "older-checkout",
            operation["source_vault_commit"],
        )
        result = evidence.reconcile_operation(repo, vault, operation)
        self.assertEqual("INTEGRATED", result["outcome"])

    def test_report_committed_on_unmerged_branch_is_not_integrated(self):
        repo, vault, _project, report, operation = self.make_reconcile_fixture()
        run_git(repo, "switch", "-q", "-c", "unmerged")
        report.write_text(
            self.report_text(
                operation_id="2" * 32,
                code_commit=operation["code_commit"],
                source_vault_commit=operation["source_vault_commit"],
            )
        )
        operation["id"] = "2" * 32
        run_git(repo, "add", str(report.relative_to(repo)))
        run_git(repo, "commit", "-q", "-m", "unmerged report")
        result = evidence.reconcile_operation(repo, vault, operation)
        self.assertEqual("CONFLICT", result["outcome"])
        self.assertIn("main", result["reason"])

    def test_duplicate_matching_reports_conflict(self):
        repo, vault, project, report, operation = self.make_reconcile_fixture()
        duplicate = project / "eval-reports" / "duplicate.md"
        duplicate.write_bytes(report.read_bytes())
        run_git(repo, "add", str(duplicate.relative_to(repo)))
        run_git(repo, "commit", "-q", "-m", "duplicate report")
        run_git(repo, "push", "-q")
        result = evidence.reconcile_operation(repo, vault, operation)
        self.assertEqual("CONFLICT", result["outcome"])
        self.assertIn("multiple", result["reason"])

    def test_untracked_result_is_not_success(self):
        repo, vault, _project, report, operation = self.make_reconcile_fixture()
        report.write_text(
            self.report_text(
                operation_id="3" * 32,
                code_commit=operation["code_commit"],
                source_vault_commit=operation["source_vault_commit"],
            )
        )
        operation["id"] = "3" * 32
        result = evidence.reconcile_operation(repo, vault, operation)
        self.assertEqual("CONFLICT", result["outcome"])
        self.assertIn("uncommitted", result["reason"])

    def test_external_vault_without_remote_accepts_its_local_main(self):
        repo, vault, _report, operation = self.make_external_reconcile_fixture()
        result = evidence.reconcile_operation(repo, vault, operation)
        self.assertEqual("INTEGRATED", result["outcome"])

    def test_external_vault_remote_without_tracking_ref_is_not_synchronized(self):
        repo, vault, _report, operation = self.make_external_reconcile_fixture()
        remote = self.root / "vault-remote.git"
        run_git(self.root, "init", "-q", "--bare", str(remote))
        run_git(vault, "remote", "add", "origin", str(remote))
        result = evidence.reconcile_operation(repo, vault, operation)
        self.assertEqual("CONFLICT", result["outcome"])
        self.assertIn("configured remote ref", result["reason"])

    def test_cli_subcommands_accept_json_inputs(self):
        manifest_path = self.root / "manifest.json"
        expected_path = self.root / "expected.json"
        report = self.root / "report.md"
        manifest_path.write_text(json.dumps(self.manifest()))
        expected_path.write_text(json.dumps(self.expected_identity()))
        report.write_text(self.report_text())
        fingerprint = subprocess.run(
            [
                sys.executable,
                str(EVIDENCE_MODULE_PATH),
                "fingerprint",
                str(self.project),
                "--bindings",
                str(manifest_path),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(0, fingerprint.returncode, fingerprint.stderr)
        self.assertRegex(fingerprint.stdout.strip(), r"^[0-9a-f]{64}$")
        validation = subprocess.run(
            [
                sys.executable,
                str(EVIDENCE_MODULE_PATH),
                "validate-evaluation",
                str(report),
                str(self.evaluation),
                "--expected",
                str(expected_path),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(0, validation.returncode, validation.stderr)
        self.assertEqual("PASS", json.loads(validation.stdout)["verdict"])


if __name__ == "__main__":
    unittest.main()

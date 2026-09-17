#!/usr/bin/env python3
"""Test diagnosis reports or emit/grade later read-only interpretation probes."""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest


SCRIPTS = Path(__file__).resolve().parent
EVIDENCE_MODULE_PATH = SCRIPTS / "_coding_loop_evidence.py"
TEMPLATE_PATH = SCRIPTS.parent / "templates" / "coding-loop-diagnosis.md"


def load_evidence_module():
    if not EVIDENCE_MODULE_PATH.exists():
        return types.SimpleNamespace()
    spec = importlib.util.spec_from_file_location(
        "_coding_loop_evidence", EVIDENCE_MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


evidence = load_evidence_module()


def validate_diagnosis(*args, **kwargs):
    implementation = getattr(evidence, "validate_diagnosis", None)
    if implementation is None:
        raise AssertionError("validate_diagnosis is not implemented")
    return implementation(*args, **kwargs)


def run_git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def rendered_template(operation, eval_report):
    replacements = {
        "<Project title>": "Sample",
        "<N>": str(operation["round"]),
        "<STAMP>": "2026-09-09-14_45",
        "<YYYY-MM-DD>": "2026-09-09",
        "<32-character lowercase hexadecimal operation id>": operation["id"],
        "<exact selected evaluation-report path>": eval_report,
        "<selected code commit>": operation["code_commit"],
        "<agreement fingerprint>": operation["agreement_revision"],
        "<source-vault main commit>": operation["source_vault_commit"],
        "<Resolved approved sources, selected round artifacts, and any unavailable or weak evidence.>": "All selected sources and round artifacts were available.",
        "<comma-separated failed or missing C/J IDs, or none>": "C1",
        "<comma-separated applicable approved AC IDs, or none>": "AC1",
        "<observed evidence with file:line when available>": "src/parser.py:41",
        "<evidence-grounded cause>": "The approved check is not implemented.",
        "<high, medium, or low>": "high",
        "<implementation defect, plan gap, PRD/evaluation defect, or execution/evidence failure>": "implementation defect",
        "<Bounded guidance by problem ID. Carry only approved obligations; label optional suggestions nonbinding.>": "P1: implement the approved C1 behavior.",
        "<REPAIR or AUTHOR INPUT>": "REPAIR",
    }
    text = TEMPLATE_PATH.read_text()
    for old, new in replacements.items():
        text = text.replace(old, new)
    if "<" in text or ">" in text:
        raise AssertionError("diagnosis template fixture has unreplaced instructions")
    return text


PROBE_CASES = [
    (
        "green_existence_only",
        "C1 passes and the product behaves correctly. J1 requires an assertion proving the "
        "authorization boundary, but the only test checks that a file exists. The approved "
        "round plan required the J1 assertion.",
        {"classification": "implementation defect", "disposition": "REPAIR"},
    ),
    (
        "product_defect",
        "C2 demonstrates that the shipped parser accepts an invalid token. The approved PRD "
        "and evaluation both require rejection, and the round plan includes that behavior.",
        {"classification": "implementation defect", "disposition": "REPAIR"},
    ),
    (
        "plan_omission",
        "J2 fails because the approved retry requirement never appears in the round plan. "
        "The implementation follows the plan exactly; the PRD and evaluation agree.",
        {"classification": "plan gap", "disposition": "REPAIR"},
    ),
    (
        "contradictory_spec",
        "The approved PRD requires retaining a record while evaluation J3 requires deleting "
        "the same record under the same condition. No precedence or exception is recorded.",
        {"classification": "PRD/evaluation defect", "disposition": "AUTHOR INPUT"},
    ),
    (
        "unavailable_evaluator",
        "The evaluator dispatch failed and no J4 result or trustworthy receipt exists. Code, "
        "tests, and round artifacts are otherwise available.",
        {"classification": "execution/evidence failure", "disposition": "AUTHOR INPUT"},
    ),
]


def emit_prompt(cases, skills: Path, stream=sys.stdout):
    print(
        "Read " + str((skills / "superdiagnose" / "SKILL.md").resolve()) +
        ". Apply that contract to each independent read-only scenario. Do not dispatch, "
        "modify files, run Git, or use the network. Return one JSON object keyed by scenario "
        "id. Each value must contain classification, disposition, and rule. The rule must "
        "cite the governing superdiagnose rule. Do not invent missing evidence.",
        file=stream,
    )
    for name, scenario, _ in cases:
        print(f"\n{name}: {scenario}", file=stream)


def validate_answers(answers, cases, stream=sys.stderr):
    class Answers(unittest.TestCase):
        def test_interpretations(self):
            self.assertIsInstance(answers, dict)
            self.assertEqual(set(answers), {case[0] for case in cases})
            for name, _, expected in cases:
                with self.subTest(case=name):
                    actual = answers[name]
                    self.assertIsInstance(actual, dict)
                    self.assertTrue(
                        actual.get("rule"), "cite the governing superdiagnose rule"
                    )
                    for key, value in expected.items():
                        self.assertEqual(actual.get(key), value, f"{name}.{key}")

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Answers)
    return unittest.TextTestRunner(stream=stream, verbosity=2).run(suite).wasSuccessful()


class DiagnosisValidationTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.expected_identity = {
            "round": 2,
            "operation_id": "0123456789abcdef0123456789abcdef",
            "eval_report": "projects/sample/eval-reports/2026-09-09-14_30-r2.md",
            "evaluated_commit": "a" * 40,
            "agreement_revision": "b" * 64,
            "source_vault_commit": "c" * 40,
            "failing_ids": ["C1", "J2"],
            "missing_ids": ["J3"],
        }
        self.valid_report = self.write_report(
            "valid.md",
            problems=[
                {
                    "problem": "P1",
                    "ids": "C1, J2, J3",
                    "acs": "AC1, AC4",
                    "evidence": "src/parser.py:41; tests/test_parser.py:18",
                    "cause": "The selected implementation omits the approved checks.",
                    "confidence": "high",
                    "classification": "implementation defect",
                }
            ],
        )

    def tearDown(self):
        self.temp.cleanup()

    def write_report(
        self,
        name,
        *,
        problems,
        disposition="REPAIR",
        round_number="2",
        operation="0123456789abcdef0123456789abcdef",
        eval_report="projects/sample/eval-reports/2026-09-09-14_30-r2.md",
        evaluated_commit=None,
        agreement_revision=None,
        source_vault_commit=None,
    ):
        evaluated_commit = "a" * 40 if evaluated_commit is None else evaluated_commit
        agreement_revision = "b" * 64 if agreement_revision is None else agreement_revision
        source_vault_commit = "c" * 40 if source_vault_commit is None else source_vault_commit
        labels = [
            "# Sample — diagnosis round 2 — 2026-09-09-14_45-r2",
            f"**Date:** 2026-09-09 · **Status:** FINAL · **Round:** {round_number}",
            f"**Operation:** `{operation}`",
            f"**Eval report:** `{eval_report}`",
            f"**Evaluated commit:** `{evaluated_commit}`",
        ]
        if agreement_revision:
            labels.append(f"**Agreement revision:** `{agreement_revision}`")
        if source_vault_commit:
            labels.append(f"**Source vault commit:** `{source_vault_commit}`")
        rows = [
            "| Problem | C/J IDs | AC IDs | Evidence | Cause | Confidence | Classification |",
            "|---|---|---|---|---|---|---|",
        ]
        rows.extend(
            "| {problem} | {ids} | {acs} | {evidence} | {cause} | {confidence} | {classification} |".format(
                **problem
            )
            for problem in problems
        )
        text = "\n".join(
            [
                *labels,
                "",
                "## Inputs and limitations",
                "All approved sources and selected round artifacts were available.",
                "",
                "## Problems",
                *rows,
                "",
                "## Repair guidance",
                "Restore the approved checks without changing the agreement.",
                "",
                "## Disposition",
                f"**{disposition}**",
                "",
            ]
        )
        path = self.root / name
        path.write_text(text)
        return path

    def test_complete_repair_report_may_start_next_round(self):
        result = validate_diagnosis(self.valid_report, self.expected_identity)
        self.assertEqual("REPAIR", result["disposition"])
        self.assertTrue(result["may_start_next_round"])
        self.assertEqual([], result["unaccounted_ids"])
        self.assertEqual([], result["errors"])

    def test_integrated_diagnosis_using_template_is_reconciled(self):
        repo = self.root / "repo"
        remote = self.root / "remote.git"
        run_git(self.root, "init", "-q", "--bare", str(remote))
        repo.mkdir()
        run_git(repo, "init", "-q", "-b", "main")
        run_git(repo, "config", "user.email", "diagnosis-test@example.invalid")
        run_git(repo, "config", "user.name", "Diagnosis Test")
        run_git(repo, "remote", "add", "origin", str(remote))
        (repo / "README.md").write_text("selected code\n")
        run_git(repo, "add", "README.md")
        run_git(repo, "commit", "-q", "-m", "selected code")
        selected_commit = run_git(repo, "rev-parse", "HEAD")
        report = repo / "vault" / "projects" / "sample" / "diagnoses" / "r1.md"
        report.parent.mkdir(parents=True)
        operation = {
            "id": "1" * 32,
            "phase": "DIAGNOSING",
            "round": 1,
            "agreement_revision": "agreement-r1",
            "code_commit": selected_commit,
            "meta_plan": "vault/projects/sample/meta-plans/r1.md",
            "goal_folder": "vault/goals/r1",
            "report": "vault/projects/sample/diagnoses/r1.md",
            "source_vault_commit": selected_commit,
        }
        eval_report = "vault/projects/sample/eval-reports/r1.md"
        report.write_text(rendered_template(operation, eval_report))
        run_git(repo, "add", "vault")
        run_git(repo, "commit", "-q", "-m", "integrated diagnosis")
        run_git(repo, "push", "-q", "-u", "origin", "main")

        result = evidence.reconcile_operation(repo, repo / "vault", operation)

        self.assertEqual("INTEGRATED", result["outcome"])
        self.assertEqual(str(report.resolve()), result["artifacts"][0]["path"])
        self.assertEqual(
            run_git(repo, "rev-parse", "main"), result["artifacts"][0]["commit"]
        )

        run_git(repo, "switch", "-q", "-c", "unmerged-diagnosis")
        report.write_text(report.read_text().replace("REPAIR", "AUTHOR INPUT"))
        run_git(repo, "add", "vault")
        run_git(repo, "commit", "-qm", "unmerged diagnosis cannot replace main")
        result = evidence.reconcile_operation(repo, repo / "vault", operation)
        self.assertEqual("CONFLICT", result["outcome"])
        self.assertIn("differ from main", result["reason"])

    def test_omitted_failing_check_cannot_start_next_round(self):
        report = self.write_report(
            "omitted.md",
            problems=[
                {
                    "problem": "P1",
                    "ids": "C1, J2",
                    "acs": "AC1",
                    "evidence": "src/parser.py:41",
                    "cause": "Missing assertion.",
                    "confidence": "high",
                    "classification": "implementation defect",
                }
            ],
        )
        result = validate_diagnosis(report, self.expected_identity)
        self.assertEqual("AUTHOR INPUT", result["disposition"])
        self.assertFalse(result["may_start_next_round"])
        self.assertEqual(["J3"], result["unaccounted_ids"])

    def test_absent_source_revision_cannot_start_next_round(self):
        report = self.write_report(
            "no-revision.md",
            problems=[
                {
                    "problem": "P1",
                    "ids": "C1, J2, J3",
                    "acs": "AC1",
                    "evidence": "src/parser.py:41",
                    "cause": "Missing assertion.",
                    "confidence": "high",
                    "classification": "implementation defect",
                }
            ],
            agreement_revision="",
        )
        result = validate_diagnosis(report, self.expected_identity)
        self.assertEqual("AUTHOR INPUT", result["disposition"])
        self.assertFalse(result["may_start_next_round"])
        self.assertIn("report is missing agreement_revision", result["errors"])

    def test_source_vault_revision_is_required_even_without_expected_value(self):
        report = self.write_report(
            "no-source-vault.md",
            problems=[
                {
                    "problem": "P1",
                    "ids": "C1, J2, J3",
                    "acs": "AC1",
                    "evidence": "src/parser.py:41",
                    "cause": "Missing assertion.",
                    "confidence": "high",
                    "classification": "implementation defect",
                }
            ],
            source_vault_commit="",
        )
        expected = dict(self.expected_identity)
        expected.pop("source_vault_commit")
        result = validate_diagnosis(report, expected)
        self.assertEqual("AUTHOR INPUT", result["disposition"])
        self.assertFalse(result["may_start_next_round"])
        self.assertIn("report is missing source_vault_commit", result["errors"])

    def test_mixed_spec_and_code_causes_require_author(self):
        report = self.write_report(
            "mixed.md",
            problems=[
                {
                    "problem": "P1",
                    "ids": "C1, J2",
                    "acs": "AC1",
                    "evidence": "src/parser.py:41",
                    "cause": "Implementation violates the approved parser rule.",
                    "confidence": "high",
                    "classification": "implementation defect",
                },
                {
                    "problem": "P2",
                    "ids": "J3",
                    "acs": "AC4",
                    "evidence": "prd.md:52; evaluation.md:31",
                    "cause": "The approved sources contradict each other.",
                    "confidence": "high",
                    "classification": "PRD/evaluation defect",
                },
            ],
            disposition="REPAIR",
        )
        result = validate_diagnosis(report, self.expected_identity)
        self.assertEqual("AUTHOR INPUT", result["disposition"])
        self.assertFalse(result["may_start_next_round"])

    def test_unsupported_or_low_confidence_classification_requires_author(self):
        unsupported = self.write_report(
            "unsupported.md",
            problems=[
                {
                    "problem": "P1",
                    "ids": "C1, J2, J3",
                    "acs": "AC1",
                    "evidence": "src/parser.py:41",
                    "cause": "The likely cause is unclear.",
                    "confidence": "high",
                    "classification": "test defect",
                }
            ],
        )
        low = self.write_report(
            "low.md",
            problems=[
                {
                    "problem": "P1",
                    "ids": "C1, J2, J3",
                    "acs": "AC1",
                    "evidence": "src/parser.py:41",
                    "cause": "The likely cause is unclear.",
                    "confidence": "low",
                    "classification": "plan gap",
                }
            ],
        )
        for report in (unsupported, low):
            with self.subTest(report=report.name):
                result = validate_diagnosis(report, self.expected_identity)
                self.assertEqual("AUTHOR INPUT", result["disposition"])
                self.assertFalse(result["may_start_next_round"])

    def test_wrong_selected_report_cannot_start_next_round(self):
        report = self.write_report(
            "wrong-report.md",
            problems=[
                {
                    "problem": "P1",
                    "ids": "C1, J2, J3",
                    "acs": "AC1",
                    "evidence": "src/parser.py:41",
                    "cause": "Missing assertion.",
                    "confidence": "high",
                    "classification": "implementation defect",
                }
            ],
            eval_report="projects/sample/eval-reports/another-r2.md",
        )
        result = validate_diagnosis(report, self.expected_identity)
        self.assertEqual("AUTHOR INPUT", result["disposition"])
        self.assertFalse(result["may_start_next_round"])
        self.assertTrue(any("eval_report mismatch" in error for error in result["errors"]))

    def test_execution_failure_with_no_check_id_is_valid_author_input(self):
        expected = dict(self.expected_identity, failing_ids=[], missing_ids=[])
        report = self.write_report(
            "unavailable.md",
            problems=[
                {
                    "problem": "P1",
                    "ids": "none",
                    "acs": "none",
                    "evidence": "dispatch receipt unavailable",
                    "cause": "The evaluator did not return trustworthy evidence.",
                    "confidence": "high",
                    "classification": "execution/evidence failure",
                }
            ],
            disposition="AUTHOR INPUT",
        )
        result = validate_diagnosis(report, expected)
        self.assertEqual("AUTHOR INPUT", result["disposition"])
        self.assertFalse(result["may_start_next_round"])
        self.assertEqual([], result["errors"])

    def test_empty_id_cells_do_not_masquerade_as_none(self):
        expected = dict(self.expected_identity, failing_ids=[], missing_ids=[])
        for field in ("ids", "acs"):
            problem = {
                "problem": "P1",
                "ids": "none",
                "acs": "none",
                "evidence": "dispatch receipt unavailable",
                "cause": "The evaluator did not return trustworthy evidence.",
                "confidence": "high",
                "classification": "execution/evidence failure",
            }
            problem[field] = ""
            report = self.write_report(
                f"empty-{field}.md",
                problems=[problem],
                disposition="AUTHOR INPUT",
            )
            with self.subTest(field=field):
                result = validate_diagnosis(report, expected)
                self.assertEqual("AUTHOR INPUT", result["disposition"])
                self.assertFalse(result["may_start_next_round"])
                self.assertTrue(any("cannot be empty" in error for error in result["errors"]))

    def test_duplicate_problem_section_is_ambiguous(self):
        report = self.root / "duplicate-problems.md"
        report.write_text(
            self.valid_report.read_text().replace(
                "## Repair guidance",
                "## Problems\n\nDuplicate narrative.\n\n## Repair guidance",
            )
        )
        result = validate_diagnosis(report, self.expected_identity)
        self.assertEqual("AUTHOR INPUT", result["disposition"])
        self.assertFalse(result["may_start_next_round"])
        self.assertIn(
            "report must contain exactly one Problems section", result["errors"]
        )

    def test_prompt_omits_expected_answers_and_answer_mode_requires_rule_citation(self):
        stream = io.StringIO()
        emit_prompt(PROBE_CASES, Path("skills"), stream)
        prompt = stream.getvalue()
        self.assertIn("green_existence_only", prompt)
        self.assertNotIn('"classification": "implementation defect"', prompt)
        answers = {
            name: {**expected, "rule": "superdiagnose Classification and disposition"}
            for name, _, expected in PROBE_CASES
        }
        self.assertTrue(validate_answers(answers, PROBE_CASES, io.StringIO()))
        answers["product_defect"].pop("rule")
        self.assertFalse(validate_answers(answers, PROBE_CASES, io.StringIO()))


def parse_probe_args(argv):
    parser = argparse.ArgumentParser(add_help=False)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--prompt", action="store_true")
    group.add_argument("--answers", type=Path)
    parser.add_argument("--skills", type=Path, default=Path("skills"))
    parser.add_argument(
        "--cases", nargs="+", choices=[case[0] for case in PROBE_CASES]
    )
    args, remaining = parser.parse_known_args(argv)
    return args, remaining


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args, remaining = parse_probe_args(argv)
    cases = [
        case for case in PROBE_CASES if not args.cases or case[0] in args.cases
    ]
    if args.prompt:
        if remaining:
            raise SystemExit(f"unrecognized arguments: {' '.join(remaining)}")
        emit_prompt(cases, args.skills)
        return 0
    if args.answers:
        if remaining:
            raise SystemExit(f"unrecognized arguments: {' '.join(remaining)}")
        try:
            answers = json.loads(args.answers.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"coding-loop-diagnosis-test: {exc}", file=sys.stderr)
            return 2
        return 0 if validate_answers(answers, cases) else 1
    program = unittest.main(argv=[sys.argv[0], *remaining], exit=False)
    return 0 if program.result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

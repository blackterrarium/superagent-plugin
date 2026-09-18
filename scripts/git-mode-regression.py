#!/usr/bin/env python3
"""Print or validate git-free skill interpretation scenarios (no model calls)."""
import argparse
import json
from pathlib import Path
import tempfile
import unittest


CASES = [
    ("local_complete", "A local leaf has passing required commands, task and final reviews, a valid "
     "completed-local receipt, and no open acceptance or repair obligations.", {"done": True}),
    ("label_without_evidence", "A row says completed-local, but the closeout receipt or required "
     "test evidence is missing.", {"done": False}),
    ("failed_descendant", "An ancestor says completed-local while one active descendant failed and "
     "has no authorized disposition.", {"done": False}),
    ("failed_review", "A local leaf is implemented and tests pass, but its required review failed.",
     {"done": False}),
    ("late_predecessor", "A delayed closeout belongs to a predecessor while the active row points "
     "to its repair successor.", {"overwrite_successor": False}),
    ("repair_replay", "A local repair and successor were durably published before a crash. A fresh "
     "tick replays the decision.", {"duplicate_successor": False, "reset_repair": False}),
    ("legacy_to_local", "An unmarked legacy goal is evaluated with effective mode none.",
     {"mode_mismatch": True, "git_operations": False}),
    ("local_to_github", "A goal recorded as none is evaluated with effective mode github.",
     {"mode_mismatch": True, "merge_claim": False}),
    ("local_receipt_in_github", "GitHub mode sees only a completed-local receipt and no verified "
     "integration evidence.", {"done": False}),
    ("local_sdd", "A local execution instruction reaches SDD's default worktree, commit, PR, merge, "
     "and finishing stages.", {"suppress_git_stages": True, "retain_test_review_gates": True}),
]


def errors_for(answers, cases):
    errors = []
    expected_names = {case[0] for case in cases}
    if not isinstance(answers, dict):
        return ["answers must be one JSON object"]
    if set(answers) != expected_names:
        errors.append("case membership mismatch: expected {} got {}".format(
            sorted(expected_names), sorted(answers)))
    for name, _, expected in cases:
        actual = answers.get(name)
        if not isinstance(actual, dict):
            errors.append(name + ": result must be an object")
            continue
        for field in ("reason", "evidence"):
            if not isinstance(actual.get(field), str) or not actual[field].strip():
                errors.append("{}.{} must be nonempty".format(name, field))
        for key, value in expected.items():
            if actual.get(key) != value:
                errors.append("{}.{} expected {!r}, got {!r}".format(
                    name, key, value, actual.get(key)))
    return errors


def validate(answers, cases, verbosity=2):
    class Answers(unittest.TestCase):
        def test_git_free_scenarios(self):
            problems = errors_for(answers, cases)
            self.assertEqual(problems, [], "\n" + "\n".join(problems))
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Answers)
    return unittest.TextTestRunner(verbosity=verbosity).run(suite).wasSuccessful()


def valid_fixture(cases):
    return {
        name: dict({"reason": "governing local-mode rule", "evidence": "fixture evidence"},
                   **expected)
        for name, _, expected in cases
    }


def self_test():
    class ValidatorSelfTest(unittest.TestCase):
        def setUp(self):
            self.answers = valid_fixture(CASES)

        def test_valid(self):
            self.assertEqual(errors_for(self.answers, CASES), [])

        def test_missing_case_fails(self):
            self.answers.pop(CASES[0][0])
            self.assertTrue(errors_for(self.answers, CASES))

        def test_extra_case_fails(self):
            self.answers["invented"] = {"reason": "x", "evidence": "y"}
            self.assertTrue(errors_for(self.answers, CASES))

        def test_empty_reason_or_evidence_fails(self):
            self.answers[CASES[0][0]]["reason"] = ""
            self.answers[CASES[1][0]]["evidence"] = ""
            problems = errors_for(self.answers, CASES)
            self.assertTrue(any("reason" in item for item in problems))
            self.assertTrue(any("evidence" in item for item in problems))

        def test_wrong_answer_fails(self):
            self.answers["local_complete"]["done"] = False
            self.assertTrue(errors_for(self.answers, CASES))

        def test_malformed_result_fails(self):
            self.answers["local_complete"] = []
            self.assertTrue(errors_for(self.answers, CASES))

    return unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ValidatorSelfTest)
    ).wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prompt", action="store_true")
    mode.add_argument("--answers", type=Path)
    mode.add_argument("--self-test", action="store_true")
    parser.add_argument("--skills", type=Path, default=Path("skills"))
    parser.add_argument("--cases", nargs="+", choices=[case[0] for case in CASES])
    args = parser.parse_args()
    cases = [case for case in CASES if not args.cases or case[0] in args.cases]
    if args.self_test:
        return 0 if self_test() else 1
    if args.answers:
        try:
            answers = json.loads(args.answers.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print("git-mode-regression: cannot read answers: {}".format(exc))
            return 1
        return 0 if validate(answers, cases) else 1

    required = ["superloop", "superauthor", "supergoal", "superplan", "superrun",
                "superfinish", "supertraverse", "superagent", "superprd", "supermeta"]
    missing = [name for name in required if not (args.skills / name / "SKILL.md").is_file()]
    if missing:
        print("git-mode-regression: missing skills: " + ", ".join(missing))
        return 2
    print("Read the actual skill contracts under {} for: {}. Apply them to each independent "
          "fixture. This is an interpretation check: do not run git, gh, network, dispatch, or "
          "mutate fixtures. Return exactly one JSON object keyed by the selected scenario ids. "
          "Each result must include nonempty `reason` and `evidence` strings naming the governing "
          "skill rule and fixture fact, plus the requested typed fields.".format(
              args.skills.resolve(), ", ".join(required)))
    for name, scenario, expected in cases:
        print("\n{}: {}\nReturn fields: {}".format(name, scenario, ", ".join(expected)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

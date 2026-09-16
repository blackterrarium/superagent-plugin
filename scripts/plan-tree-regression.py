#!/usr/bin/env python3
"""Print upfront plan-tree probes or validate fresh-interpreter JSON answers.

This program performs no model, network, Git, or fixture calls. Give ``--prompt``
output to a fresh read-only interpreter, save its single JSON object, and check it
with ``--answers``. Results exercise interpreted skill contracts, not transport.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest


CASES = (
    ('legacy_default',
     'The root has no Planning mode marker. The current environment requests upfront mode. '
     'Resolve the mode without rewriting the root.',
     {'mode': 'incremental'}),
    ('bounded_unknown',
     'An upfront implementation stage fixes scope, architecture, acceptance, contracts, and '
     'verification scenarios. Internal filenames depend on predecessor evidence; the stage '
     'bounds those names, says how preparation will resolve them, and has no preparation receipt.',
     {'upfront_valid': True, 'executable': False}),
    ('missing_architecture',
     'An upfront stage says its persistence architecture will be chosen later. It gives no '
     'bounded alternatives, decision criteria, evidence method, or discovery-stage contract.',
     {'upfront_valid': False}),
    ('open_provider',
     'S02 consumes C-INGEST@1 from S01. S01 has a closeout, but its code PR remains open and '
     'the merge commit is absent from main. Classify S02 and whole-goal completion.',
     {'executable': False, 'done': False}),
    ('declined_provider',
     'S01 was declined with an approved disposition. Active S02 still consumes C-INGEST@1 from '
     'S01, and no adopted replan removes or replaces that contract. Classify S02 and completion.',
     {'executable': False, 'done': False}),
    ('dependency_cycle',
     'The active upfront graph has S01 Depends on S02 and S02 Depends on S01. All files and stage '
     'IDs otherwise exist. Classify validation/selection.',
     {'outcome': 'BLOCKED'}),
    ('temporary_upfront_gate',
     'The current Task 1 build has a valid upfront-v1 graph and a stage with a documentation-valid '
     'PREPARED receipt. Tasks 3 and 5 have not yet installed preparation and operation-routing '
     'consumers. Classify a planning or execution selection attempt in this intermediate build.',
     {'outcome': 'BLOCKED'}),
    ('local_detail',
     'New predecessor evidence changes only file placement, helper names, and test setup. Scope, '
     'acceptance, dependency edges, shared contract behavior, and all other commitments survive.',
     {'operation': 'refine', 'role': 'PLAN_REFINER'}),
    ('contract_break',
     'Verified evidence shows a required shared output behavior cannot be preserved. Downstream '
     'consumers rely on that semantic contract.',
     {'operation': 'replan', 'role': 'REPLANNER'}),
)


def select_cases(names=None):
    """Return cases in canonical order, rejecting unknown names."""
    if not names:
        return CASES
    requested = set(names)
    known = {case[0] for case in CASES}
    unknown = sorted(requested - known)
    if unknown:
        raise ValueError('unknown case(s): ' + ', '.join(unknown))
    return tuple(case for case in CASES if case[0] in requested)


def render_prompt(skills, cases):
    """Build a probe prompt containing facts and field names, never answer values."""
    lines = [
        'Read the supplied canonical skill contracts at ' + str(skills.resolve()) +
        '/{superstage,superauthor,supertraverse}/SKILL.md. Apply their rules to each independent '
        'fixture below. This is a read-only interpretation: do not dispatch, mutate files, call '
        'Git/network services, read implementation reports, or invent absent rules.',
        'Return one JSON object keyed by scenario id. Every result must be a JSON object with a '
        'nonempty string reason citing the governing rule/evidence, plus every requested field. '
        'Use JSON booleans where a field asks for a boolean and contract spellings for strings.',
        'Global output vocabulary (not per-case answers): mode is incremental, upfront-v1, or '
        'unsupported; outcome is BLOCKED, continue, or done; operation is refine, replan, or none; '
        'role is PLAN_REFINER, REPLANNER, or none; upfront_valid, executable, and done are JSON '
        'booleans.',
    ]
    for name, facts, expected in cases:
        lines.extend(('', name + ': ' + facts,
                      'Return fields: reason, ' + ', '.join(expected.keys())))
    return '\n'.join(lines) + '\n'


def validate_answers(answers, cases):
    """Return human-readable validation errors for a decoded answer object."""
    if not isinstance(answers, dict):
        return ['top-level answer must be a JSON object']

    errors = []
    expected_names = {case[0] for case in cases}
    actual_names = set(answers)
    missing = sorted(expected_names - actual_names)
    unexpected = sorted(actual_names - expected_names)
    if missing:
        errors.append('missing case(s): ' + ', '.join(missing))
    if unexpected:
        errors.append('unexpected case(s): ' + ', '.join(unexpected))

    for name, _, expected in cases:
        if name not in answers:
            continue
        actual = answers[name]
        if not isinstance(actual, dict):
            errors.append(name + ': answer must be a JSON object')
            continue
        reason = actual.get('reason')
        if not isinstance(reason, str) or not reason.strip():
            errors.append(name + '.reason: must be a nonempty string')
        for key, value in expected.items():
            if key not in actual:
                errors.append(name + '.' + key + ': missing required field')
                continue
            observed = actual[key]
            if type(observed) is not type(value) or observed != value:  # bool is not integer here
                errors.append(name + '.' + key + ': expected ' + json.dumps(value) +
                              ', got ' + json.dumps(observed, sort_keys=True))
    return errors


def load_answers(path):
    """Decode an answers file and return (value, error), without leaking a traceback."""
    try:
        return json.loads(path.read_text(encoding='utf-8')), None
    except OSError as exc:
        return None, 'cannot read answers: ' + str(exc)
    except (UnicodeError, json.JSONDecodeError) as exc:
        return None, 'malformed answers JSON: ' + str(exc)


class ValidatorTests(unittest.TestCase):
    def valid_answers(self, cases=CASES):
        return {name: dict(expected, reason='Applied superstage evidence rule.')
                for name, _, expected in cases}

    def test_accepts_all_exact_cases_and_required_values(self):
        self.assertEqual(validate_answers(self.valid_answers(), CASES), [])

    def test_selected_cases_require_exact_selected_membership(self):
        cases = select_cases(['contract_break', 'legacy_default'])
        self.assertEqual([case[0] for case in cases], ['legacy_default', 'contract_break'])
        answers = self.valid_answers(cases)
        self.assertEqual(validate_answers(answers, cases), [])
        answers['bounded_unknown'] = {'reason': 'extra'}
        self.assertIn('unexpected case(s): bounded_unknown', validate_answers(answers, cases))

    def test_rejects_missing_case(self):
        answers = self.valid_answers()
        del answers['open_provider']
        self.assertIn('missing case(s): open_provider', validate_answers(answers, CASES))

    def test_rejects_unknown_case_selection(self):
        with self.assertRaisesRegex(ValueError, 'unknown case'):
            select_cases(['not-a-case'])

    def test_rejects_non_object_top_level_and_case_values(self):
        self.assertTrue(validate_answers([], CASES))
        answers = self.valid_answers()
        answers['legacy_default'] = 'incremental'
        self.assertIn('legacy_default: answer must be a JSON object',
                      validate_answers(answers, CASES))

    def test_rejects_missing_empty_and_non_string_reasons(self):
        for bad_reason in (None, '', '   ', True, 7, []):
            with self.subTest(reason=bad_reason):
                answers = self.valid_answers()
                if bad_reason is None:
                    del answers['legacy_default']['reason']
                else:
                    answers['legacy_default']['reason'] = bad_reason
                self.assertIn('legacy_default.reason: must be a nonempty string',
                              validate_answers(answers, CASES))

    def test_rejects_missing_wrong_and_bool_integer_types(self):
        answers = self.valid_answers()
        del answers['bounded_unknown']['executable']
        self.assertIn('bounded_unknown.executable: missing required field',
                      validate_answers(answers, CASES))
        answers = self.valid_answers()
        answers['bounded_unknown']['upfront_valid'] = 1
        errors = validate_answers(answers, CASES)
        self.assertTrue(any(error.startswith('bounded_unknown.upfront_valid:') for error in errors))
        answers = self.valid_answers()
        answers['legacy_default']['mode'] = False
        self.assertTrue(any(error.startswith('legacy_default.mode:')
                            for error in validate_answers(answers, CASES)))

    def test_prompt_has_facts_and_fields_without_expected_values(self):
        prompt = render_prompt(Path('skills'), select_cases(['legacy_default', 'bounded_unknown']))
        vocabulary = ('Global output vocabulary (not per-case answers): mode is incremental, '
                      'upfront-v1, or unsupported; outcome is BLOCKED, continue, or done; operation '
                      'is refine, replan, or none; role is PLAN_REFINER, REPLANNER, or none; '
                      'upfront_valid, executable, and done are JSON booleans.')
        self.assertIn(vocabulary, prompt)
        self.assertEqual(prompt.count(vocabulary), 1)
        self.assertLess(prompt.index(vocabulary), prompt.index('legacy_default:'))
        self.assertIn('legacy_default:', prompt)
        self.assertIn('Return fields: reason, mode', prompt)
        self.assertIn('Return fields: reason, upfront_valid, executable', prompt)
        self.assertNotIn('mode: incremental', prompt)
        self.assertNotIn('upfront_valid: true', prompt.lower())
        self.assertNotIn('executable: false', prompt.lower())

    def test_load_answers_reports_malformed_json_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            malformed = Path(directory) / 'bad.json'
            malformed.write_text('{', encoding='utf-8')
            value, error = load_answers(malformed)
            self.assertIsNone(value)
            self.assertIn('malformed answers JSON:', error)
            value, error = load_answers(Path(directory) / 'missing.json')
            self.assertIsNone(value)
            self.assertIn('cannot read answers:', error)


def run_self_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ValidatorTests)
    return unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prompt', action='store_true', help='print fresh-interpreter prompt')
    group.add_argument('--answers', type=Path, help='validate a JSON answer file')
    group.add_argument('--self-test', action='store_true', help='run validator unit tests')
    parser.add_argument('--skills', type=Path, default=Path('skills'),
                        help='canonical skill directory named in the prompt')
    parser.add_argument('--cases', nargs='+', choices=[case[0] for case in CASES],
                        help='include only these cases (default: all)')
    args = parser.parse_args(argv)
    cases = select_cases(args.cases)

    if args.self_test:
        return 0 if run_self_tests() else 1
    if args.prompt:
        sys.stdout.write(render_prompt(args.skills, cases))
        return 0

    answers, error = load_answers(args.answers)
    if error:
        print('plan-tree-regression: ' + error, file=sys.stderr)
        return 2
    errors = validate_answers(answers, cases)
    if errors:
        for item in errors:
            print('FAIL: ' + item, file=sys.stderr)
        return 1
    print('PASS: ' + str(len(cases)) + ' plan-tree scenario answer(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

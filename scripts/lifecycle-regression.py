#!/usr/bin/env python3
"""Print fresh-agent lifecycle probes or validate their JSON answers (no model/network calls).

Example: python3 scripts/lifecycle-regression.py --prompt --skills skills
Give the prompt to a fresh agent; save its JSON result, then pass --answers result.json.
This exercises interpreted skill contracts, not scheduler/GitHub transport.
"""
import argparse
import json
from pathlib import Path
import unittest

CASES = [
    ('adopted_replan', 'One row: executed — PR open, Plan leaf, PR #1 open/BLOCKED, '
     'Closeout link and leaf closeout banner. Panel adopts re-plan 3/3. Apply the decision '
     'then compute the next planning target. No code has merged.',
     {'planning': 'repair', 'done': False, 'durable_repair': True}),
    ('mixed_none_blocked', 'plan_exhausted=true. Planner returned none. Executor returns none '
     'AND explicitly reports the sole closed-out leaf PR #1 still open/BLOCKED. No decision '
     'has resolved it. Choose supervisor outcome before any new panel result.',
     {'outcome': 'escalate', 'done': False}),
    ('closeout_repair', 'A valid committed adopted repair record names this step and old leaf. '
     'Row is repair requested, with old Plan and Closeout link; old leaf has closeout banner. '
     'Compute planning and execution selection before any successor is written.',
     {'planning': 'repair', 'execution': 'none', 'done': False}),
    ('merged', 'Both queues empty. Only active leaf is completed-and-merged. Code PR is verified '
     'MERGED and its merge commit is verified in main; closeout is tracked; no repairs/blockers.',
     {'done': True}),
    ('declined', 'Both queues empty. One leaf verified merged on main; another explicitly declined '
     'with a recorded authorized reason and PR disposition; no remaining repair or blocker.',
     {'done': True}),
    ('fresh_tick', 'Fresh tick knows only persisted files: loop has adopted re-plan in Decisions '
     'but no tree edit (crash before publication). Closed-out old leaf has open blocked PR. '
     'Recover the decision before dispatch and compute planning target.',
     {'planning': 'repair', 'durable_repair': True, 'done': False}),
    ('successor', 'Repair published: active Plan successor, ready-to-execute row, successor '
     'has no closeout. Predecessor and its closeout are linked only inside repair history. '
     'Old PR integration is explicitly planned; it remains open. Compute execution target.',
     {'execution': 'successor', 'done': False}),
    ('stale_ancestor', 'Both queues return none. Root row says completed-and-merged with Closeout '
     'but links to internal child table whose leaf is executed — PR open with open PR. '
     'No authorized disposition or successor exists. Audit completion.',
     {'done': False, 'outcome': 'escalate'}),
    ('missing_evidence', 'Both queues empty. Sole row says done with a closeout link, but its '
     'claimed merged PR cannot be queried and main integration cannot be verified.',
     {'done': False, 'outcome': 'escalate'}),
    ('late_closeout', 'Current step active Plan points to ready successor. Repair history '
     'points to predecessor. A delayed superfinish for predecessor reports old PR merged. '
     'Should it replace the active link or complete the successor row?',
     {'overwrite_successor': False}),
    ('replay', 'Same adopted repair decision is replayed after its successor was committed '
     'and active Plan already points to successor. Loop status lagged publication. '
     'Should recovery create another successor or reset the row to repair requested?',
     {'duplicate_successor': False, 'reset_repair': False}),
    ('hidden_ready', 'Both queues return none. Root closed row links to internal table with '
     'ordinary ready/unplanned unfinished work. C9 discovers it but C6 cannot reach it '
     'because the ancestor is closed. Choose audit outcome before any reconciliation.',
     {'done': False, 'outcome': 'escalate'}),
    ('second_repair', 'Valid tracked R1 decision published P0->P1. P1 later failed and a '
     'separate adopted R2 published P1->P2, the active ready successor. Fresh tick replays '
     'both decisions; all links and decisions agree. Is R1 a blocking contradiction?',
     {'outcome': 'continue', 'execution': 'successor', 'duplicate_successor': False}),
    ('declined_repair', 'Repair R1 was pending. A later authorized decline resolved that '
     'repair record and step with reason and PR disposition. Fresh tick replays the old '
     'R1 decision. Both queues empty, no other obligations. Should it reopen repair?',
     {'reset_repair': False, 'done': True}),
    ('direct_merge', 'Both queues empty. Sole active code leaf completed-and-merged without '
     'a PR under direct integration. Recorded integration commit is verified on local main '
     '(no remote exists), and closeout is tracked. No unresolved history.',
     {'done': True}),
    ('closed_pr', 'Both queues empty. Active row is closed-out. Code PR was CLOSED without '
     'merge; no decline/defer decision or successor exists.',
     {'done': False, 'outcome': 'escalate'}),
]


def validate(answers, cases):
    class Answers(unittest.TestCase):
        def test_scenarios(self):
            self.assertEqual(set(answers), {case[0] for case in cases})
            for name, _, expected in cases:
                with self.subTest(case=name):
                    actual = answers[name]
                    self.assertTrue(actual.get('reason'), 'Provide rule/evidence reasoning')
                    for key, value in expected.items():
                        self.assertEqual(actual.get(key), value, name + '.' + key)
    return unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Answers)).wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prompt', action='store_true')
    group.add_argument('--answers', type=Path)
    parser.add_argument('--skills', type=Path, default=Path('skills'))
    parser.add_argument('--cases', nargs='+', choices=[case[0] for case in CASES],
                        help='Run only selected scenarios (default: all)')
    args = parser.parse_args()
    cases = [case for case in CASES if not args.cases or case[0] in args.cases]
    if args.answers:
        return 0 if validate(json.loads(args.answers.read_text()), cases) else 1
    print('Read the supplied skill contracts at ' + str(args.skills.resolve()) +
          '/{superagent,supertraverse,superplan,superrun,superfinish}/SKILL.md. '
          'Apply their algorithms to independent fixtures below. This is a read-only simulation: '
          'no dispatch, git, network or fixture mutation. Do not read implementation reports or '
          'test expectations. Return one JSON object keyed by scenario id. Each result needs '
          'a reason citing the governing rule plus the requested fields. Use booleans for done, '
          'durable_repair, overwrite_successor, duplicate_successor, reset_repair; '
          'planning values repair/none/other; execution values successor/none/other; '
          'outcome values escalate/continue/done. Do not improve or invent absent rules.')
    for name, scenario, expected in cases:
        print('\n' + name + ': ' + scenario + '\nReturn fields: ' + ', '.join(expected))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

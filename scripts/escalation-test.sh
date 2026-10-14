#!/usr/bin/env bash
# escalation-test.sh — offline tests for the SUPER_PROTECTED_PATHS helpers in _common.sh
# (superagent_protected_globs / superagent_protected_match). No network, no CLI.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=_common.sh
. "$ROOT/scripts/_common.sh"
fail() { echo "escalation-test: FAIL — $*" >&2; exit 1; }

# Unset and empty: nothing is protected, and the matcher says so with exit 1.
unset SUPER_PROTECTED_PATHS
[ -z "$(superagent_protected_globs)" ] || fail "unset key printed globs"
if superagent_protected_match tests/gate/a.py >/dev/null; then fail "unset key matched"; fi
SUPER_PROTECTED_PATHS=
if superagent_protected_match tests/gate/a.py >/dev/null; then fail "empty key matched"; fi

# The shipped default leaves the key empty.
grep -qE '^SUPER_PROTECTED_PATHS=[[:space:]]*(#|$)' "$ROOT/templates/superenv.default" \
  || fail "superenv.default must ship SUPER_PROTECTED_PATHS empty"

# Globs are split on commas and trimmed; a glob is never expanded against the filesystem.
SUPER_PROTECTED_PATHS=' tests/gate/** , tools/release_check.py,src/pkg/dev/ ,,'
want=$'tests/gate/**\ntools/release_check.py\nsrc/pkg/dev/'
[ "$(cd "$ROOT" && superagent_protected_globs)" = "$want" ] || fail "glob parsing: $(superagent_protected_globs | tr '\n' '|')"

# Matching: `**` and `*` cross directories, a trailing `/` covers the tree, `./` is ignored.
out="$(superagent_protected_match tests/gate/deep/x_test.py ./tools/release_check.py src/pkg/dev/runner.py src/pkg/app.py tools/other.py)" \
  || fail "matcher returned no match"
[ "$out" = $'tests/gate/deep/x_test.py\ntools/release_check.py\nsrc/pkg/dev/runner.py' ] || fail "matches: $(tr '\n' '|' <<<"$out")"

# Paths on stdin, as from `git diff --name-only`.
out="$(printf 'README.md\ntools/release_check.py\n' | superagent_protected_match)" || fail "stdin form returned no match"
[ "$out" = tools/release_check.py ] || fail "stdin matches: $out"
if printf 'README.md\nsrc/pkg/app.py\n' | superagent_protected_match >/dev/null; then fail "unprotected stdin matched"; fi

# The escalation rules live in skill prose; pin the ones a rewrite must not lose.
pin() { grep -qF -- "$2" "$ROOT/skills/$1/SKILL.md" || fail "$1 SKILL.md lost: $2"; }
pin superrun '### CI-failure triage — before BLOCKED'
pin superrun 'A duration that matches a configured limit is sufficient evidence of a timeout'
pin superrun 'At most **two**'
pin superrun 'red CI still never merges'
pin superbuild 'the resolution would change a **protected surface**'
pin superloop 'The packet states facts and pointers, not conclusions.'
pin superloop 'One panelist argues for the simple answer.'
pin superloop 'a bare one is'
pin superloop 'Fetch, then re-run once.'
pin superloop '### Repeat check (before every Rung 2)'
pin superloop 'No option in a repeat block may ask for more evidence, more diagnostic attempts, more budget, or an'
pin superloop 'A repeat may not converge on an unchanged retry.'
pin superrun '### Resume entry — approved protected change'
pin superloop '**Required shape of a pending decision.**'
pin superloop '`answer: yes` approves exactly this change'
pin superloop 'every option asks for more authority, evidence, attempts or budget'
pin superloop 'no panel vote can approve them or weaken acceptance'
pin superagent '**Request approval for one specific protected change:**'

# 0.15.0: constraint origins, cap summaries, investigation outside the delivery, CHECKPOINT.
pin superreplan '## Label every constraint by origin'
pin superreplan 'Never add a constraint that forbids the fix the request'
pin superreplan 'Diagnostic budgets (attempt counts, evidence lanes, observation passes) are always `[planner]`.'
pin superrefine 'carries the origin tag `[planner]`'
pin superbuild '**Constraint origin.**'
pin superbuild 'An untagged constraint is not `[planner]` for this purpose.'
pin superbuild '**At a cap, report the cheapest unblock.**'
pin superbuild '**Keep investigation out of the delivery.**'
pin superbuild '### B4.6 Deadline check — yield before the wall clock'
pin superrun '#### CHECKPOINT — yield before the wall-clock limit'
pin superrun '### Resume entry — checkpoint (superagent-driven)'
pin superrun '**Cap summary:**'
pin superloop '**Constraint origins.**'
pin superagent '### Executor checkpoints and timeouts'
pin superrun '### Resume entry — targeted round (superagent-driven)'
pin superagent 'At most one targeted round per open finding per leaf'
pin superagent 'This never escalates to the owner'

echo 'escalation-test: PASS'

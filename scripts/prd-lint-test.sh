#!/usr/bin/env bash
# prd-lint-test.sh — offline tests for scripts/prd-lint.sh. Fixture project folders live in a
# temp dir standing in for a repo (PRD_LINT_REPO_ROOT); no network, no LLM. Exit 1 on any failure.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LINT="$ROOT/scripts/prd-lint.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export PRD_LINT_REPO_ROOT="$T/repo"
mkdir -p "$T/repo/src" "$T/repo/tests/ingest" "$T/repo/examples/csv"
printf 'def main():\n    pass\n' >"$T/repo/src/app.py"
: >"$T/repo/tests/ingest/test_a.py"
: >"$T/repo/examples/csv/README.md"
: >"$T/repo/CLAUDE.md"
FAILS=0
ok()   { echo "ok   - $1"; }
fail() { echo "FAIL - $1"; FAILS=$((FAILS+1)); }

# expect <name> <want-exit> <grep-pattern> <project-dir> [lint args…]
# Runs the linter and asserts the exit code AND that one output line matches the pattern.
expect() {
  local name="$1" want="$2" pat="$3" dir="$4"; shift 4
  local out rc
  out="$("$LINT" "$dir" "$@" 2>&1)"; rc=$?
  if [[ "$rc" == "$want" ]] && grep -q -- "$pat" <<<"$out"; then ok "$name"
  else fail "$name (rc=$rc want=$want, pattern '$pat')"; printf '%s\n' "$out" | tail -8 | sed 's/^/       | /'; fi
}

# valid_project <dir> — the reference project folder every negative test mutates a copy of.
valid_project() {
  mkdir -p "$1"
  cat >"$1/prd.md" <<'EOF'
# PRD — 2026-09-05-10_00-demo
**Date:** 2026-09-05 · **Status:** READY · **Related:** [[projects/2026-09-05-10_00-demo/evaluation]]

## Objective
A demo CLI that ingests CSV files.

## Success criteria
| Id | Criterion | Verified by (check ids) |
|---|---|---|
| SC1 | The test suite passes | C1 |
| SC2 | Errors are user-readable | J1 |

## Constraints and non-goals
- none

## Locked decisions
- none

## Iteration ledger
| Round | Meta-plan | Goal folder | Inner loop | Eval report | Verdict |
|---|---|---|---|---|---|
EOF
  cat >"$1/knowledge-base.md" <<'EOF'
# Knowledge base — 2026-09-05-10_00-demo
**Date:** 2026-09-05 · **Status:** READY · **Related:** [[projects/2026-09-05-10_00-demo/prd]]

| Id | Kind | Locator | Read for |
|---|---|---|---|
| K1 | `instructions` | `CLAUDE.md` | repo conventions |
| K2 | `repo-file` | `src/app.py` | the entry point |
| K3 | `repo-glob` | `tests/ingest/**` | test style |
| K4 | `doc-url` | `https://example.com/docs` | vendor docs |
| K5 | `context7` | `/vercel/next.js` | framework docs |
| K6 | `sample-code` | `examples/csv/` | worked example |
| K7 | `entry-point` | `src/app.py:main` | where the feature is wired in |
EOF
  cat >"$1/evaluation.md" <<'EOF'
# Evaluation — 2026-09-05-10_00-demo
**Date:** 2026-09-05 · **Status:** READY · **Related:** [[projects/2026-09-05-10_00-demo/prd]]

## Environment
- setup: `true`
- cwd: `.`

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `true` | `.` | `exit 0` | 5 |

## Judged objectives
| Id | Objective | Criteria | Evidence to inspect |
|---|---|---|---|
| J1 | Errors are user-readable | Every failure path names the offending field | `src/app.py` |
EOF
}

# ── Task 2: files, headers, prd.md sections, ledger ───────────────────────────
valid_project "$T/valid"
expect "valid project exits 0"                0 'PASS prd.md:sections' "$T/valid"
expect "usage error without a dir"            2 'usage' ""
rm -rf "$T/p"; valid_project "$T/p"; rm "$T/p/evaluation.md"
expect "missing evaluation.md is a FAIL"      1 'FAIL evaluation.md:file' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's/\*\*Status:\*\* READY/Status READY/' "$T/p/prd.md"
expect "prd header without Status is a FAIL"  1 'FAIL prd.md:header' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak '/^## Constraints and non-goals/d' "$T/p/prd.md"
expect "missing prd section is a FAIL"        1 'FAIL prd.md:Constraints and non-goals missing' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's/^## Locked decisions/## Zz/; s/^## Objective/## Locked decisions/; s/^## Zz/## Objective/' "$T/p/prd.md"
expect "out-of-order prd section is a FAIL"   1 'FAIL prd.md:Success criteria .*out of order' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's/| Round | Meta-plan |/| Round | Plan |/' "$T/p/prd.md"
expect "wrong ledger header is a FAIL"        1 'FAIL prd.md:Iteration ledger' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's/|---|---|---|/|:---|:---|---:|/; /^| SC1 /d; /^| SC2 /d' "$T/p/prd.md"
expect "alignment separator with no rows is a FAIL" 1 'FAIL prd.md:Success criteria no success-criteria rows' "$T/p"

# ── Task 3: knowledge-base kinds ──────────────────────────────────────────────
expect "valid kb rows PASS"                     0 'PASS knowledge-base.md:K7' "$T/valid"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| Id | Kind | Locator | Read for |#| Id | Type | Locator | Read for |#' "$T/p/knowledge-base.md"
expect "wrong kb table header is a FAIL"        1 'FAIL knowledge-base.md:header' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#`src/app.py` | the entry point#`src/nope.py` | the entry point#' "$T/p/knowledge-base.md"
expect "missing repo-file is a FAIL"            1 "FAIL knowledge-base.md:K2 repo-file 'src/nope.py' not found" "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#`tests/ingest/\*\*`#`tests/nothing/**`#' "$T/p/knowledge-base.md"
expect "unmatched repo-glob is a FAIL"          1 'FAIL knowledge-base.md:K3' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#`https://example.com/docs`#`example.com/docs`#' "$T/p/knowledge-base.md"
expect "non-http doc-url is a FAIL"             1 'FAIL knowledge-base.md:K4' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#`/vercel/next.js`#`next.js`#' "$T/p/knowledge-base.md"
expect "malformed context7 id is a FAIL"        1 'FAIL knowledge-base.md:K5' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#`examples/csv/`#`examples/none/`#' "$T/p/knowledge-base.md"
expect "missing sample-code is a FAIL"          1 'FAIL knowledge-base.md:K6' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#`src/app.py:main`#`src/app.py:nosuchsymbol`#' "$T/p/knowledge-base.md"
expect "absent entry-point symbol is a WARN"    0 "WARN knowledge-base.md:K7 symbol 'nosuchsymbol' not found" "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#`src/app.py:main`#`src/app.py`#' "$T/p/knowledge-base.md"
expect "entry-point without :symbol is a FAIL"  1 'FAIL knowledge-base.md:K7' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| `instructions` |#| `wiki` |#' "$T/p/knowledge-base.md"
expect "unknown kind is a FAIL"                 1 "FAIL knowledge-base.md:K1 unknown kind 'wiki'" "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak '/^| K/d' "$T/p/knowledge-base.md"
expect "empty kb table is a FAIL"               1 'FAIL knowledge-base.md:table no source rows' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#`src/app.py` | the entry point#| the entry point#' "$T/p/knowledge-base.md"
expect "empty locator is a FAIL"                1 'FAIL knowledge-base.md:K2 repo-file has an empty locator' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#`src/app.py:main`#`src/app.py:`#' "$T/p/knowledge-base.md"
expect "entry-point with trailing colon is a FAIL" 1 'FAIL knowledge-base.md:K7 entry-point locator must be <path>:<symbol>' "$T/p"

# ── Task 4: evaluation checks, coverage, --json ───────────────────────────────
expect "valid evaluation PASSes"                 0 'PASS evaluation.md:C1' "$T/valid"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak '/^- setup:/d' "$T/p/evaluation.md"
expect "missing setup line is a FAIL"            1 'FAIL evaluation.md:Environment missing .- setup:' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#^- cwd: `.`#- cwd: `build/out`#' "$T/p/evaluation.md"
expect "nonexistent env cwd is a WARN"           0 "WARN evaluation.md:Environment cwd 'build/out' does not exist yet" "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| `exit 0` | 5 |#| `passes` | 5 |#' "$T/p/evaluation.md"
expect "malformed Pass when is a FAIL"           1 'FAIL evaluation.md:C1 Pass when must be' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| `exit 0` | 5 |#| `stdout ~ /ALL PASSED/` | 5 |#' "$T/p/evaluation.md"
expect "stdout regex Pass when is accepted"      0 'PASS evaluation.md:C1' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| `exit 0` | 5 |#| `exit 0` | soon |#' "$T/p/evaluation.md"
expect "non-numeric timeout is a FAIL"           1 'FAIL evaluation.md:C1 Timeout must be a whole number' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| `exit 0` | 5 |#| `exit 0` | 20 |#' "$T/p/evaluation.md"
SUPER_EVAL_TIMEOUT_MIN=10 expect "timeout above SUPER_EVAL_TIMEOUT_MIN is a FAIL" 1 'FAIL evaluation.md:C1 Timeout 20 exceeds SUPER_EVAL_TIMEOUT_MIN=10' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| C1 | `true` |#| C1 | `no-such-binary-xyz --run` |#' "$T/p/evaluation.md"
expect "command not on PATH is a WARN"           0 "WARN evaluation.md:C1 command 'no-such-binary-xyz' not on PATH" "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| C1 | `true` |#| C1 | `src/app.py` |#' "$T/p/evaluation.md"
expect "repo-relative command is a PASS"         0 "PASS evaluation.md:C1 command 'src/app.py'" "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| J1 | Errors#| C1 | Errors#' "$T/p/evaluation.md"
expect "duplicate check id is a FAIL"            1 'FAIL evaluation.md:ids duplicate check id(s): C1' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| Every failure path names the offending field |#|  |#' "$T/p/evaluation.md"
expect "judged row without criteria is a FAIL"   1 'FAIL evaluation.md:J1 judged objective has empty criteria' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak '/^| C1 /d; /^| J1 /d' "$T/p/evaluation.md"
expect "no checks at all is a FAIL"              1 'FAIL evaluation.md:checks no command checks or judged objectives' "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| SC1 | The test suite passes | C1 |#| SC1 | The test suite passes | C9 |#' "$T/p/prd.md"
expect "criterion naming an unknown check FAILs" 1 "FAIL prd.md:SC1 references unknown check id 'C9'" "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#^| C1 | `true` | `.` | `exit 0` | 5 |#| C1 | `true` | `.` | `exit 0` | 5 |\
| C2 | `true` | `.` | `exit 0` | 5 |#' "$T/p/evaluation.md"
expect "check serving no criterion FAILs"        1 "FAIL evaluation.md:C2 check id 'C2' serves no success criterion" "$T/p"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| SC1 | The test suite passes | C1 |#| SC1 | The test suite passes |  |#' "$T/p/prd.md"
expect "criterion with no check ids FAILs"       1 'FAIL prd.md:SC1 criterion has no check ids' "$T/p"
SUPER_EVAL_TIMEOUT_MIN=none expect "non-numeric SUPER_EVAL_TIMEOUT_MIN is a WARN and falls back" 0 "WARN evaluation.md:config SUPER_EVAL_TIMEOUT_MIN='none'" "$T/valid"
rm -rf "$T/p"; valid_project "$T/p"; sed -i.bak 's#| `exit 0` | 5 |#| `stdout ~ /ok\\|fine/` | 5 |#' "$T/p/evaluation.md"
expect "escaped pipe in a regex Pass when is accepted" 0 "PASS evaluation.md:C1 Pass when 'stdout ~ /ok|fine/' well-formed" "$T/p"
expect "--json emits an array"                   0 '^\[{"level":"' "$T/valid" --json
if command -v python3 >/dev/null 2>&1; then
  if "$LINT" "$T/valid" --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d and all(set(x)=={"level","file","loc","message"} for x in d)'; then
    ok "--json parses and has the four keys"
  else fail "--json parses and has the four keys"; fi
fi

echo "prd-lint-test: $FAILS failure(s)"
[[ $FAILS -eq 0 ]]

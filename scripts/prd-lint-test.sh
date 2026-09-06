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

echo "prd-lint-test: $FAILS failure(s)"
[[ $FAILS -eq 0 ]]

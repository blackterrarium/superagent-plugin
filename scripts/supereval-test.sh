#!/usr/bin/env bash
# supereval-test.sh — offline tests for scripts/_evalspec.sh (parser) and, in a later step,
# scripts/supereval.sh (the runner). Bash 3.2, no network, no LLM. Exit 1 on any failure.
# This revision covers the _evalspec.sh readers only (Stage 2 step 1).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$ROOT/scripts/_evalspec.sh"          # provides US/RS, evalspec_env, evalspec_checks
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
FAILS=0
ok()   { echo "ok   - $1"; }
fail() { echo "FAIL - $1"; FAILS=$((FAILS+1)); }

# ── evalspec_env prints "setup<US>cwd" ────────────────────────────────────────
cat >"$T/env.md" <<'EOF'
# Evaluation — env fixture
**Date:** 2026-09-06 · **Status:** READY

## Environment
- setup: `true`
- cwd: `.`

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `true` | `.` | `exit 0` | 5 |
EOF
if [[ "$(evalspec_env "$T/env.md")" == "true${US}." ]]; then
  ok "evalspec_env prints setup<US>cwd"
else
  fail "evalspec_env prints setup<US>cwd (got: $(evalspec_env "$T/env.md" | cat -v))"
fi

# ── \| round-trips to a literal | in the C record's command field (spec case 6, parser half) ──
# The command is printf 'a\|b' so BOTH wrong parsers fail: one that splits on | before unescaping
# loses the field; one that never unescapes keeps the backslash.
cat >"$T/pipe.md" <<'EOF'
# Evaluation — pipe fixture
**Date:** 2026-09-06 · **Status:** READY

## Environment
- setup: `true`
- cwd: `.`

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `printf 'a\|b'` | `.` | `exit 0` | 5 |
EOF
c_cmd="$(evalspec_checks "$T/pipe.md" | grep '^C' | head -1 | cut -d"$US" -f3)"
if [[ "$c_cmd" == "printf 'a|b'" ]]; then
  ok "evalspec_checks unescapes \\| to | in the command field"
else
  fail "evalspec_checks unescapes \\| (got: $(printf '%s' "$c_cmd" | cat -v))"
fi

# ── judged-only spec -> exactly one J record, five US fields, no C record (spec case 7 parser) ──
cat >"$T/judged.md" <<'EOF'
# Evaluation — judged-only fixture
**Date:** 2026-09-06 · **Status:** READY

## Environment
- setup: `true`
- cwd: `.`

## Judged objectives
| Id | Objective | Criteria | Evidence to inspect |
|---|---|---|---|
| J1 | Errors are readable | names the offending field | `src/app.py` |
EOF
out="$(evalspec_checks "$T/judged.md")"
ccount="$(printf '%s\n' "$out" | grep -c '^C' || true)"
jcount="$(printf '%s\n' "$out" | grep -c '^J' || true)"
jrec="$(printf '%s\n' "$out" | grep '^J' | head -1)"
nfields="$(printf '%s' "$jrec" | awk -F"$US" '{print NF}')"
jid="$(printf '%s' "$jrec" | cut -d"$US" -f2)"
if [[ "$ccount" == "0" && "$jcount" == "1" && "$nfields" == "5" && "$jid" == "J1" ]]; then
  ok "evalspec_checks emits one J record (5 US-fields) and no C record for a judged-only spec"
else
  fail "evalspec_checks judged-only (C=$ccount J=$jcount NF=$nfields id=$jid)"
fi

echo "supereval-test: $FAILS failure(s)"
[[ $FAILS -eq 0 ]]

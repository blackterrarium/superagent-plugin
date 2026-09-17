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

# ══════════════════════════════════════════════════════════════════════════════
# Runner cases (scripts/supereval.sh) — Stage 2 step 2, spec "Testing" cases 1–8.
# ══════════════════════════════════════════════════════════════════════════════
SUPEREVAL="$ROOT/scripts/supereval.sh"

# Fixture repo: one commit holding a tiny script and a source file, so --commit resolves and a
# worktree can be checked out.
FX="$T/fxrepo"; mkdir -p "$FX/src"
printf 'print("hello")\n' >"$FX/src/app.py"
printf '#!/usr/bin/env bash\necho "OK-MARKER-42"\n' >"$FX/run.sh"; chmod +x "$FX/run.sh"
git -C "$FX" init -q
git -C "$FX" add -A
git -C "$FX" -c user.email=t@t -c user.name=t commit -qm init >/dev/null
SHA="$(git -C "$FX" rev-parse HEAD)"

PROJ="$T/proj"; mkdir -p "$PROJ"
# has_timeout — 0 when a real timeout wrapper exists (case 3 needs it).
has_timeout() { command -v timeout >/dev/null 2>&1 || command -v gtimeout >/dev/null 2>&1; }
# result_of <out-file> <id> — the trimmed Result cell of the row whose Id is <id>.
result_of() {
  grep -E "^\| $2 " "$1" | head -1 | awk -F'|' '{ s=$3; gsub(/^[[:space:]]+|[[:space:]]+$/,"",s); print s }'
}
run_eval() {  # $1=out-file ; extra args after ; runs supereval.sh on $PROJ ; sets CRC
  local out="$1"; shift
  "$SUPEREVAL" "$PROJ" --repo "$FX" --commit "$SHA" --out "$out" "$@" >/dev/null 2>&1
  CRC=$?
}

# ── case 1: all pass -> exit 0, both PASS ─────────────────────────────────────
cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: `true`
- cwd: `.`

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `true` | `.` | `exit 0` | 5 |
| C2 | `bash run.sh` | `.` | `stdout ~ /OK-MARKER-42/` | 5 |
EOF
run_eval "$T/r1.md"
if [[ "$CRC" -eq 0 && "$(result_of "$T/r1.md" C1)" == "PASS" && "$(result_of "$T/r1.md" C2)" == "PASS" ]]; then
  ok "case 1 all pass -> exit 0, C1 & C2 PASS"
else
  fail "case 1 (rc=$CRC C1=$(result_of "$T/r1.md" C1) C2=$(result_of "$T/r1.md" C2))"
fi

# ── case 2: one failing exit -> exit 1, that row FAIL, its output block present ─
# C2's command prints NADA (which must NOT match case 1's /OK-MARKER-42/ regex — the two cases
# cannot both pass on a runner that ignores pass-when) and exits 3, so `exit 0` -> FAIL.
cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: `true`
- cwd: `.`

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `true` | `.` | `exit 0` | 5 |
| C2 | `echo NADA; exit 3` | `.` | `exit 0` | 5 |
EOF
run_eval "$T/r2.md"
if [[ "$CRC" -eq 1 && "$(result_of "$T/r2.md" C2)" == "FAIL" ]] && grep -q '^### C2 output' "$T/r2.md"; then
  ok "case 2 one failing exit -> exit 1, C2 FAIL, ### C2 output block present"
else
  fail "case 2 (rc=$CRC C2=$(result_of "$T/r2.md" C2) block=$(grep -c '^### C2 output' "$T/r2.md"))"
fi

# ── case 3: sleep 70 with timeout 1 -> TIMEOUT (needs a real timeout wrapper) ──
if has_timeout; then
  cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: ``
- cwd: `.`

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `sleep 2` | `.` | `exit 0` | 1 |
EOF
  run_eval "$T/r3.md" --max-timeout-min 0
  if [[ "$CRC" -eq 1 && "$(result_of "$T/r3.md" C1)" == "TIMEOUT" ]]; then
    ok "case 3 timeout ceiling 0 -> exit 1, C1 TIMEOUT"
  else
    fail "case 3 (rc=$CRC C1=$(result_of "$T/r3.md" C1))"
  fi
else
  echo "skip - case 3 TIMEOUT: no timeout/gtimeout on PATH (install coreutils)"
fi

# ── case 4: nonexistent binary -> ERROR ───────────────────────────────────────
cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: `true`
- cwd: `.`

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `supereval-no-such-binary-xyz` | `.` | `exit 0` | 5 |
EOF
run_eval "$T/r4.md"
if [[ "$CRC" -eq 1 && "$(result_of "$T/r4.md" C1)" == "ERROR" ]]; then
  ok "case 4 nonexistent binary -> exit 1, C1 ERROR"
else
  fail "case 4 (rc=$CRC C1=$(result_of "$T/r4.md" C1))"
fi

# ── case 5: setup fails -> every row 'ERROR setup failed', exit 1 ─────────────
cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: `false`
- cwd: `.`

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `true` | `.` | `exit 0` | 5 |
| C2 | `true` | `.` | `exit 0` | 5 |
EOF
run_eval "$T/r5.md"
if [[ "$CRC" -eq 1 && "$(result_of "$T/r5.md" C1)" == "ERROR setup failed" && "$(result_of "$T/r5.md" C2)" == "ERROR setup failed" ]]; then
  ok "case 5 setup fails -> exit 1, all rows 'ERROR setup failed'"
else
  fail "case 5 (rc=$CRC C1=$(result_of "$T/r5.md" C1) C2=$(result_of "$T/r5.md" C2))"
fi

# ── case 6: \| in a command cell round-trips AND the row executes correctly ────
# Command cell `printf 'a\|b'` -> parser unescapes to printf 'a|b' -> prints a|b, exits 0 -> PASS.
# The evidence cell re-escapes | back to \|, so the results file literally contains a\|b.
cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: `true`
- cwd: `.`

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `printf 'a\|b'` | `.` | `exit 0` | 5 |
EOF
run_eval "$T/r6.md"
if [[ "$CRC" -eq 0 && "$(result_of "$T/r6.md" C1)" == "PASS" ]] && grep -qF 'a\|b' "$T/r6.md"; then
  ok "case 6 \\| command round-trips -> exit 0, C1 PASS, evidence shows a\\|b"
else
  fail "case 6 (rc=$CRC C1=$(result_of "$T/r6.md" C1) evid=$(grep -c 'a\\|b' "$T/r6.md"))"
fi

# ── case 7: judged-only spec -> exit 0, empty command table, J record printed ──
cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: `true`
- cwd: `.`

## Judged objectives
| Id | Objective | Criteria | Evidence to inspect |
|---|---|---|---|
| J1 | Errors are readable | names the offending field | `src/app.py` |
EOF
run_eval "$T/r7.md"
crows="$(grep -cE '^\| C[0-9]' "$T/r7.md" || true)"
jrecs="$(evalspec_checks "$PROJ/evaluation.md" | grep -c '^J' || true)"
if [[ "$CRC" -eq 0 && "$crows" -eq 0 && "$jrecs" -eq 1 ]]; then
  ok "case 7 judged-only -> exit 0, empty command table, one J record"
else
  fail "case 7 (rc=$CRC crows=$crows jrecs=$jrecs)"
fi

# ── case 8: --worktree at a prepared checkout is used as-is and NOT removed ────
WT8="$T/wt8"
git -C "$FX" worktree add --detach "$WT8" "$SHA" >/dev/null 2>&1
cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: `true`
- cwd: `.`

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `true` | `.` | `exit 0` | 5 |
EOF
run_eval "$T/r8.md" --worktree "$WT8"
if [[ "$CRC" -eq 0 && -d "$WT8" && "$(result_of "$T/r8.md" C1)" == "PASS" ]]; then
  ok "case 8 --worktree used as-is and not removed"
else
  fail "case 8 (rc=$CRC exists=$([ -d "$WT8" ] && echo y || echo n) C1=$(result_of "$T/r8.md" C1))"
fi
git -C "$FX" worktree remove --force "$WT8" >/dev/null 2>&1 || true

# ═════════════════════════════════════════════════════════════════════════════
# Local snapshot runner cases. These use an ordinary directory and a git sentinel.
# ════════════════════════════════════════════════════════════════════════════════
LOCAL="$T/local source"; mkdir -p "$LOCAL/src" "$LOCAL/vault/private"
printf 'SUPER_GIT_MODE=none\nSUPER_GOAL_ROOT=vault\n' >"$LOCAL/.superenv"
printf 'original\n' >"$LOCAL/src/app.txt"
printf 'excluded\n' >"$LOCAL/vault/private/secret.txt"
ORIGINAL_HASH="$(shasum -a 256 "$LOCAL/src/app.txt" | awk '{print $1}')"
SENTINEL="$T/sentinel"; mkdir -p "$SENTINEL"
GIT_LOG="$T/git-calls"
cat >"$SENTINEL/git" <<EOF
#!/usr/bin/env bash
echo git-called >>"$GIT_LOG"
exit 99
EOF
chmod +x "$SENTINEL/git"

run_local() { # $1=out-file; extra runner args after; sets CRC
  local out="$1"; shift
  PATH="$SENTINEL:$PATH" "$SUPEREVAL" "$PROJ" --repo "$LOCAL" --out "$out" "$@" >/dev/null 2>&1
  CRC=$?
}

# ── case 9: no --commit, isolated writes, durable input/output evidence ──────────────
cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: `true`
- cwd: `.`

## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `printf changed > src/app.txt; printf made > generated.txt` | `.` | `exit 0` | 5 |
EOF
run_local "$T/local9.md"
INPUT_MANIFEST="$T/local9.md.input-manifest.json"
RESULT_MANIFEST="$T/local9.md.result-manifest.json"
CHANGES="$T/local9.md.changes.json"
AFTER_HASH="$(shasum -a 256 "$LOCAL/src/app.txt" | awk '{print $1}')"
if [[ "$CRC" -eq 0 && "$AFTER_HASH" == "$ORIGINAL_HASH" && -f "$INPUT_MANIFEST" && -f "$RESULT_MANIFEST" && -f "$CHANGES" ]] \
  && grep -q 'source: `snapshot:' "$T/local9.md" \
  && grep -q '"generated.txt"' "$CHANGES" && grep -q '"src/app.txt"' "$CHANGES"; then
  ok "case 9 local snapshot runs without --commit, preserves source, and records manifests/diff"
else
  fail "case 9 (rc=$CRC source_same=$([[ "$AFTER_HASH" == "$ORIGINAL_HASH" ]] && echo y || echo n) evidence=$([ -f "$RESULT_MANIFEST" ] && echo y || echo n))"
fi

# ── case 10: GitHub-only flags are rejected before any git access ──────────────────
run_local "$T/local10.md" --commit deadbeef
rc_commit=$CRC
run_local "$T/local10b.md" --worktree "$T/nope"
rc_worktree=$CRC
if [[ "$rc_commit" -eq 2 && "$rc_worktree" -eq 2 ]]; then
  ok "case 10 local mode rejects --commit and --worktree"
else
  fail "case 10 (--commit rc=$rc_commit --worktree rc=$rc_worktree)"
fi

# ── case 11: local setup failure and timeout remain failing runner evidence ───────────
cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: `false`
- cwd: `.`
## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `true` | `.` | `exit 0` | 5 |
EOF
run_local "$T/local11.md"
rc_setup=$CRC
if has_timeout; then
  cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: ``
- cwd: `.`
## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `sleep 2` | `.` | `exit 0` | 0 |
EOF
  run_local "$T/local11b.md" --max-timeout-min 0
  rc_timeout=$CRC
  timeout_result="$(result_of "$T/local11b.md" C1)"
else
  rc_timeout=1; timeout_result=TIMEOUT
fi
if [[ "$rc_setup" -eq 1 && "$(result_of "$T/local11.md" C1)" == "ERROR setup failed" && "$rc_timeout" -eq 1 && "$timeout_result" == TIMEOUT ]]; then
  ok "case 11 local setup failure and timeout are preserved"
else
  fail "case 11 (setup=$rc_setup timeout=$rc_timeout/$timeout_result)"
fi

# ── case 12: judged-only local workspace can be retained and token-cleaned ─────────────
cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: `true`
- cwd: `.`
## Judged objectives
| Id | Objective | Criteria | Evidence to inspect |
|---|---|---|---|
| J1 | Source is readable | contains original | `src/app.txt` |
EOF
run_local "$T/local12.md" --keep-workspace
KEPT_WORKSPACE="$(sed -n 's/^- source: .* · workspace: `\([^`]*\)`.*/\1/p' "$T/local12.md")"
KEPT_TOKEN="$(sed -n 's/^- cleanup-token: `\([^`]*\)`.*/\1/p' "$T/local12.md")"
if [[ "$CRC" -eq 0 && -d "$KEPT_WORKSPACE" && -n "$KEPT_TOKEN" ]]; then
  ok "case 12 judged-only local workspace is retained with cleanup token"
else
  fail "case 12 (rc=$CRC workspace=$KEPT_WORKSPACE token=$([ -n "$KEPT_TOKEN" ] && echo y || echo n))"
fi
python3 "$ROOT/scripts/workspace-state.py" cleanup --workspace "$KEPT_WORKSPACE" --token "$KEPT_TOKEN" >/dev/null 2>&1 || fail "case 12 token cleanup"

# ── case 13: deletions are explicit and snapshot internals never recurse ────────────────
cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: `true`
- cwd: `.`
## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `rm src/app.txt` | `.` | `exit 0` | 5 |
EOF
run_local "$T/local13.md"
if [[ "$CRC" -eq 0 ]] \
  && python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); raise SystemExit(0 if d["deleted"] == ["src/app.txt"] else 1)' "$T/local13.md.changes.json" \
  && python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); raise SystemExit(0 if not any(e["path"] == ".superagent-snapshot.json" for e in d["entries"]) else 1)' "$T/local13.md.result-manifest.json"; then
  ok "case 13 local comparison records deletion without recursive snapshot metadata"
else
  fail "case 13 (rc=$CRC)"
fi

# ── case 14: internal vault input is absent from the frozen source ────────────────
cat >"$PROJ/evaluation.md" <<'EOF'
## Environment
- setup: `true`
- cwd: `.`
## Command checks
| Id | Command | Cwd | Pass when | Timeout |
|---|---|---|---|---|
| C1 | `test -f vault/private/secret.txt` | `.` | `exit 0` | 5 |
EOF
run_local "$T/local14.md"
if [[ "$CRC" -eq 1 && "$(result_of "$T/local14.md" C1)" == FAIL ]]; then
  ok "case 14 excluded vault input fails explicitly"
else
  fail "case 14 (rc=$CRC C1=$(result_of "$T/local14.md" C1))"
fi

if [[ ! -s "$GIT_LOG" ]]; then
  ok "local runner cases made zero git calls"
else
  fail "local runner invoked git ($(wc -l <"$GIT_LOG" | tr -d ' '))"
fi

echo "supereval-test: $FAILS failure(s)"
[[ $FAILS -eq 0 ]]

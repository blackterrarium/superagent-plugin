#!/usr/bin/env bash
# supereval.sh — offline command-check runner for a coding-loop project's evaluation.md.
# Builds a git worktree of <commit>, runs the `## Command checks` rows against it, and writes a
# markdown results file the `supereval` skill embeds verbatim. Judged (`J`) rows are listed by
# _evalspec.sh but NOT run here — the skill dispatches an evaluator for those. Bash 3.2, no network,
# no LLM.
#
# Usage:
#   supereval.sh <project-dir> --repo <primary_root> --commit <sha> --out <results-file> \
#                [--worktree <dir>] [--keep-worktree] [--max-timeout-min <n>]
#
# Exit: 0 every command check PASS · 1 any not PASS (incl. setup failed) · 2 usage / script-setup.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$ROOT/scripts/_common.sh"     # load_superenv
. "$ROOT/scripts/_evalspec.sh"   # US/RS + evalspec_env/evalspec_checks

die2() { echo "supereval: $1" >&2; exit 2; }

# ── args ──────────────────────────────────────────────────────────────────────
PROJECT="" ; REPO="" ; COMMIT="" ; OUT="" ; WORKTREE="" ; KEEP=0 ; MAXTO=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)            REPO="${2:-}"; shift 2 ;;
    --commit)          COMMIT="${2:-}"; shift 2 ;;
    --out)             OUT="${2:-}"; shift 2 ;;
    --worktree)        WORKTREE="${2:-}"; shift 2 ;;
    --keep-worktree)   KEEP=1; shift ;;
    --max-timeout-min) MAXTO="${2:-}"; shift 2 ;;
    -* )               die2 "unknown flag: $1" ;;
    * )                if [ -z "$PROJECT" ]; then PROJECT="$1"; else die2 "unexpected argument: $1"; fi; shift ;;
  esac
done

[ -n "$PROJECT" ] || die2 "usage: supereval.sh <project-dir> --repo <repo> --commit <sha> --out <file> [--worktree <dir>] [--keep-worktree] [--max-timeout-min <n>]"
[ -d "$PROJECT" ] || die2 "not a directory: $PROJECT"
[ -n "$REPO" ]    || die2 "missing --repo"
[ -n "$COMMIT" ]  || die2 "missing --commit"
[ -n "$OUT" ]     || die2 "missing --out"
EVALFILE="$PROJECT/evaluation.md"
[ -f "$EVALFILE" ] || die2 "missing evaluation.md in $PROJECT"

load_superenv "$REPO"
CEIL_MIN="${MAXTO:-${SUPER_EVAL_TIMEOUT_MIN:-60}}"
case "$CEIL_MIN" in ''|*[!0-9]*) die2 "--max-timeout-min must be a whole number of minutes" ;; esac

mkdir -p "$(dirname "$OUT")" || die2 "cannot create output directory for $OUT"

# ── worktree ──────────────────────────────────────────────────────────────────
OWN_WORKTREE=0
if [ -z "$WORKTREE" ]; then
  WORKTREE="$(mktemp -d)"
  if ! git -C "$REPO" worktree add --detach "$WORKTREE" "$COMMIT" >/dev/null 2>&1; then
    rmdir "$WORKTREE" 2>/dev/null || true
    die2 "git worktree add failed for commit $COMMIT"
  fi
  OWN_WORKTREE=1
fi

WORK="$(mktemp -d)"
cleanup() {
  local rc=$?
  if [ "$OWN_WORKTREE" -eq 1 ] && [ "$KEEP" -eq 0 ]; then
    git -C "$REPO" worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK" 2>/dev/null || true
  exit "$rc"
}
trap cleanup EXIT

# ── timeout wrapper (mirrors superagent-tick.sh) ──────────────────────────────
TIMEOUT_BIN=""
if command -v timeout >/dev/null 2>&1; then TIMEOUT_BIN="timeout"
elif command -v gtimeout >/dev/null 2>&1; then TIMEOUT_BIN="gtimeout"
else echo "supereval: warning — no timeout/gtimeout on PATH; command checks run uncapped (install coreutils)" >&2
fi

TMP_OUT="$WORK/out" ; TMP_ERR="$WORK/err"
# run_cmd <command> <abs-dir> <timeout-seconds> — sets RC and SECS; stdout→TMP_OUT, stderr→TMP_ERR.
run_cmd() {
  local cmd="$1" dir="$2" secs="$3" start end
  start="$(date +%s)"
  if [ -n "$TIMEOUT_BIN" ]; then
    ( cd "$dir" 2>/dev/null && "$TIMEOUT_BIN" "$secs" bash -c "$cmd" ) >"$TMP_OUT" 2>"$TMP_ERR"
    RC=$?
  else
    ( cd "$dir" 2>/dev/null && bash -c "$cmd" ) >"$TMP_OUT" 2>"$TMP_ERR"
    RC=$?
  fi
  end="$(date +%s)"
  SECS=$(( end - start ))
}

# first_word_known <firstword> <abs-dir> — 0 if on PATH or a repo path (locked decision 6).
first_word_known() {
  local w="$1" dir="$2"
  command -v "$w" >/dev/null 2>&1 && return 0
  [ -e "$dir/$w" ] && return 0
  [ -e "$WORKTREE/$w" ] && return 0
  return 1
}

# pass_holds <pass-when> <exitcode> <stdout-file> — 0 if PASS.
pass_holds() {
  local pw="$1" ec="$2" of="$3"
  if [[ "$pw" =~ ^exit\ ([0-9]+)$ ]]; then
    [ "$ec" -eq "${BASH_REMATCH[1]}" ]
  elif [[ "$pw" =~ ^stdout\ ~\ /(.*)/$ ]]; then
    grep -Eq -- "${BASH_REMATCH[1]}" "$of"
  else
    return 1
  fi
}

# evidence_cell <stdout-file> <stderr-file> — last non-empty combined line, 120 chars, | -> \|.
evidence_cell() {
  local line
  line="$(cat "$1" "$2" 2>/dev/null | grep -v '^[[:space:]]*$' | tail -1)"
  line="${line:0:120}"
  printf '%s' "$line" | sed 's/|/\\|/g'
}

# ── setup ─────────────────────────────────────────────────────────────────────
ENVREC="$(evalspec_env "$EVALFILE")"
SETUP_CMD="$(printf '%s' "$ENVREC" | cut -d"$US" -f1)"
ENV_CWD="$(printf '%s' "$ENVREC" | cut -d"$US" -f2)"

SETUP_STATE="none" ; SETUP_FAILED=0 ; SETUP_EVID=""
BLOCKS="$WORK/blocks" ; : >"$BLOCKS"
if [ -n "$SETUP_CMD" ]; then
  run_cmd "$SETUP_CMD" "$WORKTREE${ENV_CWD:+/$ENV_CWD}" $(( CEIL_MIN * 60 ))
  if [ "$RC" -eq 124 ] && [ -n "$TIMEOUT_BIN" ]; then SETUP_STATE="timeout" ; SETUP_FAILED=1
  elif [ "$RC" -eq 0 ]; then SETUP_STATE="ok"
  else SETUP_STATE="exit $RC" ; SETUP_FAILED=1
  fi
  SETUP_EVID="$(evidence_cell "$TMP_OUT" "$TMP_ERR")"
  if [ "$SETUP_FAILED" -eq 1 ]; then
    { printf '### setup output\n```\n'; cat "$TMP_OUT" "$TMP_ERR" 2>/dev/null | tail -40; printf '\n```\n'; } >>"$BLOCKS"
  fi
fi

# ── command checks ────────────────────────────────────────────────────────────
ALL_PASS=1
ROWS="$WORK/rows" ; : >"$ROWS"
CHECKS="$(evalspec_checks "$EVALFILE")"
while IFS= read -r rec; do
  case "$rec" in "C$US"*) : ;; *) continue ;; esac
  id="$(printf '%s' "$rec" | cut -d"$US" -f2)"
  cmd="$(printf '%s' "$rec" | cut -d"$US" -f3)"
  ccwd="$(printf '%s' "$rec" | cut -d"$US" -f4)"
  pw="$(printf '%s' "$rec" | cut -d"$US" -f5)"
  to="$(printf '%s' "$rec" | cut -d"$US" -f6)"

  if [ "$SETUP_FAILED" -eq 1 ]; then
    printf '| %s | ERROR setup failed | - | - | `%s` |\n' "$id" "$SETUP_EVID" >>"$ROWS"
    ALL_PASS=0
    continue
  fi

  # effective per-check timeout = min(row, ceiling) minutes -> seconds
  row_min="$to" ; case "$row_min" in ''|*[!0-9]*) row_min="$CEIL_MIN" ;; esac
  eff_min="$row_min" ; [ "$eff_min" -gt "$CEIL_MIN" ] && eff_min="$CEIL_MIN"

  dir="$WORKTREE${ccwd:+/$ccwd}"
  run_cmd "$cmd" "$dir" $(( eff_min * 60 ))
  firstword="${cmd%%[[:space:]]*}"

  if [ "$RC" -eq 124 ] && [ -n "$TIMEOUT_BIN" ]; then result="TIMEOUT"
  elif ! first_word_known "$firstword" "$dir"; then result="ERROR"
  elif pass_holds "$pw" "$RC" "$TMP_OUT"; then result="PASS"
  else result="FAIL"
  fi
  [ "$result" = "PASS" ] || ALL_PASS=0

  evid="$(evidence_cell "$TMP_OUT" "$TMP_ERR")"
  printf '| %s | %s | %s | %s | `%s` |\n' "$id" "$result" "$RC" "$SECS" "$evid" >>"$ROWS"
  if [ "$result" != "PASS" ]; then
    { printf '### %s output\n```\n' "$id"; cat "$TMP_OUT" "$TMP_ERR" 2>/dev/null | tail -40; printf '\n```\n'; } >>"$BLOCKS"
  fi
done <<EOF
$CHECKS
EOF

# ── write results file ────────────────────────────────────────────────────────
{
  printf '## Environment\n'
  printf -- '- commit: `%s` · worktree: `%s` · setup: `%s` → %s\n\n' "$COMMIT" "$WORKTREE" "$SETUP_CMD" "$SETUP_STATE"
  printf '## Command checks\n'
  printf '| Id | Result | Exit | Seconds | Evidence |\n'
  printf '|---|---|---|---|---|\n'
  cat "$ROWS"
  if [ -s "$BLOCKS" ]; then printf '\n'; cat "$BLOCKS"; fi
} >"$OUT"

[ "$ALL_PASS" -eq 1 ] && exit 0 || exit 1

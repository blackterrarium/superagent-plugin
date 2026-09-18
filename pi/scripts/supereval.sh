#!/usr/bin/env bash
# supereval.sh — offline command-check runner for a coding-loop project's evaluation.md.
# Freezes either a git commit (`github`) or an owned filesystem snapshot (`none`), runs the command
# checks in that isolated workspace, and writes the results consumed by the supereval skill.
#
# Usage:
#   supereval.sh <project-dir> --repo <primary_root> --commit <sha> --out <results-file> \
#                [--worktree <dir>] [--keep-worktree] [--keep-workspace]
#                [--max-timeout-min <n>]
#
# Exit: 0 every command check PASS · 1 any not PASS (incl. setup failed) · 2 usage / script-setup.
set -u
ORIGINAL_ARGS=("$@")
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$ROOT/scripts/_common.sh"     # shared project/mode/vault resolver
. "$ROOT/scripts/_evalspec.sh"   # US/RS + evalspec_env/evalspec_checks

die2() { echo "supereval: $1" >&2; exit 2; }

# ── args ──────────────────────────────────────────────────────────────────────
PROJECT="" ; REPO="" ; COMMIT="" ; OUT="" ; WORKTREE="" ; KEEP_WORKTREE=0
KEEP_WORKSPACE=0 ; MAXTO=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)            REPO="${2:-}"; shift 2 ;;
    --commit)          COMMIT="${2:-}"; shift 2 ;;
    --out)             OUT="${2:-}"; shift 2 ;;
    --worktree)        WORKTREE="${2:-}"; shift 2 ;;
    --keep-worktree)   KEEP_WORKTREE=1; shift ;;
    --keep-workspace)  KEEP_WORKSPACE=1; shift ;;
    --max-timeout-min) MAXTO="${2:-}"; shift 2 ;;
    -* )               die2 "unknown flag: $1" ;;
    * )                if [ -z "$PROJECT" ]; then PROJECT="$1"; else die2 "unexpected argument: $1"; fi; shift ;;
  esac
done

[ -n "$PROJECT" ] || die2 "usage: supereval.sh <project-dir> --repo <repo> [--commit <sha>] --out <file> [--worktree <dir>] [--keep-worktree|--keep-workspace] [--max-timeout-min <n>]"
[ -d "$PROJECT" ] || die2 "not a directory: $PROJECT"
[ -n "$REPO" ]    || die2 "missing --repo"
[ -n "$OUT" ]     || die2 "missing --out"
EVALFILE="$PROJECT/evaluation.md"
[ -f "$EVALFILE" ] || die2 "missing evaluation.md in $PROJECT"

REPO="$(cd "$REPO" 2>/dev/null && pwd -P)" || die2 "not a directory: $REPO"
export REPO
superagent_load_context "$REPO" run || exit $?
case "$SUPER_GIT_MODE" in
  github)
    [ -n "$COMMIT" ] || die2 "missing --commit in SUPER_GIT_MODE=github"
    [ "$KEEP_WORKSPACE" -eq 0 ] || die2 "--keep-workspace requires SUPER_GIT_MODE=none"
    ;;
  none)
    [ -z "$COMMIT" ] || die2 "--commit is not valid in SUPER_GIT_MODE=none"
    [ -z "$WORKTREE" ] || die2 "--worktree is not valid in SUPER_GIT_MODE=none"
    [ "$KEEP_WORKTREE" -eq 0 ] || die2 "--keep-worktree is not valid in SUPER_GIT_MODE=none"
    ;;
esac
CEIL_MIN="${MAXTO:-${SUPER_EVAL_TIMEOUT_MIN:-60}}"
case "$CEIL_MIN" in ''|*[!0-9]*) die2 "--max-timeout-min must be a whole number of minutes" ;; esac

mkdir -p "$(dirname "$OUT")" || die2 "cannot create output directory for $OUT"

# A local evaluator owns both mutable roots for its full lifetime. Nested invocations borrow the
# scheduler's token; direct invocations acquire/release their own lock through the helper supervisor.
HELPER=""; VAULT=""
if [ "$SUPER_GIT_MODE" = none ]; then
  HELPER="$(superagent_workspace_state_helper)" || die2 "workspace helper is unavailable"
  VAULT="$(vault_root "$REPO")" || die2 "cannot resolve vault root"
  [ -d "$VAULT" ] || die2 "vault root is not a directory: $VAULT"
  if [ "${SUPER_EVAL_OWNED:-}" != 1 ]; then
    exec python3 "$HELPER" run --root "$REPO" --root "$VAULT" -- \
      env SUPER_EVAL_OWNED=1 "$0" "${ORIGINAL_ARGS[@]}"
  fi
fi

# ── worktree ──────────────────────────────────────────────────────────────────
OWN_WORKTREE=0
LOCAL_WORKSPACE=""; LOCAL_TOKEN=""; LOCAL_SOURCE_ID=""; LOCAL_INPUT_MANIFEST=""
LOCAL_PARENT=""; RESULT_COPY=""; RESULT_TOKEN=""; SOURCE_AFTER_COPY=""; SOURCE_AFTER_TOKEN=""
EVID_INPUT="${OUT}.input-manifest.json"
EVID_RESULT="${OUT}.result-manifest.json"
EVID_CHANGES="${OUT}.changes.json"
WORK="$(mktemp -d)"
if [ -z "$HELPER" ]; then HELPER="$(superagent_workspace_state_helper)" || die2 "workspace helper is unavailable"; fi

json_field() { python3 -c 'import json,sys; print(json.loads(sys.argv[1])[sys.argv[2]])' "$1" "$2"; }
snapshot_into() { python3 "$HELPER" snapshot --root "$1" --vault "$2" --out-parent "$3"; }
cleanup_snapshot() {
  [ -n "$1" ] || return 0
  python3 "$HELPER" cleanup --workspace "$1" --token "$2" >/dev/null 2>&1
}

if [ "$SUPER_GIT_MODE" = github ] && [ -z "$WORKTREE" ]; then
  WORKTREE="$(mktemp -d)"
  if ! git -C "$REPO" worktree add --detach "$WORKTREE" "$COMMIT" >/dev/null 2>&1; then
    rmdir "$WORKTREE" 2>/dev/null || true
    die2 "git worktree add failed for commit $COMMIT"
  fi
  OWN_WORKTREE=1
fi

cleanup() {
  local rc=$?
  if [ "$OWN_WORKTREE" -eq 1 ] && [ "$KEEP_WORKTREE" -eq 0 ]; then
    git -C "$REPO" worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  fi
  cleanup_snapshot "$RESULT_COPY" "$RESULT_TOKEN" || true
  cleanup_snapshot "$SOURCE_AFTER_COPY" "$SOURCE_AFTER_TOKEN" || true
  if [ "$KEEP_WORKSPACE" -eq 0 ]; then
    cleanup_snapshot "$LOCAL_WORKSPACE" "$LOCAL_TOKEN" || true
    [ -z "$LOCAL_PARENT" ] || rmdir "$LOCAL_PARENT" 2>/dev/null || true
  fi
  rm -rf "$WORK" 2>/dev/null || true
  exit "$rc"
}
trap cleanup EXIT

if [ "$SUPER_GIT_MODE" = none ]; then
  LOCAL_PARENT="$(mktemp -d)"
  snap="$(snapshot_into "$REPO" "$VAULT" "$LOCAL_PARENT")" || die2 "cannot capture source snapshot"
  LOCAL_WORKSPACE="$(json_field "$snap" workspace)"
  LOCAL_INPUT_MANIFEST="$(json_field "$snap" manifest)"
  LOCAL_SOURCE_ID="$(json_field "$snap" source_id)"
  LOCAL_TOKEN="$(json_field "$snap" token)"
  WORKTREE="$LOCAL_WORKSPACE"
  cp "$LOCAL_INPUT_MANIFEST" "$EVID_INPUT" || die2 "cannot preserve input manifest"
fi

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
  if [ "$secs" -eq 0 ] && [ -n "$TIMEOUT_BIN" ]; then
    : >"$TMP_OUT"; : >"$TMP_ERR"; RC=124
  elif [ -n "$TIMEOUT_BIN" ]; then
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

# Local mode records command writes separately from the frozen source and verifies that execution
# never changed the original project. Evidence manifests survive helper-owned workspace cleanup.
if [ "$SUPER_GIT_MODE" = none ]; then
  result_snap="$(snapshot_into "$WORKTREE" "$VAULT" "$LOCAL_PARENT")" || die2 "cannot capture result snapshot"
  RESULT_COPY="$(json_field "$result_snap" workspace)"
  result_manifest="$(json_field "$result_snap" manifest)"
  RESULT_TOKEN="$(json_field "$result_snap" token)"
  cp "$result_manifest" "$EVID_RESULT" || die2 "cannot preserve result manifest"
  changes="$(python3 "$HELPER" compare --before "$EVID_INPUT" --after "$EVID_RESULT")" || die2 "cannot compare result snapshot"
  printf '%s\n' "$changes" >"$EVID_CHANGES" || die2 "cannot preserve snapshot comparison"

  source_after="$(snapshot_into "$REPO" "$VAULT" "$LOCAL_PARENT")" || die2 "cannot verify original source"
  SOURCE_AFTER_COPY="$(json_field "$source_after" workspace)"
  source_after_manifest="$(json_field "$source_after" manifest)"
  SOURCE_AFTER_TOKEN="$(json_field "$source_after" token)"
  source_delta="$(python3 "$HELPER" compare --before "$EVID_INPUT" --after "$source_after_manifest")" || die2 "cannot compare original source"
  if ! python3 -c 'import json,sys; d=json.loads(sys.argv[1]); raise SystemExit(0 if not any(d.values()) else 1)' "$source_delta"; then
    ALL_PASS=0
    printf '### source isolation error\n```\noriginal source changed during evaluation: %s\n```\n' "$source_delta" >>"$BLOCKS"
  fi

  {
    printf '## Environment\n'
    printf -- '- source: `%s` · workspace: `%s` · manifest: `%s` · setup: `%s` → %s\n' \
      "$LOCAL_SOURCE_ID" "$WORKTREE" "$EVID_INPUT" "$SETUP_CMD" "$SETUP_STATE"
    printf -- '- result-manifest: `%s` · changes: `%s`\n' "$EVID_RESULT" "$EVID_CHANGES"
    printf -- '- cleanup-token: `%s` · retained: `%s`\n\n' "$LOCAL_TOKEN" "$KEEP_WORKSPACE"
    printf '## Command checks\n'
    printf '| Id | Result | Exit | Seconds | Evidence |\n'
    printf '|---|---|---|---|---|\n'
    cat "$ROWS"
    if [ -s "$BLOCKS" ]; then printf '\n'; cat "$BLOCKS"; fi
  } >"$OUT"
fi

[ "$ALL_PASS" -eq 1 ] && exit 0 || exit 1

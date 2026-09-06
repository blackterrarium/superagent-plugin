#!/usr/bin/env bash
# prd-lint.sh — offline validator for a coding-loop project folder
# (prd.md, knowledge-base.md, evaluation.md). Pure bash 3.2 + grep/sed/awk/find; no network, no LLM.
#
#   prd-lint.sh <project-dir> [--json]
#
# Prints one finding per line — `PASS|WARN|FAIL <file>:<loc> <message>` — or, with --json, one
# JSON array of {"level","file","loc","message"}. Exit 0 when there is no FAIL, 1 when there is,
# 2 on a usage error. WARNs never change the exit code.
# Repo root: PRD_LINT_REPO_ROOT, else `git rev-parse --show-toplevel` from the project dir.
# SUPER_EVAL_TIMEOUT_MIN resolves env > <repo>/.superenv > templates/superenv.default (load_superenv).
# Known limit: a `|` inside a table cell (e.g. in a regex) splits the row; escape it or avoid it.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$ROOT/scripts/_common.sh"

PROJECT=""; JSON=false
for a in "$@"; do
  case "$a" in
    --json) JSON=true ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) PROJECT="$a" ;;
  esac
done
if [[ -z "$PROJECT" ]]; then echo "usage: prd-lint.sh <project-dir> [--json]" >&2; exit 2; fi
if [[ ! -d "$PROJECT" ]]; then echo "prd-lint: not a directory: $PROJECT" >&2; exit 2; fi
PROJECT="$(cd "$PROJECT" && pwd)"
REPO="${PRD_LINT_REPO_ROOT:-$(git -C "$PROJECT" rev-parse --show-toplevel 2>/dev/null || true)}"
if [[ -z "$REPO" ]]; then echo "prd-lint: cannot find the repo root (set PRD_LINT_REPO_ROOT)" >&2; exit 2; fi
load_superenv "$REPO"
MAX_TIMEOUT="${SUPER_EVAL_TIMEOUT_MIN:-60}"

# ── findings ─────────────────────────────────────────────────────────────────
# One line per finding in $FINDINGS_FILE, fields separated by the ASCII unit separator so a
# message may contain '|' or ':'. (A bash array would need bash 4 to be safe under set -u.)
FINDINGS_FILE="$(mktemp)"; trap 'rm -f "$FINDINGS_FILE"' EXIT
US=$'\x1f'
FAILS=0
finding() {  # finding <PASS|WARN|FAIL> <file> <loc> <message>
  [[ "$1" == FAIL ]] && FAILS=$((FAILS+1))
  printf '%s%s%s%s%s%s%s\n' "$1" "$US" "$2" "$US" "$3" "$US" "$4" >>"$FINDINGS_FILE"
}

# ── markdown helpers ─────────────────────────────────────────────────────────
trim()        { sed 's/^[[:space:]]*//;s/[[:space:]]*$//'; }
strip_ticks() { sed 's/^`//;s/`$//'; }
# section_body <file> <heading-text> — lines strictly between "## <heading>" and the next "## "
section_body() {
  awk -v h="## $2" '$0 == h { on=1; next } on && /^## / { exit } on { print }' "$1"
}
# table_rows — data rows of every markdown table on stdin; each table's header and separator
# rows dropped
table_rows() {
  awk '!/^\|/ { n=0; next } { n++; if (n == 1) next; if ($0 ~ /^\|[[:space:]]*:?-/) next; print }'
}
# cell <n> — the n-th cell (1-based) of a "| a | b |" row on stdin, trimmed, backticks stripped
cell() { awk -F'|' -v n="$(( $1 + 1 ))" '{ print $n }' | trim | strip_ticks; }

# ── per-file checks ──────────────────────────────────────────────────────────
check_file_present() {  # <basename> — FAIL and return 1 when absent
  if [[ -f "$PROJECT/$1" ]]; then return 0; fi
  finding FAIL "$1" file "missing $1"; return 1
}
check_header() {  # <basename>
  local f="$PROJECT/$1"
  if ! head -1 "$f" | grep -q '^# '; then
    finding FAIL "$1" header "first line must be a '# <Title>' heading"
  fi
  if head -3 "$f" | grep -qE '^\*\*Date:\*\* .*\*\*Status:\*\* (DRAFT|READY)'; then
    finding PASS "$1" header "header block present"
  else
    finding FAIL "$1" header "missing '**Date:** … · **Status:** DRAFT|READY' line within the first 3 lines"
  fi
}

SC_ROWS=""
lint_prd() {
  local f="$PROJECT/prd.md" prev=0 n s ok=true
  for s in "Objective" "Success criteria" "Constraints and non-goals" "Locked decisions" "Iteration ledger"; do
    n="$(grep -n "^## $s\$" "$f" | head -1 | cut -d: -f1)"
    if [[ -z "$n" ]]; then finding FAIL prd.md "$s" "missing section '## $s'"; ok=false; continue; fi
    if (( n < prev )); then finding FAIL prd.md "$s" "section '## $s' is out of order (expected Objective, Success criteria, Constraints and non-goals, Locked decisions, Iteration ledger)"; ok=false; fi
    prev=$n
  done
  $ok && finding PASS prd.md sections "the five sections are present and in order"
  if grep -q '^| Round | Meta-plan | Goal folder | Inner loop | Eval report | Verdict |' "$f"; then
    finding PASS prd.md "Iteration ledger" "ledger header row present"
  else
    finding FAIL prd.md "Iteration ledger" "ledger header row must be '| Round | Meta-plan | Goal folder | Inner loop | Eval report | Verdict |'"
  fi
  SC_ROWS="$(section_body "$f" "Success criteria" | table_rows)"
  [[ -z "$SC_ROWS" ]] && finding FAIL prd.md "Success criteria" "no success-criteria rows"
}

# ── main ─────────────────────────────────────────────────────────────────────
HAVE_PRD=false; HAVE_KB=false; HAVE_EVAL=false
check_file_present prd.md            && HAVE_PRD=true
check_file_present knowledge-base.md && HAVE_KB=true
check_file_present evaluation.md     && HAVE_EVAL=true
$HAVE_PRD  && { check_header prd.md;            lint_prd; }
$HAVE_KB   && { check_header knowledge-base.md; }
$HAVE_EVAL && { check_header evaluation.md; }

# ── output ───────────────────────────────────────────────────────────────────
json_escape() { sed 's/\\/\\\\/g; s/"/\\"/g'; }
if $JSON; then
  printf '['
  first=true
  while IFS="$US" read -r level file loc msg; do
    $first || printf ','; first=false
    printf '{"level":"%s","file":"%s","loc":"%s","message":"%s"}' \
      "$level" "$file" "$(printf '%s' "$loc" | json_escape)" "$(printf '%s' "$msg" | json_escape)"
  done <"$FINDINGS_FILE"
  printf ']\n'
else
  while IFS="$US" read -r level file loc msg; do
    printf '%s %s:%s %s\n' "$level" "$file" "$loc" "$msg"
  done <"$FINDINGS_FILE"
fi
# Authoritative count from the findings file, not the $FAILS shell variable: finding() may run
# inside a subshell (e.g. a `cmd | while read` loop body in bash 3.2), which would silently lose
# the increment and let a FAIL-printing run exit 0.
FAILS=$(grep -c "^FAIL$US" "$FINDINGS_FILE" 2>/dev/null || true)
[[ $FAILS -eq 0 ]]

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
# A literal | inside a table cell must be written \| (standard markdown); an unescaped | splits the row.
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
RS=$'\x1e'
FAILS=0
finding() {  # finding <PASS|WARN|FAIL> <file> <loc> <message>
  [[ "$1" == FAIL ]] && FAILS=$((FAILS+1))
  printf '%s%s%s%s%s%s%s\n' "$1" "$US" "$2" "$US" "$3" "$US" "$4" >>"$FINDINGS_FILE"
}

if ! [[ "$MAX_TIMEOUT" =~ ^[0-9]+$ ]]; then
  finding WARN evaluation.md config "SUPER_EVAL_TIMEOUT_MIN='$MAX_TIMEOUT' is not a whole number of minutes; using 60"
  MAX_TIMEOUT=60
fi

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
# cell <n> — the n-th cell (1-based) of a "| a | b |" row on stdin, trimmed, backticks stripped.
# A \| escape is swapped for the ASCII RS placeholder before the awk split (so it doesn't split
# the row) and restored as a literal | afterward.
cell() { sed "s/\\\\|/$RS/g" | awk -F'|' -v n="$(( $1 + 1 ))" '{ print $n }' | trim | strip_ticks | sed "s/$RS/|/g"; }

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

lint_kb() {
  local f="$PROJECT/knowledge-base.md" rows row id kind loc path sym pat
  if grep -q '^| Id | Kind | Locator | Read for |' "$f"; then
    finding PASS knowledge-base.md header "table header present"
  else
    finding FAIL knowledge-base.md header "table header must be '| Id | Kind | Locator | Read for |'"
  fi
  rows="$(table_rows <"$f")"
  if [[ -z "$rows" ]]; then finding FAIL knowledge-base.md table "no source rows"; return; fi
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    id="$(printf '%s\n' "$row" | cell 1)"
    kind="$(printf '%s\n' "$row" | cell 2)"
    loc="$(printf '%s\n' "$row" | cell 3)"
    if [[ -z "$loc" ]]; then finding FAIL knowledge-base.md "$id" "$kind has an empty locator"; continue; fi
    case "$kind" in
      instructions|repo-file|sample-code)
        if [[ -n "$loc" && -e "$REPO/$loc" ]]; then finding PASS knowledge-base.md "$id" "$kind '$loc' exists"
        else finding FAIL knowledge-base.md "$id" "$kind '$loc' not found under the repo root"; fi ;;
      repo-glob)
        # `**` → `*`: find -path lets `*` span '/' so the pattern matches recursively (bash 3.2 has no globstar)
        pat="$REPO/$(printf '%s' "$loc" | sed 's#\*\*#*#g')"
        if [[ -n "$(find "$REPO" -path "$pat" -type f -print 2>/dev/null | head -1)" ]]; then
          finding PASS knowledge-base.md "$id" "repo-glob '$loc' matches"
        else finding FAIL knowledge-base.md "$id" "repo-glob '$loc' matches no file"; fi ;;
      entry-point)
        if [[ "$loc" != *:* || -z "${loc#*:}" ]]; then finding FAIL knowledge-base.md "$id" "entry-point locator must be <path>:<symbol>, got '$loc'"
        else
          path="${loc%%:*}"; sym="${loc#*:}"
          if [[ ! -f "$REPO/$path" ]]; then finding FAIL knowledge-base.md "$id" "entry-point file '$path' not found"
          elif grep -qF -- "$sym" "$REPO/$path"; then finding PASS knowledge-base.md "$id" "entry-point '$loc' found"
          else finding WARN knowledge-base.md "$id" "symbol '$sym' not found in $path"; fi
        fi ;;
      doc-url)
        if [[ "$loc" =~ ^https?://[^[:space:]]+$ ]]; then finding PASS knowledge-base.md "$id" "doc-url well-formed"
        else finding FAIL knowledge-base.md "$id" "doc-url '$loc' is not an http(s) URL"; fi ;;
      context7)
        if [[ "$loc" =~ ^/[^/]+/[^/]+$ ]]; then finding PASS knowledge-base.md "$id" "context7 id well-formed"
        else finding FAIL knowledge-base.md "$id" "context7 id '$loc' must look like /<org>/<project>"; fi ;;
      *) finding FAIL knowledge-base.md "$id" "unknown kind '$kind' (instructions|repo-file|repo-glob|sample-code|entry-point|doc-url|context7)" ;;
    esac
  done <<<"$rows"
}

check_command() {  # <file> <loc> <command> — first word on PATH or a repo path → PASS, else WARN
  local word="${3%% *}"
  if command -v "$word" >/dev/null 2>&1 || [[ -e "$REPO/$word" ]]; then
    finding PASS "$1" "$2" "command '$word' is on PATH or in the repo"
  else
    finding WARN "$1" "$2" "command '$word' not on PATH and not a repo path (a setup step may install it)"
  fi
}

CHECK_IDS=""
lint_eval() {
  local f="$PROJECT/evaluation.md" envsec setup cwd rows row id cmd ccwd pw to crit ev dup
  envsec="$(section_body "$f" "Environment")"
  if [[ -z "$envsec" ]]; then finding FAIL evaluation.md Environment "missing section '## Environment'"; fi
  if grep -q '^- setup:' <<<"$envsec"; then
    setup="$(sed -n 's/^- setup:[[:space:]]*//p' <<<"$envsec" | head -1 | strip_ticks)"
    [[ -n "$setup" ]] && check_command evaluation.md setup "$setup"
  else
    finding FAIL evaluation.md Environment "missing '- setup: <command>' line (the command may be empty)"
  fi
  cwd="$(sed -n 's/^- cwd:[[:space:]]*//p' <<<"$envsec" | head -1 | strip_ticks)"
  if [[ -z "$cwd" ]]; then finding FAIL evaluation.md Environment "missing '- cwd: <dir>' line"
  elif [[ ! -d "$REPO/$cwd" ]]; then finding WARN evaluation.md Environment "cwd '$cwd' does not exist yet"
  else finding PASS evaluation.md Environment "setup/cwd lines present"; fi

  if ! grep -q '^| Id | Command | Cwd | Pass when | Timeout |' "$f"; then
    finding FAIL evaluation.md "Command checks" "table header must be '| Id | Command | Cwd | Pass when | Timeout |'"
  fi
  rows="$(section_body "$f" "Command checks" | table_rows)"
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    id="$(printf '%s\n' "$row" | cell 1)";   cmd="$(printf '%s\n' "$row" | cell 2)"
    ccwd="$(printf '%s\n' "$row" | cell 3)"; pw="$(printf '%s\n' "$row" | cell 4)"
    to="$(printf '%s\n' "$row" | cell 5)"
    CHECK_IDS="${CHECK_IDS}${id}"$'\n'
    if [[ -z "$cmd" ]]; then finding FAIL evaluation.md "$id" "empty command"; else check_command evaluation.md "$id" "$cmd"; fi
    [[ -n "$ccwd" && ! -d "$REPO/$ccwd" ]] && finding WARN evaluation.md "$id" "cwd '$ccwd' does not exist yet"
    if [[ "$pw" =~ ^exit\ [0-9]+$ ]] || [[ "$pw" =~ ^stdout\ ~\ /.+/$ ]]; then
      finding PASS evaluation.md "$id" "Pass when '$pw' well-formed"
    else
      finding FAIL evaluation.md "$id" "Pass when must be 'exit <n>' or 'stdout ~ /<regex>/', got '$pw'"
    fi
    if ! [[ "$to" =~ ^[0-9]+$ ]]; then
      finding FAIL evaluation.md "$id" "Timeout must be a whole number of minutes, got '$to'"
    elif (( 10#$to > 10#$MAX_TIMEOUT )); then
      finding FAIL evaluation.md "$id" "Timeout $to exceeds SUPER_EVAL_TIMEOUT_MIN=$MAX_TIMEOUT"
    fi
  done <<<"$rows"

  if ! grep -q '^| Id | Objective | Criteria | Evidence to inspect |' "$f"; then
    finding FAIL evaluation.md "Judged objectives" "table header must be '| Id | Objective | Criteria | Evidence to inspect |'"
  fi
  rows="$(section_body "$f" "Judged objectives" | table_rows)"
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    id="$(printf '%s\n' "$row" | cell 1)"; crit="$(printf '%s\n' "$row" | cell 3)"; ev="$(printf '%s\n' "$row" | cell 4)"
    CHECK_IDS="${CHECK_IDS}${id}"$'\n'
    [[ -z "$crit" ]] && finding FAIL evaluation.md "$id" "judged objective has empty criteria"
    [[ -z "$ev" ]]   && finding FAIL evaluation.md "$id" "judged objective has empty evidence"
    [[ -n "$crit" && -n "$ev" ]] && finding PASS evaluation.md "$id" "judged objective has criteria and evidence"
  done <<<"$rows"

  dup="$(printf '%s' "$CHECK_IDS" | sort | uniq -d | tr '\n' ' ' | sed 's/ $//')"
  [[ -n "$dup" ]] && finding FAIL evaluation.md ids "duplicate check id(s): $dup"
  [[ -z "$(printf '%s' "$CHECK_IDS" | tr -d '\n')" ]] && finding FAIL evaluation.md checks "no command checks or judged objectives"
}

lint_coverage() {  # both directions of the coverage rule; needs SC_ROWS and CHECK_IDS
  local row id ids c found
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    id="$(printf '%s\n' "$row" | cell 1)"
    ids="$(printf '%s\n' "$row" | cell 3 | tr ',' ' ')"
    if [[ -z "${ids// /}" ]]; then finding FAIL prd.md "$id" "criterion has no check ids (coverage rule)"; continue; fi
    for c in $ids; do
      if grep -qx -- "$c" <<<"$CHECK_IDS"; then finding PASS prd.md "$id" "covered by $c"
      else finding FAIL prd.md "$id" "references unknown check id '$c'"; fi
    done
  done <<<"$SC_ROWS"
  while IFS= read -r c; do
    [[ -z "$c" ]] && continue
    found=false
    while IFS= read -r row; do
      [[ -z "$row" ]] && continue
      if printf '%s\n' "$row" | cell 3 | tr ', ' '\n\n' | grep -qx -- "$c"; then found=true; fi
    done <<<"$SC_ROWS"
    $found || finding FAIL evaluation.md "$c" "check id '$c' serves no success criterion (coverage rule)"
  done <<<"$CHECK_IDS"
}

# ── main ─────────────────────────────────────────────────────────────────────
HAVE_PRD=false; HAVE_KB=false; HAVE_EVAL=false
check_file_present prd.md            && HAVE_PRD=true
check_file_present knowledge-base.md && HAVE_KB=true
check_file_present evaluation.md     && HAVE_EVAL=true
$HAVE_PRD  && { check_header prd.md;            lint_prd; }
$HAVE_KB   && { check_header knowledge-base.md; lint_kb; }
$HAVE_EVAL && { check_header evaluation.md; lint_eval; }
$HAVE_PRD && $HAVE_EVAL && lint_coverage

# ── output ───────────────────────────────────────────────────────────────────
json_escape() { sed 's/\\/\\\\/g; s/"/\\"/g; s/'$'\t''/\\t/g' | tr -d '\000-\010\013-\037'; }
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

#!/usr/bin/env bash
# _evalspec.sh — shared markdown-table parser for coding-loop project specs.
# SOURCE this, do not execute. Consumed by scripts/prd-lint.sh and scripts/supereval.sh.
#
# Markdown helpers (moved out of prd-lint.sh): trim, strip_ticks, section_body, table_rows, cell.
# Readers over an evaluation.md:
#   evalspec_env    <evaluation.md> -> one line  "setup<US>cwd"
#   evalspec_checks <evaluation.md> -> one record per line:
#       command rows: C<US>id<US>command<US>cwd<US>pass-when<US>timeout-min   (file order)
#       judged  rows: J<US>id<US>objective<US>criteria<US>evidence
# Records use the ASCII unit separator US=$'\x1f' so a field may contain '|' or ':'. A literal | in
# a cell is written \| (standard markdown) and is unescaped to | in the emitted record by cell().
#
# Pure bash 3.2 + grep/sed/awk. No `set -e`/`set -u` here — this file is sourced by scripts that run
# under `set -u`, and every reference below is set-u-safe.

# US/RS are defined here (guarded) because both consumers need them and prd-lint.sh used to define
# them itself. A caller that already set them (or a re-source) is left untouched.
if [ -z "${US:-}" ]; then US=$'\x1f'; fi
if [ -z "${RS:-}" ]; then RS=$'\x1e'; fi

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

# ── evaluation.md readers ────────────────────────────────────────────────────
# evalspec_env <evaluation.md> — prints exactly one line "setup<US>cwd". A missing setup or cwd
# line yields an empty field (never an error). Mirrors lint_eval()'s first-match reads.
evalspec_env() {
  local f="$1" envsec setup cwd
  envsec="$(section_body "$f" "Environment")"
  setup="$(printf '%s\n' "$envsec" | sed -n 's/^- setup:[[:space:]]*//p' | head -1 | strip_ticks)"
  cwd="$(printf '%s\n' "$envsec" | sed -n 's/^- cwd:[[:space:]]*//p' | head -1 | strip_ticks)"
  printf '%s%s%s\n' "$setup" "$US" "$cwd"
}

# evalspec_checks <evaluation.md> — C records (every data row under "## Command checks", file
# order) then J records (every data row under "## Judged objectives"). A missing section emits
# nothing for that section. \| in any cell is unescaped to | by cell().
evalspec_checks() {
  local f="$1" rows row id cmd ccwd pw to obj crit ev
  rows="$(section_body "$f" "Command checks" | table_rows)"
  while IFS= read -r row; do
    [ -n "$row" ] || continue
    id="$(printf '%s\n' "$row" | cell 1)"
    cmd="$(printf '%s\n' "$row" | cell 2)"
    ccwd="$(printf '%s\n' "$row" | cell 3)"
    pw="$(printf '%s\n' "$row" | cell 4)"
    to="$(printf '%s\n' "$row" | cell 5)"
    printf 'C%s%s%s%s%s%s%s%s%s%s\n' "$US" "$id" "$US" "$cmd" "$US" "$ccwd" "$US" "$pw" "$US" "$to"
  done <<<"$rows"
  rows="$(section_body "$f" "Judged objectives" | table_rows)"
  while IFS= read -r row; do
    [ -n "$row" ] || continue
    id="$(printf '%s\n' "$row" | cell 1)"
    obj="$(printf '%s\n' "$row" | cell 2)"
    crit="$(printf '%s\n' "$row" | cell 3)"
    ev="$(printf '%s\n' "$row" | cell 4)"
    printf 'J%s%s%s%s%s%s%s%s\n' "$US" "$id" "$US" "$obj" "$US" "$crit" "$US" "$ev"
  done <<<"$rows"
}

#!/usr/bin/env bash
# superbuild.sh — file plumbing for the superbuild task loop (skills/superbuild/SKILL.md).
#
# The controller hands every artifact to its subagents as a FILE so task text, reports and diffs
# never pass through (and stay resident in) the controller's own context.
#
#   superbuild.sh workspace PLAN_FILE                 print (and create) this plan's scratch directory
#   superbuild.sh brief     PLAN_FILE N [OUTFILE]     extract "Task N" from the plan into a brief file
#   superbuild.sh package   PLAN_FILE BASE HEAD [OUTFILE]
#                                                     write commit list + stat + -U10 diff for BASE..HEAD
#
# Workspace: <root>/.superagent-runtime/build/<plan-slug>/ — one directory per plan, holding the
# ledger (progress.md), task briefs, implementer reports and review packages. <root> is
# $SUPERBUILD_ROOT when set, else the git toplevel of the current directory (the execution
# worktree). SUPER_GIT_MODE=none callers MUST set SUPERBUILD_ROOT to the recorded project root:
# `workspace` and `brief` then run no git command and write no .gitignore, and
# `.superagent-runtime` is already excluded from workspace-state.py manifests. `package` is
# git-only; in `none` the controller builds the review package from the manifest compare instead.
#
# Two plans can share a basename (a/plan.md vs b/plan.md), so each workspace records its owning
# plan in a `plan-path` marker; a directory owned by a different plan is skipped and the slug is
# disambiguated with the plan's parent-directory name, then a counter. A stale ledger read as
# current progress would make a controller skip whole task sequences.
#
# Adapted from the superpowers plugin's subagent-driven-development helper scripts
# (MIT, Copyright (c) 2025 Jesse Vincent).
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: superbuild.sh workspace PLAN_FILE
       superbuild.sh brief PLAN_FILE TASK_NUMBER [OUTFILE]
       superbuild.sh package PLAN_FILE BASE HEAD [OUTFILE]
EOF
  exit 2
}

workspace_dir() {
  local plan="$1" slug root base plan_dir plan_abs plan_id dir parent n
  [ -f "$plan" ] || { echo "no such plan file: $plan" >&2; exit 2; }
  slug="$(basename "$plan" .md)"
  [ -n "$slug" ] && [ "$slug" != "." ] && [ "$slug" != ".." ] \
    || { echo "cannot derive a workspace name from: $plan" >&2; exit 2; }

  if [ -n "${SUPERBUILD_ROOT:-}" ]; then
    root="$(CDPATH= cd -- "$SUPERBUILD_ROOT" && pwd -P)"
  else
    root="$(git rev-parse --show-toplevel)"
  fi
  base="$root/.superagent-runtime/build"

  # Physical path, so relative/absolute/../ spellings of one plan compare equal.
  plan_dir="$(CDPATH= cd -- "$(dirname "$plan")" && pwd -P)"
  plan_abs="$plan_dir/$(basename "$plan")"
  case "$plan_abs" in
    "$root"/*) plan_id="${plan_abs#"$root"/}" ;;
    *)         plan_id="$plan_abs" ;;
  esac

  # True when the directory is (or becomes) this plan's.
  owns() {
    if [ -e "$1/plan-path" ]; then
      [ "$(cat "$1/plan-path")" = "$plan_id" ]
    else
      mkdir -p "$1"
      printf '%s\n' "$plan_id" >"$1/plan-path"
    fi
  }

  dir="$base/$slug"
  if ! owns "$dir"; then
    parent="$(basename "$plan_dir")"
    dir="$base/$slug-$parent"
    if ! owns "$dir"; then
      n=2
      while ! owns "$base/$slug-$parent-$n"; do n=$((n + 1)); done
      dir="$base/$slug-$parent-$n"
    fi
  fi

  # Self-ignoring: keeps the scratch out of `git status` without touching a tracked file.
  # Not under SUPERBUILD_ROOT: a SUPER_GIT_MODE=none project never gets a .gitignore.
  [ -n "${SUPERBUILD_ROOT:-}" ] || printf '*\n' >"$base/.gitignore"
  (CDPATH= cd -- "$dir" && pwd)
}

cmd_brief() {
  [ $# -ge 2 ] && [ $# -le 3 ] || usage
  local plan="$1" n="$2" out
  [ -f "$plan" ] || { echo "no such plan file: $plan" >&2; exit 2; }
  case "$n" in ''|*[!0-9]*) echo "TASK_NUMBER must be a positive integer: $n" >&2; exit 2 ;; esac
  if [ $# -eq 3 ]; then out="$3"; else out="$(workspace_dir "$plan")/task-${n}-brief.md"; fi

  awk -v n="$n" '
    /^```/ { infence = !infence }
    !infence && /^#+[ \t]+Task[ \t]+[0-9]+/ {
      intask = ($0 ~ ("^#+[ \t]+Task[ \t]+" n "([^0-9]|$)"))
    }
    intask { print }
  ' "$plan" >"$out"

  if [ ! -s "$out" ]; then
    rm -f "$out"
    echo "task ${n} not found in ${plan} (no heading matching 'Task ${n}')" >&2
    exit 3
  fi
  echo "wrote ${out}: $(wc -l <"$out" | tr -d ' ') lines"
}

cmd_package() {
  [ $# -ge 3 ] && [ $# -le 4 ] || usage
  local plan="$1" base="$2" head="$3" out commits
  [ -f "$plan" ] || { echo "no such plan file: $plan" >&2; exit 2; }
  git rev-parse --verify --quiet "$base" >/dev/null || { echo "bad BASE: $base" >&2; exit 2; }
  git rev-parse --verify --quiet "$head" >/dev/null || { echo "bad HEAD: $head" >&2; exit 2; }

  # Range guards (exit 3): a wrong-branch HEAD yields a range that is empty or not rooted at
  # BASE; either would silently produce a bogus review package.
  git merge-base --is-ancestor "$base" "$head" \
    || { echo "HEAD is not a descendant of BASE: ${base}..${head}" >&2; exit 3; }
  commits="$(git rev-list --count "${base}..${head}")"
  [ "$commits" -gt 0 ] || { echo "empty commit range: ${base}..${head}" >&2; exit 3; }

  if [ $# -eq 4 ]; then
    out="$4"
  else
    out="$(workspace_dir "$plan")/review-$(git rev-parse --short "$base")..$(git rev-parse --short "$head").diff"
  fi

  {
    echo "# Review package: ${base}..${head}"
    echo
    echo "## Commits"
    git log --oneline "${base}..${head}"
    echo
    echo "## Files changed"
    git diff --stat "${base}..${head}"
    echo
    echo "## Diff"
    git diff -U10 "${base}..${head}"
  } >"$out"

  echo "wrote ${out}: ${commits} commit(s), $(wc -c <"$out" | tr -d ' ') bytes"
}

[ $# -ge 1 ] || usage
sub="$1"; shift
case "$sub" in
  workspace) [ $# -eq 1 ] || usage; workspace_dir "$1" ;;
  brief)     cmd_brief "$@" ;;
  package)   cmd_package "$@" ;;
  *)         usage ;;
esac

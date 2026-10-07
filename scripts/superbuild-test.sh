#!/usr/bin/env bash
# Offline test for scripts/superbuild.sh (workspace / brief / package).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SB="$ROOT/scripts/superbuild.sh"
T="$(cd "$(mktemp -d)" && pwd -P)"; trap 'rm -rf "$T"' EXIT
fail() { echo "superbuild: FAIL — $*" >&2; exit 1; }

R="$T/repo"; mkdir -p "$R/a" "$R/b" "$T/vault"
git -C "$R" init -q
git -C "$R" config user.email t@example.com; git -C "$R" config user.name t
cat >"$R/a/plan.md" <<'EOF'
# Demo Implementation Plan

## Global Constraints
none

### Task 1: first
- [ ] step one

```markdown
### Task 2: a heading inside a fence must not split the task
```

### Task 2: second
- [ ] step two

### Task 10: tenth
- [ ] step ten
EOF
cp "$R/a/plan.md" "$R/b/plan.md"
cp "$R/a/plan.md" "$T/vault/plan.md"
git -C "$R" add -A; git -C "$R" commit -q -m base
BASE="$(git -C "$R" rev-parse HEAD)"

# workspace: stable per plan, self-ignored, same-basename plans never share a directory.
wa="$(cd "$R" && bash "$SB" workspace a/plan.md)" || fail "workspace a"
[ "$wa" = "$R/.superagent-runtime/build/plan" ] || fail "workspace path: $wa"
[ "$(cd "$R/a" && bash "$SB" workspace ./plan.md)" = "$wa" ] || fail "workspace not stable across spellings"
wb="$(cd "$R" && bash "$SB" workspace b/plan.md)" || fail "workspace b"
[ "$wb" = "$R/.superagent-runtime/build/plan-b" ] || fail "same-basename plan shared a workspace: $wb"
wv="$(cd "$R" && bash "$SB" workspace "$T/vault/plan.md")" || fail "workspace external plan"
[ "$wv" = "$R/.superagent-runtime/build/plan-vault" ] || fail "external-vault plan workspace: $wv"
[ "$(cat "$wv/plan-path")" = "$T/vault/plan.md" ] || fail "external plan marker is not absolute"
[ -z "$(git -C "$R" status --porcelain)" ] || fail "workspace is not git-ignored"

# brief: exact task, fence-aware, no prefix match (Task 1 must not swallow Task 10).
(cd "$R" && bash "$SB" brief a/plan.md 1 >/dev/null) || fail "brief 1"
grep -q 'step one' "$wa/task-1-brief.md" || fail "brief 1 content"
grep -q 'inside a fence' "$wa/task-1-brief.md" || fail "brief 1 dropped its fenced block"
grep -q 'step two\|step ten' "$wa/task-1-brief.md" && fail "brief 1 leaked another task"
(cd "$R" && bash "$SB" brief a/plan.md 10 >/dev/null) || fail "brief 10"
grep -q 'step ten' "$wa/task-10-brief.md" || fail "brief 10 content"
(cd "$R" && bash "$SB" brief a/plan.md 7 >/dev/null 2>&1); [ $? -eq 3 ] || fail "missing task must exit 3"
[ ! -e "$wa/task-7-brief.md" ] || fail "missing task left an empty brief"

# package: commit list + stat + diff for the recorded range; bad ranges refuse.
echo one >"$R/f.txt"; git -C "$R" add f.txt; git -C "$R" commit -q -m "add f"
echo two >>"$R/f.txt"; git -C "$R" commit -q -am "extend f"
HEAD_SHA="$(git -C "$R" rev-parse HEAD)"
out="$(cd "$R" && bash "$SB" package a/plan.md "$BASE" "$HEAD_SHA")" || fail "package"
pkg="${out#wrote }"; pkg="${pkg%%: *}"
[ -f "$pkg" ] || fail "package file missing: $out"
case "$out" in *"2 commit(s)"*) ;; *) fail "package commit count: $out" ;; esac
grep -q '^+two$' "$pkg" || fail "package lost the multi-commit diff"
(cd "$R" && bash "$SB" package a/plan.md "$HEAD_SHA" "$HEAD_SHA" >/dev/null 2>&1); [ $? -eq 3 ] || fail "empty range must exit 3"
(cd "$R" && bash "$SB" package a/plan.md "$HEAD_SHA" "$BASE" >/dev/null 2>&1); [ $? -eq 3 ] || fail "reversed range must exit 3"

# SUPER_GIT_MODE=none: SUPERBUILD_ROOT, and no git command for workspace/brief.
L="$T/local"; mkdir -p "$L/bin"; cp "$R/a/plan.md" "$L/plan.md"
printf '#!/bin/sh\necho "git was called" >&2\nexit 97\n' >"$L/bin/git"; chmod +x "$L/bin/git"
wl="$(cd "$T" && PATH="$L/bin:$PATH" SUPERBUILD_ROOT="$L" bash "$SB" workspace "$L/plan.md")" || fail "none-mode workspace ran git"
[ "$wl" = "$L/.superagent-runtime/build/plan" ] || fail "none-mode workspace path: $wl"
(cd "$T" && PATH="$L/bin:$PATH" SUPERBUILD_ROOT="$L" bash "$SB" brief "$L/plan.md" 2 >/dev/null) || fail "none-mode brief ran git"
grep -q 'step two' "$wl/task-2-brief.md" || fail "none-mode brief content"
[ -z "$(find "$L" -name .gitignore)" ] || fail "none-mode workspace wrote a .gitignore"

# The final-review rules live in the skill's prose; pin the ones a rewrite must not lose.
SK="$ROOT/skills/superbuild/SKILL.md"
pin() { grep -qF -- "$1" "$SK" || fail "superbuild SKILL.md lost: $1"; }
pin 'Final review: fix wave 1/2 started (from <base7>)'
pin 'Final review: fix wave 2/2 started (from <base7>)'
pin 'final-findings-1.md'
pin 'lists strictly fewer findings than `final-findings-1.md`'
pin 'The first wave addressed at least one finding'
pin 'any must-fix deferred item still unfixed'
pin 'There is no third wave'
pin 'An interrupted wave counts once'
grep -qF 'no longer than the list' "$SK" && fail "superbuild SKILL.md: convergence test must be strict"

echo 'superbuild: PASS'

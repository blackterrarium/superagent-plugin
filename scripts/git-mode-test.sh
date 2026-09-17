#!/usr/bin/env bash
# Offline behavioral tests for git-free context discovery and authentication gates.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
T="$(mktemp -d "${TMPDIR:-/tmp}/superagent-git-mode.XXXXXX")"
trap 'rm -rf "$T"' EXIT
FAILS=0

ok() { echo "ok   - $1"; }
bad() { echo "FAIL - $1" >&2; FAILS=$((FAILS + 1)); }
check() {
  local name="$1"; shift
  if "$@"; then ok "$name"; else bad "$name"; fi
}

mkdir -p "$T/plain/nested/deeper" "$T/explicit root/sub" "$T/no-config-init" "$T/bin"
printf '%s\n' 'SUPER_GIT_MODE=none' 'SUPER_TEST_EVIDENCE=local' >"$T/plain/.superenv"
printf '%s\n' 'SUPER_GIT_MODE=none' 'SUPER_TEST_EVIDENCE=local' >"$T/explicit root/.superenv"
ln -s "$T/explicit root" "$T/root-link"

# Build GitHub fixtures with the real git before installing command sentinels.
git init -q "$T/github"
git -C "$T/github" config user.email test@example.invalid
git -C "$T/github" config user.name Test
printf 'base\n' >"$T/github/base.txt"
git -C "$T/github" add base.txt
git -C "$T/github" commit -qm base
printf '%s\n' 'SUPER_GIT_MODE=github' 'SUPER_TEST_EVIDENCE=local' >"$T/github/.superenv"
git -C "$T/github" worktree add -q "$T/github-linked" -b linked

check "default mode is github" bash -c '
  unset SUPER_GIT_MODE SUPER_TEST_EVIDENCE REPO
  . "$1/scripts/_common.sh"
  superagent_load_context "$2" run
  test "$SUPER_GIT_MODE" = github
' _ "$ROOT" "$T/github"

check "nearest .superenv selects local project from nested directory" bash -c '
  unset SUPER_GIT_MODE SUPER_TEST_EVIDENCE REPO
  . "$1/scripts/_common.sh"
  superagent_load_context "$2" run
  test "$SUPER_GIT_MODE" = none && test "$REPO" = "$(cd "$3" && pwd -P)"
' _ "$ROOT" "$T/plain/nested/deeper" "$T/plain"

check "explicit REPO wins and is physically canonicalized" bash -c '
  export REPO="$2" SUPER_GIT_MODE=none SUPER_TEST_EVIDENCE=local
  . "$1/scripts/_common.sh"
  superagent_load_context "$3" run
  test "$REPO" = "$(cd "$4" && pwd -P)"
' _ "$ROOT" "$T/root-link" "$T/plain" "$T/explicit root"

check "environment mode overrides project mode" bash -c '
  export SUPER_GIT_MODE=none SUPER_TEST_EVIDENCE=local
  unset REPO
  . "$1/scripts/_common.sh"
  superagent_load_context "$2" run
  test "$SUPER_GIT_MODE" = none && test "$REPO" = "$(cd "$2" && pwd -P)"
' _ "$ROOT" "$T/github"

check "empty mode is a configuration error" bash -c '
  export SUPER_GIT_MODE="" SUPER_TEST_EVIDENCE=local REPO="$2"
  . "$1/scripts/_common.sh"
  superagent_load_context "$2" run
  test $? -eq 2
' _ "$ROOT" "$T/plain"

check "unknown mode is a configuration error" bash -c '
  export SUPER_GIT_MODE=local SUPER_TEST_EVIDENCE=local REPO="$2"
  . "$1/scripts/_common.sh"
  superagent_load_context "$2" run
  test $? -eq 2
' _ "$ROOT" "$T/plain"

check "local mode rejects CI-only evidence" bash -c '
  export SUPER_GIT_MODE=none SUPER_TEST_EVIDENCE=ci REPO="$2"
  . "$1/scripts/_common.sh"
  superagent_load_context "$2" run
  test $? -eq 2
' _ "$ROOT" "$T/plain"

check "local init without config uses current directory" bash -c '
  export SUPER_GIT_MODE=none SUPER_TEST_EVIDENCE=local
  unset REPO
  . "$1/scripts/_common.sh"
  superagent_load_context "$2" init
  test "$REPO" = "$(cd "$2" && pwd -P)"
' _ "$ROOT" "$T/no-config-init"

check "local run without config or explicit root is rejected" bash -c '
  export SUPER_GIT_MODE=none SUPER_TEST_EVIDENCE=local
  unset REPO
  . "$1/scripts/_common.sh"
  superagent_load_context "$2" run
  test $? -eq 2
' _ "$ROOT" "$T"

check "GitHub linked worktree reloads primary-checkout config" bash -c '
  unset SUPER_GIT_MODE SUPER_TEST_EVIDENCE REPO
  . "$1/scripts/_common.sh"
  superagent_load_context "$2" run
  test "$SUPER_GIT_MODE" = github && test "$REPO" = "$(cd "$3" && pwd -P)"
' _ "$ROOT" "$T/github-linked" "$T/github"

# From this point on any git/gh invocation is a test failure, even when swallowed.
FORBIDDEN_LOG="$T/forbidden.log"
for cmd in git gh; do
  cat >"$T/bin/$cmd" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$(basename "$0") $*" >>"$FORBIDDEN_LOG"
exit 97
SH
  chmod +x "$T/bin/$cmd"
done

check "local resolver never invokes git or gh" env \
  PATH="$T/bin:/usr/bin:/bin" FORBIDDEN_LOG="$FORBIDDEN_LOG" \
  SUPER_GIT_MODE=none SUPER_TEST_EVIDENCE=local REPO="$T/plain" \
  bash -c '. "$1/scripts/_common.sh"; superagent_load_context "$PWD" run && test "$SUPER_GIT_MODE" = none' _ "$ROOT"

check "local auth gates are disabled without credential discovery" env \
  PATH="$T/bin:/usr/bin:/bin" FORBIDDEN_LOG="$FORBIDDEN_LOG" \
  SUPER_GIT_MODE=none SUPER_TEST_EVIDENCE=local REPO="$T/plain" \
  bash -c '. "$1/scripts/_common.sh"; superagent_load_context "$PWD" run && ensure_gh_auth && test "$(gh_auth_state)" = disabled' _ "$ROOT"

check "common workspace wrapper runs a command under local ownership" env \
  PATH="$T/bin:/usr/bin:/bin" FORBIDDEN_LOG="$FORBIDDEN_LOG" \
  SUPER_GIT_MODE=none SUPER_TEST_EVIDENCE=local REPO="$T/plain" \
  bash -c '. "$1/scripts/_common.sh"; superagent_load_context "$PWD" run || exit; superagent_workspace_run "$REPO" -- /bin/sh -c '\''printf owned >"$1"'\'' _ "$REPO/owned.txt"; test "$(cat "$REPO/owned.txt")" = owned' _ "$ROOT"

if [[ -s "$FORBIDDEN_LOG" ]]; then
  bad "local cases made forbidden calls: $(tr '\n' ';' <"$FORBIDDEN_LOG")"
else
  ok "local cases made zero git/gh calls"
fi

echo "git-mode-test: $FAILS failure(s)"
[[ $FAILS -eq 0 ]]

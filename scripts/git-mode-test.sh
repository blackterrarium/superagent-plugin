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

# Local lifecycle fixture: real scripts, fake harness/scheduler, isolated registry.
LIFE="$T/lifecycle with space"
mkdir -p "$LIFE/vault/2026-09-17-local/master-plans" "$T/xdg" "$T/home"
git init -q "$LIFE"
printf 'metadata sentinel\n' >"$LIFE/.git/superagent-byte-sentinel"
GIT_METADATA_BEFORE="$(find "$LIFE/.git" -type f -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256 | awk '{print $1}')"
printf '%s\n' \
  'SUPER_GIT_MODE=none' \
  'SUPER_TEST_EVIDENCE=local' \
  'SUPER_HARNESS=codex' \
  'SUPER_MODEL_SUPERVISOR=codex:inherit' \
  'SUPER_EFFORT_SUPERVISOR=inherit' \
  'SUPER_GOAL_ROOT=vault' >"$LIFE/.superenv"
PLAN="$LIFE/vault/2026-09-17-local/master-plans/PLAN.md"
printf '%s\n' '# Local plan' >"$PLAN"

cat >"$T/bin/uname" <<'SH'
#!/usr/bin/env bash
echo Linux
SH
cat >"$T/bin/systemctl" <<'SH'
#!/usr/bin/env bash
printf 'systemctl %s\n' "$*" >>"$SCHEDULER_LOG"
case "$*" in
  *is-active*) echo inactive ;;
  *is-enabled*) echo disabled ;;
esac
exit 0
SH
cat >"$T/bin/loginctl" <<'SH'
#!/usr/bin/env bash
printf 'loginctl %s\n' "$*" >>"$SCHEDULER_LOG"
exit 0
SH
cat >"$T/bin/codex" <<'SH'
#!/usr/bin/env bash
printf 'codex %s\n' "$*" >>"$HARNESS_LOG"
printf '{"type":"done"}\n'
exit 0
SH
chmod +x "$T/bin/uname" "$T/bin/systemctl" "$T/bin/loginctl" "$T/bin/codex"

LIFE_ENV=(PATH="$T/bin:/usr/bin:/bin" FORBIDDEN_LOG="$FORBIDDEN_LOG" \
  SCHEDULER_LOG="$T/scheduler.log" HARNESS_LOG="$T/harness.log" \
  XDG_CONFIG_HOME="$T/xdg" HOME="$T/home" REPO="$LIFE")

check "local launch dry-run works in an ordinary directory" env "${LIFE_ENV[@]}" \
  bash "$ROOT/scripts/launch.sh" "$PLAN" --dry-run --slug local

check "local bootstrap runs under owned workspace without GitHub auth" env "${LIFE_ENV[@]}" \
  bash -c 'before="$(test -f "$HARNESS_LOG" && wc -l <"$HARNESS_LOG" || echo 0)"; "$1/scripts/bootstrap.sh" "$2" >/dev/null; after="$(wc -l <"$HARNESS_LOG")"; test "$after" -gt "$before" && grep -q -- "--skip-git-repo-check" "$HARNESS_LOG" && test ! -d "$REPO/.superagent-runtime/workspace.lockd"' _ "$ROOT" "$PLAN"

check "local launch registers project root and mode" env "${LIFE_ENV[@]}" \
  bash -c '"$1/scripts/launch.sh" "$2" --slug local --interval 30m >/dev/null && envf="$XDG_CONFIG_HOME/superagent/local.env" && physical="$(cd "$REPO" && pwd -P)" && set -a && . "$envf" && set +a && test "$SUPERAGENT_GIT_MODE" = none && test "$SUPERAGENT_PROJECT_ROOT" = "$physical" && grep -q "^git_mode: none$" "$LOOP_FILE" && grep -q "^project_root: $physical$" "$LOOP_FILE"' _ "$ROOT" "$PLAN"

check "local tick uses owned workspace and Codex skip-repo flag" env "${LIFE_ENV[@]}" \
  bash -c 'set -a; . "$XDG_CONFIG_HOME/superagent/local.env"; set +a; LOG_FILE="$3" "$1/scripts/superagent-tick.sh" && grep -q -- "--skip-git-repo-check" "$HARNESS_LOG" && test ! -d "$(cd "$2" && pwd -P)/.superagent-runtime/workspace.lockd"' _ "$ROOT" "$LIFE" "$T/tick.log"

check "busy local workspace makes a tick yield without dispatch" env "${LIFE_ENV[@]}" \
  bash -c 'marker="$3"; python3 "$1/scripts/workspace-state.py" run --root "$2" -- /bin/sh -c '\''touch "$1"; sleep 2'\'' _ "$marker" >/dev/null 2>&1 & holder=$!; while test ! -f "$marker"; do sleep 0.02; done; before="$(wc -l <"$HARNESS_LOG")"; set -a; . "$XDG_CONFIG_HOME/superagent/local.env"; set +a; LOG_FILE="$4" "$1/scripts/superagent-tick.sh"; rc=$?; after="$(wc -l <"$HARNESS_LOG")"; wait "$holder"; test "$rc" -eq 0 && test "$before" -eq "$after"' _ "$ROOT" "$LIFE" "$T/busy.marker" "$T/busy-tick.log"

PEER="$T/peer project"
PEER_GOAL="$LIFE/vault/2026-09-17-peer"
PEER_LOOP="$PEER_GOAL/loop-status/peer.md"
mkdir -p "$PEER" "$(dirname "$PEER_LOOP")"
PEER_P="$(cd "$PEER" && pwd -P)"
{
  printf '%s\n' 'SUPER_GIT_MODE=none' 'SUPER_TEST_EVIDENCE=local' 'SUPER_HARNESS=codex' \
    'SUPER_MODEL_SUPERVISOR=codex:inherit' 'SUPER_EFFORT_SUPERVISOR=inherit'
  printf 'SUPER_GOAL_ROOT=%q\n' "$LIFE/vault"
} >"$PEER/.superenv"
cat >"$PEER_LOOP" <<EOF
---
master_plan: $PEER_GOAL/master-plans/PLAN.md
git_mode: none
project_root: $PEER_P
status: WAITING FOR PLAN
iteration: 0
---
EOF
check "shared external vault contention yields without a second writer" env "${LIFE_ENV[@]}" \
  bash -c 'marker="$5"; python3 "$1/scripts/workspace-state.py" run --root "$3" -- /bin/sh -c '\''touch "$1"; sleep 2'\'' _ "$marker" >/dev/null 2>&1 & holder=$!; while test ! -f "$marker"; do sleep 0.02; done; before="$(wc -l <"$HARNESS_LOG")"; REPO="$2" LOOP_FILE="$4" LOG_FILE="$6" "$1/scripts/superagent-tick.sh"; rc=$?; after="$(wc -l <"$HARNESS_LOG")"; wait "$holder"; test "$rc" -eq 0 && test "$before" -eq "$after" && test ! -d "$2/.superagent-runtime/workspace.lockd"' _ "$ROOT" "$PEER" "$LIFE/vault" "$PEER_LOOP" "$T/shared-vault.marker" "$T/shared-vault-tick.log"

check "local status reports GitHub auth disabled" env "${LIFE_ENV[@]}" \
  bash -c 'out="$("$1/scripts/status.sh" --json local)"; printf "%s" "$out" | grep -q '\''"gh_auth":"disabled"'\''' _ "$ROOT"

MIXED_XDG="$T/mixed-xdg"
MIXED_BIN="$T/mixed-bin"
MIXED_GH_LOG="$T/mixed-gh.log"
LOCAL_LOOP="$(bash -c 'set -a; . "$1"; printf "%s" "$LOOP_FILE"' _ "$T/xdg/superagent/local.env")"
mkdir -p "$MIXED_XDG/superagent" "$MIXED_BIN"
{
  printf 'REPO=%q\n' "$LIFE"
  printf 'LOOP_FILE=%q\n' "$LOCAL_LOOP"
  printf '%s\n' 'SUPERAGENT_GIT_MODE=none' 'GH_TOKEN=must-not-leak'
} >"$MIXED_XDG/superagent/a-local.env"
{
  printf 'REPO=%q\n' "$T/github"
  printf 'LOOP_FILE=%q\n' "$T/missing-github-loop.md"
  printf '%s\n' 'SUPERAGENT_GIT_MODE=github'
} >"$MIXED_XDG/superagent/z-github.env"
cat >"$MIXED_BIN/gh" <<'SH'
#!/usr/bin/env bash
printf '%s|%s\n' "${GH_TOKEN-unset}" "$*" >>"$MIXED_GH_LOG"
case "$*" in
  'auth token') exit 1 ;;
  'auth status') echo 'Logged in to github.com account mixed-test'; exit 0 ;;
esac
exit 0
SH
chmod +x "$MIXED_BIN/gh"
check "mixed status isolates each registry row and probes only GitHub mode" env \
  PATH="$MIXED_BIN:$T/bin:/usr/bin:/bin" MIXED_GH_LOG="$MIXED_GH_LOG" \
  XDG_CONFIG_HOME="$MIXED_XDG" HOME="$T/home" \
  bash -c 'out="$("$1/scripts/status.sh" --json)"; printf "%s" "$out" | grep -q '\''"slug":"a-local".*"gh_auth":"disabled"'\'' && printf "%s" "$out" | grep -q '\''"slug":"z-github".*"gh_auth":"ok:mixed-test"'\'' && test -s "$MIXED_GH_LOG" && ! grep -q must-not-leak "$MIXED_GH_LOG"' _ "$ROOT"

check "local answer records input without git" env "${LIFE_ENV[@]}" \
  bash -c 'envf="$XDG_CONFIG_HOME/superagent/local.env"; set -a; . "$envf"; set +a; loop="$LOOP_FILE"; sed -e "s/^status:.*/status: WAITING FOR INPUT/" "$loop" >"$loop.tmp"; mv "$loop.tmp" "$loop"; "$1/scripts/answer.sh" --no-kick local proceed >/dev/null; grep -q "^answer: proceed$" "$loop"' _ "$ROOT"

check "local stop and force-stop inspection avoid worktree probes" env "${LIFE_ENV[@]}" \
  bash -c '"$1/scripts/stop.sh" "$2" --dry-run --slug local >/dev/null && "$1/scripts/force-stop.sh" --slug local >/dev/null' _ "$ROOT" "$PLAN"

check "slug controls load the registered local root outside the project" env \
  PATH="$T/bin:/usr/bin:/bin" FORBIDDEN_LOG="$FORBIDDEN_LOG" \
  SCHEDULER_LOG="$T/scheduler.log" HARNESS_LOG="$T/harness.log" \
  XDG_CONFIG_HOME="$T/xdg" HOME="$T/home" \
  bash -c 'cd "$3"; unset REPO SUPER_GIT_MODE SUPER_TEST_EVIDENCE; "$1/scripts/stop.sh" "$2" --dry-run --slug local >/dev/null && "$1/scripts/force-stop.sh" --slug local >/dev/null' _ "$ROOT" "$PLAN" "$T"

check "local force-stop reaps only a provably dead workspace lock" env "${LIFE_ENV[@]}" \
  bash -c 'physical="$(cd "$REPO" && pwd -P)"; lock="$physical/.superagent-runtime/workspace.lockd"; mkdir -p "$lock"; printf "%s\n" '\''{"schema":1,"token":"dead-token","owner_pid":99999999,"process_group":null,"operation":"dead tick"}'\'' >"$lock/owner.json"; "$1/scripts/force-stop.sh" --slug local --apply --no-kick >/dev/null; test ! -d "$lock"' _ "$ROOT"

check "recorded local mode mismatch stops before harness dispatch" env "${LIFE_ENV[@]}" \
  bash -c 'printf "%s\n" "SUPER_GIT_MODE=github" "SUPER_HARNESS=codex" >"$REPO/.superenv"; before="$(wc -l <"$HARNESS_LOG")"; set -a; . "$XDG_CONFIG_HOME/superagent/local.env"; set +a; LOG_FILE="$2" "$1/scripts/superagent-tick.sh" >/dev/null 2>&1; rc=$?; after="$(wc -l <"$HARNESS_LOG")"; test "$rc" -eq 2 && test "$before" -eq "$after"' _ "$ROOT" "$T/mismatch.log"

GIT_METADATA_AFTER="$(find "$LIFE/.git" -type f -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256 | awk '{print $1}')"
if [[ "$GIT_METADATA_BEFORE" == "$GIT_METADATA_AFTER" ]]; then
  ok "local lifecycle leaves existing git metadata bytes unchanged"
else
  bad "local lifecycle changed existing git metadata bytes"
fi

if [[ -s "$FORBIDDEN_LOG" ]]; then
  bad "local cases made forbidden calls: $(tr '\n' ';' <"$FORBIDDEN_LOG")"
else
  ok "local cases made zero git/gh calls"
fi

echo "git-mode-test: $FAILS failure(s)"
[[ $FAILS -eq 0 ]]

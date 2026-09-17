#!/usr/bin/env bash
# plan-tree-config-test.sh — offline model-routing checks.  It exercises the
# shipped loader and role bridge with fake harness CLIs; it never calls a real CLI.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMON="$ROOT/scripts/_common.sh"
BRIDGE="$ROOT/scripts/role-bridge.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
BIN="$T/bin"; mkdir -p "$BIN" "$T/repo" "$T/cwd" "$T/tmp"
export TMPDIR="$T/tmp"
FAILS=0
ok() { echo "ok   - $1"; }
fail() { echo "FAIL - $1"; FAILS=$((FAILS + 1)); }
check() { local name="$1"; shift; if "$@"; then ok "$name"; else fail "$name"; fi; }

# This is the native Claude dispatch predicate consumed by the supervisor: a
# tier plus non-inherit effort must select the named generated definition.
. "$COMMON"
check "native Claude tier plus effort requires named definition" \
  superagent_native_claude_definition_required claude claude:sonnet medium
check "native Claude tier plus inherit may use general-purpose" bash -c \
  ". '$COMMON'; ! superagent_native_claude_definition_required claude claude:sonnet inherit"
check "bridged planning role is not mistaken for native definition" bash -c \
  ". '$COMMON'; ! superagent_native_claude_definition_required claude codex:gpt-5.6-terra medium"

# Keep the shims intentionally small: role-bridge owns the argument shaping.
for bin in claude codex agent pi; do
  cat >"$BIN/$bin" <<'EOF'
#!/usr/bin/env bash
printf '%s|' "$(basename "$0")" >>"$TEST_LOG"
printf '%s ' "$@" >>"$TEST_LOG"
printf '\n' >>"$TEST_LOG"
out=""; prior=""
for arg in "$@"; do [ "$prior" = -o ] && out="$arg"; prior="$arg"; done
if [ -n "$out" ]; then printf 'fake-result\n' >"$out"; else printf 'fake-result\n'; fi
EOF
  chmod +x "$BIN/$bin"
done
printf 'routing prompt\n' >"$T/prompt.txt"
cat >"$T/route.sh" <<'EOF'
#!/usr/bin/env bash
set -u
. "$COMMON"
load_superenv "$REPO"
dispatch() {
  local role="$1" model_key="$2" effort_key="$3" model harness
  model="${!model_key}"; harness="$(superagent_role_harness "$model")"
  [ "$harness" = inherit ] && harness="$SUPER_HARNESS"
  "$BRIDGE" --harness "$harness" --model "$(superagent_role_model "$model")" \
    --effort "${!effort_key}" --tools planner --cwd "$CWD" --prompt-file "$PROMPT" --role "$role" >/dev/null || return
  printf '%s|%s|%s|%s\n' "$role" "$harness" "$(superagent_role_model "$model")" "${!effort_key}"
}
dispatch plan-refiner SUPER_MODEL_PLAN_REFINER SUPER_EFFORT_PLAN_REFINER || exit $?
dispatch replanner SUPER_MODEL_REPLANNER SUPER_EFFORT_REPLANNER
EOF
chmod +x "$T/route.sh"
run_pair() {
  local label="$1" repo="$2"; shift 2
  : >"$T/$label.log"
  env -i PATH="$BIN:/usr/bin:/bin" TMPDIR="$T/tmp" TEST_LOG="$T/$label.log" \
    COMMON="$COMMON" BRIDGE="$BRIDGE" REPO="$repo" CWD="$T/cwd" PROMPT="$T/prompt.txt" "$@" \
    "$T/route.sh" >"$T/$label.out" 2>"$T/$label.err"
}

echo 'SUPER_HARNESS=claude' >"$T/repo/.superenv"
echo 'SUPER_MODEL_PLAN_REFINER=claude:repo-refiner' >>"$T/repo/.superenv"
echo 'SUPER_EFFORT_PLAN_REFINER=low' >>"$T/repo/.superenv"
echo 'SUPER_MODEL_REPLANNER=claude:repo-replanner' >>"$T/repo/.superenv"
echo 'SUPER_EFFORT_REPLANNER=medium' >>"$T/repo/.superenv"
run_pair process "$T/repo" SUPER_HARNESS=claude SUPER_MODEL_PLAN_REFINER=codex:gpt-process-refiner SUPER_EFFORT_PLAN_REFINER=xhigh SUPER_MODEL_REPLANNER=pi:process/replanner SUPER_EFFORT_REPLANNER=max
check "process: refiner resolves its own model and effort" grep -qx 'plan-refiner|codex|gpt-process-refiner|xhigh' "$T/process.out"
check "process: replanner resolves its own model and effort" grep -qx 'replanner|pi|process/replanner|max' "$T/process.out"
check "process: actual bridge calls distinct foreign CLIs" bash -c "grep -q '^codex|.*-m gpt-process-refiner .*model_reasoning_effort=xhigh ' '$T/process.log' && grep -q '^pi|.*--model process/replanner:max ' '$T/process.log'"

# Repo pins stay role-specific.
run_pair repo "$T/repo"
check "repo: role pins remain independent" bash -c "grep -qx 'plan-refiner|claude|repo-refiner|low' '$T/repo.out' && grep -qx 'replanner|claude|repo-replanner|medium' '$T/repo.out' && [ \"\$(wc -l <'$T/repo.log' | tr -d ' ')\" = 2 ]"
check "repo: actual bridge records both roles" bash -c "grep -q 'role=plan-refiner ' '$T/tmp/superagent-bridge/'*.log && grep -q 'role=replanner ' '$T/tmp/superagent-bridge/'*.log"

# Deliberately equal pins remain two independent role dispatches.
echo 'SUPER_MODEL_PLAN_REFINER=codex:gpt-equal' >"$T/repo/.superenv"
echo 'SUPER_EFFORT_PLAN_REFINER=medium' >>"$T/repo/.superenv"
echo 'SUPER_MODEL_REPLANNER=codex:gpt-equal' >>"$T/repo/.superenv"
echo 'SUPER_EFFORT_REPLANNER=medium' >>"$T/repo/.superenv"
run_pair equal "$T/repo"
check "repo: equal pins dispatch both named roles" bash -c "grep -qx 'plan-refiner|codex|gpt-equal|medium' '$T/equal.out' && grep -qx 'replanner|codex|gpt-equal|medium' '$T/equal.out' && [ \"\$(wc -l <'$T/equal.log' | tr -d ' ')\" = 2 ]"

# With only a harness in repo config, the real loader layers that build's
# defaults over the canonical template. Exercise every shipped harness layer.
rm -f "$T/repo/.superenv"
run_pair claude_default "$T/repo"
check "harness defaults: Claude refiner" grep -qx 'plan-refiner|claude|sonnet|medium' "$T/claude_default.out"
check "harness defaults: Claude replanner" grep -qx 'replanner|claude|claude-opus-4-8|high' "$T/claude_default.out"

echo 'SUPER_HARNESS=codex' >"$T/repo/.superenv"
run_pair codex_default "$T/repo"
check "harness defaults: Codex refiner" grep -qx 'plan-refiner|codex|gpt-5.6-terra|medium' "$T/codex_default.out"
check "harness defaults: Codex replanner" grep -qx 'replanner|codex|gpt-5.6-sol|high' "$T/codex_default.out"

echo 'SUPER_HARNESS=cursor' >"$T/repo/.superenv"
run_pair cursor_default "$T/repo"
check "harness defaults: Cursor refiner inherits" grep -qx 'plan-refiner|cursor|inherit|inherit' "$T/cursor_default.out"
check "harness defaults: Cursor replanner inherits" grep -qx 'replanner|cursor|inherit|inherit' "$T/cursor_default.out"

echo 'SUPER_HARNESS=pi' >"$T/repo/.superenv"
run_pair harness "$T/repo"
check "harness defaults: Pi refiner pin reaches bridge" grep -qx 'plan-refiner|pi|openai-codex/gpt-5.6-terra|medium' "$T/harness.out"
check "harness defaults: Pi replanner pin reaches bridge" grep -qx 'replanner|pi|openai-codex/gpt-5.6-sol|high' "$T/harness.out"

# Cursor has no native effort transport. A bridged Codex refiner still carries
# the foreign effort, while native inherit omits model and effort flags.
echo 'SUPER_HARNESS=cursor' >"$T/repo/.superenv"
echo 'SUPER_MODEL_PLAN_REFINER=codex:gpt-cursor-refiner' >>"$T/repo/.superenv"
echo 'SUPER_EFFORT_PLAN_REFINER=high' >>"$T/repo/.superenv"
echo 'SUPER_MODEL_REPLANNER=inherit' >>"$T/repo/.superenv"
echo 'SUPER_EFFORT_REPLANNER=high' >>"$T/repo/.superenv"
run_pair cursor "$T/repo"
check "cursor: bridged refiner preserves foreign effort" grep -qx 'plan-refiner|codex|gpt-cursor-refiner|high' "$T/cursor.out"
check "cursor: native effort has no CLI transport" bash -c "grep -qx 'replanner|cursor|inherit|high' '$T/cursor.out' && grep -q '^agent|' '$T/cursor.log' && ! grep -q '^agent|.*--model ' '$T/cursor.log' && ! grep -q '^agent|.*--effort ' '$T/cursor.log'"

# A missing configured bridge CLI fails; the loader cannot silently reroute it.
echo 'SUPER_HARNESS=claude' >"$T/repo/.superenv"
echo 'SUPER_MODEL_PLAN_REFINER=pi:missing/refiner' >>"$T/repo/.superenv"
echo 'SUPER_EFFORT_PLAN_REFINER=high' >>"$T/repo/.superenv"
echo 'SUPER_MODEL_REPLANNER=claude:repo-replanner' >>"$T/repo/.superenv"
echo 'SUPER_EFFORT_REPLANNER=medium' >>"$T/repo/.superenv"
rm -f "$BIN/pi"
run_pair unavailable "$T/repo"; rc=$?
check "unavailable bridge CLI fails" test "$rc" -ne 0
check "unavailable bridge CLI names configured harness" grep -q 'harness=pi' "$T/unavailable.err"

echo "plan-tree-config-test: $FAILS failure(s)"
[ "$FAILS" -eq 0 ]

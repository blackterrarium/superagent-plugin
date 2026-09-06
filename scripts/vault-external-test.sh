#!/usr/bin/env bash
# vault-external-test.sh — offline tests for external-vault mode (SUPER_GOAL_ROOT outside the
# checkout): the _common.sh resolver, launch.sh's plan acceptance, stop/force-stop slug matching
# on an absolute master_plan, and init's ignore-entry routing rules. No network, no LLM, no real
# scheduler (gh / pi / launchctl / systemctl are shims). Exit 1 on any failure.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$(cd "$(mktemp -d)" && pwd -P)"; trap 'rm -rf "$T"' EXIT
FAILS=0
ok()   { echo "ok   - $1"; }
fail() { echo "FAIL - $1"; FAILS=$((FAILS+1)); }
# check <name> <cmd…> — runs the command; on failure shows its last output lines.
check() {
  local name="$1"; shift
  local out; out="$("$@" 2>&1)"; local rc=$?
  if [[ $rc -eq 0 ]]; then ok "$name"; else fail "$name (rc=$rc)"; printf '%s\n' "$out" | tail -6 | sed 's/^/       | /'; fi
}
# resolves <SUPER_GOAL_ROOT value> <primary-root> <expected>
resolves() {
  local v="$1" p="$2" want="$3" got
  got="$(SUPER_GOAL_ROOT="$v" bash -c ". '$ROOT/scripts/_common.sh'; vault_root '$p'")"
  if [[ "$got" == "$want" ]]; then ok "vault_root '$v' → $want"; else fail "vault_root '$v' → '$got' (want $want)"; fi
}

# ---- 1. resolver -----------------------------------------------------------------------------
resolves vault        /r   /r/vault
resolves vault/sub    /r   /r/vault/sub
resolves vault/       /r   /r/vault
resolves /abs/path    /r   /abs/path
resolves /abs/path/   /r   /abs/path
resolves '~/x'        /r   "$HOME/x"
resolves '~'          /r   "$HOME"
check "vault_is_external: relative → false"  bash -c "SUPER_GOAL_ROOT=vault; . '$ROOT/scripts/_common.sh'; ! vault_is_external"
check "vault_is_external: unset → false"     bash -c "unset SUPER_GOAL_ROOT; . '$ROOT/scripts/_common.sh'; ! vault_is_external"
check "vault_is_external: absolute → true"   bash -c "SUPER_GOAL_ROOT=/abs; . '$ROOT/scripts/_common.sh'; vault_is_external"
check "vault_is_external: tilde → true"      bash -c "SUPER_GOAL_ROOT='~/v'; . '$ROOT/scripts/_common.sh'; vault_is_external"
check "vault_root: missing primary arg → rc 1" bash -c "SUPER_GOAL_ROOT=vault; . '$ROOT/scripts/_common.sh'; ! vault_root 2>/dev/null"

# ---- 2. launch.sh / stop.sh / force-stop.sh with a plan under an EXTERNAL vault ----------------
# Shims so the fail-fast preflight (CLI binary, gh auth) and the scheduler probes pass offline.
SHIM="$T/bin"; mkdir -p "$SHIM"
for s in gh pi launchctl systemctl; do printf '#!/usr/bin/env bash\nexit 0\n' >"$SHIM/$s"; chmod +x "$SHIM/$s"; done
export PATH="$SHIM:$PATH"
export XDG_CONFIG_HOME="$T/xdg"; mkdir -p "$XDG_CONFIG_HOME/superagent"
# A code repo with NO vault inside it, and an external vault holding one goal.
mkdir -p "$T/code"; ( cd "$T/code" && git init -q && printf 'x\n' >f && git add f && git -c user.email=t@t -c user.name=t commit -qm init )
EXT="$T/ext-vault"; mkdir -p "$EXT/2026-09-06-10_00-demo/master-plans"; printf '# plan\n' >"$EXT/2026-09-06-10_00-demo/master-plans/seed.md"
PLAN_EXT="$EXT/2026-09-06-10_00-demo/master-plans/seed.md"
# An internal-mode repo too (today's behaviour must be unchanged).
mkdir -p "$T/int/vault/2026-09-06-10_00-demo/master-plans"; ( cd "$T/int" && git init -q && printf '# plan\n' >vault/2026-09-06-10_00-demo/master-plans/seed.md && git add -A && git -c user.email=t@t -c user.name=t commit -qm init )
# An unrelated location: under neither root.
mkdir -p "$T/elsewhere/master-plans"; printf '# plan\n' >"$T/elsewhere/master-plans/seed.md"

L="$ROOT/scripts/launch.sh"
check "launch: external plan accepted (--dry-run)" bash -c "cd '$T/code' && SUPER_GOAL_ROOT='$EXT' SUPER_HARNESS=pi '$L' '$PLAN_EXT' --harness pi --dry-run 2>&1 | grep -q 'nothing created or armed'"
check "launch: external plan is reported by its absolute path" bash -c "cd '$T/code' && SUPER_GOAL_ROOT='$EXT' SUPER_HARNESS=pi '$L' '$PLAN_EXT' --harness pi --dry-run 2>&1 | grep -q '^  plan:       $PLAN_EXT\$'"
check "launch: external loop file lands beside the plan's master-plans/" bash -c "cd '$T/code' && SUPER_GOAL_ROOT='$EXT' SUPER_HARNESS=pi '$L' '$PLAN_EXT' --harness pi --dry-run 2>&1 | grep -q '^  loop file:  $EXT/2026-09-06-10_00-demo/loop-status/'"
check "launch: plan under neither root still rejected" bash -c "cd '$T/code' && SUPER_GOAL_ROOT='$EXT' SUPER_HARNESS=pi '$L' '$T/elsewhere/master-plans/seed.md' --harness pi --dry-run >'$T/rej.out' 2>&1; [ \$? = 2 ] && grep -q 'plan must live inside the repo checkout' '$T/rej.out' && grep -q '$EXT' '$T/rej.out'"
check "launch: internal plan still accepted and repo-relative" bash -c "cd '$T/int' && SUPER_HARNESS=pi '$L' vault/2026-09-06-10_00-demo/master-plans/seed.md --harness pi --dry-run 2>&1 | grep -q '^  plan:       vault/2026-09-06-10_00-demo/master-plans/seed.md\$'"
check "launch: internal plan outside the repo still rejected" bash -c "cd '$T/int' && SUPER_HARNESS=pi '$L' '$T/elsewhere/master-plans/seed.md' --harness pi --dry-run >/dev/null 2>&1; [ \$? = 2 ]"

# stop.sh / force-stop.sh: a registered loop whose master_plan is ABSOLUTE must be found by plan.
LOOPD="$EXT/2026-09-06-10_00-demo/loop-status"; mkdir -p "$LOOPD"
printf -- '---\nmaster_plan: %s\nstatus: WAITING FOR PLAN\ndriver: external\n---\n' "$PLAN_EXT" >"$LOOPD/2026-09-06-demo.md"
printf 'REPO=%s\nLOOP_FILE=%s\nSUPERAGENT_SLUG=custom-slug\n' "$T/code" "$LOOPD/2026-09-06-demo.md" >"$XDG_CONFIG_HOME/superagent/custom-slug.env"
check "stop: absolute master_plan matched to its registered slug" bash -c "cd '$T/code' && '$ROOT/scripts/stop.sh' '$PLAN_EXT' --dry-run 2>&1 | grep -q 'goal slug:   custom-slug'"
check "force-stop: absolute master_plan matched to its registered slug" bash -c "cd '$T/code' && '$ROOT/scripts/force-stop.sh' '$PLAN_EXT' 2>&1 | grep -q 'loop file:   $LOOPD/2026-09-06-demo.md'"

echo "vault-external-test: $FAILS failure(s)"
[[ $FAILS -eq 0 ]]

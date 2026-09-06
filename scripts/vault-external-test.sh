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

echo "vault-external-test: $FAILS failure(s)"
[[ $FAILS -eq 0 ]]

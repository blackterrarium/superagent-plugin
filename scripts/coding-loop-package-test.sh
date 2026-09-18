#!/usr/bin/env bash
# Run Stage 1/2 helpers from copied distributable packages, without source-checkout fallback.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
for harness in claude codex cursor pi; do
  source="$ROOT/$harness"
  [[ "$harness" != codex ]] || source="$source/plugins/superagent"
  package="$T/$harness"
  if [[ "$harness" == claude ]]; then
    mkdir -p "$package/scripts" "$package/templates" "$package/skills"
    cp "$ROOT/scripts/_common.sh" "$ROOT/scripts/_evalspec.sh" "$ROOT/scripts/prd-lint.sh" \
      "$ROOT/scripts/supereval.sh" "$ROOT/scripts/workspace-state.py" "$package/scripts/"
    cp "$ROOT/templates/superenv.default" "$package/templates/"
    cp -R "$ROOT/skills/"* "$package/skills/"
  else
    cp -R "$source" "$package"
  fi
  # Test entry points are copied separately; all production dependencies must ship already.
  cp "$ROOT/scripts/prd-lint-test.sh" "$ROOT/scripts/supereval-test.sh" "$package/scripts/"
  [[ -x "$package/scripts/workspace-state.py" ]] || { echo "FAIL: $harness lacks executable workspace-state.py"; exit 1; }
  (
    cd /
    bash "$package/scripts/prd-lint-test.sh"
    bash "$package/scripts/supereval-test.sh"
    SUPER_GIT_MODE=none REPO="$T" bash -c '. "$1"; superagent_load_context "$2" run; test "$REPO" = "$(cd "$2" && pwd -P)"' \
      _ "$package/scripts/_common.sh" "$T"
  )
  echo "PASS: $harness copied-package Stage 1/2 helpers"
done

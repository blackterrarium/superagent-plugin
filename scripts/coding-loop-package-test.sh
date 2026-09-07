#!/usr/bin/env bash
# Run Stage 1/2 helpers from copied distributable packages, without source-checkout fallback.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
for harness in codex pi; do
  source="$ROOT/$harness"
  [[ "$harness" != codex ]] || source="$source/plugins/superagent"
  package="$T/$harness"
  cp -R "$source" "$package"
  # Test entry points are copied separately; all production dependencies must ship already.
  cp "$ROOT/scripts/prd-lint-test.sh" "$ROOT/scripts/supereval-test.sh" "$package/scripts/"
  bash "$package/scripts/prd-lint-test.sh"
  bash "$package/scripts/supereval-test.sh"
  echo "PASS: $harness copied-package Stage 1/2 helpers"
done

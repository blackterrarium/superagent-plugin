#!/usr/bin/env bash
# Run Stage 1–3 helpers from copied distributable packages, without source-checkout fallback.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
for harness in codex cursor pi; do
  source="$ROOT/$harness"
  [[ "$harness" != codex ]] || source="$source/plugins/superagent"
  package="$T/$harness"
  cp -R "$source" "$package"
  # Isolated import must resolve only shipped production files, even from a neutral cwd.
  (cd "$T" && python3 -I - "$package" "$harness" <<'CHECK'
import importlib, pathlib, subprocess, sys
package = pathlib.Path(sys.argv[1]).resolve()
harness = sys.argv[2]
sys.path.insert(0, str(package / 'scripts'))
for name in ('_coding_loop_evidence', '_coding_loop_state'):
    module = importlib.import_module(name)
    assert pathlib.Path(module.__file__).resolve().is_relative_to(package), module.__file__
    subprocess.run([sys.executable, '-I', str(package / 'scripts' / (name + '.py')), '--help'], check=True, stdout=subprocess.DEVNULL)
assert '## Problems' in (package / 'templates/coding-loop-diagnosis.md').read_text()
for name in ('superdiagnose', 'supercode', 'supercode-external', 'supermeta'):
    text = (package / 'skills' / name / 'SKILL.md').read_text()
    assert 'GENERATED FILE' in text, name
    assert not any(marker in text for marker in ('cc-only', 'codex-only', 'cursor-only', 'pi-only')), name
    assert '${CLAUDE_PLUGIN_ROOT}' not in text, name
supercode = (package / 'skills/supercode/SKILL.md').read_text()
assert 'consumer `supercode`' in supercode
assert '--supervisor-state STATE' in supercode
meta = (package / 'skills/supermeta/SKILL.md').read_text()
assert '_coding_loop_state.py meta-entry STATE' in meta
assert 'AUTHOR_APPROVED' in meta and 'AUTONOMOUS_REPAIR' in meta
native = {'codex': 'For native Codex, spawn_agent', 'cursor': 'Use one native agent', 'pi': 'Use one blocking role-bridge.sh process'}
assert native[harness] in supercode
assert all(value not in supercode for key, value in native.items() if key != harness)
external = (package / 'skills/supercode-external/SKILL.md').read_text()
assert '--supervisor supercode' in external
assert 'SUPERAGENT_SCRIPT_DIR' in external and 'SUPERAGENT_SCRIPT_DIR' in supercode
assert 'never fall back to helpers from a source' in supercode
assert 'Invoke the installed `scripts/launch.sh' not in external
CHECK
  )
  # Test entry points are copied separately; all production dependencies must ship already.
  cp "$ROOT/scripts/prd-lint-test.sh" "$ROOT/scripts/supereval-test.sh" "$package/scripts/"
  bash "$package/scripts/prd-lint-test.sh"
  bash "$package/scripts/supereval-test.sh"
  echo "PASS: $harness copied-package Stage 1–3 helpers"
done

"""Make isolated approved control snapshots after positive integration; never grades."""
from pathlib import Path
import hashlib
import json
import subprocess

run_root = Path('/private/tmp/prd-coverage-validation-20260909')
provenance = json.loads((run_root / 'provenance.json').read_text())
assert 'positive_integrated_commit' in provenance

def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()

assert git(run_root / 'repo', 'rev-parse', 'main') == provenance['positive_integrated_commit']
manifest = {}
for label in ('candidate-a', 'candidate-b'):
    root = run_root / label
    root.mkdir(exist_ok=False)
    for name in ('repo', 'vault'):
        source, checkout, bare = run_root / name, root / name, root / (name + '.git')
        subprocess.run(['git', 'clone', '-q', '--bare', str(source), str(bare)], check=True)
        subprocess.run(['git', 'clone', '-q', str(bare), str(checkout)], check=True)
        git(checkout, 'config', 'user.name', 'Coverage validation')
        git(checkout, 'config', 'user.email', 'coverage-validation@example.invalid')
    manifest[label] = {'code_commit': git(root / 'repo', 'rev-parse', 'HEAD'),
                       'initial_vault_commit': git(root / 'vault', 'rev-parse', 'HEAD')}

positive = run_root / 'candidate-a/repo'
negative = run_root / 'candidate-b/repo'
selected = negative / 'test_product.py'
original = selected.read_text()
old = '            self.assertEqual(destination.read_bytes(), before)'
new = '            self.assertTrue(destination.exists())'
assert original.count(old) == 1
assert old in (positive / 'test_product.py').read_text()
changed = original.replace(old, new)
assert changed.replace(new, old) == original
selected.write_text(changed)
assert git(negative, 'diff', '--name-only') == 'test_product.py'
assert git(negative, 'diff', '--numstat') == '1\t1\ttest_product.py'
assert (positive / 'product.py').read_bytes() == (negative / 'product.py').read_bytes()
git(negative, 'diff', '--check')
(run_root / 'mutation.diff').write_text(git(negative, 'diff') + '\n')
git(negative, 'add', 'test_product.py')
git(negative, 'commit', '-qm', 'test: record selected validation candidate')
git(negative, 'push', '-q')
manifest['candidate-b']['code_commit'] = git(negative, 'rev-parse', 'HEAD')
manifest['protocol'] = {'one_assertion_replaced': True, 'changed_files': ['test_product.py'],
                         'product_sha256': hashlib.sha256((positive / 'product.py').read_bytes()).hexdigest(),
                         'agreement_bytes_identical': True}
for name in ('prd.md', 'knowledge-base.md', 'evaluation.md'):
    a = run_root / 'candidate-a/vault/projects/2026-09-09-json-preservation' / name
    b = run_root / 'candidate-b/vault/projects/2026-09-09-json-preservation' / name
    assert a.read_bytes() == b.read_bytes()
for name in ('requirements.md', 'AGENTS.md', '.superenv', '.gitignore', 'product.py'):
    assert (positive / name).read_bytes() == (negative / name).read_bytes()
(run_root / 'snapshots.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))

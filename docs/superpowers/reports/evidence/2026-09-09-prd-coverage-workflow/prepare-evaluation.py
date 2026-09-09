"""Controller transport for one approved snapshot; invokes installed lint/runner, never grades."""
from pathlib import Path
import datetime
import json
import os
import re
import subprocess
import sys

run_root = Path('/private/tmp/prd-coverage-validation-20260909')
label = sys.argv[1]
assert label in ('candidate-a', 'candidate-b')
root = run_root / label
repo, vault = root / 'repo', root / 'vault'
project = vault / 'projects/2026-09-09-json-preservation'
provenance = json.loads((run_root / 'provenance.json').read_text())
package = Path(provenance['package'])
env = {k: v for k, v in os.environ.items() if not k.startswith(('SUPER_', 'TICK_'))}
env.update(SUPER_GOAL_ROOT=str(vault), PRD_LINT_REPO_ROOT=str(repo), TMPDIR=str(root / 'tmp') + '/')
(root / 'tmp').mkdir(exist_ok=True)

def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()

for path in (repo, vault):
    assert Path(git(path, 'rev-parse', '--show-toplevel')).resolve() == path.resolve()
    origin = Path(git(path, 'remote', 'get-url', 'origin')).resolve()
    assert run_root in origin.parents
    git(path, 'fetch', '-q', 'origin')
    assert git(path, 'branch', '--show-current') == 'main'
    assert git(path, 'rev-list', '--left-right', '--count', 'main...origin/main') == '0\t0'
    assert not git(path, 'status', '--porcelain', '--untracked-files=no')
code_sha = git(repo, 'rev-parse', 'main')
vault_sha = git(vault, 'rev-parse', 'HEAD')
for name in ('prd.md', 'knowledge-base.md', 'evaluation.md'):
    assert '**Status:** READY' in (project / name).read_text()
assert '| 1 | [[' in (project / 'prd.md').read_text()
subprocess.run([str(package / 'scripts/prd-lint.sh'), str(project), '--json'],
               cwd=repo, env=env, check=True, stdout=(root / 'lint.json').open('w'))
results = root / 'command-results.md'
command = [str(package / 'scripts/supereval.sh'), str(project), '--repo', str(repo),
           '--commit', code_sha, '--out', str(results), '--keep-worktree']
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
process = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True, timeout=600)
assert results.is_file(), process.stderr
raw = results.read_text()
worktree = Path(re.search(r'worktree: `([^`]+)`', raw).group(1))
assert git(worktree, 'rev-parse', 'HEAD') == code_sha
for name in ('product.py', 'test_product.py'):
    assert (worktree / name).is_file()
for name in ('requirements.md', 'AGENTS.md'):
    assert (worktree / name).read_bytes() == (run_root / 'source' / name).read_bytes()
    assert git(repo, 'show', provenance['source_commit'] + ':' + name) == (run_root / 'source' / name).read_text().strip()
prd = (project / 'prd.md').read_text().split('## Iteration ledger', 1)[0]
evaluation = (project / 'evaluation.md').read_text()
packet = f'''# Acceptance evidence packet

Evaluated code commit: {code_sha}
Code evidence root (detached): {worktree}
Named implementation evidence: {worktree}/product.py and {worktree}/test_product.py.
Project/vault root: {vault}; packet source snapshot commit: {vault_sha}.
Approved source-project revision: {provenance['approved_project_commit']} in the original vault.
Binding requirements/AGENTS code revision: {provenance['source_commit']}.
Approval receipt: {run_root}/approval.json; actual user message “yes” approved v1.
The immutable AGENTS proposed policy is now approved; initialization is complete.
Snapshot roots here identify the actual execution source. Original source paths inside the
verbatim agreement identify binding provenance; their content is reproduced below.
Only the selected code commit is being evaluated. No previous judgments are supplied.
Runner exit code: {process.returncode}.

## Full evaluation.md verbatim
```markdown
{evaluation}```

## PRD requirements, constraints and decisions verbatim (ledger omitted)
```markdown
{prd}```

## Binding requirements.md verbatim
Source: requirements.md at {provenance['source_commit']}.
```markdown
{(worktree / 'requirements.md').read_text()}```

## Binding AGENTS.md verbatim
Source: AGENTS.md at {provenance['source_commit']}.
```markdown
{(worktree / 'AGENTS.md').read_text()}```

## Command results verbatim
```markdown
{raw}```
'''
(root / 'evaluator-packet.md').write_text(packet)
receipt = dict(label=label, repo=str(repo), vault=str(vault), project=str(project),
               code_commit=code_sha, vault_commit=vault_sha, worktree=str(worktree),
               command=command, cwd=str(repo), started_utc=started,
               ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               runner_exit=process.returncode, runner_stdout=process.stdout, runner_stderr=process.stderr,
               context_available=True, packet=str(root / 'evaluator-packet.md'))
(root / 'evaluation-prep.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))

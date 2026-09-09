from pathlib import Path
import json,subprocess,datetime,sys
r=Path(__file__).resolve().parent
label=sys.argv[1]; root=r/label
prep=json.loads((root/'evaluation-prep.json').read_text())
repo=Path(prep['repo']); vault=Path(prep['vault']); project=Path(prep['project'])
def git(path,*args): return subprocess.check_output(['git','-C',str(path),*args],text=True).strip()
assert git(repo,'rev-parse','HEAD')==prep['code_commit']
assert git(vault,'rev-parse','--show-toplevel')==str(vault)
assert not git(vault,'status','--porcelain')
judge=(root/'judged-results.md').read_text()
assert '| J1 | PASS |' in judge or '| J1 | FAIL |' in judge
verdict='PASS' if prep['runner_exit']==0 and prep['context_available'] and '| J1 | PASS |' in judge else 'FAIL'
assert not list((vault/'2026-09-09-15_18-json-preservation-r1').glob('loop-status/*.md'))
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d-%H_%M')
rel=Path('eval-reports')/(stamp+'-r1.md'); report=project/rel; report.parent.mkdir(exist_ok=True)
report.write_text(f'# JSON preservation — eval report round 1 — {stamp}-r1\n**Date:** 2026-09-09 · **Status:** FINAL · **Related:** [[projects/2026-09-09-json-preservation/prd]] · [[projects/2026-09-09-json-preservation/meta-plans/2026-09-09-15_16-r1]] · **Round:** 1\n\n'+(root/'command-results.md').read_text()+'\n## Judged objectives\n'+judge+f'\n## Verdict\n**{verdict}** — '+('all checks passed' if verdict=='PASS' else 'J1')+'\n**Inner loop:** none found\n**Warnings:** none\n')
prd=project/'prd.md'; before=prd.read_text(); lines=before.splitlines()
rows=[i for i,line in enumerate(lines) if line.startswith('| 1 |')]; assert len(rows)==1
idx=rows[0]; parts=lines[idx].split('|'); assert [s.strip() for s in parts[4:7]]==['-','-','-']
parts[5]=f' [[projects/2026-09-09-json-preservation/eval-reports/{stamp}-r1]] ';parts[6]=f' {verdict} ';lines[idx]='|'.join(parts)
prd.write_text('\n'.join(lines)+'\n')
assert (root/'command-results.md').read_text() in report.read_text()
git(vault,'add',str(report.relative_to(vault)),str(prd.relative_to(vault)))
git(vault,'commit','-m',f'docs(project): json-preservation round 1 eval {verdict}')
git(vault,'push','origin','main')
commit=git(vault,'rev-parse','HEAD');assert commit==git(vault,'rev-parse','origin/main')
(root/'evaluation-final.json').write_text(json.dumps({'verdict':verdict,'report':str(report),'vault_commit':commit,'evaluated_commit':prep['code_commit'],'judge_task':'/root/evaluator_'+label[-1]},indent=2)+'\n')
# Code remains in the snapshot primary; remove only the runner-created detached tree.
git(repo,'worktree','remove','--force',prep['worktree'])
print(json.dumps({'candidate':label,'verdict':verdict,'vault_commit':commit,'report':str(report)}))

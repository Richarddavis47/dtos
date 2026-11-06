from pathlib import Path
import json,subprocess
from concurrent.futures import ThreadPoolExecutor
b=Path('/workspace/2234-release')
heads=[]
for root in sorted(b.glob('prior-candidate-*')):
 if (root/'source.json').exists():heads.append(json.loads((root/'source.json').read_text())['candidate'])
def api(t):return json.loads(subprocess.check_output(['gh','api','repos/Richarddavis47/dtos/'+t],text=True))
rows=[]
for head in heads:
 data=api('actions/runs?head_sha='+head+'&per_page=20')
 runs=[r for r in data['workflow_runs'] if r['event']=='pull_request']
 with ThreadPoolExecutor(max_workers=4) as pool:
  jobs=list(pool.map(lambda r:api('actions/runs/'+str(r['id'])+'/jobs?per_page=100')['jobs'],runs))
 for r,j in zip(runs,jobs):rows.append({'run':r,'jobs':j})
(b/'prior-hosted-status-final.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps([{'source':r['run']['head_sha'],'id':r['run']['id'],'name':r['run']['name'],'conclusion':r['run']['conclusion'],'jobs':[(j['name'],j['conclusion']) for j in r['jobs']]} for r in rows]))

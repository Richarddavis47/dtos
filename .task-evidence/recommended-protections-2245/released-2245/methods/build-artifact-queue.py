from pathlib import Path
import json,subprocess,re
b=Path('/workspace/2245-recommended-protections');p=json.loads(Path('/workspace/dtos-publisher-2245/.github/release-plans/2245.json').read_text());s=json.loads((b/'source.json').read_text())
def api(path):return json.loads(subprocess.check_output(['gh','api','repos/'+p['repository']+'/'+path],text=True))
records=[];artifacts=[]
for expected in p['runs']:
 run=api('actions/runs/'+str(expected['id']));assert run['head_sha']==s['candidate'] and run['event']=='pull_request' and run['path']==expected['path'] and run['status']=='completed' and run['conclusion']=='success',expected['name']
 jobs=api('actions/runs/'+str(expected['id'])+'/jobs?per_page=100')['jobs']
 for name in expected['jobs']:
  rows=[j for j in jobs if j['name']==name];assert len(rows)==1 and rows[0]['status']=='completed' and rows[0]['conclusion']=='success',name
 a=api('actions/runs/'+str(expected['id'])+'/artifacts?per_page=100')['artifacts'];records.append(dict(run=run,jobs=jobs,artifacts=a));artifacts+=a
mapping={x['name']:x['file'] for x in json.loads(Path('/workspace/dtos-publisher-2244/.github/release-plans/2244.json').read_text())['artifacts']};queue=[]
for name,file in mapping.items():
 rows=[a for a in artifacts if a['name']==name and not a['expired']];assert len(rows)==1,name;a=rows[0];assert a['workflow_run']['head_sha']==s['candidate'];sha=a['digest'].removeprefix('sha256:');assert re.fullmatch('[a-f0-9]{64}',sha);queue.append(dict(id=a['id'],name=name,run=a['workflow_run']['id'],file=file,bytes=a['size_in_bytes'],sha256=sha))
assert len(queue)==15 and sum(len(r['jobs']) for r in p['runs'])==13
(b/'hosted-final-records.json').write_text(json.dumps(records,indent=2)+'\n');(b/'artifact-download-queue.json').write_text(json.dumps(queue,indent=2)+'\n');print(dict(candidate=s['candidate'],tree=s['tree'],jobs=13,original_artifacts=len(queue)))

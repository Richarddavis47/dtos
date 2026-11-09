from pathlib import Path
import json,subprocess,re
b=Path('/workspace/2242-trade-partner-history-link');root=Path('/workspace/dtos-publisher-2242');p=json.loads((root/'.github/release-plans/2242.json').read_text());source=json.loads((b/'source.json').read_text());assert p['candidate']==source['candidate'] and p['tree']==source['tree']
def api(path):return json.loads(subprocess.check_output(['gh','api','repos/'+p['repository']+'/'+path],text=True))
records=[];all_artifacts=[]
for expected in p['runs']:
 run=api('actions/runs/'+str(expected['id']));assert run['head_sha']==p['candidate'] and run['event']=='pull_request' and run['path']==expected['path'];assert run['status']=='completed' and run['conclusion']=='success',expected['name']
 jobs=api('actions/runs/'+str(expected['id'])+'/jobs?per_page=100')['jobs']
 for name in expected['jobs']:
  found=[j for j in jobs if j['name']==name];assert len(found)==1 and found[0]['status']=='completed' and found[0]['conclusion']=='success',name
 artifacts=api('actions/runs/'+str(expected['id'])+'/artifacts?per_page=100')['artifacts'];records.append(dict(run=run,jobs=jobs,artifacts=artifacts));all_artifacts.extend(artifacts)
assert sum(len(r['jobs']) for r in p['runs'])==13
mapping={x['name']:x['file'] for x in json.loads(Path('/workspace/dtos-publisher-2239/.github/release-plans/2239.json').read_text())['artifacts']}
queue=[]
for name,file in mapping.items():
 found=[a for a in all_artifacts if a['name']==name and not a['expired']];assert len(found)==1,name;a=found[0];assert a['workflow_run']['head_sha']==p['candidate'];sha=a['digest'].removeprefix('sha256:');assert re.fullmatch('[0-9a-f]{64}',sha);queue.append(dict(id=a['id'],name=name,run=a['workflow_run']['id'],file=file,sha256=sha,bytes=a['size_in_bytes']))
(b/'hosted-final-records.json').write_text(json.dumps(records,indent=2)+'\n');(b/'artifact-download-queue.json').write_text(json.dumps(queue,indent=2)+'\n');print({'source':p['candidate'],'required_jobs':13,'artifacts':len(queue)})

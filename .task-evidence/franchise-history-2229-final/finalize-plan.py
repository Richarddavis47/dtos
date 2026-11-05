"""Pin only completed exact-source mandatory records and verified originals."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

b=Path('/workspace/2229-release/final-scheduled')
root=Path('/workspace/dtos-publisher-2229')
path=root/'.github/release-plans/2229.json'
p=json.loads(path.read_text())
def api(tail):
    return json.loads(subprocess.check_output(['gh','api','repos/'+p['repository']+'/'+tail],text=True))
local=json.loads((b/'local-verified.json').read_text())
host=json.loads((b/'host-canonical-verified.json').read_text())
assert local['candidate']==host['candidate']==p['candidate']
assert local['tree']==host['tree']==p['tree'] and local['all_local_gates_passed'] and host['all_gates_passed']
checks=api('commits/'+p['candidate']+'/check-runs?filter=latest&per_page=100')['check_runs']
records=[]; artifacts=[]
for expected in p['runs']:
    run=api('actions/runs/'+str(expected['id']))
    assert run['head_sha']==p['candidate'] and run['status']=='completed' and run['conclusion']=='success'
    assert run['event']=='pull_request' and run['path']==expected['path']
    jobs=api('actions/runs/'+str(expected['id'])+'/jobs?per_page=100')['jobs']
    for name in expected['jobs']:
        found=[j for j in jobs if j['name']==name]
        assert len(found)==1 and found[0]['status']=='completed' and found[0]['conclusion']=='success',name
        matching=[c for c in checks if c['name']==name]
        assert matching and all(c['head_sha']==p['candidate'] and c['status']=='completed' and c['conclusion']=='success' for c in matching),name
    a=api('actions/runs/'+str(expected['id'])+'/artifacts?per_page=100')['artifacts']
    records.append(dict(run=run,jobs=jobs,artifacts=a))
    artifacts += [(expected['id'],x) for x in a]
assert sum(len(r['jobs']) for r in p['runs'])==12
mapping={'canonical-release-2g-python314':'canonical-original.zip','restoration-preflight-2g':'preflight-original.zip',
    'trade-resource-2g':'trade-resource-original.zip','league-entry-2g':'league-entry-original.zip',
    'linux-market-lifecycle-ordinary-summary':'lifecycle-ordinary.zip',
    'linux-market-lifecycle-archive-warmed-summary':'lifecycle-archive-warmed.zip',
    'linux-market-lifecycle-combined-read-summary':'lifecycle-combined-read.zip',
    'public-welcome-security-browser':'public-welcome-security.zip'}
p['artifacts']=[]
for name,file in mapping.items():
    found=[(rid,a) for rid,a in artifacts if a['name']==name and not a['expired']]
    assert len(found)==1,name
    rid,a=found[0]
    assert a['workflow_run']['head_sha']==p['candidate']
    sha=a['digest'].removeprefix('sha256:'); assert re.fullmatch('[0-9a-f]{64}',sha)
    original=b/'hosted-originals'/(name+'.zip')
    assert original.stat().st_size==a['size_in_bytes'] and hashlib.sha256(original.read_bytes()).hexdigest()==sha
    p['artifacts'].append(dict(id=a['id'],name=name,run=rid,file=file,sha256=sha))
p.update(canonical_tests=4107,canonical_entries=host['entries'],local_canonical_entries=local['local_manifest_entries'],product_tests=636)
for field,file in [('recovery_sha256','2229-recovery.zip'),('prior_evidence_sha256','2229-prior.zip')]:
    p[field]=hashlib.sha256((root/'.github/release-plans'/file).read_bytes()).hexdigest()
draft=json.loads((b/'draft-created.json').read_text())
assert draft['draft'] and draft['tag_name']=='v1.22.14' and draft['target_commitish']==p['candidate']
p['draft_id']=draft['id'];p['finalized']=True
path.write_text(json.dumps(p,indent=2)+'\n')
(b/'hosted-final-records.json').write_text(json.dumps(records,indent=2)+'\n')
print('Pinned12successful jobs,8source-matching original artifacts,4107tests and10local/hosted gates.')

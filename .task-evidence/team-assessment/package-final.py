"""Package existing completed results only; never run or synthesize tests."""
from pathlib import Path
from collections import Counter
import hashlib,json,re,subprocess,zipfile
b=Path('/workspace/team-assessment-validation');p=b/'canonical'
head='a332afe8fc545320c9a74134ab56f87c66b91af4';tree='6b8ea104ce38338270d33ffb9ae225e6018395b6'
r=json.loads((p/'result.json').read_text());assert r['head']==head and r['tree']==tree and r['passed'] and r['exit_code']==0
assert 'Validation UID 1000' in (b/'clean-console-a332afe.log').read_text()
events=Counter(json.loads(line)['event'] for line in (p/'tests.jsonl').read_text().splitlines())
assert events['start']==events['stop'] and not any(events[k] for k in ('failure','error','skip'))
t=[json.loads(line) for line in (p/'canonical-trace.jsonl').read_text().splitlines()];completed=[x for x in t if x.get('event')=='validation_child_completed']
assert len(completed)==10 and all(x['return_code']==0 for x in completed)
assert any(x.get('event')=='validator_final_summary' and x.get('gates')==10 for x in t)
manifest=json.loads((p/'manifest.json').read_text());sums=dict(line.split('  ',1)[::-1] for line in (p/'SHA256SUMS').read_text().splitlines())
for row in manifest:
 q=p/row['name'];assert q.stat().st_size==row['bytes'];assert hashlib.sha256(q.read_bytes()).hexdigest()==row['sha256']==sums[row['name']]
assert len(manifest)==len(sums)
assert 'Ran 71 tests' in (b/'focused-a332afe.log').read_text() and '\nOK\n' in (b/'focused-a332afe.log').read_text()
assert r['cgroup_limit']==2147483648 and not r['final_memory']['cgroup_memory_events'].get('oom_kill')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd='/workspace/team-assessment-candidate',text=True).strip()==head
assert not subprocess.check_output(['git','status','--porcelain'],cwd='/workspace/team-assessment-candidate',text=True).strip()
summary={'baseline':'dd3366d7b3d5e713c8004ec5e34b72ac9a27a94f','original_candidate':'cd400cf84ce6f80405848d43b95e7fece975c42b','validated_candidate':head,'tree':tree,'python':r['python'],'test_uid':1000,'focused_tests':71,'regression_events':dict(events),'canonical_gates':10,'all_gates_passed':True,'manifest_payloads_verified':len(manifest),'elapsed_seconds':r['elapsed_seconds'],'cgroup_limit':r['cgroup_limit'],'kernel_peak':r['kernel_peak'],'oom_events':r['final_memory']['cgroup_memory_events'],'release_actions':'No merge, tag, GitHub release or deployment performed.','limitations':'Disposable tests, not live Granite acceptance. Earlier failed and incomplete attempts are separate. No grading, Trade, scoring, lineup-selection or resource-admission policy changes.'}
(b/'FINAL_VALIDATION.json').write_text(json.dumps(summary,indent=2)+'\n')
pattern=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
archive=b/'validation-a332afe.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for q in sorted(p.rglob('*')):
  if q.is_file():
   if q.suffix in {'.json','.jsonl','.log','.txt','.md','.py','.html','.js'}:assert not pattern.search(q.read_bytes()),q.name
   z.write(q,'canonical/'+str(q.relative_to(p)))
 for name in ['FINAL_VALIDATION.json','original-canonical.log','candidate.patch','candidate-a332afe.patch','candidate-a332afe.json','source-and-original-failure.json','focused-a332afe.log','invocation.json','invocation-focused-a332afe.json','run-clean.py','clean-console-a332afe.log','patch-application-proof.json']:
  z.write(b/name,name)
assert archive.stat().st_size<100*1024**2
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps(summary,indent=2));print('Archive SHA256',hashlib.sha256(archive.read_bytes()).hexdigest(),archive.stat().st_size)

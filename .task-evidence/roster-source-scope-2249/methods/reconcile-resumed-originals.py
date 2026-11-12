"""Recheck retained original bytes/results, never rerun or recreate test execution."""
from pathlib import Path,PurePosixPath
from collections import Counter
import json,hashlib,zipfile,re,subprocess,datetime
B=Path(__file__).resolve().parent;S=Path('/workspace/dtos-sleeper-relevance-2249');s=json.loads((B/'source.json').read_text())
def sha(raw):return hashlib.sha256(raw).hexdigest()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip()==s['candidate'];assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=S,text=True).strip()==s['tree'];assert not subprocess.check_output(['git','status','--porcelain'],cwd=S,text=True).strip()
proofs=[]
for kind in ['local','hosted']:
 z=zipfile.ZipFile(B/'hosted-originals/canonical-original.zip') if kind=='hosted' else None
 root=B/'local-canonical'
 def read(name):return z.read(name) if z else (root/name).read_bytes()
 result=json.loads(read('result.json'));assert result['head']==s['candidate'] and result['tree']==s['tree'] and result['passed'] and result['exit_code']==0 and result['cgroup_limit']==2147483648 and result['python'].startswith('3.14.3') and result['cpus']==2 and result['network']=='none';assert result['process_cleanup']['validator_reaped'] and not result['process_cleanup']['timeout_triggered'];assert not any(result['final_memory']['cgroup_memory_events'].get(k,0) for k in ['oom','oom_kill'])
 console=read('unittest-console.log');assert re.search(rb'Ran 4419 tests in [0-9.]+s\s+OK\s*$',console)
 events=[json.loads(x) for x in read('tests.jsonl').splitlines()];counts=Counter(x['event'] for x in events);assert counts['start']==counts['stop']==4419 and not any(counts[k] for k in ['failure','error','skip'])
 trace=[json.loads(x) for x in read('canonical-trace.jsonl').splitlines()];gates=[x for x in trace if x.get('event')=='validation_child_completed'];assert len(gates)==10 and all(x['return_code']==0 for x in gates);assert any(x.get('event')=='validator_exit' and x.get('exit_code')==0 for x in trace)
 manifest=json.loads(read('manifest.json'));sums={name:h for h,name in (x.split('  ',1) for x in read('SHA256SUMS').decode().splitlines())};assert len(manifest)==len(sums);names=set()
 for row in manifest:
  n=PurePosixPath(row['name']);assert not n.is_absolute() and '..' not in n.parts and row['name'] not in names;names.add(row['name']);raw=read(row['name']);assert len(raw)==row['bytes'] and sha(raw)==row['sha256']==sums[row['name']]
 if z:
  assert z.testzip() is None;assert set(n for n in z.namelist() if not n.endswith('/'))<=names|{'manifest.json','SHA256SUMS','container-state.json','container.log'};z.close()
 else:
  assert {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name not in ['manifest.json','SHA256SUMS']}==names
 receipts=json.loads((B/('host-canonical-verified.json' if z else 'local-verified.json')).read_text());assert receipts['console_sha256']==sha(console) and receipts['tests']==4419
 proofs.append(dict(kind=kind,tests=4419,ten_gates_passed=True,original_manifest_entries=len(manifest),console_sha256=sha(console),process_reaped=True,oom_events=0))
required=json.loads((B/'validation-runs.json').read_text());jobs=[];runs=[]
for row in required['runs']:
 run=json.loads(subprocess.check_output(['gh','api',f"repos/Richarddavis47/dtos/actions/runs/{row['id']}"],text=True));assert run['head_sha']==s['candidate'] and run['status']=='completed' and run['conclusion']=='success' and run['path']==row['path'];live=json.loads(subprocess.check_output(['gh','api',f"repos/Richarddavis47/dtos/actions/runs/{row['id']}/jobs?per_page=100"],text=True))['jobs']
 for name in row['jobs']:
  matches=[j for j in live if j['name']==name];assert len(matches)==1;job=matches[0];assert job['head_sha']==s['candidate'] and job['status']=='completed' and job['conclusion']=='success';jobs.append(dict(id=job['id'],name=name,conclusion='success',run=run['id']))
 runs.append(dict(id=run['id'],head_sha=run['head_sha'],conclusion=run['conclusion']))
assert len(jobs)==13
q=json.loads((B/'artifact-download-queue.json').read_text());assert len(q)==15
for row in q:
 p=B/'hosted-originals'/row['file'];assert p.stat().st_size==row['bytes'] and hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==row['sha256']
state=json.loads((B/'local-container-state-original.json').read_text());assert state['State']['ExitCode']==0 and not state['State']['Running'] and state['State']['Pid']==0 and not state['State']['OOMKilled'];assert state['HostConfig']['Memory']==state['HostConfig']['MemorySwap']==2147483648
cleanup=json.loads((B/'local-container-cleanup.json').read_text());assert cleanup['stopped_container_removed'] and cleanup['all_original_manifest_bytes_verified']
f=json.loads((B/'focused-exact/result.json').read_text());assert f['commit']==s['candidate'] and f['tree']==s['tree'] and f['tests']==123 and f['passed'] and not f['dirty'] and f['failures']==f['errors']==f['skipped']==0
r=dict(observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),candidate=s['candidate'],tree=s['tree'],verified=True,original_records=proofs,focused_tests=123,required_hosted_jobs=jobs,runs=runs,original_native_archives=15,local_cleanup_verified=True,scope='Original byte/manifest/console/event/process records reconciled with fresh GitHub results. No tests rerun; narratives alone are not evidence. Earlier failed/cancelled/incomplete records remain separate.')
(B/'resumed-original-reconciliation.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))

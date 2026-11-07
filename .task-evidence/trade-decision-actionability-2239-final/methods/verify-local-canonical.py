from pathlib import Path
from collections import Counter
import hashlib,json,re
b=Path('/workspace/2239-trade-actionability');c=b/'canonical';source=json.loads((b/'source.json').read_text());r=json.loads((c/'result.json').read_text())
assert r['head']==source['candidate'] and r['tree']==source['tree'] and r['passed'] and r['exit_code']==0
assert r['cgroup_limit']==2147483648 and r['cpus']==2 and r['network']=='none' and r['python'].startswith('3.14.3')
assert not r['final_memory']['cgroup_memory_events']['oom_kill'] and not r['final_memory']['cgroup_memory_events']['oom']
console=(c/'unittest-console.log').read_bytes();match=re.search(rb'Ran (\d+) tests in [0-9.]+s\s+OK\s*$',console);assert match and int(match[1])==4271
counts=Counter(json.loads(x)['event'] for x in (c/'tests.jsonl').read_text().splitlines());assert counts['start']==counts['stop']==4271 and not any(counts[k] for k in ['error','failure','skip'])
trace=[json.loads(x) for x in (c/'canonical-trace.jsonl').read_text().splitlines()];g=[x for x in trace if x.get('event')=='validation_child_completed'];assert len(g)==10 and all(x['return_code']==0 for x in g) and any(x.get('event')=='validator_final_summary' and x.get('gates')==10 for x in trace)
manifest=json.loads((c/'manifest.json').read_text());sums=dict(x.split('  ',1)[::-1] for x in (c/'SHA256SUMS').read_text().splitlines());assert len(sums)==len(manifest)
for row in manifest:
 data=(c/row['name']).read_bytes();assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']==sums[row['name']]
summary=dict(candidate=source['candidate'],tree=source['tree'],tests=4271,all_local_gates_passed=True,local_manifest_entries=len(manifest),console_sha256=hashlib.sha256(console).hexdigest(),kernel_peak=r['kernel_peak'],elapsed_seconds=r['elapsed_seconds'],cgroup_limit=r['cgroup_limit'])
(b/'local-verified.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
parts=b/'readable-console';parts.mkdir(exist_ok=True);chunks=[];start=0
while start<len(console):
 end=min(start+60000,len(console))
 while end<len(console) and console[end]&0xc0==0x80:end-=1
 assert end>start
 chunks.append(console[start:end]);start=end
for i,data in enumerate(chunks,1):(parts/f'unittest-console-{i:03d}.log').write_bytes(data)
assert b''.join(chunks)==console
(parts/'SHA256SUMS').write_text(''.join(hashlib.sha256(d).hexdigest()+f'  unittest-console-{i:03d}.log\n' for i,d in enumerate(chunks,1)))

from pathlib import Path
from collections import Counter
import hashlib,json,re,zipfile
b=Path('/workspace/2232-release');p=b/'hosted-originals/canonical-release-2g-python314.zip';m=json.loads((b/'source.json').read_text())
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 r=json.loads(z.read('result.json'));manifest=json.loads(z.read('manifest.json'))
 assert r['head']==m['candidate'] and r['tree']==m['tree'] and r['passed'] and r['exit_code']==0
 assert r['cgroup_limit']==2147483648 and r['cpus']==2 and r['network']=='none'
 assert not r['final_memory']['cgroup_memory_events']['oom_kill']
 sums=dict(line.split('  ',1)[::-1] for line in z.read('SHA256SUMS').decode().splitlines());assert len(sums)==len(manifest)
 for row in manifest:
  data=z.read(row['name']);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']==sums[row['name']]
 console=z.read('unittest-console.log');match=re.search(rb'Ran (\d+) tests in [0-9.]+s\s+OK\s*$',console);assert match and int(match[1])==4152
 ev=Counter(json.loads(line)['event'] for line in z.read('tests.jsonl').splitlines());assert ev['start']==ev['stop']==4152 and not any(ev[x] for x in ['failure','error','skip'])
 tr=[json.loads(line) for line in z.read('canonical-trace.jsonl').splitlines()];g=[x for x in tr if x.get('event')=='validation_child_completed'];assert len(g)==10 and all(x['return_code']==0 for x in g) and any(x.get('event')=='validator_final_summary' and x.get('gates')==10 for x in tr)
 out=b/'host-canonical-readable';out.mkdir(exist_ok=True)
 for name in ['result.json','manifest.json','SHA256SUMS','canonical.log','canonical-trace.jsonl','unittest-console.log','tests.jsonl','memory.jsonl']:(out/name).write_bytes(z.read(name))
 parts=[];block=bytearray()
 for line in console.splitlines(keepends=True):
  if block and len(block)+len(line)>400000:parts.append(bytes(block));block.clear()
  block.extend(line)
 if block:parts.append(bytes(block))
 for i,data in enumerate(parts,1):(out/f'console-{i:03d}.log').write_bytes(data)
 assert b''.join(parts)==console
report=dict(candidate=m['candidate'],tree=m['tree'],tests=4152,all_gates_passed=True,entries=len(manifest),original_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),console_sha256=hashlib.sha256(console).hexdigest(),kernel_peak=r['kernel_peak'],elapsed_seconds=r['elapsed_seconds'],scope='Original hosted exact-source canonical artifact; checksum-verified payloads and authoritative full-console success')
(b/'host-canonical-verified.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

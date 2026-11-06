"""Package original exact-source evidence after all local canonical gates pass."""
from collections import Counter
from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2233-release');c=b/'canonical';m=json.loads((b/'source.json').read_text());r=json.loads((c/'result.json').read_text())
assert r['passed'] and r['exit_code']==0 and r['head']==m['candidate'] and r['tree']==m['tree']
assert r['cgroup_limit']==2147483648 and r['cpus']==2 and r['network']=='none' and not r['final_memory']['cgroup_memory_events']['oom_kill']
console=(c/'unittest-console.log').read_bytes();match=re.search(rb'Ran (\d+) tests in [0-9.]+s\s+OK\s*$',console);assert match and int(match[1])==4180
counts=Counter(json.loads(x)['event'] for x in (c/'tests.jsonl').read_text().splitlines());assert counts['start']==counts['stop']==4180 and not any(counts[k] for k in ['error','failure','skip'])
trace=[json.loads(x) for x in (c/'canonical-trace.jsonl').read_text().splitlines()];g=[x for x in trace if x.get('event')=='validation_child_completed'];assert len(g)==10 and all(x['return_code']==0 for x in g) and any(x.get('event')=='validator_final_summary' and x.get('gates')==10 for x in trace)
manifest=json.loads((c/'manifest.json').read_text());sums=dict(x.split('  ',1)[::-1] for x in (c/'SHA256SUMS').read_text().splitlines());assert len(sums)==len(manifest)
for row in manifest:
 data=(c/row['name']).read_bytes();assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']==sums[row['name']]
summary=dict(candidate=m['candidate'],tree=m['tree'],tests=4180,all_local_gates_passed=True,local_manifest_entries=len(manifest),console_sha256=hashlib.sha256(console).hexdigest(),kernel_peak=r['kernel_peak'],elapsed_seconds=r['elapsed_seconds'],cgroup_limit=r['cgroup_limit'])
(b/'local-verified.json').write_text(json.dumps(summary,indent=2)+'\n')
parts=b/'readable-console';parts.mkdir(exist_ok=True);chunks=[];block=bytearray()
for line in console.splitlines(keepends=True):
 if block and len(block)+len(line)>400000:chunks.append(bytes(block));block.clear()
 block.extend(line)
if block:chunks.append(bytes(block))
for i,d in enumerate(chunks,1):(parts/f'unittest-console-{i:03d}.log').write_bytes(d)
assert b''.join(chunks)==console
(parts/'SHA256SUMS').write_text(''.join(hashlib.sha256(d).hexdigest()+f'  unittest-console-{i:03d}.log\n' for i,d in enumerate(chunks,1)))
pre=json.loads((b/'local-preflight/result.json').read_text());assert pre['passed'] and pre['complete'] and pre['head']==m['candidate'] and pre['tree']==m['tree']
assert (b/'local-preflight/raw.log').read_bytes()==(b/'local-preflight-console.log').read_bytes()
files={}
for folder,prefix in [('canonical','local-canonical'),('local-preflight','local-preflight'),('browser-final','current-production-coverage'),('readable-console','readable-console')]:
 for p in sorted((b/folder).rglob('*')):
  if p.is_file():files[prefix+'/'+str(p.relative_to(b/folder))]=p
for name in ['SCOUT_HANDOFF.md','source.json','candidate-production.patch','source-integrity.json','local-verified.json','focused-exact.log','local-preflight-console.log','commands.md','run-clean.py','run-constrained.py','invocation.json','local-console.log','preservation.json','baseline.json','package-final.py','package-prior-report.json','harness-preservation.json','checkout-reuse.json','publisher-focused.log','publisher-focused-final.log','publisher-lint-final.log','offline-publication-guards.json','offline-publication-guards-final.log','before-after.json','before-after.py','before-after.log','resource-verified.json','lifecycle-verified.json','product-artifact-integrity.log']:
 files[name]=b/name
out=Path('/workspace/dtos-publisher-2233/.github/release-plans/2233-recovery.zip');assert not out.exists(),'Preserve any earlier recovery archive before replacing'
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,p in sorted(files.items()):
  if p.suffix in {'.json','.jsonl','.log','.txt','.md','.py','.patch','.html','.js'}:assert not pattern.search(p.read_bytes()),name
  z.write(p,name)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
assert out.stat().st_size<100*1024**2
print(json.dumps(summary));print('Recovery bytes',out.stat().st_size,'sha256',hashlib.sha256(out.read_bytes()).hexdigest())

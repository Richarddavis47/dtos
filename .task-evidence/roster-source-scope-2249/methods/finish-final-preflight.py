"""Serial final focused/native/canonical execution; no duplicate or unsafe overlap."""
from pathlib import Path
import subprocess,json,time,hashlib,re
import yaml
B=Path('/workspace/2249-sleeper-relevance');S=Path('/workspace/dtos-sleeper-relevance-2249')
s=json.loads((B/'source.json').read_text())
while not (B/'focused-exact/result.json').exists():time.sleep(2)
f=json.loads((B/'focused-exact/result.json').read_text())
assert f['passed'] and f['tests']==123 and f['failures']==f['errors']==f['skipped']==0 and not f['dirty']
assert f['commit']==s['candidate'] and f['tree']==s['tree'] and f['memory_limit']==2147483648
# Wait for --rm retirement, rather than starting a second VFS container while
# the previous run still owns its layer. Never stop or kill a healthy test.
while True:
 ids=subprocess.check_output(['docker','ps','-aq'],text=True).split()
 owns=False
 for c in ids:
  r=json.loads(subprocess.check_output(['docker','inspect',c],text=True))[0]
  if any(m.get('Source')==str(B/'focused-exact') and m.get('Destination')=='/output' for m in r['Mounts']):owns=True
 if not owns:break
 time.sleep(2)
(B/'focused-ready.json').write_text(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],passed=True,tests=123,memory_limit=f['memory_limit'],peak=f['peak'],original_console_sha256=hashlib.file_digest((B/'focused-exact/original-console.log').open('rb'),'sha256').hexdigest(),owned_focused_container_retired=True),indent=2)+'\n')
with (B/'native-sequence-original.log').open('xb') as sink:subprocess.run(['python',str(B/'run-local-resource.py')],stdout=sink,stderr=subprocess.STDOUT,check=True)
O=B/'local-canonical';O.mkdir(exist_ok=False);yp=S/'.github/workflows/canonical-release-recovery.yml';w=yaml.safe_load(yp.read_text());step=next(x for x in w['jobs']['canonical-release']['steps'] if x.get('name')=='Prepare disposable validation harness');rows=[]
for name,code in re.findall(r"cat > ([^\n]+) <<'PY'\n(.*?)\nPY",step['run'],re.S):
 if name.endswith('/runner.py'):p=O/'runner.py'
 elif name.endswith('/observer/sitecustomize.py'):p=O/'observer/sitecustomize.py'
 else:continue
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(code+'\n');rows.append(dict(member=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
assert len(rows)==2
(B/'canonical-runner-extraction.json').write_text(json.dumps(dict(source=s,workflow_sha256=hashlib.sha256(yp.read_bytes()).hexdigest(),runners=rows),indent=2)+'\n')
subprocess.run(['python',str(B/'start-release-canonical.py')],check=True)

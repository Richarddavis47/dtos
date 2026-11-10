"""Start one bounded canonical run; detached terminal is not a test pass."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
b=Path('/workspace/2245-recommended-protections');source=Path('/workspace/dtos-2245-local-completion');s=json.loads((b/'source.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==s['candidate']
assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=source,text=True).strip()==s['tree']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True).strip()
assert not subprocess.check_output(['docker','ps','-a','--filter','name=^/dtos-protections-local-completion$','--format','{{.ID}}'],text=True).strip(),'Existing run must be inspected, never duplicated'
(b/'fixture-final').mkdir(exist_ok=True)
args=['docker','run','--detach','--name','dtos-protections-local-completion','--init','--user','1000:1000','--memory=2g','--memory-swap=2g','--cpus=2','--network=none','--env','HOME=/tmp','--env','NODE_OPTIONS=--max-old-space-size=256','--env','DTOS_EXPECTED_HEAD='+s['candidate'],'--volume',str(source)+':/app','--volume','/workspace/dtos/.git:/workspace/dtos/.git:ro','--volume',str(b/'local-canonical')+':/output','--volume',str(b/'fixture-final')+':/fixture','--workdir','/app','dtos-canonical314:2245','python','-c',"import os,runpy; assert os.geteuid()==1000; print('Validation UID',os.geteuid(),flush=True); runpy.run_path('/output/runner.py',run_name='__main__')"]
image=json.loads(subprocess.check_output(['docker','image','inspect','dtos-canonical314:2245'],text=True))[0]
report=dict(candidate=s['candidate'],tree=s['tree'],command=args,runtime_image=image['Id'],harness_sha256=hashlib.sha256((b/'local-canonical/runner.py').read_bytes()).hexdigest(),observer_sha256=hashlib.sha256((b/'local-canonical/observer/sitecustomize.py').read_bytes()).hexdigest(),started_at=datetime.now(timezone.utc).isoformat(),state='STARTING; not validation success',method='Official canonical CLI and every gate unchanged. Local orchestration110m and bounded0.5s observer14000samples; actual2GiB/twoCPU/network-none/non-root. Terminal-detached container explicitly tracked; stopped container retained for original logs/exit inspection, then removed after verification.')
(b/'canonical-invocation.json').write_text(json.dumps(report,indent=2)+'\n')
container=subprocess.check_output(args,text=True).strip();report.update(container=container,state='RUNNING; await complete official result/10gates/4346tests, actual exit and cleanup. Startup return is not a pass.');(b/'canonical-invocation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

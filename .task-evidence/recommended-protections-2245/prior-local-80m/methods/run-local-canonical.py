from pathlib import Path
import hashlib,json,subprocess,os
b=Path('/workspace/2245-recommended-protections'); source=Path('/workspace/dtos-2245-validate-release')
s=json.loads((b/'source.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==s['candidate']
assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=source,text=True).strip()==s['tree']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True).strip()
(b/'fixture-final').mkdir(exist_ok=True)
args=['docker','run','--name','dtos-protections-final','--rm','--init','--user','1000:1000','--memory=2g','--memory-swap=2g','--cpus=2','--network=none','--env','HOME=/tmp','--env','NODE_OPTIONS=--max-old-space-size=256','--env','DTOS_EXPECTED_HEAD='+s['candidate'],'--volume',str(source)+':/app','--volume','/workspace/dtos/.git:/workspace/dtos/.git:ro','--volume',str(b/'local-canonical')+':/output','--volume',str(b/'fixture-final')+':/fixture','--workdir','/app','dtos-canonical314:2245','python','-c',"import os,runpy; assert os.geteuid()==1000; print('Validation UID',os.geteuid(),flush=True); runpy.run_path('/output/runner.py',run_name='__main__')"]
image=json.loads(subprocess.check_output(['docker','image','inspect','dtos-canonical314:2245'],text=True))[0]
(b/'canonical-invocation.json').write_text(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],command=args,runtime_image=image['Id'],harness_sha256=hashlib.sha256((b/'local-canonical/runner.py').read_bytes()).hexdigest(),observer_sha256=hashlib.sha256((b/'local-canonical/observer/sitecustomize.py').read_bytes()).hexdigest(),method='Unchanged prior accepted canonical runner/observer; unchanged canonical entry point; actual 2 GiB, non-root, 8 GiB scratch prerequisite'),indent=2)+'\n')
raise SystemExit(subprocess.run(args).returncode)

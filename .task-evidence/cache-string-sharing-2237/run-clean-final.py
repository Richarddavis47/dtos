"""Run the unchanged canonical harness as UID1000 in a fresh exact checkout."""
import json,subprocess,re,sys
from pathlib import Path
b=Path('/workspace/2237-cache-duplication');source=Path('/workspace/dtos')
cache=Path('/workspace/2223-focused314/runtime314-layer-cache-id.txt').read_text().strip();assert re.fullmatch('[a-f0-9]{64}',cache)
runtime='/var/lib/docker/vfs/dir/'+cache
im=json.loads(subprocess.check_output(['docker','image','inspect','dtos-canonical314-flat:2223'],text=True))[0]
assert im['Id']=='sha256:2c9de92bf8e05a79587f6edba94052cf614c984a5cb81a62613871388cd6533e'
assert not any(any(k in v.split('=',1)[0].upper() for k in ('TOKEN','SECRET','PASSWORD','PROXY')) for v in im['Config']['Env'])
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip();assert head=='4fb702964b34d84a593fb917b5e654b9b8ff0adf'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True).strip()
(b/'fixture-final').mkdir(exist_ok=True)
args=['docker','run','--name','dtos-cache-sharing-clean','--rm','--init','--user','1000:1000','--memory=2g','--memory-swap=2g','--cpus=2','--network=none']
for name in ['usr','bin','lib','lib64','etc','opt','var','root','run']:args+=['--mount',f'type=bind,src={runtime}/{name},dst=/{name},readonly']
for item in im['Config']['Env']:args+=['--env',item]
args+=['--env','HOME=/tmp','--env','NODE_OPTIONS=--max-old-space-size=256','--env','DTOS_EXPECTED_HEAD='+head,'--volume',str(source)+':/app','--volume','/workspace/dtos/.git:/workspace/dtos/.git:ro','--volume',str(b/'canonical')+':/output','--volume',str(b/'fixture-final')+':/fixture','--workdir','/app','dtos-canonical-runtime-mounts:2223','/usr/local/bin/python','-c',"import os,runpy; assert os.geteuid()==1000; print('Validation UID',os.geteuid(),flush=True); runpy.run_path('/output/runner.py',run_name='__main__')"]
if len(sys.argv)>1:
 args=args[:-2]+['-m','unittest',*sys.argv[1:]]
(b/'invocation-final.json').write_text(json.dumps({'candidate':head,'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=source,text=True).strip(),'runtime_image':im['Id'],'command':args,'harness':'Unchanged prior canonical harness; canonical entry point unchanged; 8GiB disk prerequisite retained; no root/elevated test process'},indent=2)+'\n')
raise SystemExit(subprocess.run(args).returncode)

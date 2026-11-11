from common import *
import subprocess,json,datetime
s=load_source();root=BASE/'anchor-probe';root.mkdir(exist_ok=False);args=docker_base(s,readonly=True)+['-v',str(root)+':/output',IMAGE_ID,'python','/evidence/anchor-probe.py'];write_json(root/'invocation.json',dict(source=s,args=args,at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
with (root/'original-console.log').open('x') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT)
assert r.returncode==0,'Supplemental original failure retained; do not edit app source speculatively'
print((root/'result.json').read_text())

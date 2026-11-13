"""Preserve C8 records, execute mandatory exactC9 controls once; stop on failures."""
from common import *
from pathlib import Path
import subprocess,time,json
S=load_source();A=BASE/'attempt-c8-hosted-copy-assertion-failure'
def run(label,args):
 assert_checkout(S)
 with (BASE/('c9-'+label+'-original.log')).open('x') as f:r=subprocess.run(args,cwd=BASE,stdout=f,stderr=subprocess.STDOUT)
 print(json.dumps(dict(phase=label,exit=r.returncode)),flush=True);assert r.returncode==0,label

def wait(n):
 r=json.loads((BASE/n).read_text())
 while True:
  d=json.loads(subprocess.check_output(['docker','inspect',r['container']],text=True))[0]
  if not d['State']['Running']:return d
  time.sleep(5)
while not (BASE/'c9-affected/result.json').exists():time.sleep(5)
r=json.loads((BASE/'c9-affected/result.json').read_text());assert r['passed'] and r['commit']==S['candidate'] and r['tests']==4
names=['visual-final','visual-final-invocation.json','visual-final-container-original.json','visual-final-verified.json','focused-exact','focused-exact-invocation.json','focused-exact-container-original.json','focused-ready.json','fixture-isolation-exact','fixture-isolation-invocation.json','fixture-isolation-ready.json','harness-contract-exact','harness-contract-exact-invocation.json','harness-contract-exact-container-original.json','harness-contract-ready.json','discovery-final','discovery-final-invocation.json','discovery-final-verified.json','canonical-harness-extraction.json','local-preflight','local-restoration-unused','local-resident-refresh','local-resource-native-archives','resource-inputs.json','resource-invocation.json','resource-native-guards.json','resource-preservation-verified.json']
for n in names:
 p=BASE/n
 if p.exists():assert not (A/n).exists();p.rename(A/n)
run('normal-start',['python','start-controls-durable.py','normal']);wait('fixture-isolation-invocation.json');run('normal-collect',['python','collect-controls-durable.py','normal'])
run('features-start',['python','start-controls-durable.py','features']);wait('focused-exact-invocation.json');run('features-collect',['python','collect-controls-durable.py','features'])
run('harness-start',['python','start-harness-contract.py']);wait('harness-contract-exact-invocation.json');run('harness-collect',['python','collect-harness-contract.py'])
run('resource',['python','run-local-resource.py'])
run('prepare',['python','prepare-canonical-harness.py'])
run('full-start',['python','start-release-canonical.py']);wait('canonical-invocation.json');run('full-collect',['python','collect-local-completion.py'])
print('Full exact-source local validation complete; hosted reconciliation and publication still required.',flush=True)

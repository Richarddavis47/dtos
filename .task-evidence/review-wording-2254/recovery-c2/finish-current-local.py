"""Finish healthy exact-source local checks once; preserve every original outcome."""
from common import *
import time,datetime
s=load_source();i=json.loads((BASE/'canonical-invocation.json').read_text());assert i['source']==s
while True:
 d=json.loads(command('docker','inspect',i['container']))[0]
 if not d['State']['Running']:break
 time.sleep(20)
def run(label,args):
 assert_checkout(s)
 with (BASE/(label+'-controller-original.log')).open('x')as f:r=subprocess.run(args,cwd=BASE,stdout=f,stderr=subprocess.STDOUT)
 print(json.dumps(dict(phase=label,exit=r.returncode,at=datetime.datetime.now(datetime.timezone.utc).isoformat())),flush=True);assert r.returncode==0,label
try:run('full-collect',['python','collect-local-completion.py'])
finally:
 if not (BASE/'closed-originals-restored.json').exists():run('closed-originals-restore',['python','preserve-closed-evidence.py','restore'])
for mode in ['normal','features']:
 run(mode+'-start',['python','start-controls-durable.py',mode]);inv='fixture-isolation-invocation.json' if mode=='normal' else 'focused-exact-invocation.json';c=json.loads((BASE/inv).read_text())['container']
 while json.loads(command('docker','inspect',c))[0]['State']['Running']:time.sleep(10)
 run(mode+'-collect',['python','collect-controls-durable.py',mode])
run('harness-start',['python','start-harness-contract.py']);c=json.loads((BASE/'harness-contract-exact-invocation.json').read_text())['container']
while json.loads(command('docker','inspect',c))[0]['State']['Running']:time.sleep(10)
run('harness-collect',['python','collect-harness-contract.py'])
for name,args in [('run-local-resource.py',[]),('run-local-capital-capture.py',[]),('run-retained-history-probe.py',[]),('run-local-history-capture.py',[]),('run-supplement-candidate-capture.py',[]),('run-extra-candidate-capture.py',['after']),('run-native-candidate-capture.py',[])]:run(name.removesuffix('.py'),['python',name]+args)
write_json(BASE/'local-and-captures-ready.json',dict(source=s,passed=True,scope='Actual completed final-source local ten-gate original plus required preservation/resource and bounded capture controls; hosted/publisher/manual review remain separate.'))

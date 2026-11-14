from common import *
import time,datetime
while not (BASE/'c14-pre-full-ready.json').exists():time.sleep(10)
S=load_source();assert json.loads((BASE/'c14-pre-full-ready.json').read_text())['source']==S
assert S['candidate']=='d812de9125fcd0971c4b521186369cdc2c72f012';assert_checkout(S)
def run(label,args):
 assert_checkout(S)
 with (BASE/('c14-'+label+'-original.log')).open('x') as f:r=subprocess.run(args,cwd=BASE,stdout=f,stderr=subprocess.STDOUT)
 print(json.dumps(dict(phase=label,exit=r.returncode,at=datetime.datetime.now(datetime.timezone.utc).isoformat())),flush=True);assert r.returncode==0,label
run('scratch-preserve',['python','preserve-final-source-scratch.py','preserve']);run('official-harness',['python','prepare-canonical-harness.py']);run('full-start',['python','start-release-canonical.py'])
i=json.loads((BASE/'canonical-invocation.json').read_text());assert i['source']==S
while True:
 d=json.loads(command('docker','inspect',i['container']))[0]
 if not d['State']['Running']:break
 time.sleep(20)
run('full-collect',['python','collect-local-completion.py']);run('scratch-restore',['python','preserve-final-source-scratch.py','restore']);original=digest(BASE/'local-canonical/manifest.json')
for name,args in [('run-local-capital-capture.py',[]),('run-retained-history-probe.py',[]),('run-local-history-capture.py',[]),('run-supplement-candidate-capture.py',[]),('run-extra-candidate-capture.py',['after']),('run-native-candidate-capture.py',[])]:
 run(name.removesuffix('.py'),['python',name]+args);assert digest(BASE/'local-canonical/manifest.json')==original
write_json(BASE/'post-full-acceptance-ready.json',dict(source=S,passed=True,original_canonical_manifest_sha256=original,scope='Completed final-source full local and separate original current fixture captures. Hosted, manual review and publisher remain required.'))
write_json(BASE/'current-final-extra-native-ready.json',dict(source=S,passed=True,scope='Actual current-source captures, not owner live, physical Safari or automatic visual PASS.'))

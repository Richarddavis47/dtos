from pathlib import Path
import time,subprocess,json,sys,datetime
b=Path('/workspace/2248-market-needs-final')
for _ in range(90):
 p=b/'local-canonical/tests.jsonl'
 if p.exists():
  rows=[json.loads(x) for x in p.read_text().splitlines()]
  assert not any(r['event'] in {'error','failure'} for r in rows),'Known canonical failure; do not launch more controls'
  break
 time.sleep(5)
else:raise RuntimeError('Canonical did not start; native launch held')
for name,log in [('run-local-resource.py','local-resource-launch-original.log'),('run-retained-history-probe.py','retained-replay-launch-original.log')]:
 with (b/log).open('x') as sink:r=subprocess.run([sys.executable,str(b/name)],stdout=sink,stderr=subprocess.STDOUT)
 assert r.returncode==0,name+' original failure retained'
print(json.dumps(dict(native_and_retained_controls_complete=True,at=datetime.datetime.now(datetime.timezone.utc).isoformat())))

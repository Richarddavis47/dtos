"""Bounded read-only progress; no restart, admission override or test mutation."""
from pathlib import Path
import json,collections,time,datetime,subprocess
BASE=Path('/workspace/2248-market-needs-final');inv=json.loads((BASE/'canonical-invocation.json').read_text());deadline=datetime.datetime.fromisoformat(inv['started_at']).timestamp()+7500
for i in range(251):
 p=BASE/'local-canonical/tests.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
 counts=dict(collections.Counter(r['event'] for r in rows))
 state=json.loads(subprocess.check_output(['docker','-H','unix:///var/run/docker.sock','inspect',inv['container']],text=True))[0]['State']
 result=BASE/'local-canonical/result.json'
 record=dict(observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),events=counts,last_test=rows[-1]['test'] if rows else None,running=state['Running'],container_exit=state['ExitCode'] if not state['Running'] else None)
 if result.exists() and not state['Running']:record['final_result']=json.loads(result.read_text())
 with (BASE/'local-watch-original.log').open('a') as out:out.write(json.dumps(record)+'\n')
 print(json.dumps(record),flush=True)
 if not state['Running']:break
 if time.time()>deadline:raise RuntimeError('Bounded watch expired; not validation success')
 time.sleep(30)

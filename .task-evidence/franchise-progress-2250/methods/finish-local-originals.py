"""Bounded observer: preserves failures, collects only verified successful originals."""
import datetime,json,subprocess,time,fcntl
from pathlib import Path
B=Path(__file__).resolve().parent
lock=(B/'local-completion.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
s=json.loads((B/'source.json').read_text());inv=json.loads((B/'canonical-invocation.json').read_text());container=inv['container'];started=time.monotonic();limit=170*60
status=dict(source=s,state='WAITING_FOR_ORIGINAL_LOCAL_RESULT',observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
def write():
 status['observed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();(B/'local-completion-observer.json').write_text(json.dumps(status,indent=2)+'\n')
write()
while True:
 record=json.loads(subprocess.check_output(['docker','inspect',container],text=True))[0];state=record['State']
 if not state['Running']:
  break
 assert time.monotonic()-started<limit,'Bounded observer elapsed; do not terminate/relabel actual test work'
 time.sleep(5)
status.update(state='ORIGINAL_CONTAINER_EXITED',exit_code=state['ExitCode'],oom_killed=state['OOMKilled']);write()
assert state['ExitCode']==0 and not state['OOMKilled'] and state['Pid']==0,'Failed/incomplete original remains held; no cleanup or release'
r=json.loads((B/'local-canonical/result.json').read_text());assert r['head']==s['candidate'] and r['tree']==s['tree'] and r['passed'] and r['exit_code']==0,'Original source/result mismatch; hold'
for script,log in [('collect-local-completion.py','collect-local-completion-original.log'),('run-retained-history-probe.py','retained-history-probe-launch-original.log'),('run-local-capital-capture.py','local-capital-capture-launch-original.log')]:
 status.update(state='COLLECTING_'+script);write()
 with (B/log).open('xb') as sink:subprocess.run(['python',str(B/script)],stdout=sink,stderr=subprocess.STDOUT,check=True)
status.update(state='LOCAL_ORIGINALS_AND_REQUIRED_SUPPLEMENTAL_CAPTURES_VERIFIED');write()
print('Exact-source full local originals, ten gates, process cleanup and separately labelled supplemental captures verified. Release is still separately guarded.')

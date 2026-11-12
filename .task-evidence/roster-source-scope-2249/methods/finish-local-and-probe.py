"""Finish only an actual successful local run; never merge/publish from a waiter."""
from pathlib import Path
import json,time,subprocess,datetime,fcntl
B=Path('/workspace/2249-sleeper-relevance');lock=(B/'local-completion.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
s=json.loads((B/'source.json').read_text());status=dict(source=s,state='WAITING_FOR_FULL_RESULT',started_at=datetime.datetime.now(datetime.timezone.utc).isoformat());(B/'local-completion-waiter.json').write_text(json.dumps(status,indent=2)+'\n')
while not (B/'local-canonical/result.json').exists():time.sleep(3)
r=json.loads((B/'local-canonical/result.json').read_text());assert r['head']==s['candidate'] and r['tree']==s['tree'] and r['passed'] and r['exit_code']==0,'Original mandatory local result failed/incomplete; preserve andhold'
# The manifest and process may finish just after result.json is sealed.
while True:
 c=json.loads((B/'canonical-invocation.json').read_text())['container'];x=json.loads(subprocess.check_output(['docker','inspect',c],text=True))[0]
 if not x['State']['Running']:break
 time.sleep(2)
assert x['State']['Pid']==0 and x['State']['ExitCode']==0
assert not (B/'local-container-cleanup.json').exists()
with (B/'collect-local-completion-original.log').open('xb') as sink:subprocess.run(['python',str(B/'collect-local-completion.py')],stdout=sink,stderr=subprocess.STDOUT,check=True)
with (B/'retained-history-probe-launch-original.log').open('xb') as sink:subprocess.run(['python',str(B/'run-retained-history-probe.py')],stdout=sink,stderr=subprocess.STDOUT,check=True)
status.update(state='LOCAL_GATES_AND_REQUIRED_PROBE_VERIFIED',finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat());(B/'local-completion-waiter.json').write_text(json.dumps(status,indent=2)+'\n');print('Actual local4419/ten gates, originalmanifest, cleanup and existingnativefeature recorder completed. Release remains separately guarded.')

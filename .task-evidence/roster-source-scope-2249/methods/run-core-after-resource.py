from pathlib import Path
import json,time,subprocess,os
b=Path('/workspace/2249-sleeper-relevance')
while True:
 p=b/'resource-invocation.json'
 if p.exists():
  r=json.loads(p.read_text())
  if r.get('completed_at'):
   assert r.get('passed'),r.get('failure');break
 time.sleep(2)
s=json.loads((b/'source.json').read_text())
args=['docker','run','--rm','--init','--user','1000:1000','--memory=2g','--memory-swap=2g','--cpus=2','--network=none','-v','/workspace/dtos-sleeper-relevance-2249:/app:ro','-v','/workspace/dtos/.git:/workspace/dtos/.git:ro','-v',str(b/'focused-core-runner.py')+':/runner.py:ro','-v',str(b/'focused-core')+':/output','-e','HOME=/tmp','-e','NODE_OPTIONS=--max-old-space-size=256','-e','GIT_CONFIG_COUNT=1','-e','GIT_CONFIG_KEY_0=safe.directory','-e','GIT_CONFIG_VALUE_0=/app','-e','DTOS_EXPECTED_HEAD='+s['candidate'],'-e','DTOS_EXPECTED_TREE='+s['tree'],'-w','/app','sha256:f70a0c6402700dfb954c99d8163d4164926f74435c34d2e7e462407151663ae6','python','/runner.py','tests.test_dynamic_needs','tests.test_roster_diagnostic_http','tests.test_team_trade_need','tests.test_roster_diagnostic_browser','tests.test_roster_diagnostic_aging_browser','tests.test_trade_projection_freshness']
(b/'focused-core-invocation.json').write_text(json.dumps(dict(source=s,args=args),indent=2)+'\n')
with (b/'focused-core/original-console.log').open('xb') as f:rc=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT).returncode
r=json.loads((b/'focused-core/result.json').read_text());assert rc==0 and r['passed'] and not r['dirty'];assert r['commit']==s['candidate'] and r['tree']==s['tree'];(b/'focused-core-ready.json').write_text(json.dumps(r,indent=2)+'\n')

"""Wait only for the already-running native controls, then launch the official full gate."""
import json,time,subprocess
from pathlib import Path
b=Path('/workspace/2249-sleeper-relevance')
while True:
 p=b/'resource-invocation.json'
 if p.exists():
  r=json.loads(p.read_text())
  if r.get('completed_at'):
   assert r.get('passed') and not r.get('failure'),r.get('failure')
   break
 time.sleep(2)
subprocess.run(['python',str(b/'start-release-canonical.py')],check=True)

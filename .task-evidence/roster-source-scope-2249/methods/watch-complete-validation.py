"""Bounded local progress watcher. It observes existing work and never retries tests."""
from pathlib import Path
import json,time,collections,datetime,subprocess
B=Path('/workspace/2249-sleeper-relevance')
for _ in range(240):
 p=B/'local-canonical/tests.jsonl';rows=[]
 for line in p.read_text().splitlines():
  try:rows.append(json.loads(line))
  except json.JSONDecodeError:pass
 counts=collections.Counter(x['event'] for x in rows)
 data=dict(observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),local_events=dict(counts),latest=rows[-1].get('test') if rows else None,local_finished=(B/'local-canonical/result.json').exists())
 if data['local_finished']:data['local_result']=json.loads((B/'local-canonical/result.json').read_text());print(json.dumps(data),flush=True);break
 print(json.dumps(data),flush=True)
 time.sleep(30)

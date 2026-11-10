from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import json,time,sys
b=Path('/workspace/2245-recommended-protections');c=b/'local-canonical'
if '--wait' in sys.argv:
 for _ in range(11):
  if (c/'result.json').exists():break
  time.sleep(5)
rows=[]
for line in (c/'tests.jsonl').read_text().splitlines():
 try:rows.append(json.loads(line))
 except json.JSONDecodeError:pass # Only a concurrent progress sample; final verifier is strict.
counts=dict(Counter(r['event'] for r in rows));trace=[]
if (c/'canonical-trace.jsonl').exists():
 for line in (c/'canonical-trace.jsonl').read_text().splitlines():
  try:trace.append(json.loads(line))
  except json.JSONDecodeError:pass
r=dict(observed_at=datetime.now(timezone.utc).isoformat(),counts=counts,latest_test=rows[-1]['test'],completed_gates=sum(x.get('event')=='validation_child_completed' for x in trace),result_present=(c/'result.json').exists())
if r['result_present']:r['result']=json.loads((c/'result.json').read_text())
p=b/'WORK_STATUS.json';s=json.loads(p.read_text());s['observed_at']=r['observed_at'];s['local_events']=counts;s['local_full_status']='Final original result is present; requires exact-source/counter/manifest/gate/exit verification' if r['result_present'] else 'RUNNING; no pass claim, same original source/official CLI under2GiB';p.write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(r))

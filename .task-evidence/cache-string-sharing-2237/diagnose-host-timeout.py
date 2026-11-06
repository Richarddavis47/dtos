from pathlib import Path
import json,statistics,collections,zipfile
b=Path('/workspace/2237-cache-duplication')
def parse(path):
 rows=[]
 for line in path.read_text().splitlines():
  try:rows.append(json.loads(line))
  except json.JSONDecodeError:pass
 starts={};dur={}
 for r in rows:
  if r['event']=='start':starts[r['test']]=r
  if r['event']=='stop' and r['test'] in starts:dur[r['test']]=r['time']-starts[r['test']]['time']
 return rows,starts,dur
local,ls,ld=parse(b/'canonical/tests.jsonl');host,hs,hd=parse(b/'host-failed-4fb-attempt1/tests.jsonl')
counts=collections.Counter(r['event'] for r in host);matched=[dict(test=t,local_seconds=ld[t],host_seconds=d,ratio=d/ld[t],delta=d-ld[t]) for t,d in hd.items() if t in ld and ld[t]>.001]
long=[r for r in matched if r['local_seconds']>=.2];notstopped=[t for t in hs if t not in hd]
fail=[r for r in host if r['event'] in ['failure','error','skip']]
trace=[json.loads(r) for r in (b/'host-failed-4fb-attempt1/canonical-trace.jsonl').read_text().splitlines()]
with zipfile.ZipFile(b/'canonical-4fb-attempt1-failed-original.zip') as z:
 first=json.loads(z.read('memory.jsonl').splitlines()[0]);environment=z.read('environment.txt').decode();state=json.loads(z.read('container-state.json'))
result=dict(candidate='4fb702964b34d84a593fb917b5e654b9b8ff0adf',tree='4051883efb1f225dcd71e07f1998e45c9d96fb39',failure='4200s whole-validator deadline; not an OOM',host_events=dict(counts),failures=fail,incomplete=notstopped,matched=len(matched),matched_local_seconds=sum(r['local_seconds'] for r in matched),matched_host_seconds=sum(r['host_seconds'] for r in matched),median_ratio_over_200ms=statistics.median(r['ratio'] for r in long),largest_deltas=sorted(matched,key=lambda r:r['delta'],reverse=True)[:30],completed_gates=[r for r in trace if r['event']=='validation_child_completed'],memory_fields=list(first),environment=environment,container_state=state,limitation='Per-test wall-time comparison establishes slower execution, not a CPU-frequency or hypervisor root cause. No completed full hosted regression or unexecuted gates are claimed.')
(b/'host-timeout-diagnosis.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['host_events','incomplete','matched_local_seconds','matched_host_seconds','median_ratio_over_200ms','largest_deltas']},indent=2))

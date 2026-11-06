"""Complete synthetic JSON equivalence, separately from lifecycle peak capture."""
import gc,hashlib,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,'/app')
from src.platform.cache_json import load_cache_json
from src.platform.cache_restoration_admission import restoration_admission
from src.platform.fois_admission import WORKING_RESERVE_BYTES,SAFETY_MARGIN_BYTES
from src.platform.lifecycle import memory_snapshot
b=Path('/evidence');m=json.loads((b/'source.json').read_text());assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==m['candidate'];rows=[]
assert memory_snapshot()['cgroup_limit_bytes']==2147483648
assert Path('/sys/fs/cgroup/memory.swap.max').read_text().strip()=='0'
def digest(v):
 h=hashlib.sha256()
 for part in json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=False).iterencode(v):h.update(part.encode())
 return h.hexdigest()
for name in ['oneqb','superflex']:
 path=b/'fixture'/(name+'.json');before=path.stat();values=[];plans=[]
 for decode in [json.load,load_cache_json]:
  plan=restoration_admission(before.st_size,memory_snapshot(),False,fois_working_bytes=WORKING_RESERVE_BYTES,fois_safety_bytes=SAFETY_MARGIN_BYTES);assert plan['would_admit'];plans.append(plan)
  with path.open() as handle:values.append(decode(handle))
 assert values[0]==values[1]
 digests=[digest(v) for v in values];assert digests[0]==digests[1]
 assert path.stat().st_size==before.st_size and path.stat().st_mtime_ns==before.st_mtime_ns
 rows.append(dict(fixture=name,bytes=before.st_size,all_payload_values_equal=True,semantic_digest=digests[0],source_file_unchanged=True,admission_plans=plans))
 del values;gc.collect()
assert not memory_snapshot()['cgroup_memory_events']['oom_kill']
result=dict(candidate=m['candidate'],tree=m['tree'],passed=True,scope='All serialized synthetic source, identity, scoring, projection, pick, valuation and consumer fields; no production data. Separate equivalence measurement, not added to lifecycle peak.',rows=rows,final_memory=memory_snapshot())
(b/'complete-payload-verified.json').write_text(json.dumps(result,indent=2)+'\n');print('Both full payloads are value-exact; full 16x admission checked before each decode; source files unchanged.')

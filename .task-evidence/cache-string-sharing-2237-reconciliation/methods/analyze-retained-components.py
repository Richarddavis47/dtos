"""Post-lifecycle structural opportunity bounds only; not a restore peak."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,'/app')
from src.platform.cache_json import load_cache_json
from src.platform.lifecycle import memory_snapshot
b=Path('/evidence');assert memory_snapshot()['cgroup_limit_bytes']==2147483648
with (b/'fixture/oneqb.json').open(encoding='utf8') as f:data=load_cache_json(f)['data']
def size(v,seen):
 i=id(v)
 if i in seen:return 0
 seen.add(i);n=sys.getsizeof(v)
 if isinstance(v,dict):n+=sum(size(k,seen)+size(x,seen) for k,x in v.items())
 elif isinstance(v,(list,tuple)):n+=sum(size(x,seen) for x in v)
 return n

def groups(rows):
 pool={};shared={};count={}
 for key,value in rows.items():
  canonical=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
  if canonical not in pool:pool[canonical]=value
  shared[key]=pool[canonical];count[canonical]=count.get(canonical,0)+1
 before=size(rows,set());after=size(shared,set());assert json.dumps(rows,sort_keys=True)==json.dumps(shared,sort_keys=True)
 return {'rows':len(rows),'distinct_value_groups':len(pool),'largest_equal_group':max(count.values(),default=0),'standalone_graph_before':before,'alias_graph_lower_bound':after,'hypothetical_bytes_saved':before-after,'caveat':'Hypothetical identical-content alias graph only,not a safe production mutation contract,measured RSS or full-lifecycle peak saving.'}
production=data['canonical_player_production'];disclosures={k:v['canonical_production'] for k,v in data['valuation_intelligence']['assets'].items()}
result={'fixture_sha256':hashlib.file_digest((b/'fixture/oneqb.json').open('rb'),'sha256').hexdigest(),'prepared_rows':groups(production['players']),'disclosures':groups(disclosures),'serialized_components':{k:len(json.dumps(data[k],separators=(',',':'),ensure_ascii=False).encode()) for k in ['players','normalized_players','season_matchups','canonical_player_production','valuation_intelligence']},'derived_actuals_serialized':len(json.dumps(production['sleeper_actuals'],separators=(',',':'),ensure_ascii=False).encode()),'disclosure_serialized':len(json.dumps(disclosures,separators=(',',':'),ensure_ascii=False).encode()),'production_changes':False,'limitations':['All rows fictional; no privateGranite payload.','Complete content-equality confirms duplicate structure but does not authorize shared mutable aliases.','Fresh missing reference-analysis template is explicitly shared immutable-by-contract; retained per-asset disclosures currently use independent asdict containers.','Nested standalone graph/serialized figures overlap. No derived data is removed from an admission basis.']}
(b/'reconciliation/retained-component-opportunities.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

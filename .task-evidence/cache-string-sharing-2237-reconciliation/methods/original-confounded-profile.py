"""Matched producer-derived cache lifecycle; no private production payload or mocked admission."""
import argparse,asyncio,gc,hashlib,json,logging,os,sys,tempfile,threading,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/app')
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['plain','strings','strings-wide','strings-short','shallow','shared-short','stream','both','candidate'],required=True);p.add_argument('--fixture',default='oneqb');p.add_argument('--output-label');p.add_argument('--owned-cache',action='store_true');p.add_argument('--league-id');a=p.parse_args();b=Path('/evidence');root=b/'fixture'
for key in ['CACHE','METADATA_DB','INTELLIGENCE_CHECKPOINT','FOIS_DB','HISTORY_DB','ACCOUNT_DB']:os.environ['DTOS_'+key+'_FILE']=str(root/(key.lower()+'.sqlite3'))
os.environ.update(DTOS_PROJECTION_DB_FILE=str(root/'projections.sqlite3'),DTOS_DURABLE_HISTORY_REQUIRED='0',SLEEPER_BASE_URL='http://127.0.0.1:9/v1',DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root/'seasons'))
import dtos_app,psutil
from services import league_preparation as prep
from src.core.league_runtime import LeagueRuntime
from src.platform.lifecycle import memory_snapshot,lifecycle_coordinator
from src.platform.memory_reclamation import release_unused_allocator_pages
from src.core.valuation_intelligence import engine
logging.disable(logging.CRITICAL)
assert memory_snapshot()['cgroup_limit_bytes']==2147483648 and Path('/sys/fs/cgroup/memory.swap.max').read_text().strip()=='0'
path=root/(a.fixture+'.json');owned=None
if a.owned_cache:
 import shutil
 owned=tempfile.TemporaryDirectory(prefix='cache-owned-profile-');target=Path(owned.name)/'cache.json'
 with path.open('rb') as reader,target.open('wb') as writer:
  shutil.copyfileobj(reader,writer,1024*1024);writer.flush();os.fsync(writer.fileno())
 path=target
original_load=json.load;original_cache_load=getattr(prep,'load_cache_json',None);original_bind=__import__('services.player_evidence',fromlist=['bind_retained_actuals']).bind_retained_actuals
stages=[];samples=[];stop=threading.Event();pool_stats=[]
def sample(label):
 stat=dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines());r=dict(label=label,monotonic=time.monotonic(),file_bytes=int(stat['file']),kernel_bytes=int(stat['kernel']),**memory_snapshot());stages.append(r);return r
def watch():
 while not stop.wait(.005):samples.append(memory_snapshot()['cgroup_current_bytes'])
def pooled(handle,*args,**kwargs):
 pool={};cost=0;hits=0
 def intern(s):
  nonlocal cost,hits
  if not 1<len(s)<=(128 if a.mode in ('strings-short','shared-short') else 1024):return s
  old=pool.get(s)
  if old is not None:hits+=1;return old
  if len(pool)<(65536 if a.mode in ('strings-wide','strings-short','shared-short') else 16384) and cost+len(s)*4<=(16777216 if a.mode in ('strings-wide','strings-short','shared-short') else 2097152):pool[s]=s;cost+=len(s)*4
  return s
 def strings(value):
  if isinstance(value,str):return intern(value)
  if isinstance(value,list):
   for i,v in enumerate(value):
    if isinstance(v,str):value[i]=intern(v)
    elif isinstance(v,list):strings(v)
  return value
 def hook(obj):
  for k,v in obj.items():obj[k]=strings(v)
  return obj
 result=original_load(handle,*args,object_hook=hook,**kwargs);pool_stats.append(dict(hits=hits,entries=len(pool),character_upper_bytes=cost));return result

def load(*args,**kwargs):
 sample('before_decode');decoder=original_cache_load if a.mode=='candidate' else pooled if a.mode in ('strings','strings-wide','strings-short','shared-short','both') else original_load
 value=decoder(*args,**kwargs);sample('after_decode');return value

def disclosure(value):
 from dataclasses import fields,asdict
 from src.core.player_value_projection.models import ProductionContext
 if not isinstance(value,ProductionContext):return asdict(value)
 return {field.name: tuple(asdict(window) for window in value.windows) if field.name=='windows' else getattr(value,field.name) for field in fields(value)}

def bind(*args,**kwargs):
 sample('before_actuals_binding')
 if a.mode in ('shallow','shared-short'):
  with patch('services.player_evidence.asdict',side_effect=disclosure):r=original_bind(*args,**kwargs)
 else:r=original_bind(*args,**kwargs)
 sample('after_actuals_binding');return r

def stream(value):
 normalized=engine.canonical_semantic_value(value);h=hashlib.sha256();encoder=json.JSONEncoder(sort_keys=True,separators=(',',':'),default=str)
 for chunk in encoder.iterencode(normalized):h.update(chunk.encode('utf8'))
 return h.hexdigest()

def publish(runtime):
 sample('after_materialization');projection=dtos_app.ProjectionService(league_id=runtime.league_id,scoring_profile_id=runtime.scoring_profile);projection.restore_into(runtime.state['data']);sample('after_projection_restore');dtos_app._publish_runtime_context(runtime,projection);sample('after_canonical_publication')
# Identity comes from documented synthetic fixture metadata, not a production read.
league_id=a.league_id or ('oneqb-rich' if a.fixture=='oneqb' else 'superflex-rich');runtime=LeagueRuntime(league_id)
gc.collect();release_unused_allocator_pages();before=sample('before_restore');start_peak=int(Path('/sys/fs/cgroup/memory.peak').read_text());thread=threading.Thread(target=watch);thread.start();started=time.monotonic()
try:
 with patch.object(prep,'league_cache_file',return_value=path),patch.object(prep if original_cache_load else prep.json,'load_cache_json' if original_cache_load else 'load',side_effect=load),patch('services.player_evidence.bind_retained_actuals',side_effect=bind):
  if a.mode in ('stream','both','candidate'):
   with patch.object(engine,'_semantic_digest',side_effect=stream):success=prep.restore_cached_runtime(runtime,publish,expected_season=2026)
  else:success=prep.restore_cached_runtime(runtime,publish,expected_season=2026)
 assert success
finally:stop.set();thread.join()
retained=sample('retained_after_publication');operation_peak=int(Path('/sys/fs/cgroup/memory.peak').read_text());seconds=time.monotonic()-started
# Exact score/provenance value digest after peak capture; this is a separate verification allocation.
source=runtime.state['data'];facts={k:source.get(k) for k in ['season_matchups','canonical_player_production']};facts['disclosures']={k:v.get('canonical_production') for k,v in source['valuation_intelligence']['assets'].items()};h=hashlib.sha256()
for chunk in json.JSONEncoder(sort_keys=True,separators=(',',':'),default=str).iterencode(facts):h.update(chunk.encode())
# Uniquely owned graph accounting, separate from the measured operation's peak.
def size(o,seen):
 i=id(o)
 if i in seen:return 0
 seen.add(i);n=sys.getsizeof(o)
 if isinstance(o,dict):n+=sum(size(k,seen)+size(v,seen) for k,v in o.items())
 elif isinstance(o,(list,tuple)):n+=sum(size(v,seen) for v in o)
 return n
components={k:size(source.get(k),set()) for k in ['players','normalized_players','season_matchups','canonical_player_production','valuation_intelligence']};components['sleeper_actuals']=size(source['canonical_player_production']['sleeper_actuals'],set());components['consumer_disclosures']=size(facts['disclosures'],set());total=size(source,set());del facts,source
asyncio.run(runtime.close());del runtime;gc.collect();release_unused_allocator_pages();after=sample('after_close_harness_gc_trim')
result=dict(mode=a.mode,owned_retained_file=a.owned_cache,cache_file_page_scope=('Exact raw fixture copied streaming and fsynced inside this container before initial sample, no cache clearing. Initial and peak raw cgroup include its charged file pages.' if owned else 'Existing bind-mounted fixture; cached file-page ownership may be outside this child cgroup. Actual file/anon counters are reported.'),decode_control=('Standard JSON loader substituted only in this disposable matched control; all admission/binding/publication code and input remain unchanged.' if a.mode=='plain' and original_cache_load else 'Unmodified selected source decoder'),fixture=a.fixture,source_head=__import__('subprocess').check_output(['git','rev-parse','HEAD'],text=True).strip(),source_tree=__import__('subprocess').check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),working_tree_clean=not __import__('subprocess').check_output(['git','status','--porcelain'],text=True).strip(),cache_bytes=path.stat().st_size,cache_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),enforced_limit=2147483648,swap_limit=0,python=sys.version,prior_kernel_peak_bytes=start_peak,operation_kernel_peak_bytes=operation_peak,operation_established_new_peak=operation_peak>start_peak,operation_kernel_peak_increment=operation_peak-before['cgroup_current_bytes'],passed=True,seconds=seconds,stages=stages,sampled_peak=max(samples+[r['cgroup_current_bytes'] for r in stages[:-1]]),sampled_peak_increment=max(samples+[r['cgroup_current_bytes'] for r in stages[:-1]])-before['cgroup_current_bytes'],retained_increment=retained['cgroup_current_bytes']-before['cgroup_current_bytes'],component_owned_graph_bytes=components,union_graph_bytes=total,exact_actuals_and_disclosures_digest=h.hexdigest(),pool_stats=pool_stats,limitations=['New synthetic producer-derived991asset cohort, not private Granite. No measured production attribution.','5ms samples can miss brief peaks; kernel lifetime includes imports and separate graph/verification instrumentation.','sys.getsizeof graph accounting happens after operation capture and is not RSS. Component graphs overlap; do not add them.','GC/allocator trim after close is disclosed harness cleanup, not a new production behavior.'],kernel_lifetime_peak=int(Path('/sys/fs/cgroup/memory.peak').read_text()),children_after=[p.pid for p in psutil.Process().children(recursive=True)],lifecycle=lifecycle_coordinator.snapshot()['phase'])
if owned:
 owned.cleanup();result['owned_cache_scratch_removed']=not Path(owned.name).exists()
(b/('profile-'+a.fixture+'-'+(a.output_label or a.mode)+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['mode','cache_bytes','seconds','operation_kernel_peak_increment','sampled_peak_increment','retained_increment','union_graph_bytes','pool_stats','exact_actuals_and_disclosures_digest']}))

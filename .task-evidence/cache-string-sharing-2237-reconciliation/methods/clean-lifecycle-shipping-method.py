"""No graph/digest instrumentation before measuring actual runtime cleanup."""
import argparse,asyncio,gc,hashlib,json,logging,os,subprocess,sys,tempfile,time,weakref
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/app');p=argparse.ArgumentParser();p.add_argument('--decoder',choices=['standard','shipping'],required=True);p.add_argument('--pressure',action='store_true');a=p.parse_args();b=Path('/evidence');root=b/'fixture'
for key in ['CACHE','METADATA_DB','INTELLIGENCE_CHECKPOINT','FOIS_DB','HISTORY_DB','ACCOUNT_DB']:os.environ['DTOS_'+key+'_FILE']=str(root/(key.lower()+'.sqlite3'))
os.environ.update(DTOS_PROJECTION_DB_FILE=str(root/'projections.sqlite3'),DTOS_DURABLE_HISTORY_REQUIRED='0',SLEEPER_BASE_URL='http://127.0.0.1:9/v1',DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root/'seasons'))
import dtos_app,psutil
from services import league_preparation as prep
from src.core.league_runtime import LeagueRuntime
from src.platform.lifecycle import memory_snapshot,lifecycle_coordinator,HeavyWorkDeferred
from src.platform.memory_reclamation import release_unused_allocator_pages
logging.disable(logging.CRITICAL);assert memory_snapshot()['cgroup_limit_bytes']==2147483648 and Path('/sys/fs/cgroup/memory.swap.max').read_text().strip()=='0'
original_decoder=prep.load_cache_json;decoder=json.load if a.decoder=='standard' else original_decoder;stages=[];cycles=[];pressure=[]
def sample(label):
 s=dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines());x=dict(label=label,**memory_snapshot(),anon=int(s['anon']),file=int(s['file']),inactive_file=int(s['inactive_file']),peak=int(Path('/sys/fs/cgroup/memory.peak').read_text()));stages.append(x);return x

def publish(r):
 service=dtos_app.ProjectionService(league_id=r.league_id,scoring_profile_id=r.scoring_profile);service.restore_into(r.state['data']);dtos_app._publish_runtime_context(r,service)

def restore(name):
 r=LeagueRuntime(name+'-rich');t=time.monotonic()
 with patch.object(prep,'league_cache_file',return_value=paths[name]),patch.object(prep,'load_cache_json',decoder):assert prep.restore_cached_runtime(r,publish,expected_season=2026)
 assert r.state['data']['canonical_player_production']['sleeper_actuals']['source_generation']==r.state['data']['season_matchups']['semantic_generation']
 return r,time.monotonic()-t

def close(r):
 lid=r.league_id;assert r.active_requests==0 and not r.pinned and not r.background_tasks
 asyncio.run(r.close());assert lid not in dtos_app.canonical_history_store._current

with tempfile.TemporaryDirectory(prefix='clean-lifecycle-') as d:
 import shutil
 paths={}
 for name in ['oneqb','superflex']:
  path=Path(d)/(name+'.json')
  with (root/(name+'.json')).open('rb') as r,path.open('wb') as w:shutil.copyfileobj(r,w,1024*1024);w.flush();os.fsync(w.fileno())
  paths[name]=path
 gc.collect();release_unused_allocator_pages();initial=sample('initial_owned_file_pages');sf,_=restore('superflex');sample('one_warm')
 if a.pressure:
  cache_bytes=paths['oneqb'].stat().st_size
  plan=prep.restoration_admission(cache_bytes,memory_snapshot(),False,fois_working_bytes=prep.FOIS_WORKING,fois_safety_bytes=prep.FOIS_SAFETY,expansion_factor=prep.CACHE_EXPANSION_FACTOR,minimum_working_bytes=prep.CACHE_MINIMUM_WORKING,cache_safety_bytes=prep.CACHE_SAFETY,service_limit_bytes=prep.SERVICE_LIMIT)
  required=plan['required_bytes']
  target=2147483648-required+32*1024**2
  while memory_snapshot()['cgroup_current_bytes']<target:
   assert memory_snapshot()['cgroup_current_bytes']<2147483648-512*1024**2
   chunk=bytearray(8*1024**2)
   for offset in range(0,len(chunk),4096):chunk[offset]=1
   pressure.append(chunk)
  del chunk
  before=sample('constrained_before_restore');candidate=LeagueRuntime('oneqb-rich');deferred=False
  try:
   with patch.object(prep,'league_cache_file',return_value=paths['oneqb']),patch.object(prep,'load_cache_json',decoder):prep.restore_cached_runtime(candidate,publish,expected_season=2026)
  except HeavyWorkDeferred:deferred=True
  assert deferred and not candidate.state['data'];del candidate
  sample('correctly_deferred_without_competitor');ref=weakref.ref(sf);close(sf);del sf;gc.collect();release_unused_allocator_pages();assert ref() is None
  after=sample('fixture_owner_released_idle_runtime');qb,seconds=restore('oneqb');sample('same_pressure_completed_after_release');close(qb);del qb;gc.collect();release_unused_allocator_pages();pressure.clear();gc.collect();release_unused_allocator_pages();sample('pressure_removed')
  cases=dict(deferred_before_release=True,completed_after_release=True,seconds=seconds,required_capacity=required,raw_usage_released=before['cgroup_current_bytes']-after['cgroup_current_bytes'],scope='Disposable explicit owner close of known idle unpinned runtime only; no application eviction policy change or assertion that production has such a victim.')
 else:
  refs=[]
  for i in range(3):
   qb,seconds=restore('oneqb');warm=sample('two_warm_'+str(i));refs.append(weakref.ref(qb));close(qb);del qb;immediate=sample('closed_before_gc_trim_'+str(i));gc.collect();release_unused_allocator_pages();clean=sample('closed_after_harness_gc_trim_'+str(i));assert refs[-1]() is None;cycles.append(dict(index=i,seconds=seconds,warm_bytes=warm['cgroup_current_bytes'],after_close_bytes=immediate['cgroup_current_bytes'],after_gc_trim_bytes=clean['cgroup_current_bytes']))
  close(sf);del sf;gc.collect();release_unused_allocator_pages();sample('all_owned_runtimes_closed');cases=dict(cycles=cycles,scope='Actual source close protocols; GC/allocator trim separately identified as harness actions.')
 assert not psutil.Process().children(recursive=True) and lifecycle_coordinator.snapshot()['phase']=='idle'
 assert not dtos_app.canonical_history_store._current
 assert all(x['cgroup_memory_events']['oom']==x['cgroup_memory_events']['oom_kill']==0 for x in stages)
 sample('before_scratch_unlink')
sample('after_scratch_unlink');assert not Path(d).exists()
report=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),decoder=a.decoder,pressure=a.pressure,passed=True,initial=initial,stages=stages,cases=cases,public_identity_count_retained=len(dtos_app.canonical_history_store._identities),children_after=[],scratch_removed=True,scope='Exact shipping source and unmodified digest/binding/guards. No graph analysis or full JSON digest during lifecycle measurement. Synthetic only,not Granite. No active-context eviction,source acquisition or source changes.')
(b/'reconciliation'/('clean-'+a.decoder+('-pressure' if a.pressure else '')+'.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['decoder','pressure','passed','cases','public_identity_count_retained']}))

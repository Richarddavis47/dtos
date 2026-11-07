"""Only completed-refresh-task ownership varies; full real restore/publication."""
import argparse,asyncio,gc,hashlib,inspect,json,logging,os,psutil,subprocess,sys,tempfile,time,weakref
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,'/app');p=argparse.ArgumentParser();p.add_argument('--mode',choices=['control','shipping'],required=True);p.add_argument('--failed-worker',action='store_true');p.add_argument('--reader',action='store_true');p.add_argument('--repeat',type=int,default=1);a=p.parse_args();b=Path('/evidence');out=b/'runtime-retention';root=b/'fixture'
for key in ['CACHE','METADATA_DB','INTELLIGENCE_CHECKPOINT','FOIS_DB','HISTORY_DB','ACCOUNT_DB']:os.environ['DTOS_'+key+'_FILE']=str(root/(key.lower()+'.sqlite3'))
os.environ.update(DTOS_PROJECTION_DB_FILE=str(root/'projections.sqlite3'),DTOS_DURABLE_HISTORY_REQUIRED='0',SLEEPER_BASE_URL='http://127.0.0.1:9/v1',DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root/'seasons'))
import dtos_app
from services import league_preparation as prep,league_maintenance as maintenance
from src.core.league_runtime import LeagueRuntime,RuntimeState
from src.platform.lifecycle import memory_snapshot,lifecycle_coordinator
from src.platform.memory_reclamation import release_unused_allocator_pages
logging.disable(logging.CRITICAL);assert memory_snapshot()['cgroup_limit_bytes']==2147483648 and Path('/sys/fs/cgroup/memory.swap.max').read_text().strip()=='0'
original=inspect.getsource(maintenance.ensure_periodic_refresh)
if a.mode=='control':
 proposed=(out/'baseline-periodic-refresh.py').read_text()
 namespace={};exec(compile(proposed,'<verified-baseline-refresh-control>','exec'),maintenance.__dict__,namespace);maintenance.ensure_periodic_refresh=namespace['ensure_periodic_refresh']
else:proposed=original
stages=[]
def sample(label):
 stat=dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines());x=dict(label=label,**memory_snapshot(),anon=int(stat['anon']),file=int(stat['file']),inactive_file=int(stat['inactive_file']),kernel_peak=int(Path('/sys/fs/cgroup/memory.peak').read_text()));stages.append(x);return x
class Publication(dict):pass

def publish(r):
 if not isinstance(r.state['data'],Publication):r.apply_data(Publication(r.state['data']))
 service=dtos_app.ProjectionService(league_id=r.league_id,scoring_profile_id=r.scoring_profile);service.restore_into(r.state['data']);dtos_app._publish_runtime_context(r,service)

def facts(r):
 d=r.state['data'];h=hashlib.sha256()
 for chunk in json.JSONEncoder(sort_keys=True,separators=(',',':'),default=str).iterencode({'matchups':d['season_matchups'],'production':d['canonical_player_production'],'disclosures':{k:v['canonical_production'] for k,v in d['valuation_intelligence']['assets'].items()}}):h.update(chunk.encode())
 return h.hexdigest()

async def main():
 import shutil
 with tempfile.TemporaryDirectory(prefix='retention-lifecycle-') as directory:
  paths=[]
  for n,src in enumerate([root/'oneqb.json',out/'next-publication.json']):
   target=Path(directory)/str(n)
   with src.open('rb') as r,target.open('wb') as w:shutil.copyfileobj(r,w,1024*1024);w.flush();os.fsync(w.fileno())
   paths.append(target)
  gc.collect();release_unused_allocator_pages();initial=sample('initial');runtime=LeagueRuntime('oneqb-rich',status=RuntimeState.WARM)
  def restore(path):
   with patch.object(prep,'league_cache_file',return_value=path):assert prep.restore_cached_runtime(runtime,publish,expected_season=2026)
  t=time.monotonic();restore(paths[0]);sample('first_publication');ref=weakref.ref(runtime.state['data']);first_facts=json.loads((out/'memory-baseline.json').read_text())['source_fact_digest']
  entered,parked=asyncio.Event(),asyncio.Event();calls=0
  async def sleep(_):
   nonlocal calls
   calls+=1
   if calls==1:await entered.wait()
   else:parked.set();await asyncio.Event().wait()
  async def refresh(r):
   source=r.state['data']
   if a.failed_worker:raise RuntimeError('disposable failed-refresh traceback')
   return source
  api=SimpleNamespace(sleep=sleep,create_task=asyncio.create_task,shield=asyncio.shield,gather=asyncio.gather,to_thread=asyncio.to_thread,CancelledError=asyncio.CancelledError)
  with patch.object(maintenance,'asyncio',api),patch('src.platform.storage_accounting.periodic_storage_accounting',return_value={}):
   maintenance.ensure_periodic_refresh(runtime,refresh,interval_seconds=900);entered.set();await asyncio.wait_for(parked.wait(),3)
   reader=runtime.brain_context if a.reader else None
   if a.reader:runtime.active_requests+=1
   sample('completed_refresh_parked');restore(paths[1]);sample('replacement_published')
   for _ in range(3):await asyncio.sleep(0)
   released_before_gc=ref() is None;sample('replacement_before_harness_gc_trim');gc.collect();release_unused_allocator_pages();settled=sample('replacement_settled');old_retained=ref() is not None
   if a.reader:
    assert reader._data is ref() and runtime.active_requests==1
    runtime.active_requests-=1;del reader
    for _ in range(3):await asyncio.sleep(0)
    gc.collect();release_unused_allocator_pages();sample('legitimate_reader_released')
   old_after_reader_release=ref() is not None
   assert old_after_reader_release is (a.mode=='control')
   operation_end=sample('publication_measurement_end_before_verification');measured_kernel_peak=operation_end['kernel_peak']
   second_facts=facts(runtime);assert first_facts==second_facts
   await runtime.close()
   for _ in range(3):await asyncio.sleep(0)
   gc.collect();release_unused_allocator_pages();sample('runtime_closed');assert ref() is None and not psutil.Process().children(recursive=True)
  assert not dtos_app.canonical_history_store._current and lifecycle_coordinator.snapshot()['phase']=='idle'
  operation_peak=max(x['kernel_peak'] for x in stages)
 sample('scratch_removed')
 report=dict(mode=a.mode,repeat=a.repeat,measured_kernel_peak=measured_kernel_peak,released_before_gc=released_before_gc,failed_worker=a.failed_worker,reader=a.reader,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),instrumentation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),original_maintenance_sha256=hashlib.sha256(original.encode()).hexdigest(),effective_maintenance_sha256=hashlib.sha256(proposed.encode()).hexdigest(),environment={'limit':2147483648,'swap':0,'cpus':2,'network':'none','python':sys.version},input_sha256=[hashlib.file_digest(src.open('rb'),'sha256').hexdigest() for src in [root/'oneqb.json',out/'next-publication.json']],initial=initial,stages=stages,old_generation_held_after_replacement=old_retained,old_generation_held_after_reader_release=old_after_reader_release,source_fact_digest=second_facts,retained_after_replacement=settled['cgroup_current_bytes']-initial['cgroup_current_bytes'],seconds=time.monotonic()-t,children_after=[],scratch_removed=not Path(directory).exists(),passed=True,scope='Same final application source and fixed inputs/instrumentation. Only control substitutes the verified baseline maintenance function; shipping uses unmodified candidate. Decoder/digest/binding/guards identical. Entire native fact digest matches retained original fixture result. Operation kernel peak captured before verification. GC/trim separately disclosed. Not privateGranite or liveacceptance.')
 assert all(x['cgroup_memory_events']['oom']==x['cgroup_memory_events']['oom_kill']==0 for x in stages)
 name='memory-final-'+a.mode+'-'+str(a.repeat)+('-failed' if a.failed_worker else '')+('-reader' if a.reader else '')
 (out/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['mode','failed_worker','reader','old_generation_held_after_replacement','old_generation_held_after_reader_release','retained_after_replacement','source_fact_digest']}))
asyncio.run(main())

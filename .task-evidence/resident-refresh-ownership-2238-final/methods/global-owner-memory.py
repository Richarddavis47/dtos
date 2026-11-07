"""Matched global scheduler ownership; real guarded restore/publication, mocked acquisition."""
import argparse,asyncio,gc,hashlib,inspect,json,logging,os,subprocess,sys,tempfile,time,weakref
from pathlib import Path
from unittest.mock import patch
import shutil
sys.path.insert(0,'/app')
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['control','shipping'],required=True);p.add_argument('--repeat',type=int,default=1);p.add_argument('--reader',action='store_true');p.add_argument('--failed-ingest',action='store_true');a=p.parse_args()
b=Path('/evidence');out=b/'runtime-retention';inputs=out/'global-fixtures'
for key in ['CACHE','METADATA_DB','INTELLIGENCE_CHECKPOINT','FOIS_DB','HISTORY_DB','ACCOUNT_DB']:os.environ['DTOS_'+key+'_FILE']=str(b/'fixture'/(key.lower()+'.sqlite3'))
os.environ.update(DTOS_PROJECTION_DB_FILE=str(b/'fixture/projections.sqlite3'),DTOS_DURABLE_HISTORY_REQUIRED='0',SLEEPER_BASE_URL='http://127.0.0.1:9/v1',DTOS_SLEEPER_SEASON_CACHE_ROOT=str(b/'fixture/seasons'))
import dtos_app,psutil
from services import league_preparation as prep
from src.core.league_runtime import LeagueRuntime,RuntimeState
from src.platform.lifecycle import memory_snapshot,lifecycle_coordinator
from src.platform.memory_reclamation import release_unused_allocator_pages
logging.disable(logging.CRITICAL)
assert memory_snapshot()['cgroup_limit_bytes']==2147483648 and Path('/sys/fs/cgroup/memory.swap.max').read_text().strip()=='0'
assert lifecycle_coordinator.startup_complete()
original=inspect.getsource(dtos_app.refresh_global_evidence)
if a.mode=='control':
 effective=(out/'baseline-global-evidence.py').read_text();namespace={};exec(compile(effective,'<verified-baseline-global-owner>','exec'),dtos_app.__dict__,namespace);dtos_app.refresh_global_evidence=namespace['refresh_global_evidence']
else:effective=original
stages=[]
def sample(label):
 stat=dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines());row=dict(label=label,**memory_snapshot(),anon=int(stat['anon']),file=int(stat['file']),inactive_file=int(stat['inactive_file']),kernel_peak=int(Path('/sys/fs/cgroup/memory.peak').read_text()));stages.append(row);return row
class Publication(dict):pass

def publish(runtime):
 runtime.apply_data(Publication(runtime.state['data']));service=dtos_app.ProjectionService(league_id=runtime.league_id,scoring_profile_id=runtime.scoring_profile);service.restore_into(runtime.state['data']);dtos_app._publish_runtime_context(runtime,service)

def restore(runtime,path):
 with patch.object(prep,'league_cache_file',return_value=path):assert prep.restore_cached_runtime(runtime,publish,expected_season=2026)

def facts(runtime):
 data=runtime.state['data'];h=hashlib.sha256()
 for chunk in json.JSONEncoder(sort_keys=True,separators=(',',':'),default=str).iterencode({'matchups':data['season_matchups'],'production':data['canonical_player_production'],'disclosures':{k:v['canonical_production'] for k,v in data['valuation_intelligence']['assets'].items()}}):h.update(chunk.encode())
 return h.hexdigest()

async def run():
 with tempfile.TemporaryDirectory(prefix='global-owner-memory-') as directory:
  paths=[]
  for name in ['first.json','next.json']:
   path=Path(directory)/name
   with (inputs/name).open('rb') as src,path.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024);dst.flush();os.fsync(dst.fileno())
   paths.append(path)
  gc.collect();release_unused_allocator_pages();initial=sample('initial');runtime=LeagueRuntime('oneqb-rich',status=RuntimeState.WARM)
  began=time.monotonic();restore(runtime,paths[0]);sample('first_publication');old=weakref.ref(runtime.state['data']);arrivals,permits=asyncio.Queue(),asyncio.Queue();calls=[]
  async def sleep(delay):arrivals.put_nowait(delay);await permits.get()
  class Proxy:
   def __getattr__(self,key):return sleep if key=='sleep' else getattr(asyncio,key)
  async def ingest(season,path):
   calls.append(season)
   if a.failed_ingest:raise RuntimeError('Disposable ingestion failure')
   return {'status':'complete'}
  with patch.object(dtos_app,'STATE',runtime.state),patch.object(dtos_app,'asyncio',Proxy()),patch('services.global_evidence_ingestion.ingest_in_background',new=ingest):
   task=asyncio.create_task(dtos_app.refresh_global_evidence())
   try:
    assert await asyncio.wait_for(arrivals.get(),3)==30;permits.put_nowait(None);assert await asyncio.wait_for(arrivals.get(),3)==21600;assert calls==[2026];sample('global_scheduler_parked')
    reader=runtime.brain_context if a.reader else None
    if a.reader:runtime.active_requests=1
    restore(runtime,paths[1]);sample('replacement_published')
    for _ in range(3):await asyncio.sleep(0)
    released_before_gc=old() is None;sample('replacement_before_gc_trim');gc.collect();release_unused_allocator_pages();settled=sample('replacement_settled');held_after_replacement=old() is not None
    if a.reader:
     assert reader._data is old() and runtime.active_requests==1;runtime.active_requests=0;del reader
     for _ in range(3):await asyncio.sleep(0)
     gc.collect();release_unused_allocator_pages();sample('legitimate_reader_released')
    held_after_reader=old() is not None;assert held_after_reader is (a.mode=='control')
    measured=sample('operation_end_before_verification');peak=measured['kernel_peak'];seconds=time.monotonic()-began
    second_facts=facts(runtime)
   finally:task.cancel();await asyncio.gather(task,return_exceptions=True)
   assert task.done();del task
  for _ in range(3):await asyncio.sleep(0)
  await runtime.close()
  for _ in range(3):await asyncio.sleep(0)
  gc.collect();release_unused_allocator_pages();sample('measured_runtime_closed');assert old() is None
  # Independently repeat A only after the measured interval to verify source
  # identity. No digest walk or verification restore contaminates its peak.
  verifier=LeagueRuntime('oneqb-rich',status=RuntimeState.WARM);restore(verifier,paths[0]);first_facts=facts(verifier);assert first_facts==second_facts;await verifier.close();gc.collect();release_unused_allocator_pages();sample('verification_finished')
  assert not dtos_app.canonical_history_store._current and lifecycle_coordinator.snapshot()['phase']=='idle' and not psutil.Process().children(recursive=True)
 sample('scratch_removed')
 report=dict(mode=a.mode,repeat=a.repeat,failed_ingest=a.failed_ingest,reader=a.reader,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),working_tree_clean=not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),original_function_sha256=hashlib.sha256(original.encode()).hexdigest(),effective_function_sha256=hashlib.sha256(effective.encode()).hexdigest(),instrumentation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),inputs={name:dict(bytes=(inputs/name).stat().st_size,sha256=hashlib.file_digest((inputs/name).open('rb'),'sha256').hexdigest()) for name in ['first.json','next.json']},environment=dict(python=sys.version,limit=2147483648,swap=0,cpus=2,network='none'),stages=stages,released_before_gc=released_before_gc,held_after_replacement=held_after_replacement,held_after_reader_release=held_after_reader,measured_kernel_peak=peak,retained_increment=settled['cgroup_current_bytes']-initial['cgroup_current_bytes'],source_fact_digest=second_facts,seconds=seconds,children_after=[],scratch_removed=not Path(directory).exists(),passed=True,qualification='Only the real global evidence coroutine varies; source acquisition mocked identically,not claimed completed. Both measured guarded restorations/publications are real; final A verification occurs after peak capture. Identical decoder/digest/inputs/admission; GC/trim separate and identical. Disposable source-compatible structure,not privateGranite or live recovery.')
 assert report['working_tree_clean'] and all(x['cgroup_memory_events']['oom']==x['cgroup_memory_events']['oom_kill']==0 for x in stages)
 name=f'global-memory-{a.mode}-{a.repeat}'+('-failed' if a.failed_ingest else '')+('-reader' if a.reader else '')
 (out/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['mode','repeat','reader','failed_ingest','retained_increment','measured_kernel_peak','source_fact_digest','passed']}))
asyncio.run(run())

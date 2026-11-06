"""New unused-reference recovery control; reuses prior synthetic inputs unchanged.

Not a reproduction of Granite contents, not a new universal restoration bound.
All pressure bytes are explicit harness memory, never subtracted from telemetry.
"""
import asyncio,gc,hashlib,json,os,shutil,subprocess,sys,tempfile,threading,time,weakref
from pathlib import Path
from unittest.mock import patch


def main():
 root=Path('/evidence');scratch=tempfile.TemporaryDirectory(prefix='restoration-recovery-');sp=Path(scratch.name)
 cache=Path('/prior/oneqb.json');prior=Path('/prior/projections.sqlite3');db=sp/'projections.sqlite3';shutil.copyfile(prior,db)
 for key,name in {'CACHE':'cache.json','METADATA_DB':'metadata.sqlite3','INTELLIGENCE_CHECKPOINT':'intelligence.sqlite3','FOIS_DB':'fois.sqlite3','HISTORY_DB':'retired.sqlite3','ACCOUNT_DB':'accounts.sqlite3'}.items():os.environ['DTOS_'+key+'_FILE']=str(sp/name)
 os.environ.update(DTOS_PROJECTION_DB_FILE=str(db),DTOS_DURABLE_HISTORY_REQUIRED='0',DTOS_HISTORY_STORAGE_ROOT=str(sp),DTOS_SLEEPER_SEASON_CACHE_ROOT=str(sp/'seasons'),SLEEPER_BASE_URL='http://127.0.0.1:9/v1')
 sys.path.insert(0,'/app')
 import dtos_app
 from services import league_preparation as prep
 from src.core.league_runtime import LeagueRuntime
 from src.core.intelligence.context import IntelligenceContext
 from src.core.intelligence.models import IntelligenceResult
 from src.core.intelligence.cache import intelligence_cache
 from src.core.fois import process_execution as workers
 from src.platform.lifecycle import lifecycle_coordinator,memory_snapshot,HeavyWorkDeferred
 from src.platform.trade_execution import _recover_unused,TradeControl
 from src.platform.memory_reclamation import release_unused_allocator_pages
 assert memory_snapshot()['cgroup_limit_bytes']==2147483648 and Path('/sys/fs/cgroup/memory.swap.max').read_text().strip()=='0'
 report={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'scope':__doc__,'policy_unchanged':True,'samples':[],'expired_results':3,'cache_bytes':cache.stat().st_size,'fixture_sha256':hashlib.sha256(cache.read_bytes()).hexdigest(),'source_requests':0,'production_changes':False}
 def sample(label):
  s=memory_snapshot();st=dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines());r={'at':time.monotonic(),'label':label,**s,**{k:int(st[k]) for k in ['anon','file','inactive_file','kernel']}};report['samples'].append(r);return r
 payload=json.loads(cache.read_text());live=LeagueRuntime(str(payload['data']['league']['league_id']));live.apply_data(payload['data']);live.active_requests=1;live_data=live.state['data'];del payload
 report['fixture_structure']={k:len(live_data.get(k) or ()) for k in ['teams','players','normalized_players']}
 refs=[]
 def old_result(data):
  teams=tuple(data['teams']);context=IntelligenceContext(league_id=str(data['league']['league_id']),active_roster_id=1,league=data['league'],roster=teams[0],teams=teams,picks=(),settings=data['league'].get('scoring_settings',{}),opponents=teams[1:],market={},front_offices=(),cached_data=data,user_preferences={},snapshot_key='expired')
  return IntelligenceResult(context=context,decision=None,decisions={},player_portfolio=None,pick_portfolio=None,player_reports={},front_office_model=None,trades=(),market=None,player_values={},roster=None,league=None,recommendation=None,timings_ms={},cache_hit=False)
 for n in range(3):
  result=intelligence_cache.get_or_create('snapshot:retired-context-'+str(n),lambda:old_result(json.loads(cache.read_text())),ttl=0)
  refs.append(weakref.ref(result));del result
 fresh=intelligence_cache.get_or_create('fresh-active-context',lambda:old_result(live_data),ttl=3600)
 worker=workers.warm_fois_executor_sync();report['idle_worker']=worker
 gc.collect();release_unused_allocator_pages();before=sample('live_and_expired_contexts_ready')
 # Explicit bounded harness pressure represents unrelated committed allocations.
 amount=max(0,2147483648-before['cgroup_current_bytes']-300*1024**2-4*1024**2);pressure=bytearray(amount)
 for offset in range(0,amount,4096):pressure[offset]=1
 report['harness_pressure_bytes']=amount;at=sample('before_baseline_restore')
 target=LeagueRuntime(live.league_id);published=[]
 def publish(runtime):
  projections=dtos_app.ProjectionService(league_id=runtime.league_id,scoring_profile_id=runtime.scoring_profile)
  attached=projections.restore_into(runtime.state['data']);report['projection_attached']=attached
  dtos_app._publish_runtime_context(runtime,projections);published.append(runtime.league_id)
 with patch.object(prep,'league_cache_file',return_value=cache):
  try:result=prep.restore_cached_runtime(target,publish,expected_season=2026)
  except HeavyWorkDeferred:report['baseline_outcome']='deferred'
  else:raise AssertionError('Expected baseline deferral, got '+str(result))
 assert target.state['data']=={} and not published and all(r() is not None for r in refs)
 report['before_plan']=prep.restoration_admission(cache.stat().st_size,at,False,fois_working_bytes=prep.FOIS_WORKING,fois_safety_bytes=prep.FOIS_SAFETY)
 assert report['before_plan']['would_admit'] is False
 with lifecycle_coordinator.phase('cache_persistence',wait=False):
  report['manual_existing_recovery']=_recover_unused(TradeControl(deadline=time.monotonic()+30))
 report['expired_refs_released']=all(r() is None for r in refs);assert report['expired_refs_released']
 after=sample('after_manual_existing_recovery');report['after_plan']=prep.restoration_admission(cache.stat().st_size,after,False,fois_working_bytes=prep.FOIS_WORKING,fois_safety_bytes=prep.FOIS_SAFETY)
 assert report['after_plan']['would_admit'] is True
 assert intelligence_cache.peek('fresh-active-context') is fresh and live.state['data'] is live_data and live.active_requests==1
 stop=threading.Event();observations=[]
 def watch():
  while not stop.wait(.005):observations.append((time.monotonic(),memory_snapshot()['cgroup_current_bytes']))
 monitor=threading.Thread(target=watch);monitor.start();start=time.monotonic()
 try:
  with patch.object(prep,'league_cache_file',return_value=cache):assert prep.restore_cached_runtime(target,publish,expected_season=2026)
 finally:stop.set();monitor.join()
 report['restoration_seconds']=time.monotonic()-start;report['sample_interval_ms']=5;report['restore_sampled_increment_bytes']=max([after['cgroup_current_bytes'],*[v for _,v in observations]])-after['cgroup_current_bytes'];report['sampling_limitation']='Five-ms thread samples can miss short peaks; lifetime kernel peak is separate and includes explicit pressure setup.'
 report['restored_outcome']='restored';report['same_required_bytes']=report['before_plan']['required_bytes']==report['after_plan']['required_bytes'];sample('after_restore');assert report['same_required_bytes'] and published==[live.league_id]
 report['live_runtime_untouched']=live.state['data'] is live_data and live.active_requests==1
 report['memory_released_bytes']=at['cgroup_current_bytes']-after['cgroup_current_bytes'];report['kernel_lifetime_peak_bytes']=int(Path('/sys/fs/cgroup/memory.peak').read_text());report['source_contexts_not_evicted']=True
 target_data=target.state['data'];assert target_data['league']==live_data['league'] and target_data['roster_positions']==live_data['roster_positions']
 del target_data;asyncio.run(target.close());live.active_requests=0;asyncio.run(live.close());intelligence_cache.invalidate();del fresh,live_data,pressure
 gc.collect();release_unused_allocator_pages();asyncio.run(workers.shutdown_fois_executor());final=sample('after_cleanup');assert not final['cgroup_memory_events']['oom_kill']
 report['cleanup_worker_count']=len(__import__('multiprocessing').active_children());assert report['cleanup_worker_count']==0
 scratch.cleanup();report['scratch_exists_after']=sp.exists();assert not sp.exists();report['passed']=True
 out=root/'baseline-recovery-probe.json';out.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ['head','cache_bytes','baseline_outcome','restored_outcome','memory_released_bytes','restore_sampled_increment_bytes','harness_pressure_bytes','manual_existing_recovery','cleanup_worker_count','passed']}))

if __name__=='__main__':main()

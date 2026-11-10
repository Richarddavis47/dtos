"""Baseline route/guard reproduction; synthetic metadata is not a live admission sample."""
from pathlib import Path
import asyncio,json,os,sys,unittest
from datetime import datetime,timezone
from unittest.mock import patch,Mock
sys.path.insert(0,'/app')
from tests.test_cold_league_recovery import ColdLeagueRecoveryTests
from tests.test_league_runtime import league_data
from tests.test_import_commissioner_integrity import snapshot
from src.core.league_runtime import LeagueRuntimeError,RuntimeState
from services import league_preparation as p
from src.platform.lifecycle import lifecycle_coordinator,memory_snapshot

OUT=Path('/evidence/baseline-probe');OUT.mkdir(exist_ok=True);RECORDS=[]
class Probe(ColdLeagueRecoveryTests):
 def setUp(self):
  super().setUp();self.store.activate(self.account,'100');self.cache=Path(self.folder.name)/'saved-200.json';self.chain=[];self.restore_calls=0;self.cleanup_results=[]
  self.payload=dict(data=league_data('200'),last_sync=datetime.now(timezone.utc).isoformat());self.write_cache()
  self.enterContext(patch.object(p,'league_cache_file',return_value=self.cache));original_cleanup=p.reclaim_unused_analytical_memory
  def cleanup():
   result=original_cleanup();self.cleanup_results.append(result);return result
  self.enterContext(patch.object(p,'reclaim_unused_analytical_memory',side_effect=cleanup))
  async def hydrate(runtime):
   self.restore_calls+=1
   if not await p.restore_cached_runtime_owned(runtime,lambda r:None,expected_season=2026):raise LeagueRuntimeError('Incompatible disposable saved publication')
   return runtime.state['data']
  self.manager._hydrator=hydrate;original_get=self.manager.get
  async def observed_get(*args,**kwargs):
   try:return await original_get(*args,**kwargs)
   except Exception as exc:
    chain=[];seen=set();e=exc
    while e is not None and id(e) not in seen and len(chain)<4:
     seen.add(id(e));chain.append(type(e).__name__);e=e.__cause__
    self.chain.append(chain);raise
  self.manager.get=observed_get
 def write_cache(self,size=None):
  raw=json.dumps(self.payload).encode();self.cache.write_bytes(raw)
  if size:
   assert len(raw)<size
   with self.cache.open('ab') as f:
    remaining=size-len(raw)
    while remaining:
     chunk=min(65536,remaining);f.write(b' '*chunk);remaining-=chunk
 def post(self):return self.client.post('/account/leagues/200/activate',data={'csrf_token':self.csrf},follow_redirects=False)
 def capture(self,name,response,model=None):
  r=self.manager.resident('200');RECORDS.append(dict(case=name,http=response.status_code,retry_after=response.headers.get('Retry-After'),generic_failure='League preparation did not finish' in response.text,waiting_label='League preparation is waiting' in response.text,chain=self.chain,runtime_state=r.status.value if r else None,deferrals=self.manager.deferrals,failures=self.manager.failures,restore_calls=self.restore_calls,cleanup_fixture_results=self.cleanup_results,recovery_fixture_metadata=r.lifecycle.get('cache_restore_memory_recovery') if r else None,cache_bytes=self.cache.stat().st_size,admission_inputs=model,real_container_sample=memory_snapshot(),provider_requests=len(self.source_requests)))
 def test_01_reported_metadata_pressure_is_deferral_but_generic_failure(self):
  self.write_cache(35839104);model={'cgroup_current_bytes':1502986240,'cgroup_limit_bytes':2147483648};before=snapshot(self.store)
  with patch.object(p,'memory_snapshot',return_value=model),patch.object(p,'load_cache_json') as decode:
   response=self.post();self.assertEqual(response.status_code,503);self.assertIn('League preparation did not finish',response.text);self.assertIsNone(response.headers.get('Retry-After'));decode.assert_not_called()
  self.assertEqual(self.chain,[['LeagueRuntimeDeferred','HeavyWorkDeferred']]);self.assertEqual(self.manager.deferrals,1);self.assertEqual(self.manager.failures,0);self.assertEqual(snapshot(self.store),before);self.assertEqual(len(self.cleanup_results),1);self.assertEqual(self.source_requests,[]);self.capture('modeled queued-sample inputs; not original guard evidence',response,model)
 def test_02_cooldown_does_not_repeat_cleanup_or_restore(self):
  model={'cgroup_current_bytes':2*1024**3-200*1024**2,'cgroup_limit_bytes':2*1024**3}
  with patch.object(p,'memory_snapshot',return_value=model),patch.object(p,'load_cache_json') as decode:
   first=self.post();second=self.post();decode.assert_not_called()
  self.assertEqual(first.status_code,second.status_code,503);self.assertEqual(self.restore_calls,1);self.assertEqual(len(self.cleanup_results),1);self.assertEqual(self.chain[-1],['LeagueRuntimeDeferred']);self.capture('cooldown reuse; no repeated heavyweight allocation',second,model)
 def test_03_unknown_telemetry_defers_without_cleanup_or_decode(self):
  with patch.object(p,'memory_snapshot',return_value={}),patch.object(p,'load_cache_json') as decode:
   response=self.post();decode.assert_not_called()
  self.assertEqual(response.status_code,503);self.assertEqual(self.cleanup_results,[]);self.assertEqual(self.manager.resident('200').status,RuntimeState.DEFERRED);self.capture('unknown telemetry; fail closed',response,{})
 def test_04_actual_lease_conflict_is_separate_from_memory(self):
  with lifecycle_coordinator.phase('sleeper_sync'),patch.object(p,'load_cache_json') as decode:
   response=self.post();decode.assert_not_called()
  self.assertEqual(response.status_code,503);self.assertEqual(self.cleanup_results,[]);self.assertEqual(self.manager.resident('200').status,RuntimeState.DEFERRED);self.capture('held fixture sync lease; no memory decision',response)
 def test_05_real_healthy_fixture_restoration_activates(self):
  before=memory_snapshot();self.assertEqual(before['cgroup_limit_bytes'],2147483648);response=self.post();self.assertEqual(response.status_code,303,response.text);self.assertEqual(self.store.context_for_session(self.token).active_league_id,'200');self.assertEqual(self.manager.resident('200').status,RuntimeState.WARM);self.assertEqual(self.manager.resident('200').state['data'],self.payload['data']);self.assertEqual(self.source_requests,[]);self.capture('small real cache/real admission; not Granite payload or protected live journey',response)
 def test_06_incompatible_cache_is_failure_not_deferral(self):
  self.payload['data']['league']['league_id']='300';self.write_cache();response=self.post();self.assertEqual(response.status_code,503);self.assertEqual(self.manager.resident('200').status,RuntimeState.FAILED);self.assertEqual(self.manager.failures,1);self.assertEqual(self.manager.deferrals,0);self.assertEqual(self.source_requests,[]);self.capture('foreign league body rejected; no source fallback',response)

if __name__=='__main__':
 names=[n for n in dir(Probe) if n.startswith('test_0')];suite=unittest.TestSuite(Probe(n) for n in names);result=unittest.TextTestRunner(verbosity=2).run(suite);report=dict(baseline='abbe723a0566cf84a8fff947cf7320cb66567a77',tree='cf649ee06ec3228d51d251ce7afbdbb15866f398',tests=result.testsRun,passed=result.wasSuccessful(),cases=RECORDS,method='Real account routes,manager,owned restoration and native lease; model telemetry explicitly separated. Pressure file is harmless JSON+whitespace metadata fixture, never a production cache or representative memory study. Native cleanup results here are fixture-only, not original Render cleanup evidence. Healthy small publication uses actual enforced2GiB telemetry. No providers or production state.');(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(not result.wasSuccessful())

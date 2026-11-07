"""Bounded ownership reproduction using real asyncio tasks; not production data."""
import asyncio,gc,json,sys,weakref
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,'/app')
from services import league_maintenance as maintenance
from src.core.league_runtime import LeagueRuntime,RuntimeState

class Snapshot(dict):pass

async def run(failed=False):
 runtime=LeagueRuntime('111',status=RuntimeState.WARM)
 first=Snapshot(league={'league_id':'111','season':'2026'},payload=bytearray(1024*1024))
 ref=weakref.ref(first);runtime.state['data']=first;del first
 tick,parked=asyncio.Event(),asyncio.Event();sleep_calls=0
 async def sleep(_):
  nonlocal sleep_calls
  sleep_calls+=1
  if sleep_calls==1:await tick.wait()
  else:parked.set();await asyncio.Event().wait()
 async def refresh(r):
  previous=r.state['data']
  if failed:raise RuntimeError('disposable failure retaining candidate frame')
  return previous
 api=SimpleNamespace(sleep=sleep,create_task=asyncio.create_task,shield=asyncio.shield,gather=asyncio.gather,to_thread=asyncio.to_thread,CancelledError=asyncio.CancelledError)
 with patch.object(maintenance,'asyncio',api),patch('src.platform.storage_accounting.periodic_storage_accounting',return_value={}):
  maintenance.ensure_periodic_refresh(runtime,refresh,interval_seconds=900)
  tick.set();await asyncio.wait_for(parked.wait(),2)
  runtime.apply_data({'league':{'league_id':'111','season':'2026'},'publication':'new'})
  gc.collect();held_while_parked=ref() is not None
  active=runtime.active_requests;current=runtime.state['data']['publication']
  await runtime.close();gc.collect();released_after_close=ref() is None
 return dict(case='exception' if failed else 'success',obsolete_generation_retained_while_sleeping=held_while_parked,released_only_after_close=released_after_close,active_requests=active,new_publication_preserved=current=='new')

async def main():
 rows=[await run(),await run(True)]
 report=dict(source='shipping baseline',cases=rows,expected_unwanted_retention=True,method='Existing real periodic loop and real asyncio worker. Only interval scheduling/storage bookkeeping isolated; no admission or source result seeded. Weak reference tracks obsolete dictionary after a separate legal publication.')
 Path('/evidence/runtime-retention/baseline-ownership-reproduction.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
 assert all(r['obsolete_generation_retained_while_sleeping'] and r['released_only_after_close'] and r['new_publication_preserved'] for r in rows)
asyncio.run(main())

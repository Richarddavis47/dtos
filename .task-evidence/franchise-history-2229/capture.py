import sys;sys.path.insert(0,'/app')
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
import gc,hashlib,json,statistics,subprocess,time
from unittest.mock import patch
from services.franchise_timeline import franchise_timeline
from src.ui.franchise_timeline import render_franchise_timeline
from src.core.historical_memory.graph import HistoricalAssetGraph
from tests.test_franchise_timeline_coverage import FranchiseTimelineCoverageTests
from tests.test_historical_tracker_phase2 import DAY,ARK
out=Path('/evidence/replay');out.mkdir(exist_ok=True)
helper=FranchiseTimelineCoverageTests();helper.setUp();f=helper.f
records=[]
def mem(name):
 p=Path('/sys/fs/cgroup')/name;return p.read_text().strip() if p.exists() else None
try:
 for league,roster in ((DAY,'3'),(ARK,'1')):
  f.data=f.fixture.data[league];graph=HistoricalAssetGraph(f.fixture.store,league,f.data)
  before=deepcopy(f.data);view=franchise_timeline(graph,roster)
  hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(f.fixture.temp.name).rglob('*.json')}
  times=[]
  with patch.object(graph,'prepare_indexes',side_effect=AssertionError('no graph build')),patch.object(graph,'events',side_effect=AssertionError('no trade tree')),patch('services.sleeper.sleeper_get',side_effect=AssertionError('no providers')):
   for _ in range(20):
    started=time.perf_counter();view=franchise_timeline(graph,roster);render_franchise_timeline(view);times.append(time.perf_counter()-started)
  assert f.data==before
  assert hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(f.fixture.temp.name).rglob('*.json')}
  response=helper.client.get('/history/team/'+league+':franchise:'+roster);assert response.status_code==200
  (out/(league+'.html')).write_text(response.text)
  (out/(league+'.json')).write_text(json.dumps(view,indent=2,default=str))
  (out/(league+'-coverage.json')).write_text(json.dumps(f.fixture.store.transaction_coverage(league),indent=2))
  records.append({'league':league,'roster':roster,'scope':'Retained October 12 source replay, not live completeness','total_events_for_roster':view['total'],'displayed_events':len(view['events']),'noncompleted_or_unattributed':view['attempts_total'],'seasons':view['seasons'],'warm_seconds':times,'median_seconds':statistics.median(times),'provider_calls':0,'asset_graph_builds':0,'source_files_unchanged':True,'data_unchanged':True})
 f.data=f.fixture.data[DAY];helper.past()
 with patch.object(f.fixture.store,'season_chain',return_value={'seasons':[{'season':2022,'league_id':'9000000000000002022','cache_status':'unavailable'}]}):
  response=helper.client.get('/history/team/'+DAY+':franchise:1');assert response.status_code==200
  (out/'synthetic-complete-partial-unknown.html').write_text(response.text)
  (out/'synthetic-complete-partial-unknown.json').write_text(json.dumps(franchise_timeline(HistoricalAssetGraph(f.fixture.store,DAY,f.data),'1'),indent=2))
finally:helper.doCleanups()
gc.collect()
report={'observed_at':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'limit':mem('memory.max'),'swap_limit':mem('memory.swap.max'),'peak':mem('memory.peak'),'final_current':mem('memory.current'),'events':mem('memory.events'),'records':records,'limits':['Small retained fixtures, not a production worst-case memory profile.','No live source refresh or private owner account verification.','Cleanup observations do not establish long-term leak freedom.']}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print({k:report[k] for k in ('head','tree','limit','peak','events')});print([(r['league'],r['total_events_for_roster'],r['median_seconds']) for r in records])

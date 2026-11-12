"""Bounded retained replay audit on actual production source; no live history claim."""
import os,sys,json,hashlib,subprocess,tempfile
from pathlib import Path
root=Path(tempfile.mkdtemp(prefix='franchise-progress-audit-'))
for key,name in {'CACHE':'cache.json','PROJECTION_DB':'projections.sqlite3','METADATA_DB':'metadata.sqlite3','INTELLIGENCE_CHECKPOINT':'intelligence.sqlite3','FOIS_DB':'fois.sqlite3','HISTORY_DB':'history.sqlite3','ACCOUNT_DB':'accounts.sqlite3'}.items():os.environ['DTOS_'+key+'_FILE']=str(root/name)
os.environ.update(DTOS_DURABLE_HISTORY_REQUIRED='0',SLEEPER_BASE_URL='http://127.0.0.1:9/v1',DTOS_FIXTURE_ROOT=str(root),DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root/'seasons'),DTOS_HISTORY_STORAGE_ROOT=str(root))
sys.path.insert(0,'/app')
from tests.test_completed_trade_observations import CompletedTradeObservationTests
from tests.test_franchise_timeline_coverage import fixtures
from src.core.gm_behavioral_intelligence.diagnostics import _movement_evidence
records=[]
case=CompletedTradeObservationTests();case.setUp()
try:
 for league,roster in [(fixtures.DAY,'4'),(fixtures.ARK,'1')]:
  case.f.f.data=case.f.f.fixture.data[league];graph=case.f.graph();view=case.view(roster);html=case.f.page(roster);counts=[]
  for raw in graph.transaction_archive():
   if raw['type']!='trade' or str(raw['status']).casefold() not in {'complete','completed'}:continue
   parties,moves,complete,cats=_movement_evidence(raw['raw'])
   if roster not in parties:continue
   incoming=[dict(kind=k,exact_asset=i) for k,i,a,b,_ in moves if b==roster and k in ['player','pick']];outgoing=[dict(kind=k,exact_asset=i) for k,i,a,b,_ in moves if a==roster and k in ['player','pick']]
   counts.append(dict(transaction_id=raw['sleeper_transaction_id'],season=raw['season'],incoming=incoming,outgoing=outgoing,category_support=cats))
  records.append(dict(control='retained Day Traders' if league==fixtures.DAY else 'retained Arkham',source_seasons=[x['season'] for x in view['seasons']],coverage=[dict(season=x['season'],state=x['state']) for x in view['seasons']],existing_observations=view['completed_trade_observations'],direct_retained_movements=counts,has_franchise_change_summary='How this franchise changed' in html,has_season_selector='name="season"' in html,has_observed_net_summary='Observed net trade' in html))
finally:case.doCleanups()
cg=Path('/sys/fs/cgroup');result=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),working_tree_clean=not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),source_fixture_sha256=hashlib.sha256(Path('tests/fixtures/trade_timeline_sources.json').read_bytes()).hexdigest(),scope='Retained source replay, partial acquisition and bounded samples; not live or exhaustive league coverage. No current ownership/price/score is used as historical evidence.',cases=records,memory_limit=int((cg/'memory.max').read_text()),kernel_peak=int((cg/'memory.peak').read_text()),events=dict(x.split() for x in (cg/'memory.events').read_text().splitlines()))
assert result['commit']=='05c717e50b47683963ed40d66946e9f6eea76694' and result['working_tree_clean'] and result['memory_limit']==2147483648;Path('/evidence/baseline-probe.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

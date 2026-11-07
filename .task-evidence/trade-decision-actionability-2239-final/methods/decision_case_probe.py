import sys
sys.path.insert(0,'/app')
from copy import deepcopy
from pathlib import Path
import json,subprocess
from services.trade_intelligence import generate_trade_workflow,evaluate_trade_request
from tests import test_trade_discovery_repair as discovery
from tests import test_trade_recommendation_clarity as clarity
from tests import test_trade_lineup_detail as slots
b=Path('/evidence/cases');b.mkdir(exist_ok=True);out={}
def selected(e):
 return {k:e.get(k) for k in ('recommendation','generated_trade_eligible','market_evidence','decision_context','recommendation_trace','multi_horizon_impact','provenance','personalization','reserve_evidence')}
f=discovery.DiscoveryRepairTests();f.setUp()
try:
 original=deepcopy(f.data)
 for strategy in ('WIN NOW','RETOOL','REBUILD'):
  r=generate_trade_workflow(f.data,dict(workflow='recommended',active_roster_id=1,strategy=strategy));rows=[x for x in r['results'] if x['evaluation']['generated_trade_eligible']];paired=[]
  for row in rows[:2]:
   e=row['evaluation'];other=evaluate_trade_request(f.data,{**row['proposal'],'strategy':strategy},projection_reader=f.fixture.reader)['evaluation'];fields=('recommendation','generated_trade_eligible','market_evidence','multi_horizon_impact')
   equal={k:json.loads(json.dumps(e[k]))==json.loads(json.dumps(other[k])) for k in fields};assert all(equal.values())
   paired.append(dict(proposal=row['proposal'],recommended=selected(e),evaluate=selected(other),exact_numeric_and_verdict_agreement=equal))
  assert rows;out[strategy]=dict(qualified=len(rows),returned=len(r['results']),search_evidence=r['search_evidence'],pairs=paired)
 assert f.data==original
finally:f.doCleanups()
f=clarity.RecommendationClarityTests();f.setUp()
try:
 e=f.evaluate(strategy='WIN NOW');assert abs(e['decision_context']['lineup']['delta']-6.31)<1e-8;out['meaningful_current_upgrade']=selected(e)
 f.f.f.prices(a=995,c=75);f.f.f.points['c']=20.01;f.f.f.publish();e=f.evaluate(assets_sent=['a'],assets_received=['c'],strategy='WIN NOW');assert e['recommendation']=='REJECT' and not e['generated_trade_eligible'];out['expensive_marginal_upgrade']=selected(e)
finally:f.doCleanups()
f=slots.TradeLineupDetailTests();f.setUp()
try:
 f.f.feed=[r for r in f.f.feed if r['player_id']!='2-9'];f.f.publish();e=f.evaluate();assert not e['generated_trade_eligible'];out['missing_partner_def_projection']=selected(e)
finally:f.doCleanups()
out['source']=subprocess.check_output(['git','rev-parse','HEAD','HEAD^{tree}'],text=True).splitlines();out['scope']='Disposable, source-compatible fixtures. Direct final evaluator and actual recommendation workflow; no production offers, preference mutation or new provider acquisition.'
(b/'matched-cases.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'strategies':{k:out[k]['qualified'] for k in ('WIN NOW','RETOOL','REBUILD')},'paired_verdict_and_numeric_agreement':True,'source':out['source']}))

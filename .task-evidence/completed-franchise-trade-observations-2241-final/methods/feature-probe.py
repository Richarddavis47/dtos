"""Record actual prepared summaries; raw retained inputs independently establish the control."""
from pathlib import Path
import sys
sys.path.insert(0, "/app")
import hashlib,json,subprocess
from tests.test_completed_trade_observations import CompletedTradeObservationTests
root=Path('/evidence');source=Path('tests/fixtures/trade_timeline_sources.json');capture=json.loads(source.read_text())['leagues'][0];seen={str(r['transaction_id']):r for rows in capture['transactions'].values() for r in rows if r.get('type')=='trade' and r.get('status') in ('complete','completed') and 4 in r.get('roster_ids',[])}
expected=dict(completed_trades=len(seen),firsts_received=0,firsts_sent=0,receiving_trades=0,sending_trades=0)
for r in seen.values():
 legs={(p['season'],p['round'],p['roster_id'],p['previous_owner_id'],p['owner_id']) for p in r.get('draft_picks') or [] if p.get('round')==1};incoming=sum(p[4]==4 for p in legs);outgoing=sum(p[3]==4 for p in legs);expected['firsts_received']+=incoming;expected['firsts_sent']+=outgoing;expected['receiving_trades']+=int(bool(incoming));expected['sending_trades']+=int(bool(outgoing))
assert expected==dict(completed_trades=2,firsts_received=3,firsts_sent=1,receiving_trades=1,sending_trades=1)
records=[]
for name in ('retained_day','multi_team','partial_pick','supported_zero','unknown'):
 case=CompletedTradeObservationTests();case.setUp()
 try:
  if name=='multi_team':case.f.past({'1':[case.trade()]})
  elif name=='partial_pick':case.f.past({'1':[case.trade(draft_picks=[case.pick(),case.pick(None,2,1)])]})
  elif name=='supported_zero':case.f.past({'1':[case.trade(draft_picks=[])]})
  row=case.row('4' if name=='retained_day' else '2');records.append(dict(case=name,summary=row))
  if name=='retained_day':assert {k:row[k] for k in expected}==expected
 finally:case.doCleanups()
report=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),working_tree_clean=not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),source_fixture_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),raw_retained_expectations=expected,cases=records,live_observation=False,scope='Actual prepared retained-source replay plus explicitly disposable controls; no production payload or manager-intent claim.')
(root/'feature.json').write_text(json.dumps(report,indent=2)+'\n');print('Recorded5actualsummaries; retained Day counts independently match raw source values')

"""Inspect existing behavior with explicitly disposable prices, not real coverage."""
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import json,sys
sys.path.insert(0,'/app')
from tests.test_trade_timeline import TradeTimelineTests, DAY, ARK
from src.core.historical_memory.graph import HistoricalAssetGraph
from src.core.historical_intelligence.market_comparison import observation_clocks

rows=[]
def run(name, setup, check):
    h=TradeTimelineTests();h.setUp()
    try:
        g=h.load()
        setup(h,g)
        g=HistoricalAssetGraph(h.store,DAY,h.data[DAY],h.memory)
        assets=[{'asset_id':'DTOS-P-1','to_franchise_id':DAY+':franchise:1'},
                {'asset_id':'PICK-2027-R1-ORIG4','to_franchise_id':DAY+':franchise:2'}]
        result=g._trade_time_intelligence({'occurred_at':'2026-03-01T00:00:00Z'},assets)
        print(name,json.dumps(result),flush=True)
        check(result)
        rows.append(dict(case=name,coverage=result['coverage_state'],valued=result['valued_assets'],
            total=result['total_assets'],side_totals=result['side_totals'],
            fairness_state=result['fairness_state'],reason=result['reason'],
            assets=[{k:a.get(k) for k in ('asset_id','value','observed_at','source_knowledge_at','match_state','temporal_reason','admission_reason')} for a in result['assets']]))
    finally:h.tearDown()

def prices(h,g,quote='2026-03-01T00:00:00Z'):
    h.capture('player:1',quote,value=700)
    h.capture('pick:2027:1:4',quote,value=350,kind='future_pick')
def complete(r):
    assert r['valued_assets']==2 and len(r['side_totals'])==2
def partial(r):
    assert r['valued_assets']==1 and not r['side_totals']
def absent(r):
    assert r['valued_assets']==0 and not r['side_totals']

run('constructed_complete_same_instant',prices,complete)
run('constructed_partial_pick_missing',lambda h,g:h.capture('player:1','2026-03-01T00:00:00Z',value=700),partial)
run('post_trade_quote_excluded',lambda h,g:prices(h,g,'2026-03-01T12:00:01Z'),absent)
run('knowledge_after_trade_excluded',lambda h,g:h.capture('player:1','2026-03-01T11:00:00Z',known='2026-03-01T13:00:00Z'),absent)
run('opaque_units_excluded',lambda h,g:h.capture('player:1','2026-03-01T11:00:00Z',semantics=False),absent)
run('old_quotes_existing_estimate_policy',lambda h,g:prices(h,g,'2026-01-01T00:00:00Z'),complete)

def newer_incompatible(h,g):
    h.capture('player:1','2026-02-20T00:00:00Z',event='2026-02-20T00:00:00Z',value=400)
    h.capture('player:1','2026-02-28T00:00:00Z',event='2026-02-28T00:00:00Z',semantics=False,value=450)
run('latest_clock_candidate_incompatible_older_compatible_not_recovered',newer_incompatible,absent)

def foreign(h,g):
    h.capture('player:1','2026-03-01T00:00:00Z')
    with h.memory._connect() as c:
        for row in c.execute('SELECT observation_id,provider_evidence_json FROM global_market_observations').fetchall():
            data=json.loads(row['provider_evidence_json'])
            for item in data:item['metadata']['league_id']=ARK
            c.execute('UPDATE global_market_observations SET provider_evidence_json=? WHERE observation_id=?',(json.dumps(data),row['observation_id']))
run('explicit_foreign_league_quote_excluded',foreign,absent)

h=TradeTimelineTests();h.setUp()
try:
    g=h.load()
    h.capture('player:1','2026-03-01T00:00:00Z')
    obs=h.memory.observations(limit=1)[0]
    ambiguous=replace(obs,provider_evidence=tuple(replace(r,observed_at='2026-03-01') for r in obs.provider_evidence))
    assert observation_clocks(ambiguous,'2026-03-01T00:00:00Z') is None
    model=g.trade_timeline('1333655835015942144')
    branch=next(b for b in model['branches'] if b['asset_id']=='PICK-2026-R2-ORIG7')
    assert branch['converted_asset'] and branch['converted_asset']['asset_id']=='DTOS-P-13346'
    dossier=g.trade_dossier('1333655835015942144')
    assert not dossier['trade_time_intelligence']['side_totals']
    identity_control={'date_only_observation_order':'unknown / withheld','exact_pick':'PICK-2026-R2-ORIG7',
        'later_converted_player':'DTOS-P-13346','price_substitution':False,
        'notice':'Retained Sleeper pick-conversion identity; prices in other cases are synthetic and do not establish coverage.'}
finally:h.tearDown()

result={'scope':'Disposable source-shaped canonical producer/store controls only; no actual historical provider prices',
    'cases':rows,'identity_control':identity_control,
    'gaps_not_corrected':[
        'Current UI does not display a calculated quote age or package side totals.',
        'Current package admission permits old dated estimates and does not enforce a maximum age; temporal confidence alone is not the documented freshness policy requested for this feature.',
        'Reader selects latest clock-eligible observation before checking its semantic compatibility; an older compatible candidate can remain unused.',
        'Historical league-format parity is not established merely by matching provider format across package assets.'
    ],'release':'Not justified by these fixtures; real trade/quote overlap remains unverified.'}
Path('/evidence/contracts.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))

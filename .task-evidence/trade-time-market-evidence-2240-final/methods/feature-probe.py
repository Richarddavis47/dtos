"""Final-source characterization from retained disposable input values."""
import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,'/app')
from tests import test_trade_time_market_evidence as fixtures
from tests.test_market_observation_producer_identity import prepared
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from copy import deepcopy

results=[]
for mode in ['newer_incompatible','newer_foreign','partial_old','zero','conflicting']:
    h=fixtures.TradeTimeMarketEvidenceTests();h.setUp()
    try:
        if mode=='zero':h.capture(seconds=0,value=0)
        elif mode=='partial_old':h.capture(seconds=-30*86400,value=275)
        else:
            h.capture(value=400)
            if mode=='newer_incompatible':
                data,_=prepared();semantic=deepcopy(CheckpointPipeline._market_observations(data,'player:1')[0].metadata['comparison_semantics']);semantic['value_scale']='native_units'
                h.capture(seconds=-60,value=800,metadata={'comparison_semantics':semantic})
            elif mode=='newer_foreign':h.capture(seconds=-60,value=800,metadata={'league_id':fixtures.fixtures.ARK})
            else:h.capture(value=800)
        row=h.row()
        response=h.f.client.get('/trades/history/'+fixtures.fixtures.ROOT)
        assert response.status_code==200
        retained=h.f.fixture.memory.observations(asset_id='player:12506',limit=10)
        raw=[dict(value=r.canonical_value,observed_at=r.provider_evidence[0].observed_at) for r in retained]
        expected={'newer_incompatible':400,'newer_foreign':400,'partial_old':275,'zero':0,'conflicting':None}[mode]
        assert row['value']==expected
        assert 'Package totals are not shown' in response.text
        results.append(dict(case=mode,retained_fixture_values=raw,selected_value=row['value'],age_seconds=row['quote_age_seconds'],
            state=row['match_state'],source_providers=[r['provider'] for r in row['provider_evidence']],package_totals_displayed=False))
    finally:h.doCleanups()
git=lambda *args:subprocess.check_output(['git',*args],text=True).strip()
assert not git('status','--porcelain')
out={'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'working_tree_clean':True,
    'scope':'Explicitly disposable retained values; no actual historic provider prices or independently observed live coverage',
    'cases':results,'package_display_policy':'Per-asset only; no maximum-age cutoff or package totals introduced'}
Path('/evidence/feature.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))

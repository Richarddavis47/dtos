"""Disposable matched publication controls; no production or provider reads."""
import os
from pathlib import Path
import sys
root = Path('/tmp/relevance-probe')
root.mkdir()
for key, name in {'CACHE':'cache.json','PROJECTION_DB':'projections.sqlite3','METADATA_DB':'metadata.sqlite3','INTELLIGENCE_CHECKPOINT':'intelligence.sqlite3','FOIS_DB':'fois.sqlite3','HISTORY_DB':'history.sqlite3','ACCOUNT_DB':'accounts.sqlite3'}.items():
    os.environ['DTOS_'+key+'_FILE'] = str(root/name)
os.environ.update(DTOS_DURABLE_HISTORY_REQUIRED='0', SLEEPER_BASE_URL='http://127.0.0.1:9/v1', DTOS_FIXTURE_ROOT=str(root), DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root/'seasons'), DTOS_HISTORY_STORAGE_ROOT=str(root))
sys.path.insert(0,'/app')
from datetime import datetime, timezone
import json, subprocess, unittest
from tests.test_market_roster_relevance import MarketNeedFixture
from src.core.intelligence.roster_diagnostics import diagnose_league

case = unittest.TestCase()
results = []
try:
    f = MarketNeedFixture(case)
    def observe(name):
        snapshot = f.f.capital.reader.snapshot()
        diagnostic = diagnose_league(f.data, snapshot, projection_reader=f.f.capital.reader)
        team = diagnostic['teams']['1']
        html = f.client.get('/market', params={'q': f.player_id, 'front_office':1}).text
        results.append(dict(case=name, team_points=team['optimal_points'], starting_ids=team['optimal_ids'], rb_gain=team['positions']['RB']['add_one_gain'], rb_need=team['positions']['RB']['starter_need'], team_state=team['evidence']['conclusion_state'], source_freshness=team['evidence']['projection_freshness'], limitations=team['evidence']['limitations'], personalized_action='Explore in Trade For' in html, snapshot_rows=len(snapshot['players']), eligible_players=sum(len(t['players']) for t in f.data['teams'])))
    observe('complete_control')
    f.data['players']['unused-record'] = dict(id='unused-record', name='Disposable unused source row', position='WR', team='NYJ', status='Unknown')
    f.need_case.publish(f.f)
    observe('identical_rosters_plus_unrostered_missing_projection')
    assert results[0]['team_points'] == results[1]['team_points']
    assert results[0]['starting_ids'] == results[1]['starting_ids']
    assert results[0]['rb_gain'] == results[1]['rb_gain']
    cg=Path('/sys/fs/cgroup')
    report=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),observed_at=datetime.now(timezone.utc).isoformat(),memory_limit=int((cg/'memory.max').read_text()),peak=int((cg/'memory.peak').read_text()),events=dict(line.split() for line in (cg/'memory.events').read_text().splitlines()),cases=results,source='Disposable compatible native Sleeper fixtures and actual rendered Market routes; not live Granite.',production_payload_read=False)
    Path('/output/baseline-probe.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
finally:
    case.doCleanups()

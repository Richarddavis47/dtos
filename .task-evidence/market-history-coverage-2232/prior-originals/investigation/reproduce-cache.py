"""New disposable source-to-HTML cache probe, not a live customer snapshot."""
from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import patch

from src.ui.render_cache import GenerationRenderCache
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from tests.test_market_observation_producer_identity import prepared, checkpoint
from tests.test_market_trend_current_integration import CurrentMarketHTTPTests

case = CurrentMarketHTTPTests()
case.setUp()
try:
    with patch('routes.market.market_render_cache', GenerationRenderCache('probe-page')), patch('routes.market.market_body_render_cache', GenerationRenderCache('probe-body')):
        before = case.client.get('/market?selected=player%3A1').text
        initial = case.client.get('/api/market/assets/player:1').json()['market_trend']
        generation = case.market.semantic_generation
        data, asset = prepared(960)
        stamp = '2026-06-01T12:00:00+00:00'
        observations = tuple(replace(row, observed_at=stamp) for row in CheckpointPipeline._market_observations(data, 'player:1'))
        price = asset['layers']['market_value']['value']
        assert price == 80
        case.memory.put_sparse(checkpoint('newly-retained-earlier-checkpoint', price, stamp), market_context_id='fixture', provider_evidence=observations)
        current = case.client.get('/api/market/assets/player:1').json()['market_trend']
        directory = case.client.get('/api/market/assets').json()['assets'][0]['market_trend']
        after = case.client.get('/market?selected=player%3A1').text
        report = {'scope':'Disposable canonical producer/store, actual Market routes and render caches; not live', 'generation_unchanged':generation == case.market.semantic_generation,'before':{k:initial[k] for k in ('magnitude','checkpoint_count','comparison_start_at','comparison_end_at','confidence')},'after_api':{k:current[k] for k in ('magnitude','checkpoint_count','comparison_start_at','comparison_end_at','confidence')},'directory_matches':directory['magnitude']==current['magnitude'],'html_identical':before==after,'html_has_current_movement':'+120.00 Market points' in after,'html_has_old_movement':'+100.00 Market points' in after}
        Path('/evidence/baseline-cache-probe.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)
        assert current['magnitude']==120 and current['checkpoint_count']==3
        assert '+120.00 Market points' in after, 'API admits the new comparison, but selected HTML retains old history'
finally:
    case.doCleanups()

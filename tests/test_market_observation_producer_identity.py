"""Producer -> prepared handoff -> sparse store -> active explanation proof."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from services.asset_explanations import market_explanation
from src.ui.explanations import explanation_panel
from src.core.valuation.normalization import prepare_market_normalization
from src.core.valuation.universe import ValuationUniverse
from src.core.valuation_intelligence.engine import _score_asset
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.core.intelligence_memory.models import IntelligenceCheckpoint, CheckpointTrigger, ProvenanceType, EvidenceCompleteness
from src.core.market_trends import MarketTrendService
from tests.test_valuation_universe import fixture


def prepared(value=9000):
    data, state = fixture()
    row = data['market_data']['providers']['FantasyCalc']['1']
    row.update(value=value, format='dynasty_2qb', format_details={'num_teams': 12, 'num_qbs': 2, 'ppr': 1},
               source_updated_at=None, retrieved_at='2026-08-31T12:00:00+00:00')
    prepare_market_normalization(data['market_data'])
    universe = ValuationUniverse(data, state)
    asset = universe.by_id['player:1']
    scored = _score_asset(asset, [], {}, None)
    data['valuation_intelligence'] = {'assets': {'player:1': scored}}
    return data, asset


def checkpoint(identity, value, timestamp):
    return IntelligenceCheckpoint(checkpoint_id=identity, asset_id='player:1', asset_type='player',
        timestamp=timestamp, season=2026, trigger_type=CheckpointTrigger.SEASON_START,
        provenance_type=ProvenanceType.LIVE_CAPTURED, market_value=value, confidence=80,
        evidence_completeness=EvidenceCompleteness.COMPLETE, model_version='producer-test-1')


class ProducerIdentityTests(unittest.TestCase):
    def test_active_price_selection_and_generation_binding(self):
        data, asset = prepared()
        evidence = CheckpointPipeline._market_observations(data, 'player:1')
        self.assertEqual([r.provider for r in evidence], ['FantasyCalc'])
        self.assertEqual(evidence[0].raw_value, 9000)
        self.assertEqual(evidence[0].normalized_value, asset['layers']['market_value']['value'])
        self.assertIsNone(evidence[0].metadata['source_updated_at'])
        self.assertEqual(evidence[0].observed_at, '2026-08-31T12:00:00+00:00')
        self.assertLess(len(json.dumps(evidence[0].metadata)), 1000)
        data['valuation_intelligence']['assets']['player:1']['valuation_layers']['market_value']['value'] += 1
        self.assertEqual(CheckpointPipeline._market_observations(data, 'player:1'), ())

    def test_unknown_format_preserves_price_but_not_comparability(self):
        data, asset = prepared()
        price = asset['layers']['market_value']['value']
        data['market_data']['providers']['FantasyCalc']['1'].pop('format')
        rebuilt = ValuationUniverse(data, {'data': data}).by_id['player:1']
        self.assertEqual(rebuilt['layers']['market_value']['value'], price)
        self.assertIsNone(rebuilt['market_observation_evidence'])
        from src.core.valuation.observation_identity import observation_evidence
        quote = data['market_data']['providers']['FantasyCalc']['1']
        for unknown in ('unknown', 'unavailable', ''):
            quote['format'] = unknown
            self.assertIsNone(observation_evidence([('FantasyCalc', quote, price)], canonical_value=price))

    def test_new_comparable_pair_reaches_active_explanation(self):
        with TemporaryDirectory() as temp:
            store = IntelligenceCheckpointStore(Path(temp) / 'memory.db')
            for n, value in enumerate((9000, 3000), 1):
                data, asset = prepared(value)
                evidence = CheckpointPipeline._market_observations(data, 'player:1')
                store.put_sparse(checkpoint(str(n), asset['layers']['market_value']['value'], f'2026-09-{n:02}T12:00:00Z'),
                                 market_context_id='test', provider_evidence=evidence)
            trend = MarketTrendService(store).trend_for_asset('player:1', None)
            self.assertEqual(trend['direction'], 'falling')
            html = explanation_panel(market_explanation({'asset': {'asset_id': 'player:1', 'values': {'market_value': None}}}, trend, league_id='A'))
            self.assertIn('falling', html)
            self.assertIn('does not by itself establish why', html)

    def test_identity_transition_persists_without_rewriting_legacy_and_replay_is_bounded(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'memory.db'
            store = IntelligenceCheckpointStore(path)
            data, asset = prepared()
            evidence = CheckpointPipeline._market_observations(data, 'player:1')
            point = checkpoint('old', asset['layers']['market_value']['value'], '2026-09-01T00:00:00Z')
            store.put_sparse(point, market_context_id='test', provider_evidence=tuple(replace(r, metadata={}) for r in evidence))
            with store._connect() as c:
                old = tuple(c.execute('SELECT * FROM global_market_observations').fetchone())
            new = replace(point, checkpoint_id='new', timestamp='2026-09-02T00:00:00Z')
            store.put_sparse(new, market_context_id='test', provider_evidence=evidence)
            def sizes():
                return [p.stat().st_size if p.exists() else 0 for p in (path, Path(str(path)+'-wal'), Path(str(path)+'-shm'))]
            before = sizes()
            for _ in range(100):
                store.put_sparse(new, market_context_id='test', provider_evidence=evidence)
            self.assertEqual(sizes(), before)
            with store._connect() as c:
                self.assertEqual(c.execute('SELECT count(*) FROM global_market_observations').fetchone()[0], 2)
                self.assertIn(old, [tuple(r) for r in c.execute('SELECT * FROM global_market_observations')])
            trend = MarketTrendService(store).trend_for_asset('player:1', None)
            self.assertEqual(trend['direction'], 'not_comparable')
            self.assertEqual(MarketTrendService(IntelligenceCheckpointStore(path)).trend_for_asset('player:1', None), trend)

    def test_pick_concepts_never_acquire_same_identity(self):
        from src.core.valuation.observation_identity import observation_evidence
        data, _ = prepared()
        quote = deepcopy(data['market_data']['providers']['FantasyCalc']['1'])
        quote.update(market_format='fc:12:2qb:ppr', year=2027, round=1, pick_type='generic_round')
        price = quote['normalization_reference']['normalized_value']
        generic = observation_evidence([('FantasyCalc', quote, price)], canonical_value=price)
        quote.update(pick_type='range', range='EARLY')
        ranged = observation_evidence([('FantasyCalc', quote, price)], canonical_value=price)
        self.assertNotEqual(generic['observations'][0]['metadata']['comparison_semantics'], ranged['observations'][0]['metadata']['comparison_semantics'])

    def test_new_format_boundary_is_material_even_at_unchanged_price(self):
        from src.core.valuation.observation_identity import observation_evidence
        with TemporaryDirectory() as temp:
            store = IntelligenceCheckpointStore(Path(temp) / 'memory.db')
            data, asset = prepared()
            price = asset['layers']['market_value']['value']
            for n, size in enumerate((12, 10), 1):
                # Exercise the producer identity boundary, not current format
                # selection: unsupported variants never enter current consensus.
                quote = data['market_data']['providers']['FantasyCalc']['1']
                quote['format_details']['num_teams'] = size
                data['valuation_intelligence']['assets']['player:1']['market_observation_evidence'] = observation_evidence(
                    [('FantasyCalc', quote, price)], canonical_value=price)
                store.put_sparse(checkpoint(str(n), price, f'2026-09-{n:02}T00:00:00Z'),
                                 market_context_id='test', provider_evidence=CheckpointPipeline._market_observations(data, 'player:1'))
            self.assertEqual(store.market_memory_health()['observation_count'], 2)
            result = MarketTrendService(store).trend_for_asset('player:1', None)
            self.assertEqual(result['direction'], 'not_comparable')
            self.assertIn('INCOMPATIBLE_OBSERVATION_BOUNDARY', result['comparison_reasons'])

    def test_retrieval_only_repreparation_reuses_one_row_without_file_growth(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'memory.db'
            store = IntelligenceCheckpointStore(path)
            data, asset = prepared()
            point = replace(checkpoint('first', asset['layers']['market_value']['value'], '2026-09-01T00:00:00Z'),
                            observations=CheckpointPipeline._market_observations(data, 'player:1'))
            first, _, created = store.resolve_observation(point, market_context_id='test')
            self.assertTrue(created)
            def sizes():
                return [p.stat().st_size if p.exists() else 0 for p in (path, Path(str(path)+'-wal'), Path(str(path)+'-shm'))]
            before = sizes()
            for n in range(100):
                stamp = f'2026-09-02T00:{n // 60:02}:{n % 60:02}Z'
                data['market_data']['providers']['FantasyCalc']['1']['retrieved_at'] = stamp
                selected = ValuationUniverse(data, {'data': data}).by_id['player:1']
                data['valuation_intelligence']['assets']['player:1'] = _score_asset(selected, [], {}, None)
                replay = replace(point, checkpoint_id=str(n), timestamp=stamp,
                                 observations=CheckpointPipeline._market_observations(data, 'player:1'))
                result, _, created = store.resolve_observation(replay, market_context_id='test')
                self.assertFalse(created)
                self.assertEqual(result.observation_id, first.observation_id)
            self.assertEqual(sizes(), before)
            self.assertEqual(store.market_memory_health()['observation_count'], 1)

    def test_active_pick_handoff_preserves_generic_concept_and_selected_scale(self):
        data, _ = prepared()
        data['market_data']['pick_quotes'] = {'FantasyCalc': [{
            'provider': 'FantasyCalc', 'value': 3000, 'market_format': 'fc:12:2qb:ppr',
            'year': 2027, 'round': 1, 'pick_type': 'generic_round', 'confidence': 90,
            'availability': 'current', 'retrieved_at': datetime.now(timezone.utc).isoformat()}]}
        prepare_market_normalization(data['market_data'])
        asset = ValuationUniverse(data, {'data': data}).by_id['pick:2027:1:4']
        self.assertIsNotNone(asset['layers']['market_value']['value'])
        data['valuation_intelligence']['assets'][asset['asset_id']] = _score_asset(asset, [], {}, None)
        evidence = CheckpointPipeline._market_observations(data, asset['asset_id'])
        self.assertEqual(len(evidence), 1)
        identity = json.loads(evidence[0].metadata['comparison_semantics']['format_key'])[0]
        self.assertEqual(identity['concept'], {'type': 'generic_round', 'year': 2027, 'round': 1})
        self.assertEqual(evidence[0].raw_value, 3000)
        self.assertEqual(evidence[0].normalized_value, asset['layers']['market_value']['value'])

    def test_observation_contract_transition_is_methodology_not_player_movement(self):
        from src.core.valuation_intelligence.changes import METHODOLOGY, METHODOLOGY_ID, compare
        self.assertEqual(METHODOLOGY['market_observation_identity'], 'observation-identity-1')
        self.assertEqual(compare({'methodology_id': 'legacy'}, {'methodology_id': METHODOLOGY_ID}),
                         ('METHODOLOGY_VERSION_CHANGED',))

    def test_capture_keeps_selected_normalization_not_legacy_default(self):
        from src.core.intelligence_memory.service import IntelligenceMemoryService
        from src.core.valuation.config import NORMALIZATION_VERSION
        with TemporaryDirectory() as temp:
            store = IntelligenceCheckpointStore(Path(temp) / 'memory.db')
            data, asset = prepared()
            evidence = CheckpointPipeline._market_observations(data, 'player:1')
            captured, _ = IntelligenceMemoryService(store).capture(
                asset_id='player:1', asset_type='player', timestamp='2026-09-01T00:00:00Z', season=2026,
                trigger=CheckpointTrigger.SEASON_START, provenance=ProvenanceType.LIVE_CAPTURED,
                market_value=asset['layers']['market_value']['value'], confidence=80,
                completeness=EvidenceCompleteness.COMPLETE, market_observations=evidence)
            self.assertEqual(captured.normalization_version, NORMALIZATION_VERSION)
            with store._connect() as connection:
                raw = connection.execute('SELECT normalization_version,provider_evidence_json FROM global_market_observations').fetchone()
            self.assertEqual(raw[0], NORMALIZATION_VERSION)
            self.assertEqual(json.loads(raw[1])[0]['normalization_version'], NORMALIZATION_VERSION)

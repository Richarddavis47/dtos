"""Compact preparation is semantic, scoped, readonly and replay-stable."""
import tempfile
import unittest
from pathlib import Path

from services.player_evidence import prepare_player_production
from src.core.data_platform.global_evidence import GlobalEvidenceStore
from tests.test_player_production_stream import fact
from src.core.player_value_projection.canonical_production import prepared_production_context


class PreparedPlayerEvidenceTests(unittest.TestCase):
    def test_modeled_intrinsic_and_future_value_are_not_historical_or_projection_evidence(self):
        from src.core.valuation_intelligence.engine import _score_asset
        asset = {'asset_id': 'player:1', 'asset_type': 'player', 'identity': {'player_name': 'Example'},
                 'layers': {'intrinsic_dtos_value': {'value': 600}, 'future_value': {'value': 700}}}
        row = _score_asset(asset, [], {}, None)
        available = {item['name'] for item in row['categories'] if item['available']}
        self.assertNotIn('Historical', available)
        self.assertNotIn('Projection', available)
        supported = _score_asset(asset, [], {}, None, {'weekly_projected_points': 0})
        self.assertTrue(next(item for item in supported['categories'] if item['name'] == 'Projection')['available'])

    def test_universe_and_brain_read_same_prepared_production(self):
        from dataclasses import asdict
        from src.core.player_value_projection.canonical_production import canonical_production_context
        from src.core.valuation.universe import ValuationUniverse
        from src.core.valuation_intelligence import build_valuation_intelligence
        from tests.test_canonical_production_context import evidence
        from tests.test_trade_intelligence import fixture_data
        data = fixture_data()
        player_id = next(iter(data['players']))
        data['players'][player_id]['fantasy_points'] = 999  # Legacy field must not win.
        data['canonical_player_production'] = {'league_id': data['league']['league_id'],
            'generation': 'production-v1', 'players': {player_id: {'production': asdict(
                canonical_production_context(evidence([12, 14])) )}}}
        universe = ValuationUniverse(data, {})
        asset = universe.by_id[player_id]
        self.assertEqual(asset['layers']['current_production_value']['value'], 13)
        brain = build_valuation_intelligence(data, {})
        row = brain['assets'][f'player:{player_id}']
        self.assertEqual(row['canonical_production'], asset['canonical_production'])
        self.assertTrue(next(item for item in row['categories'] if item['name'] == 'Performance')['available'])

    def test_orchestrator_consumes_prepared_evidence_and_invalidates_generation(self):
        from copy import deepcopy
        from dataclasses import asdict
        from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry
        from src.core.player_value_projection.canonical_production import canonical_production_context
        from tests.test_canonical_production_context import evidence
        from tests.test_trade_intelligence import fixture_data
        data = fixture_data()
        player_id = data['teams'][0]['players'][0]['id']
        snapshot = {'league_id': data['league']['league_id'], 'generation': 'first',
                    'players': {player_id: {'production': asdict(canonical_production_context(evidence([13])))}}}
        data['canonical_player_production'] = snapshot
        engine = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache())
        first = engine.analyze(data, 1)
        self.assertEqual(first.player_values[player_id].production.windows[3].fantasy_points, 13)
        data['canonical_player_production'] = deepcopy(snapshot)
        data['canonical_player_production']['generation'] = 'second'
        data['canonical_player_production']['players'][player_id]['production'] = asdict(canonical_production_context(evidence([14])))
        second = engine.analyze(data, 1)
        self.assertEqual(second.player_values[player_id].production.windows[3].fantasy_points, 14)
        self.assertNotEqual(first.context.evidence_generation, second.context.evidence_generation)
        self.assertEqual(first.player_values[player_id].production.windows[3].fantasy_points, 13)

    def test_replay_league_scoring_and_material_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'global.sqlite3'
            store = GlobalEvidenceStore(path, reserve_bytes=0)
            store.publish([fact('1', 5)], retrieved_at='2025-09-02T00:00:00Z')
            data = {'league': {'league_id': 'A', 'season': 2025}, 'players': {'1': {}, '2': {}},
                    'scoring_settings': {'rec': 1}}
            first = prepare_player_production(data, expected_league_id='A', as_of='2025-09-03T00:00:00Z', path=path)
            before = path.stat().st_size
            second = prepare_player_production(data, expected_league_id='A', as_of='2025-09-04T00:00:00Z', path=path)
            self.assertEqual(first, second)
            self.assertEqual(first['players']['1']['production']['windows'][3]['fantasy_points'], 5)
            consumed = prepared_production_context(first, league_id='A', player_id='1')
            self.assertEqual(consumed.windows[3].fantasy_points, 5)
            with self.assertRaises(ValueError):
                prepared_production_context(first, league_id='B', player_id='1')
            self.assertIsNone(first['players']['2']['production']['windows'][3]['fantasy_points'])
            self.assertEqual(path.stat().st_size, before)
            data['league']['league_id'] = 'B'
            data['scoring_settings'] = {'rec': .5}
            other = prepare_player_production(data, expected_league_id='B', as_of='2025-09-04T00:00:00Z', path=path)
            self.assertEqual(other['players']['1']['production']['windows'][3]['fantasy_points'], 2.5)
            self.assertNotEqual(other['generation'], first['generation'])
            self.assertEqual(store.counts(), {'production': 1})
            store.publish([fact('1', 6)], retrieved_at='2025-09-05T00:00:00Z')
            later = prepare_player_production(data, expected_league_id='B', as_of='2025-09-06T00:00:00Z', path=path)
            self.assertNotEqual(later['generation'], other['generation'])
            historical = prepare_player_production(data, expected_league_id='B', as_of='2025-09-04T00:00:00Z', path=path)
            self.assertEqual(historical, other)

    def test_absent_store_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'absent.sqlite3'
            data = {'league': {'league_id': 'A', 'season': 2026}, 'players': {'1': {}},
                    'scoring_settings': {'rec': 1}}
            result = prepare_player_production(data, expected_league_id='A', as_of='2026-09-01T00:00:00Z', path=path)
            self.assertFalse(path.exists())
            self.assertEqual(result['availability'], 'not_connected')
            self.assertEqual(result['provider_calls'], 0)

    def test_context_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            prepare_player_production({'league': {'league_id': 'A'}}, expected_league_id='B',
                                      as_of='2026-01-01T00:00:00Z')

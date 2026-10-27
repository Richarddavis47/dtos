"""Actual canonical Market publication → authenticated Custom readiness controls."""
from __future__ import annotations

import copy
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from services.personal_rankings import PersonalRankingError, build_universe
from src.core.asset_market import AssetMarketCache
from src.core.accounts.personal_store import load_personal
from src.core.historical_memory.store import HistoricalStore
from tests.test_asset_market import _brain_asset
from tests import test_personal_rankings as personal


class CanonicalRankingAvailabilityTests(unittest.TestCase):
    state = personal.PersonalRankingsHTTPTests.state
    post = personal.PersonalRankingsHTTPTests.post
    initialize = personal.PersonalRankingsHTTPTests.initialize
    use_account = personal.PersonalRankingsHTTPTests.use_account

    def setUp(self):
        personal.PersonalRankingsHTTPTests.setUp(self)
        # Normal refresh_public_market output has provider evidence, not a
        # top-level generation/generated_at. Use the real immutable read model.
        self.data['market_data'] = {'providers': {}, 'provider_status': {}}
        self.data['valuation_intelligence'] = {
            'schema_version': '1.0', 'generated_at': '2026-10-24T00:00:00Z',
            'semantic_generation': 'canonical-fixture-A', 'assets': {
                row['asset_id']: _brain_asset(row['asset_id'], row['values']['market_value'], None, None)
                for row in personal.PreparedMarket(self.data).rows},
        }
        self.data['pick_ledger'] = [
            {**pick, 'season': pick['year']} for team in self.data['teams']
            for pick in team['picks_owned']]
        self.history = HistoricalStore(Path(self.temp.name) / 'history.sqlite3')
        self.cache = AssetMarketCache()
        self.market = self.cache.get(self.data, {'data': self.data}, self.history, 'league-1')

    def test_real_market_ready_without_synthetic_provider_timestamp(self):
        directory = self.market.directory(limit=250, minimum=0)
        self.assertGreater(directory['total'], 0)
        self.assertNotIn('generation', self.data['market_data'])
        response = self.client.get('/api/my-dtos')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertGreater(len(response.json()['rows']), 0)
        ready = self.initialize()
        self.assertTrue(ready['personal_available'])

    def test_canonical_inactive_price_survives_refresh_without_personal_rewrite(self):
        self.initialize()
        self.post('reorder', asset_id='player:3', to_position=1)
        self.post('tiers', asset_id='player:2', tier_start=True)
        self.post('preferences', asset_id='player:2', preferences={'target': True})
        saved = load_personal(self.store, 'account-a', 'league-1', 1)
        before = self.state()
        data = copy.deepcopy(self.data)
        data['players']['2'].update(status='Inactive', active=True)
        self.publish(data)
        directory = self.market.directory(limit=250, minimum=0)
        neutral = next(r for r in directory['assets'] if r['asset_id'] == 'player:2')
        self.assertEqual(neutral['status'], 'Inactive')
        self.assertEqual(neutral['values']['market_value'], 600)
        current = self.state()
        self.assertTrue(current['personal_available'], current['limitations'])
        self.assertEqual([(r['asset_id'], r['market_value'], r['personal_value']) for r in current['rows']],
                         [(r['asset_id'], r['market_value'], r['personal_value']) for r in before['rows']])
        self.assertEqual(load_personal(self.store, 'account-a', 'league-1', 1), saved)

    def publish(self, data):
        data['valuation_intelligence']['semantic_generation'] += '-next'
        self.data = data
        self.market = self.cache.get(data, {'data': data}, self.history, 'league-1')

    def test_snapshot_inputs_are_pinned_even_when_original_data_is_mutated(self):
        self.data['valuation_intelligence']['semantic_generation'] = 'superseded-B'
        self.assertFalse(self.market.compatible_prepared_inputs(self.data))
        response = self.client.get('/api/my-dtos')
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIsNone(load_personal(self.store, 'account-a', 'league-1', 1))

    def test_generation_changes_during_directory_read_reject_initialization_without_write(self):
        state = self.state()
        original = self.market.directory
        def transitioned(**kwargs):
            result = original(**kwargs)
            self.data['valuation_intelligence']['semantic_generation'] = 'generation-B'
            return result
        with patch.object(self.market, 'directory', side_effect=transitioned):
            result = self.post('initialize', state=state)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertIsNone(load_personal(self.store, 'account-a', 'league-1', 1))

    def test_runtime_replacement_during_initialization_rejects_before_commit(self):
        state = self.state()
        original = self.market.directory
        def transitioned(**kwargs):
            result = original(**kwargs)
            self.data = copy.deepcopy(self.data)
            return result
        with patch.object(self.market, 'directory', side_effect=transitioned):
            result = self.post('initialize', state=state)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertIsNone(load_personal(self.store, 'account-a', 'league-1', 1))

    def test_refresh_preserves_order_tiers_flags_and_read_only_storage(self):
        self.initialize()
        self.post('reorder', asset_id='player:3', to_position=1)
        self.post('tiers', asset_id='player:3', tier_start=True)
        self.post('preferences', asset_id='pick:2028:1:4', preferences={'protect': True})
        saved = load_personal(self.store, 'account-a', 'league-1', 1)
        data = copy.deepcopy(self.data)
        data['valuation_intelligence']['assets']['player:3']['valuation_layers']['market_value']['value'] = 400
        self.publish(data)
        for _ in range(5):
            current = self.state()
            self.assertTrue(current['personal_available'])
            self.assertEqual(current['rows'][0]['asset_id'], 'player:3')
        self.assertEqual(load_personal(self.store, 'account-a', 'league-1', 1), saved)
        self.use_account('account-b')
        self.assertFalse(self.state()['initialized'])
        self.assertIsNone(load_personal(self.store, 'account-b', 'league-1', 1))

    def test_new_removed_and_changed_pick_ownership_do_not_rewrite_saved_intent(self):
        self.initialize()
        self.post('preferences', asset_id='pick:2028:1:4', preferences={'protect': True})
        saved = load_personal(self.store, 'account-a', 'league-1', 1)
        data = copy.deepcopy(self.data)
        data['players']['6'] = {'full_name': 'New eligible QB', 'position': 'QB'}
        data['valuation_intelligence']['assets']['player:6'] = _brain_asset('player:6', 990, None, None)
        moved = data['teams'][0]['picks_owned'].pop()
        moved['current_owner_id'] = 2
        data['teams'][1]['picks_owned'].append(moved)
        data['pick_ledger'][0]['current_owner_id'] = 2
        self.publish(data)
        current = self.state()
        self.assertIn('player:6', current['new_asset_ids'])
        pick = next(row for row in current['rows'] if row['asset_id'] == 'pick:2028:1:4')
        self.assertEqual(pick['trade_asset_id'], '2028-R1-4')
        self.assertFalse(pick['owned'])
        self.assertTrue(pick['preferences']['protect'])
        data = copy.deepcopy(self.data)
        data['players']['2']['status'] = 'Retired'
        self.publish(data)
        self.assertFalse(self.state()['personal_available'])
        self.assertEqual(load_personal(self.store, 'account-a', 'league-1', 1), saved)

    def test_zero_missing_and_unavailable_market_remain_distinct_and_retry_recovers(self):
        rows = {row['asset_id']: row for row in self.state()['rows']}
        self.assertEqual(rows['player:4']['market_value'], 0)
        self.assertNotIn('player:5', rows)
        market = self.market
        self.market = None
        for _ in range(3):
            response = self.client.get('/api/my-dtos')
            self.assertEqual(response.status_code, 503, response.text)
            self.assertIn('retry', response.json()['message'])
            self.assertIn('Neutral Trade', response.json()['message'])
        self.assertIsNone(load_personal(self.store, 'account-a', 'league-1', 1))
        self.market = market
        self.assertGreater(len(self.state()['rows']), 0)

    def test_unchanged_real_reader_uses_no_factories_and_has_stable_storage(self):
        from contextlib import ExitStack
        targets = ('src.core.asset_market.engine.AssetMarketCache.get',
                   'services.sleeper.sleeper_get',
                   'services.trade_intelligence.generate_trade_workflow',
                   'src.core.trade_intelligence.lineup.optimal_legal_lineup',
                   'src.core.fois.service.FOISService._generate_sync',
                   'src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct')
        with closing(self.store.connect()) as connection:
            before = '\n'.join(connection.iterdump())
        samples = []
        with ExitStack() as stack:
            spies = [stack.enter_context(patch(target, side_effect=AssertionError(target))) for target in targets]
            for _ in range(10):
                began = time.perf_counter()
                self.state()
                samples.append(round((time.perf_counter() - began) * 1000, 3))
            self.assertTrue(all(spy.call_count == 0 for spy in spies))
        with closing(self.store.connect()) as connection:
            after = '\n'.join(connection.iterdump())
            self.assertEqual(after, before)
        if os.getenv('DTOS_PERSONAL_AVAILABILITY_EVIDENCE'):
            destination = Path(os.environ['DTOS_PERSONAL_AVAILABILITY_EVIDENCE'])
            destination.mkdir(parents=True, exist_ok=True)
            (destination / 'prepared-read-controls.json').write_text(json.dumps({
                'fixture': 'Actual canonical Market reader; disposable authenticated account; six eligible assets',
                'http_read_count': 10, 'response_ms': samples,
                'expensive_entry_point_calls': dict(zip(targets, [spy.call_count for spy in spies])),
                'logical_database_sha256_before': hashlib.sha256(before.encode()).hexdigest(),
                'logical_database_sha256_after': hashlib.sha256(after.encode()).hexdigest(),
                'preference_rows_created': 0,
            }, indent=2))

    def test_different_league_and_invalid_legacy_identity_remain_unavailable(self):
        foreign = copy.deepcopy(self.data)
        foreign['league']['league_id'] = 'other-league'
        with self.assertRaises(PersonalRankingError):
            build_universe(foreign, self.market)
        legacy = personal.PreparedMarket(self.data)
        with self.assertRaises(PersonalRankingError):
            build_universe(self.data, legacy)

    def test_invalid_saved_document_fails_safely_and_never_resets_intent(self):
        self.initialize()
        for document in ({}, {'schema': 999, 'order': []}):
            with self.subTest(document=document):
                encoded = json.dumps(document)
                with self.store.transaction() as connection:
                    connection.execute('UPDATE account_personal_rankings SET document_json=?', (encoded,))
                response = self.client.get('/api/my-dtos')
                self.assertNotEqual(response.status_code, 200)
                self.assertNotIn('personal_available', response.json())
                with closing(self.store.connect()) as connection:
                    self.assertEqual(connection.execute('SELECT document_json FROM account_personal_rankings').fetchone()[0], encoded)

    def test_cached_provider_curve_survives_real_publication_and_private_http(self):
        from src.core.provider_network import build_provider_network
        from src.core.valuation_intelligence import build_valuation_intelligence
        from src.core.valuation.calibration import cached_market_consensus
        from src.core.valuation.normalization import prepare_market_normalization
        from services.trade_intelligence import build_trade_workspace
        data = copy.deepcopy(self.data)
        data['market_data'] = {'providers': {'FantasyCalc': {
            str(i): {'value': i * 100, 'confidence': 90, 'format': 'dynasty_2qb'}
            for i in range(1, 101)}}}
        prepare_market_normalization(data['market_data'])
        expected = cached_market_consensus(data['market_data'], tuple(data['players']))
        data['market_data']['providers']['FantasyCalc'] = {
            k: v for k, v in data['market_data']['providers']['FantasyCalc'].items() if k in data['players']}

        def publish(candidate):
            candidate.pop('valuation_intelligence', None)
            build_provider_network(candidate, {})
            build_valuation_intelligence(candidate, {})
            self.publish(candidate)
        publish(data)
        self.initialize()
        self.post('reorder', asset_id='player:1', to_position=1)
        self.post('tiers', asset_id='player:3', tier_start=True)
        self.post('preferences', asset_id='player:2', preferences={'target': True})
        before, saved = self.state(), load_personal(self.store, 'account-a', 'league-1', 1)
        candidate = copy.deepcopy(self.data)
        prepare_market_normalization(candidate['market_data'])
        publish(candidate)
        after = self.state()
        self.assertTrue(after['personal_available'], after['limitations'])
        self.assertEqual([(r['asset_id'], r['market_value'], r['personal_value']) for r in after['rows']],
                         [(r['asset_id'], r['market_value'], r['personal_value']) for r in before['rows']])
        self.assertEqual(load_personal(self.store, 'account-a', 'league-1', 1), saved)
        directory = {r['asset_id']: r for r in self.market.directory(minimum=0, limit=250)['assets']}
        workspace = build_trade_workspace(self.data, 1)
        for row in after['rows']:
            if row['asset_id'].startswith('player:'):
                pid = row['asset_id'].removeprefix('player:')
                self.assertEqual(row['market_value'], expected[pid][0])
                self.assertEqual(directory[row['asset_id']]['values']['market_value'], expected[pid][0])
                self.assertEqual(workspace['canonical_market_facts'][pid].value, expected[pid][0])

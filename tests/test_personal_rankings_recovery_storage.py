"""Disposable authenticated recovery: bounded durable intent and security fences.

These controls mutate fixture accounts only.  They do not imply live production
access or physical-device acceptance.
"""
from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, closing
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

from src.core.accounts.personal_store import (
    MAX_DOCUMENT_BYTES, PersonalRevisionConflict, encode_document,
    load_personal, save_personal,
)
from tests import test_personal_rankings as personal


class PersonalRankingsRecoveryStorageTests(unittest.TestCase):
    state = personal.PersonalRankingsHTTPTests.state
    post = personal.PersonalRankingsHTTPTests.post
    initialize = personal.PersonalRankingsHTTPTests.initialize
    use_account = personal.PersonalRankingsHTTPTests.use_account

    def setUp(self):
        personal.PersonalRankingsHTTPTests.setUp(self)

    def document(self, account='account-a'):
        return load_personal(self.store, account, 'league-1', 1)

    def facts(self):
        with closing(self.store.connect()) as connection:
            return '\n'.join(connection.iterdump())

    def unrelated_facts(self):
        return [line for line in self.facts().splitlines()
                if 'INSERT INTO "account_personal_rankings"' not in line]

    def remove(self, key, *, state=None, **fields):
        return self.post('remove_asset', state=state, asset_id=key,
                         confirmation='REMOVE FROM CUSTOM ORDER', **fields)

    def evidence(self, name, value):
        if os.getenv('DTOS_RANKING_RECOVERY_STORAGE_EVIDENCE'):
            folder = Path(os.environ['DTOS_RANKING_RECOVERY_STORAGE_EVIDENCE'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (name + '.json')).write_text(json.dumps(value, indent=2), encoding='utf-8')

    def test_full_saved_order_refresh_and_blocker_reads_leave_persistence_unchanged(self):
        self.market.rows = [self.market.row(f'player:{index}', 1000 - index / 10,
                                          ('QB', 'RB', 'WR', 'TE')[index % 4],
                                          f'Fixture Player {index}')
                            for index in range(1, 1001)]
        self.initialize()
        self.assertEqual(self.post('reorder', asset_id='player:999', to_position=1).status_code, 200)
        self.assertEqual(self.post('tiers', asset_id='player:999', tier_start=True).status_code, 200)
        self.assertEqual(self.post('preferences', asset_id='player:999', preferences={'avoid': True}).status_code, 200)
        saved = self.document()
        self.market.generation = 'Market-refresh-with-same-identities'
        self.market.rows[0]['values']['market_value'] = 875
        self.assertTrue(self.state()['personal_available'])
        self.market.rows[99]['status'] = 'Retired'
        self.market.generation = 'Market-retired-asset'
        self.assertFalse(self.state()['personal_available'])
        before = self.facts()
        database = Path(self.store.path)
        file_before = hashlib.sha256(database.read_bytes()).hexdigest()
        size_before = database.stat().st_size
        targets = (
            'services.sleeper.sleeper_get',
            'services.trade_intelligence.generate_trade_workflow',
            'src.core.trade_intelligence.lineup.optimal_legal_lineup',
            'src.core.fois.service.FOISService._generate_sync',
            'src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct',
            'src.core.asset_market.engine.AssetMarketCache.get',
            'src.core.accounts.personal_store.save_personal',
        )
        elapsed = []
        with ExitStack() as stack:
            guards = {name: stack.enter_context(patch(name, side_effect=AssertionError(name)))
                      for name in targets}
            for _ in range(20):
                began = time.perf_counter()
                state = self.state()
                elapsed.append(round((time.perf_counter() - began) * 1000, 3))
                self.assertFalse(state['personal_available'])
                self.assertEqual(len(state['rows']), 1000)
                self.assertEqual(self.client.get('/account/my-dtos').status_code, 200)
            self.assertEqual({name: guard.call_count for name, guard in guards.items()},
                             {name: 0 for name in targets})
        self.assertEqual(self.document(), saved)
        self.assertEqual(self.facts(), before)
        self.assertEqual(database.stat().st_size, size_before)
        self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), file_before)
        encoded = encode_document({key: value for key, value in saved.items()
                                   if key not in {'revision', 'created_at', 'updated_at'}})
        self.assertLess(len(encoded.encode()), MAX_DOCUMENT_BYTES)
        self.evidence('bounded-read-preservation', {
            'fixture': '1000 saved assets; one retired; disposable authenticated account',
            'read_pairs': 20, 'read_ms': elapsed, 'ranked_count': len(saved['order']),
            'document_bytes': len(encoded.encode()), 'document_byte_limit': MAX_DOCUMENT_BYTES,
            'database_bytes_before': size_before, 'database_bytes_after': database.stat().st_size,
            'database_sha256_before': file_before,
            'database_sha256_after': hashlib.sha256(database.read_bytes()).hexdigest(),
            'logical_sha256_before': hashlib.sha256(before.encode()).hexdigest(),
            'logical_sha256_after': hashlib.sha256(self.facts().encode()).hexdigest(),
            'guarded_calls': {name: 0 for name in targets},
        })

    def test_confirmed_single_asset_recovery_preserves_other_order_tiers_and_all_flags(self):
        self.initialize()
        for command, fields in (
            ('reorder', {'asset_id': 'player:3', 'to_position': 1}),
            ('tiers', {'asset_id': 'player:3', 'tier_start': True}),
            ('tiers', {'asset_id': 'player:2', 'tier_start': True}),
            ('preferences', {'asset_id': 'player:2', 'preferences': {'avoid': True}}),
            ('preferences', {'asset_id': 'player:3', 'preferences': {'target': True}}),
            ('preferences', {'asset_id': 'pick:2028:1:4', 'preferences': {'protect': True}}),
        ):
            self.assertEqual(self.post(command, **fields).status_code, 200)
        saved = self.document()
        self.market.rows = [row for row in self.market.rows if row['asset_id'] != 'player:2']
        self.market.generation = 'Market-no-longer-ranks-player-2'
        unrelated_before = self.unrelated_facts()
        response = self.remove('player:2')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['personal_available'])
        recovered = self.document()
        self.assertEqual(recovered['revision'], saved['revision'] + 1)
        self.assertEqual(recovered['created_at'], saved['created_at'])
        self.assertEqual(recovered['order'], [key for key in saved['order'] if key != 'player:2'])
        self.assertEqual(recovered['baseline']['ids'], [key for key in saved['baseline']['ids'] if key != 'player:2'])
        self.assertEqual(recovered['baseline']['generation'], saved['baseline']['generation'])
        self.assertEqual(recovered['tiers'], ['player:3'])
        self.assertEqual(recovered['preferences'], saved['preferences'])
        self.assertEqual(self.unrelated_facts(), unrelated_before)
        self.assertNotIn('market_value', encode_document({key: value for key, value in recovered.items()
                                                         if key not in {'revision', 'created_at', 'updated_at'}}))
        # Reloading and recreating the AccountStore must not revive a removed
        # ranking or silently drop its separate acquisition preference.
        from src.core.accounts import AccountStore
        reopened = AccountStore(self.store.path)
        self.assertEqual(load_personal(reopened, 'account-a', 'league-1', 1), recovered)
        self.evidence('single-asset-recovery', {
            'revision_before': saved['revision'], 'revision_after': recovered['revision'],
            'before_order': saved['order'], 'after_order': recovered['order'],
            'before_tiers': saved['tiers'], 'after_tiers': recovered['tiers'],
            'all_sparse_intent_preserved': recovered['preferences'] == saved['preferences'],
            'compatible_after_recovery': response.json()['personal_available'],
            'only_preference_document_changed': True,
        })

    def test_recovery_preview_retry_and_confirmed_write_launch_no_expensive_analysis(self):
        targets = (
            'services.sleeper.sleeper_get',
            'services.trade_intelligence.generate_trade_workflow',
            'services.team_headquarters.build_team_headquarters',
            'src.core.intelligence.orchestrator.IntelligenceOrchestrator.analyze',
            'src.core.trade_intelligence.lineup.optimal_legal_lineup',
            'src.core.intelligence.team_strength.prepare_for_data',
            'src.core.fois.service.FOISService._generate_sync',
            'src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct',
            'src.core.market_trends.service.MarketTrendService.trend_for_asset',
            'src.core.asset_market.engine.AssetMarketCache.get',
        )
        with ExitStack() as stack:
            guards = {name: stack.enter_context(patch(name, side_effect=AssertionError(name)))
                      for name in targets}
            self.initialize()
            self.market.rows[1]['status'] = 'Retired'
            for _ in range(3):
                self.assertFalse(self.state()['personal_available'])
                self.assertEqual(self.client.get('/account/my-dtos').status_code, 200)
            response = self.remove('player:2')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()['personal_available'])
            self.assertEqual({name: guard.call_count for name, guard in guards.items()},
                             {name: 0 for name in targets})
        self.evidence('recovery-work-counts', {
            'fixture': 'Disposable authenticated initialize, three blocked retry/read pairs, confirmed single-asset removal',
            'guarded_calls': {name: 0 for name in targets},
            'provider_synchronization': 0, 'discovery': 0, 'solver': 0,
            'fois_generation': 0, 'historical_reconstruction': 0,
        })

    def test_recovery_requires_confirmation_csrf_context_and_current_revision(self):
        self.initialize()
        self.market.rows[1]['status'] = 'Retired'
        state = self.state()
        before = self.facts()
        payload = {'command': 'remove_asset', 'asset_id': 'player:2',
                   'confirmation': 'REMOVE FROM CUSTOM ORDER',
                   'expected_revision': state['revision'], 'market_generation': state['generation'],
                   'context': state['context']}
        cases = (
            ({**payload, 'confirmation': ''}, {'X-CSRF-Token': self.csrf}, 422),
            (payload, {}, 403),
            (payload, {'X-CSRF-Token': self.csrf, 'Origin': 'https://foreign.invalid'}, 403),
            ({**payload, 'expected_revision': state['revision'] - 1}, {'X-CSRF-Token': self.csrf}, 409),
            ({**payload, 'market_generation': 'old'}, {'X-CSRF-Token': self.csrf}, 409),
            ({**payload, 'context': {**state['context'], 'roster_id': 2}}, {'X-CSRF-Token': self.csrf}, 409),
        )
        for command, headers, status in cases:
            with self.subTest(status=status, fields=tuple(command)):
                response = self.client.post('/api/my-dtos', json=command, headers=headers)
                self.assertEqual(response.status_code, status, response.text)
                self.assertEqual(self.facts(), before)

    def test_recovery_session_revoked_after_admission_cannot_commit(self):
        self.initialize()
        self.market.rows[1]['status'] = 'Retired'
        state = self.state()
        original = save_personal
        after_revocation = []
        def revoke_then_save(*args, **kwargs):
            self.store.revoke_session(self.tokens['account-a'][0])
            after_revocation.append(self.facts())
            return original(*args, **kwargs)
        with patch('src.core.accounts.personal_store.save_personal', side_effect=revoke_then_save):
            response = self.remove('player:2', state=state)
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(len(after_revocation), 1)
        self.assertEqual(self.facts(), after_revocation[0])
        self.assertIn('player:2', self.document()['order'])

    def test_recovery_is_account_and_league_scoped(self):
        self.initialize()
        original_a = self.document()
        self.use_account('account-b')
        self.initialize()
        self.assertEqual(self.post('reorder', asset_id='player:3', to_position=1).status_code, 200)
        original_b = self.document('account-b')
        self.market.rows[1]['status'] = 'Retired'
        response = self.remove('player:2')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.document(), original_a)
        self.assertEqual(self.document('account-b')['revision'], original_b['revision'] + 1)
        self.assertEqual(self.document('account-b')['order'][0], 'player:3')
        self.assertIsNone(load_personal(self.store, 'account-b', 'other-league', 1))
        self.assertIsNone(load_personal(self.store, 'account-b', 'league-1', 2))
        self.use_account('account-a')
        self.assertFalse(self.state()['personal_available'])
        self.assertEqual(self.document(), original_a)

    def test_concurrent_recovery_and_edit_have_one_cas_winner(self):
        self.initialize()
        original = self.document()
        recovered = {key: copy.deepcopy(value) for key, value in original.items()
                     if key not in {'revision', 'created_at', 'updated_at'}}
        recovered['order'].remove('player:2')
        recovered['baseline']['ids'].remove('player:2')
        reordered = {key: copy.deepcopy(value) for key, value in original.items()
                     if key not in {'revision', 'created_at', 'updated_at'}}
        reordered['order'].reverse()
        barrier = threading.Barrier(2)
        before = self.facts()
        def save(value):
            barrier.wait(timeout=3)
            try:
                result = save_personal(self.store, 'account-a', 'league-1', 1, value,
                                       expected_revision=original['revision'])
                return result['order']
            except PersonalRevisionConflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(save, (recovered, reordered)))
        self.assertEqual(results.count('conflict'), 1)
        winner = next(result for result in results if result != 'conflict')
        self.assertEqual(self.document()['order'], winner)
        self.assertEqual(self.document()['revision'], original['revision'] + 1)
        self.assertEqual(self.document()['preferences'], original['preferences'])
        # Only the single durable preference row may differ.
        after = self.facts()
        self.assertEqual([line for line in after.splitlines() if 'INSERT INTO "account_personal_rankings"' not in line],
                         [line for line in before.splitlines() if 'INSERT INTO "account_personal_rankings"' not in line])

    def test_removed_exact_pick_keeps_protection_separate_from_other_same_round_pick(self):
        self.initialize()
        key, other = 'pick:2028:1:4', 'pick:2028:1:5'
        self.assertEqual(self.post('preferences', asset_id=key, preferences={'protect': True}).status_code, 200)
        saved = self.document()
        self.data['teams'][0]['picks_owned'] = []
        self.market.generation = 'Market-exact-pick-unavailable'
        self.assertFalse(self.state()['personal_available'])
        response = self.remove(key)
        self.assertEqual(response.status_code, 200, response.text)
        recovered = self.document()
        self.assertTrue(response.json()['personal_available'])
        self.assertEqual(recovered['preferences'], saved['preferences'])
        self.assertTrue(recovered['preferences'][key]['protect'])
        self.assertNotIn(other, recovered['preferences'])
        self.assertIn(other, recovered['order'])
        self.assertNotIn(key, recovered['order'])


if __name__ == '__main__':
    unittest.main()

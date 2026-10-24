"""Saved compatibility recovery through authenticated Trade HTTP boundaries.

All writes use disposable accounts.  Source transport is prepared, while the
ranking store, router, personal adapter and Trade calculations are real paths.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from src.core.accounts.personal_store import load_personal
from tests import test_personal_rankings as personal


class PersonalRankingsRecoveryTradeTests(unittest.TestCase):
    operations = (
        ('generate', {'workflow': 'shop', 'asset_id': 'a', 'partner_roster_id': 0,
                      'shop_preference': 'draft_capital'}),
        ('generate', {'workflow': 'trade_for', 'asset_id': '2028-R1-4', 'partner_roster_id': 0}),
        ('generate', {'workflow': 'recommended', 'partner_roster_id': 0}),
        ('assist', {'instruction': 'make this trade work'}),
        ('alternatives', {}), ('balance', {}), ('calculate', {}), ('evaluate', {}),
    )

    def setUp(self):
        self.fixture = personal.PersonalRankingsTradeHTTPTests(
            'test_calculator_keeps_canonical_and_personal_costs_distinct')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.editor = self.fixture.editor
        self.editor.initialize()

    def document(self):
        return load_personal(self.editor.store, 'account-a', 'league-1', 1)

    def make_one_price_unavailable(self):
        row = next(row for row in self.editor.market.rows if row['asset_id'] == 'player:b')
        row['values']['market_value'] = None
        self.editor.market.generation = 'Market-with-one-missing-price'

    def recover(self, key='player:b', **overrides):
        return self.editor.post('remove_asset', asset_id=key,
                                confirmation='REMOVE FROM CUSTOM ORDER', **overrides)

    def evidence(self, name, result):
        output = os.getenv('DTOS_PERSONAL_RECOVERY_EVIDENCE')
        if output:
            destination = Path(output)
            destination.mkdir(parents=True, exist_ok=True)
            (destination / (name + '.json')).write_text(json.dumps(result, indent=2, default=str))

    def test_named_blocker_stops_every_custom_workflow_without_discovery_or_evaluation(self):
        before = deepcopy(self.document())
        self.make_one_price_unavailable()
        state = self.editor.state()
        self.assertFalse(state['personal_available'])
        self.assertEqual([row['asset_id'] for row in state['compatibility_issues']], ['player:b'])
        workspace = self.editor.client.get('/api/trades/workspace').json()['personalization']
        self.assertFalse(workspace['available'])
        self.assertEqual(workspace['compatibility_issues'], state['compatibility_issues'])
        self.assertEqual(workspace['recovery_url'], '/account/my-dtos#personal-compatibility')
        results = []
        forbidden = ('generate_trade_workflow', 'assist_trade_request', 'create_trade_alternatives',
                     'balance_trade_market', 'calculate_trade_market', 'evaluate_trade_request')
        from contextlib import ExitStack
        with ExitStack() as stack:
            spies = [stack.enter_context(patch('routes.trades.' + name,
                         side_effect=AssertionError('Blocked Custom must not calculate: ' + name)))
                     for name in forbidden]
            for endpoint, extra in self.operations:
                with self.subTest(endpoint=endpoint, workflow=extra.get('workflow')):
                    result = self.fixture.trade('custom', endpoint=endpoint, **extra)
                    self.assertEqual(result.status_code, 409, result.text)
                    detail = result.json()['detail']
                    self.assertEqual(detail['code'], 'personal_evidence_unavailable')
                    self.assertIn('b', detail['message'])
                    self.assertEqual(detail['recovery_url'], workspace['recovery_url'])
                    self.assertNotIn('evaluation', result.json())
                    self.assertNotIn('results', result.json())
                    results.append({'endpoint': endpoint, 'workflow': extra.get('workflow'),
                                    'status': result.status_code, 'detail': detail})
            for spy in spies:
                spy.assert_not_called()
        self.assertEqual(self.document(), before)
        neutral = self.fixture.trade('neutral')
        self.assertEqual(neutral.status_code, 200, neutral.text)
        self.assertEqual(neutral.json()['evaluation']['recommendation'], 'WORTH PURSUING')
        self.evidence('blocked-custom-workflows', {'results': results, 'heavy_trade_calls': 0,
                      'saved_document_unchanged': True, 'neutral_status': neutral.status_code})

    def test_explicit_one_asset_recovery_restores_all_supported_custom_workflows(self):
        self.editor.post('reorder', asset_id='player:a', to_position=1)
        self.editor.post('tiers', asset_id='player:c', tier_start=True)
        before = self.document()
        neutral_before = self.fixture.trade('neutral').json()['evaluation']
        custom_before = self.fixture.trade('custom').json()['evaluation']
        self.make_one_price_unavailable()
        removed = self.recover()
        self.assertEqual(removed.status_code, 200, removed.text)
        after = self.document()
        self.assertEqual(after['order'], [key for key in before['order'] if key != 'player:b'])
        self.assertEqual(after['tiers'], before['tiers'])
        self.assertEqual(after['preferences'], before['preferences'])
        self.assertEqual(after['revision'], before['revision'] + 1)
        self.assertTrue(removed.json()['personal_available'])
        results = []
        for endpoint, extra in self.operations:
            with self.subTest(endpoint=endpoint, workflow=extra.get('workflow')):
                result = self.fixture.trade('custom', endpoint=endpoint, **extra)
                self.assertEqual(result.status_code, 200, result.text)
                results.append({'endpoint': endpoint, 'workflow': extra.get('workflow'),
                                'status': result.status_code,
                                'result_count': result.json().get('count')})
        custom = self.fixture.trade('custom').json()['evaluation']
        neutral = self.fixture.trade('neutral').json()['evaluation']
        for key in ('market_evidence', 'lineup_impact', 'multi_horizon_impact', 'player_facts'):
            self.assertEqual(neutral[key], neutral_before[key], key)
            self.assertEqual(custom[key], neutral[key], key)
        for key in ('recommendation', 'generated_trade_eligible', 'personal_value_evidence'):
            if key == 'personal_value_evidence':
                for side in ('sent', 'received'):
                    self.assertEqual(custom[key][side], custom_before[key][side])
            else:
                self.assertEqual(custom[key], custom_before[key], key)
        self.assertEqual(custom['dimensions']['counterparty_plausibility'],
                         neutral['dimensions']['counterparty_plausibility'])
        self.evidence('recovered-custom-workflows', {'results': results,
                      'order_preserved_except_explicit_asset': True,
                      'neutral_market_lineup_and_counterparty_unchanged': True,
                      'custom_recommendation': custom['recommendation'],
                      'neutral_recommendation': neutral['recommendation']})

    def test_removal_preserves_sparse_protection_and_exact_pick_identity_in_neutral_trade(self):
        for asset in ('player:b', 'pick:2028:1:3'):
            result = self.editor.post('preferences', asset_id=asset, preferences={'protect': True})
            self.assertEqual(result.status_code, 200, result.text)
        before = self.document()
        self.make_one_price_unavailable()
        self.assertEqual(self.recover().status_code, 200)
        self.assertEqual(self.document()['preferences'], before['preferences'])
        generated = self.fixture.trade('neutral', endpoint='generate', workflow='recommended',
                                       partner_roster_id=0)
        self.assertEqual(generated.status_code, 200, generated.text)
        locks = generated.json()['constraints']['protected_assets']
        self.assertIn('b', locks)
        self.assertIn('2028-R1-3', locks)
        self.assertNotIn('2028-R1-4', locks)
        for row in generated.json()['results']:
            self.assertTrue({'b', '2028-R1-3'}.isdisjoint(row['proposal']['assets_sent']))

    def test_removed_asset_never_receives_an_invented_custom_price_or_endorsement(self):
        self.make_one_price_unavailable()
        self.assertEqual(self.recover().status_code, 200)
        calculator = self.fixture.trade('custom', endpoint='calculate', assets_sent=['b'])
        self.assertEqual(calculator.status_code, 200, calculator.text)
        self.assertIsNone(calculator.json()['personal']['sent']['total'])
        self.assertEqual(calculator.json()['personal']['sent']['missing_asset_ids'], ['b'])
        self.assertIsNotNone(calculator.json()['market']['sent']['total'])
        evaluated = self.fixture.trade('custom', assets_sent=['b'])
        self.assertEqual(evaluated.status_code, 422, evaluated.text)
        self.assertEqual(evaluated.json()['detail']['code'], 'personal_evidence_unavailable')
        self.assertNotIn('evaluation', evaluated.json())

    def test_recovery_revision_and_source_transition_withhold_inflight_trade_result(self):
        from services.trade_intelligence import evaluate_trade_request
        self.make_one_price_unavailable()
        self.assertEqual(self.recover().status_code, 200)

        def evaluate_then_change_source(*args, **kwargs):
            result = evaluate_trade_request(*args, **kwargs)
            self.editor.market.semantic_generation = 'semantic-replaced-during-evaluation'
            return result

        with patch('routes.trades.evaluate_trade_request', side_effect=evaluate_then_change_source):
            changed = self.fixture.trade('custom')
        self.assertEqual(changed.status_code, 409, changed.text)
        self.assertEqual(changed.json()['detail']['code'], 'personal_context_changed')
        self.assertNotIn('evaluation', changed.json())
        retry = self.fixture.trade('custom')
        self.assertEqual(retry.status_code, 200, retry.text)

    def test_stale_recovery_cannot_change_newer_order_or_restore_stale_trade_context(self):
        self.make_one_price_unavailable()
        state = self.editor.state()
        workspace = self.editor.client.get('/api/trades/workspace').json()
        moved = self.editor.post('reorder', asset_id='player:a', to_position=1)
        self.assertEqual(moved.status_code, 200, moved.text)
        latest = self.document()
        stale = self.recover(state=state)
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertEqual(self.document(), latest)
        payload = {'workflow': 'create', 'active_roster_id': 1, 'partner_roster_id': 2,
                   'assets_sent': ['a'], 'assets_received': ['2028-R1-4'], 'strategy': 'REBUILD',
                   'workspace_context': workspace['workspace_context'], 'valuation_mode': 'custom',
                   'personal_revision': state['revision'], 'personal_market_generation': state['generation']}
        stale_trade = self.editor.client.post('/api/trades/evaluate', json=payload,
                           headers={'X-CSRF-Token': self.editor.csrf})
        self.assertEqual(stale_trade.status_code, 409, stale_trade.text)
        self.assertEqual(stale_trade.json()['detail']['code'], 'personal_revision_changed')
        self.assertNotIn('evaluation', stale_trade.json())
        self.assertEqual(self.document(), latest)

import unittest
from copy import deepcopy
from unittest.mock import patch

from services.trade_intelligence import build_trade_workspace, evaluate_trade_request, generate_trade_workflow
from src.core.trade_intelligence.engine.trade_generator import generate_proposals
from tests.test_batch5_trade_strategy import asset, side
from tests.test_trade_intelligence import fixture_data
from services.shop_asset_search import preference, rank_returns


class ShopAssetFoundationTests(unittest.TestCase):
    def test_active_workflow_preference_changes_market_order_not_assessment(self):
        from src.core.trade_intelligence.models import TradeProposal
        data = fixture_data()
        recorded = []
        def construct(active, partner, outgoing, incoming, **kwargs):
            target = next(a for a in outgoing if a.asset_id == kwargs['required_sent_asset_id'])
            return (TradeProposal(active, partner, (target,), (incoming[0],), 'fixture'),)
        def evaluate(source, payload, **kwargs):
            partner = payload['partner_roster_id']
            result = {'proposal': deepcopy(payload), 'evaluation': {
                'generated_trade_eligible': True, 'recommendation': 'SMASH ACCEPT' if partner == 2 else 'WORTH PURSUING',
                'provenance': {'evaluation_id': str(partner)}, 'dimensions': {
                    'counterparty_plausibility': {'assessment': 'PLAUSIBLE', 'explanation': 'Fixture supported benefit'},
                    'confidence': {'assessment': 'MEDIUM'},
                    'package_quality': {'active': {'incoming_lineup_contributors': payload['assets_received']}},
                    'strategic_fit': {'active': {'horizons': {'current_week': {'delta': 1 if partner == 2 else 8}},
                                                'future_capital': {'received': []}}}}}}
            recorded.append(deepcopy(result['evaluation']))
            return result
        with patch('services.trade_intelligence.generate_proposals', side_effect=construct), \
                patch('services.trade_intelligence.evaluate_trade_request', side_effect=evaluate):
            base = generate_trade_workflow(data, {'workflow': 'shop', 'active_roster_id': 1, 'asset_id': '1-QB-0'})
            win = generate_trade_workflow(data, {'workflow': 'shop', 'active_roster_id': 1, 'asset_id': '1-QB-0', 'shop_preference': 'win_now'})
        self.assertEqual([m['counterparty_roster_id'] for m in base['markets']], [2, 3])
        self.assertEqual([m['counterparty_roster_id'] for m in win['markets']], [3, 2])
        self.assertEqual(recorded[:2], recorded[2:])
        self.assertEqual(base['count'], 2)  # Never force five markets.

    def test_mid_search_player_pick_and_market_changes_discard_shop(self):
        for kind in ('shopped_player', 'return_player', 'pick', 'market'):
            with self.subTest(kind=kind):
                data = fixture_data()
                changed = []
                def mutation(*args, **kwargs):
                    if not changed:
                        if kind == 'shopped_player':
                            data['teams'][0]['players'].pop(0)
                        elif kind == 'return_player':
                            data['teams'][1]['players'].pop(0)
                        elif kind == 'pick':
                            data['teams'][1]['picks_owned'][0]['current_owner_id'] = 3
                        else:
                            data['market_data']['generation'] = 'new'
                        changed.append(True)
                    return ()
                with patch('services.trade_intelligence.generate_proposals', side_effect=mutation):
                    with self.assertRaisesRegex(ValueError, 'Canonical evidence changed'):
                        generate_trade_workflow(data, {'workflow': 'shop', 'active_roster_id': 1, 'asset_id': '1-QB-0'})

    def test_preferences_are_request_local(self):
        data = fixture_data()
        with patch('src.core.trade_intelligence.horizon_impact.evaluate_horizon_impact', return_value={'availability': 'unavailable'}):
            first = generate_trade_workflow(data, {'workflow': 'shop', 'active_roster_id': 1,
                'asset_id': '1-QB-0', 'shop_preference': 'position_need', 'shop_position': 'WR'})
            second = generate_trade_workflow(data, {'workflow': 'shop', 'active_roster_id': 1, 'asset_id': '1-QB-1'})
        self.assertEqual(first['shop_preference']['name'], 'position_need')
        self.assertEqual(second['shop_preference']['name'], 'best_overall')
        self.assertIsNone(second['shop_preference']['position'])
        self.assertNotIn('shop_preference', data)

    def test_preference_order_is_explicit_and_does_not_change_shared_results(self):
        from dataclasses import replace
        assets = {'old': replace(asset('old', 900, 2), position='WR', age=30),
                  'young': replace(asset('young', 100, 2), position='WR', age=22)}
        def row(pid, recommendation, delta):
            return {'proposal': {'assets_received': [pid]}, 'evaluation': {
                'recommendation': recommendation, 'provenance': {'evaluation_id': pid},
                'dimensions': {'confidence': {'assessment': 'MEDIUM'},
                    'counterparty_plausibility': {'assessment': 'PLAUSIBLE'},
                    'package_quality': {'active': {'assessment': 'BOUNDED CONTRIBUTION', 'incoming_lineup_contributors': [pid]}},
                    'strategic_fit': {'active': {'horizons': {'current_week': {'delta': delta}}, 'future_capital': {'received': []}}}}}}
        rows = [row('old', 'SMASH ACCEPT', 1), row('young', 'FAIR / OPTIONAL', 7)]
        before = deepcopy(rows)
        self.assertEqual(rank_returns(rows, assets, preference({}))[0][0], rows[0])
        self.assertEqual(rank_returns(rows, assets, preference({'shop_preference': 'win_now'}))[0][0], rows[1])
        self.assertEqual(rows, before)
        rows[1]['evaluation']['recommendation'] = 'SMASH ACCEPT'
        self.assertEqual(rank_returns(rows, assets, preference({'shop_preference': 'youth_rebuild'}))[0][0], rows[1])
        self.assertEqual(rank_returns(rows, assets, preference({'shop_preference': 'draft_capital'})), [])
        rows[0]['evaluation']['dimensions']['package_quality']['active']['incoming_lineup_contributors'] = []
        ranked = rank_returns(rows, assets, preference({'shop_preference': 'position_need', 'shop_position': 'WR'}))
        self.assertEqual([row[0] for row in ranked], [rows[1]])

    def test_preference_constraints_change_construction_before_evaluation(self):
        from dataclasses import replace
        outgoing = (asset('target', 100, 1),)
        incoming = (asset('qb', 100, 2), replace(asset('wr', 50, 2), position='WR'),
                    replace(asset('pick', 50, 2), kind='pick', position=None, season=2027, round=1))
        for pref in ({'shop_preference': 'draft_capital'}, {'shop_preference': 'position_need', 'shop_position': 'WR'}):
            rows = generate_proposals(1, 2, outgoing, incoming, required_sent_asset_id='target',
                                     construction_only=True, return_preference=preference(pref))
            self.assertTrue(rows)
            for row in rows:
                if pref['shop_preference'] == 'draft_capital':
                    self.assertTrue(any(a.kind == 'pick' for a in row.assets_received))
                else:
                    self.assertTrue(any(a.position == 'WR' for a in row.assets_received))

    def test_invalid_or_conflicting_preferences_reject_instead_of_silent_ignore(self):
        for payload in ({'shop_preference': 'invented'}, {'shop_preference': 'position_need'},
                        {'shop_preference': 'win_now', 'shop_position': 'WR'}, {'shop_preference': ['win_now', 'draft_capital']}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                preference(payload)
        self.assertEqual(preference({})['name'], 'best_overall')

    def test_only_currently_owned_explicit_asset_can_be_shopped(self):
        for target in ('', '2-QB-0', 'unknown'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                generate_trade_workflow(fixture_data(), {'workflow': 'shop', 'active_roster_id': 1, 'asset_id': target})

    def test_bounded_returns_preserve_shopped_asset_and_sides_without_legacy_brain(self):
        outgoing = (asset('target', 100, 1), asset('extra', 20, 1))
        incoming = tuple(asset(str(i), i + 1, 2) for i in range(20))
        diagnostics = {}
        with patch('src.core.trade_intelligence.engine.trade_generator._value', side_effect=AssertionError('legacy price')), \
                patch('src.core.trade_intelligence.engine.trade_generator.evaluate_trade_guardrails', side_effect=AssertionError('legacy grade')):
            rows = generate_proposals(1, 2, outgoing, incoming, required_sent_asset_id='target',
                                      construction_only=True, search_diagnostics=diagnostics)
        self.assertTrue(rows)
        self.assertLessEqual(len(rows), 6)
        for row in rows:
            self.assertEqual((row.active_roster_id, row.partner_roster_id), (1, 2))
            self.assertIn('target', [a.asset_id for a in row.assets_sent])
            self.assertTrue(all(a.source_roster_id == 2 for a in row.assets_received))
        self.assertIn('target', diagnostics['shortlisted_asset_ids']['sent'])
        self.assertNotIn('target', diagnostics['shortlisted_asset_ids']['received'])

    def test_shop_uses_identical_manual_shared_assessment(self):
        data = fixture_data()
        workspace = build_trade_workspace(data, 1)
        payload = {'active_roster_id': 1, 'partner_roster_id': 2, 'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0']}
        impact = {'sides': {'active': side(1, 5), 'partner': side(2, -5)}}
        before = deepcopy(data)
        with patch('src.core.trade_intelligence.horizon_impact.evaluate_horizon_impact', return_value=impact):
            manual = evaluate_trade_request(data, {**payload, 'workflow': 'create'}, workspace=workspace)
            shop = evaluate_trade_request(data, {**payload, 'workflow': 'shop'}, workspace=workspace)
        self.assertEqual(manual['evaluation'], shop['evaluation'])
        self.assertEqual(data, before)

    def test_no_forced_markets_and_all_proposals_use_shared_evaluator(self):
        data = fixture_data()
        before = deepcopy(data)
        with patch('src.core.trade_intelligence.horizon_impact.evaluate_horizon_impact', return_value={'availability': 'unavailable'}), \
                patch('services.trade_intelligence.evaluate_trade_request', wraps=evaluate_trade_request) as evaluate:
            result = generate_trade_workflow(data, {'workflow': 'shop', 'active_roster_id': 1, 'asset_id': '1-QB-0'})
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['search_evidence']['partner_count'], 2)
        self.assertGreater(evaluate.call_count, 0)
        self.assertLessEqual(evaluate.call_count, 12)
        readers = [call.kwargs['projection_reader'] for call in evaluate.call_args_list]
        self.assertTrue(all(reader is readers[0] for reader in readers))
        self.assertEqual(evaluate.call_count, result['search_evidence']['full_evaluations'])
        self.assertEqual(data, before)

    def test_protected_shopped_asset_does_not_get_evaluated_or_replaced(self):
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=AssertionError('protected asset evaluated')):
            result = generate_trade_workflow(fixture_data(), {'workflow': 'shop', 'active_roster_id': 1,
                'asset_id': '1-QB-0', 'protected_assets': ['1-QB-0']})
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['target_asset_id'], '1-QB-0')


if __name__ == '__main__':
    unittest.main()

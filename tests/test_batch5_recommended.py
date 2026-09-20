"""Recommended workflow migration: shared semantics before search calibration."""
import unittest
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from services.trade_intelligence import build_trade_workspace, evaluate_trade_request, generate_trade_workflow
from services.recommended_trade_search import discover, session_constraints, family_identity, surface_evidence
from src.core.trade_intelligence.models import TradeProposal
from tests.test_batch5_trade_strategy import asset
from tests.test_batch5_trade_strategy import side
from tests.test_trade_intelligence import fixture_data


class RecommendedBoundaryTests(unittest.TestCase):
    def test_stable_gain_is_not_timing_and_known_bye_context_is_bounded(self):
        row = {'evaluation': {'multi_horizon_impact': {'team_strength_generation': 'g',
                'sides': {'active': {'weekly': {2: {'delta': 2, 'pre': {}}}}}},
                'dimensions': {'strategic_fit': {'active': {'horizons': {
                    'next_n': {'delta': 2, 'availability': 'complete', 'weeks_requested': [2, 3]}}}}}}}
        stable = surface_evidence(row)
        self.assertEqual(stable['why_now']['availability'], 'unavailable')
        self.assertEqual(len(stable['stable_opportunity_reasons']), 1)
        week = row['evaluation']['multi_horizon_impact']['sides']['active']['weekly'][2]
        week['pre']['known_bye_player_ids'] = ['p']
        result = surface_evidence(row)
        self.assertEqual(result['why_now']['catalysts'][0]['type'], 'UPCOMING_BYE_LINEUP_FIT')
        row['evaluation']['dimensions']['strategic_fit']['active']['horizons']['next_n']['weeks_requested'] = [3]
        self.assertEqual(surface_evidence(row)['why_now']['availability'], 'unavailable')

    def test_front_office_only_request_preserves_model_and_separates_result_cache(self):
        from src.core.intelligence.orchestrator import IntelligenceOrchestrator
        from src.core.intelligence.cache import IntelligenceCache
        from src.core.intelligence.registry import IntelligenceRegistry
        registry = IntelligenceRegistry()
        calls = []
        registry.register('trade', lambda *args: calls.append('trade') or ())
        engine = IntelligenceOrchestrator(registry=registry, cache=IntelligenceCache())
        data = fixture_data()
        context_only = engine.analyze(data, 1, include_trade_opportunities=False)
        self.assertEqual(calls, [])
        full = engine.analyze(data, 1)
        self.assertEqual(calls, ['trade'])
        self.assertEqual(context_only.front_office_model, full.front_office_model)
        engine.analyze(data, 1, include_trade_opportunities=False)
        self.assertEqual(calls, ['trade'])

    def test_navigation_does_not_run_or_claim_a_completed_search(self):
        from services.trade_intelligence import build_trade_center
        from components.trade_intelligence import trade_center
        with patch('src.core.intelligence.orchestrator.intelligence_orchestrator.analyze', side_effect=AssertionError('search on navigation')):
            result = build_trade_center(fixture_data(), 1)
        self.assertEqual(result['search_state'], 'not_started')
        self.assertIn('No recommendation search has run', trade_center(result))

    def test_recommended_rejects_wrong_league_and_midsearch_change(self):
        from types import SimpleNamespace
        with patch('src.platform.league_context.current_league_context', return_value=SimpleNamespace(league_id='other')):
            with self.assertRaisesRegex(ValueError, 'league context changed'):
                generate_trade_workflow(fixture_data(), {'workflow': 'recommended', 'active_roster_id': 1})
        data = fixture_data()
        def changed(*args, **kwargs):
            data['teams'][0]['players'].pop()
            return {'theses': [], 'discovery_seconds': 0}
        with patch('services.recommended_trade_search.discover', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'Canonical evidence changed'):
                generate_trade_workflow(data, {'workflow': 'recommended', 'active_roster_id': 1})

    def test_value_tag_means_price_edge_not_sell_high_or_intrinsic_bargain(self):
        row = {'evaluation': {'market_evidence': {'availability': 'full', 'difference': 10}}}
        result = surface_evidence(row)
        self.assertEqual(result['reason_tags'], ['VALUE OPPORTUNITY'])
        self.assertEqual(result['why_now']['availability'], 'unavailable')
        row['evaluation']['market_evidence']['availability'] = 'partial'
        self.assertEqual(surface_evidence(row)['reason_tags'], [])

    def test_discovery_uses_eligible_slots_not_roster_counts_or_market_prices(self):
        from types import SimpleNamespace
        a, b = asset('a', 100, 1), asset('b', 1, 2)
        workspace = {'active_roster_id': 1, 'pools': {1: (a,), 2: (b,)}}
        def weekly(pid):
            return {2: {'available': True, 'optimal': {'entries': [
                {'asset_id': pid, 'slot': 'QB', 'position': 'QB', 'projected_points': 1}]}}}
        profile = {'league_id': 'L', 'season': 2026, 'current_week': 2, 'semantic_generation': 'G',
                   'projection_generation': 'P', 'scoring_profile_id': 'S',
                   'teams': {'1': {'weekly': weekly('a')}, '2': {'weekly': weekly('b')}}}
        snapshot = {'league_id': 'L', 'season': 2026, 'week': 2, 'horizon_generation': 'P',
                    'scoring_profile_id': 'S', 'players': {'a': {'canonical_projection': 2}, 'b': {'canonical_projection': 3}}}
        reader = SimpleNamespace(snapshot=lambda: {}, week_snapshot=lambda *args, **kwargs: snapshot)
        with patch('services.recommended_trade_search.compatible_profile', return_value=profile):
            found = discover({}, workspace, reader, set(), set())
            self.assertEqual(len(found['theses']), 1)
            self.assertEqual(found['theses'][0]['receive']['asset_id'], 'b')
            refreshed = discover({}, workspace, reader, set(), set(), excluded_families={found['theses'][0]['family_id']})
            self.assertEqual(refreshed['theses'], [])
            self.assertEqual(refreshed['session_excluded_theses'], 1)
            c = asset('c', 1, 3)
            workspace['pools'][3] = (c,)
            profile['teams']['3'] = {'weekly': weekly('c')}
            snapshot['players']['c'] = {'canonical_projection': 4}
            advanced = discover({}, workspace, reader, set(), set(), max_theses=1,
                                excluded_families={found['theses'][0]['family_id']})
            self.assertEqual(len(advanced['theses']), 1)
            self.assertEqual(advanced['theses'][0]['receive']['asset_id'], 'c')
            self.assertEqual(discover({}, workspace, reader, {'a'}, set())['theses'], [])
            profile['teams']['1']['weekly'][2]['optimal']['entries'][0]['slot'] = 'TE'
            self.assertEqual(discover({}, workspace, reader, set(), set())['theses'], [])

    def test_missing_compatible_strength_returns_no_invented_opportunity(self):
        with patch('services.recommended_trade_search.compatible_profile', return_value=None):
            from types import SimpleNamespace
            result = discover({}, {'active_roster_id': 1, 'pools': {1: (), 2: ()}},
                              SimpleNamespace(snapshot=lambda: {}), set(), set())
        self.assertFalse(result['theses'])
        self.assertIn('COMPATIBLE_PREPARED_LINEUPS_UNAVAILABLE', result['limitations'])

    def test_no_false_change_catalyst_from_unrelated_or_incompatible_evidence(self):
        row = {'evaluation': {'retrieved_at': 'today', 'market_history': [1, 999],
               'projection_history': {'week2': 1, 'week3': 99}, 'fois': {'trades': 500},
               'pick_range': 'EARLY', 'roster_count': 99, 'playoff_seed': 1}}
        result = surface_evidence(row)
        self.assertEqual(result['reason_tags'], [])
        self.assertEqual(result['why_now']['availability'], 'unavailable')
        self.assertIsNone(result['why_now']['urgency'])

    def test_current_state_catalyst_is_not_historical_movement(self):
        result = surface_evidence({'evaluation': {'multi_horizon_impact': {'team_strength_generation': 'g'},
            'dimensions': {'strategic_fit': {'active': {'horizons': {
                'playoff_window': {'delta': 5, 'availability': 'complete', 'weeks_requested': [14, 15]}}}}}}})
        self.assertEqual(result['reason_tags'], ['ROSTER CONSTRUCTION'])
        self.assertEqual(result['why_now']['catalysts'][0]['temporal_claim'], 'current_state_not_historical_movement')
        self.assertIsNone(result['why_now']['historical_movement'])

    def test_refresh_family_ignores_equivalent_pick_sweetener_and_is_league_bound(self):
        assets = {'a': asset('a', 20, 1), 'b': asset('b', 20, 2),
                  'p1': replace(asset('p1', 1, 1), kind='pick'), 'p2': replace(asset('p2', 1, 1), kind='pick')}
        p = {'active_roster_id': 1, 'partner_roster_id': 2, 'assets_sent': ['a', 'p1'], 'assets_received': ['b']}
        first = family_identity('L', {'proposal': p}, assets)
        p['assets_sent'] = ['a', 'p2']
        self.assertEqual(first, family_identity('L', {'proposal': p}, assets))
        self.assertNotEqual(first, family_identity('other', {'proposal': p}, assets))
        self.assertEqual(session_constraints({'excluded_recommendation_families': [first]})[1], {first})
        with self.assertRaises(ValueError):
            session_constraints({'excluded_recommendation_families': [first] * 65})
        with self.assertRaises(ValueError):
            session_constraints({'recommendation_filter': ['invalid']})

    def test_active_recommended_fair_and_session_exclusion_no_legacy_generator(self):
        data = fixture_data()
        before = deepcopy(data)
        workspace = build_trade_workspace(data, 1)
        sent = next(a for a in workspace['pools'][1] if a.asset_id == '1-QB-0')
        received = next(a for a in workspace['pools'][2] if a.asset_id == '2-QB-0')
        proposal = TradeProposal(1, 2, (sent,), (received,), 'fixture')
        def assessed(source, payload, **kwargs):
            return {'proposal': deepcopy(payload), 'evaluation': {'generated_trade_eligible': False,
                'recommendation': 'FAIR / OPTIONAL', 'legal': True,
                'legality': {'execution_status': 'NO IDENTIFIED OWNERSHIP OR CAPACITY BLOCKER'},
                'dimensions': {'counterparty_plausibility': {'assessment': 'PLAUSIBLE'}, 'confidence': {'assessment': 'MEDIUM'}},
                'provenance': {'evaluation_id': 'one'}}}
        with patch('services.recommended_trade_search.discover', return_value={'theses': [{}], 'discovery_seconds': 0}), \
                patch('services.recommended_trade_search.construct', return_value=[proposal]), \
                patch('services.trade_intelligence.evaluate_trade_request', side_effect=assessed), \
                patch('src.core.trade_intelligence.engine.trade_generator._value', side_effect=AssertionError('legacy')):
            result = generate_trade_workflow(data, {'workflow': 'recommended', 'active_roster_id': 1})
            self.assertEqual(result['count'], 1)
            family = result['results'][0]['family_id']
            refreshed = generate_trade_workflow(data, {'workflow': 'recommended', 'active_roster_id': 1,
                'excluded_recommendation_families': [family]})
            self.assertEqual(refreshed['count'], 0)
            self.assertEqual(generate_trade_workflow(data, {'workflow': 'recommended', 'active_roster_id': 1})['count'], 1)
        self.assertEqual(data, before)

    def test_recommended_package_uses_exact_manual_multi_horizon_assessment(self):
        data = fixture_data()
        before = deepcopy(data)
        workspace = build_trade_workspace(data, 1)
        payload = {'active_roster_id': 1, 'partner_roster_id': 2,
                   'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0']}
        for impact in ({'sides': {'active': side(1, 5), 'partner': side(2, -5)}},
                       {'availability': 'unavailable'}):
            with self.subTest(impact=impact), patch(
                'src.core.trade_intelligence.horizon_impact.evaluate_horizon_impact', return_value=impact,
            ) as horizon:
                manual = evaluate_trade_request(data, {**payload, 'workflow': 'create'}, workspace=workspace)
                recommended = evaluate_trade_request(data, {**payload, 'workflow': 'recommended'}, workspace=workspace)
                self.assertEqual(horizon.call_count, 2)
                self.assertEqual(manual['evaluation'], recommended['evaluation'])
        self.assertEqual(data, before)


if __name__ == '__main__':
    unittest.main()

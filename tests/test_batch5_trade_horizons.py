import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests import test_batch5_team_strength as strength_tests
from src.core.intelligence.team_strength import prepare_for_data
from src.core.trade_intelligence.horizon_impact import evaluate_horizon_impact


class TradeHorizonTests(unittest.TestCase):
    def setUp(self):
        strength_tests.TeamStrengthTests.setUp(self)
        self.data['league'].update(sport='nfl', roster_positions=['QB', 'BN'], settings={
            'leg': 2, 'last_scored_leg': 1, 'start_week': 1, 'playoff_week_start': 4,
            'playoff_teams': 4, 'playoff_round_type': 0, 'playoff_type': 0})
        self.data['teams'] = [{'roster_id': r['roster_id'], 'players': [
            {'id': pid, 'position': 'QB', 'roster_slot': 'Starter' if pid in r['starters'] else 'Bench'}
            for pid in r['players']]} for r in self.rosters]
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.service, self.data)

    def proposal(self, sent='a', received='c'):
        return SimpleNamespace(active_roster_id=1, partner_roster_id=2,
            assets_sent=(SimpleNamespace(asset_id='player:'+sent, kind='player'),),
            assets_received=(SimpleNamespace(asset_id='player:'+received, kind='player'),))

    def test_both_sides_optimal_not_submitted_and_no_mutation(self):
        before = copy.deepcopy(self.data)
        result = evaluate_horizon_impact(self.data, self.proposal(), self.service)
        active, partner = result['sides']['active'], result['sides']['partner']
        self.assertEqual(active['horizons']['current_week']['delta'], -2)
        self.assertEqual(partner['horizons']['current_week']['delta'], 2)
        self.assertEqual(active['horizons']['next_n']['delta'], -6)
        self.assertEqual(active['horizons']['playoff_window']['delta'], -4)
        self.assertEqual(active['weekly'][2]['pre']['optimal']['entries'][0]['asset_id'], 'a')
        self.assertEqual(self.data, before)
        evaluate_horizon_impact(self.data, self.proposal('b', 'd'), self.service)
        self.assertEqual(evaluate_horizon_impact(self.data, self.proposal(), self.service), result)
        self.assertEqual(self.data, before)

    def test_wrong_owner_or_league_fails_closed(self):
        self.assertEqual(evaluate_horizon_impact(self.data, self.proposal('c', 'a'), self.service)['reason_codes'], ['PLAYER_OWNERSHIP_MISMATCH'])
        self.data['league']['league_id'] = 'B'
        self.assertEqual(evaluate_horizon_impact(self.data, self.proposal(), self.service)['availability'], 'unavailable')

    def test_stale_dependencies_are_unavailable_not_legacy_fallbacks(self):
        mutations = {
            'season': lambda d: d['league'].update(season=2027),
            'roster': lambda d: d['teams'][0]['players'].pop(),
            'rules': lambda d: d['league']['roster_positions'].append('QB'),
            'methodology': lambda d: d['team_strength'].update(methodology_version='retired'),
            'projection_generation': lambda d: d['team_strength'].update(projection_generation='stale'),
            'scoring': lambda d: d.update(scoring_settings={'pass_yd': 2}),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                data = copy.deepcopy(self.data)
                mutate(data)
                result = evaluate_horizon_impact(data, self.proposal(), self.service)
                self.assertEqual(result['availability'], 'unavailable')
                self.assertEqual(result['reason_codes'], ['COMPATIBLE_TEAM_STRENGTH_UNAVAILABLE'])

    def test_independent_fois_generation_does_not_require_projection_rebuild(self):
        before = evaluate_horizon_impact(self.data, self.proposal(), self.service)
        self.data['front_office_evidence'] = {'league_id': 'A', 'generation': 'historical-independent'}
        self.assertEqual(evaluate_horizon_impact(self.data, self.proposal(), self.service), before)

    def test_reuses_pretrade_profile_and_only_prepares_two_hypothetical_rosters(self):
        from src.core.intelligence.team_strength import prepare_team_strength
        with patch('src.core.trade_intelligence.horizon_impact.prepare_team_strength', wraps=prepare_team_strength) as prepare:
            first = evaluate_horizon_impact(self.data, self.proposal(), self.service)
            second = evaluate_horizon_impact(self.data, self.proposal('b', 'd'), self.service)
        self.assertEqual(prepare.call_count, 2)
        self.assertTrue(all(len(call.kwargs['rosters']) == 2 for call in prepare.call_args_list))
        self.assertEqual(first['sides']['active']['weekly'][2]['pre'], second['sides']['active']['weekly'][2]['pre'])
        self.assertNotEqual(first['sides']['active']['weekly'][2]['post'], second['sides']['active']['weekly'][2]['post'])

    def test_search_projection_reuse_is_exact_and_generation_local(self):
        from services.trade_intelligence import _SearchProjectionReader
        proposals = [self.proposal(), self.proposal('b', 'd'), self.proposal()]
        expected = [evaluate_horizon_impact(self.data, p, self.service) for p in proposals]
        cached = _SearchProjectionReader(self.service)
        with patch.object(self.service, 'week_snapshot', wraps=self.service.week_snapshot) as reads:
            actual = [evaluate_horizon_impact(self.data, p, cached) for p in proposals]
        self.assertEqual(actual, expected)
        self.assertEqual(reads.call_count, len(cached.weeks))
        self.assertEqual(reads.call_count, 4)
        with self.assertRaisesRegex(ValueError, 'generation mismatch'):
            cached.week_snapshot(2, generation_snapshot=copy.deepcopy(cached.pinned))
        fresh = _SearchProjectionReader(self.service)
        self.assertEqual(fresh.weeks, {})

    def test_partial_horizon_has_no_numeric_delta(self):
        self.service.publish_horizon({2:self.payloads[2], 3:None, 4:self.payloads[4], 5:self.payloads[5]}, data=self.data, league_id='A', season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.service, self.data)
        result = evaluate_horizon_impact(self.data, self.proposal(), self.service)
        self.assertIsNone(result['sides']['active']['horizons']['next_n']['delta'])
        partial = result['sides']['active']['horizons']['next_n']
        self.assertNotIn(3, partial['comparable_weeks'])
        self.assertIsNotNone(partial['supported_week_delta_subtotal'])
        self.assertEqual(partial['availability'], 'partial_or_unavailable')
        self.assertEqual(result['sides']['active']['horizons']['current_week']['delta'], -2)

    def test_existing_evaluator_view_uses_same_canonical_entries(self):
        from src.core.trade_intelligence.bilateral import evaluate_bilateral
        from src.core.trade_intelligence.models import TradeAsset, TradeProposal
        def asset(pid, owner):
            return TradeAsset(pid, 'player', pid, 'QB', None, None, 100, None, 0, owner, trade_value=100)
        proposal = TradeProposal(1, 2, (asset('a', 1),), (asset('c', 2),), 'Manual')
        impact = evaluate_horizon_impact(self.data, proposal, self.service)
        result = evaluate_bilateral(proposal, active_team=self.data['teams'][0],
            partner_team=self.data['teams'][1], league=self.data['league'], horizon_impact=impact)
        self.assertEqual(result['lineup_impact']['active']['delta'], -2)
        self.assertEqual(result['lineup_impact']['active']['pre']['entries'][0]['asset_id'], 'a')
        unavailable = evaluate_bilateral(proposal, active_team=self.data['teams'][0],
            partner_team=self.data['teams'][1], league=self.data['league'],
            horizon_impact={'availability': 'unavailable'})
        self.assertIsNone(unavailable['lineup_impact']['active']['delta'])
        self.assertFalse(unavailable['lineup_impact']['active']['pre']['available'])

    def test_multiple_incoming_players_with_real_weekly_contribution_not_penalized(self):
        from src.core.trade_intelligence.package_quality import package_profile
        for week, rows in self.payloads.items():
            values = {'a': 4, 'b': 1, 'c': 8 if week % 2 == 0 else 7, 'd': 7 if week % 2 == 0 else 8}
            for row in rows:
                row['stats'] = {'pass_yd': values[row['player_id']]}
        self.service.publish_horizon(self.payloads, data=self.data, league_id='A', season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.service, self.data)
        proposal = self.proposal()
        proposal.assets_received += (SimpleNamespace(asset_id='player:d', kind='player'),)
        for asset in (*proposal.assets_sent, *proposal.assets_received):
            asset.trade_value = None
        impact = evaluate_horizon_impact(self.data, proposal, self.service)
        quality = package_profile(proposal.assets_received, proposal.assets_sent, impact['sides']['active'])
        self.assertEqual(quality['assessment'], 'USEFUL DEPTH')
        self.assertEqual(quality['incoming_lineup_contributors'], ['c', 'd'])
        self.assertFalse(quality['universal_package_discount'])
        self.assertIsNone(quality['market_concentration'])

    def test_market_fair_three_for_one_can_be_poor_actual_lineup_package(self):
        from src.core.trade_intelligence.package_quality import package_profile
        from src.core.trade_intelligence.market_balance import market_balance
        self.data['players'].append({'id': 'e', 'position': 'QB'})
        self.data['teams'][1]['players'].append({'id': 'e', 'position': 'QB', 'roster_slot': 'Bench'})
        for week, rows in self.payloads.items():
            rows.append({'player_id': 'e', 'season': 2026, 'week': week, 'stats': {'pass_yd': 1}, 'player': {'position': 'QB'}})
            for row in rows:
                row['stats'] = {'pass_yd': {'a': 10, 'b': 5, 'c': 3, 'd': 2, 'e': 1}[row['player_id']]}
        self.service.publish_horizon(self.payloads, data=self.data, league_id='A', season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.service, self.data)
        proposal = self.proposal()
        proposal.assets_received += tuple(SimpleNamespace(asset_id='player:'+pid, kind='player') for pid in ('d', 'e'))
        proposal.assets_sent[0].trade_value = 300
        for asset in proposal.assets_received:
            asset.trade_value = 100
        impact = evaluate_horizon_impact(self.data, proposal, self.service)
        quality = package_profile(proposal.assets_received, proposal.assets_sent, impact['sides']['active'])
        self.assertEqual(market_balance(proposal.assets_sent, proposal.assets_received)['ratio'], 1)
        self.assertEqual(quality['assessment'], 'POOR')
        self.assertEqual(quality['incoming_lineup_contributors'], [])
        self.assertIn('PACKAGE_STUFFING', quality['reason_codes'])

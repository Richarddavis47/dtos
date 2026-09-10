"""Exercise the real orchestrator, roster adapter, Team HQ and shared window."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from src.core.intelligence.cache import IntelligenceCache
from src.core.intelligence.orchestrator import IntelligenceOrchestrator
from services.team_headquarters import build_team_headquarters
from tests.test_trade_intelligence import fixture_data


class ActiveRosterGradingTests(unittest.TestCase):
    def test_dossier_rejects_unscoped_production_and_stale_brain_rank(self):
        player = self.data['teams'][0]['players'][0]
        key = player['id']
        player.update(recent_points=[99, 98], season_average=88, previous_season_average=77)
        self.data['valuation_intelligence'] = {'semantic_generation': 'legacy', 'assets': {
            f'player:{key}': {'ranks': {'global_market': {'overall': {'rank': 1}}}}}}
        result = self.engine.analyze(self.data, 1)
        value = result.player_values[key]
        self.assertEqual(value.production.status.value, 'unavailable')
        self.assertFalse(value.positional.scoped_ranks['global_market'])
        self.assertEqual(value.projection.projected_points, 15)

    def test_team_hq_secondary_grades_are_canonical_not_parallel(self):
        from services.team_headquarters import calculate_team_grades
        result = self.engine.analyze(self.data, 1)
        card = result.roster.team_intelligence[1]
        grades = calculate_team_grades([], self.data['teams'][0], result.roster)
        for key, dimension in (('Youth', card.youth), ('Depth', card.depth),
                               ('Flexibility', card.roster_flexibility),
                               ('Roster Construction', card.overall)):
            self.assertEqual(grades[key]['score'], dimension.score)
            self.assertEqual(grades[key]['grade'], dimension.grade)
            self.assertEqual(grades[key]['generation'], card.generation)
        unknown = calculate_team_grades([], self.data['teams'][0])
        self.assertTrue(all(row['score'] is None for row in unknown.values()))

    def setUp(self):
        self.data = fixture_data()
        self.snapshot = {'league_id': 'league-1', 'week': 1, 'projection_snapshot_id': 'p1',
            'players': {p['id']: {'week': 1, 'weekly_projected_points': 15}
                        for team in self.data['teams'] for p in team['players']}}
        self.patch = patch('src.core.projection_intelligence.projection_service.snapshot', side_effect=lambda: self.snapshot)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.engine = IntelligenceOrchestrator(cache=IntelligenceCache())

    def test_active_price_and_lineup_can_disagree_without_generic_grade(self):
        for team in self.data['teams']:
            for player in team['players']:
                key = player['id']
                self.snapshot['players'][key]['weekly_projected_points'] = 30 if team['roster_id'] == 1 else 10
                self.data['market_data']['providers']['FantasyCalc'][key]['value'] = 1000 if team['roster_id'] == 1 else 9000
        result = self.engine.analyze(self.data, 1)
        first, second = result.roster.team_intelligence[1], result.roster.team_intelligence[2]
        self.assertGreater(first.starting_lineup.score, second.starting_lineup.score)
        self.assertLess(first.market_asset_strength.score, second.market_asset_strength.score)
        self.assertEqual(first.market_asset_strength.category, 'Market asset strength')
        self.assertIsNone(first.dynasty.score)
        self.assertIsNone(first.overall.score)
        self.assertIsNone(first.future_strength)
        self.assertEqual(first.current_window.value, 'Unavailable')
        self.assertTrue(all(card.dynasty_value is None and card.overall_score is None for card in result.roster.players.values()))

    def test_active_elite_starters_and_deep_roster_are_distinct(self):
        for index, player in enumerate(self.data['teams'][0]['players']):
            self.snapshot['players'][player['id']]['weekly_projected_points'] = 40 if index < 7 else 1
        result = self.engine.analyze(self.data, 1)
        first, second = result.roster.team_intelligence[1], result.roster.team_intelligence[2]
        self.assertGreater(first.starting_lineup.score, second.starting_lineup.score)
        self.assertLess(first.depth.score, second.depth.score)
        self.assertNotEqual(result.team_assessment.roster_evidence.actual_starter_ids,
                            result.team_assessment.roster_evidence.optimal_starter_ids)

    def test_active_missing_and_partial_evidence_do_not_become_negative(self):
        missing = self.data['teams'][0]['players'][0]['id']
        del self.snapshot['players'][missing]
        del self.data['market_data']['providers']['FantasyCalc'][missing]
        result = self.engine.analyze(self.data, 1)
        card = result.team_assessment.team
        self.assertIsNone(card.starting_lineup.score)
        self.assertIsNone(card.market_asset_strength.score)
        self.assertEqual(card.current_window.value, 'Unavailable')
        self.assertNotEqual(card.overall.grade, 'F')

    def test_active_strong_current_lineup_and_older_profile_remain_distinct(self):
        from src.core.valuation.player_methodology import REFERENCE_SCORING
        prepared = {'league_id': 'league-1', 'season': 2026, 'generation': 'history1',
                    'reference_scoring': REFERENCE_SCORING, 'players': {}}
        for team in self.data['teams']:
            for player in team['players']:
                player['age'] = 34 if team['roster_id'] == 1 else 23
                self.data['players'][player['id']]['age'] = player['age']
                self.snapshot['players'][player['id']]['weekly_projected_points'] = 30 if team['roster_id'] == 1 else 12
                prepared['players'][player['id']] = {'reference_seasons': [
                    {'season': 2025, 'games': 17, 'ppg': 18, 'targets': 8, 'opportunities': 18}]}
        self.data['canonical_player_production'] = prepared
        result = self.engine.analyze(self.data, 1)
        older, younger = result.roster.team_intelligence[1], result.roster.team_intelligence[2]
        self.assertGreater(older.starting_lineup.score, younger.starting_lineup.score)
        self.assertLess(older.youth.score, younger.youth.score)
        self.assertEqual(older.youth.category, 'Longevity context')
        self.assertIsNone(older.future_outlook.score)

    def test_active_switch_generation_and_replay(self):
        first = self.engine.analyze(self.data, 1)
        self.engine.analyze(self.data, 2)
        same = self.engine.analyze(self.data, 1)
        self.assertEqual(first.team_assessment, same.team_assessment)
        self.snapshot = deepcopy(self.snapshot)
        self.snapshot['projection_snapshot_id'] = 'p2'
        self.snapshot['players'][self.data['teams'][0]['players'][0]['id']]['weekly_projected_points'] = 30
        changed = self.engine.analyze(self.data, 1)
        self.assertNotEqual(first.team_assessment.generation, changed.team_assessment.generation)
        self.assertNotEqual(first.team_assessment.projected_points, changed.team_assessment.projected_points)

    def test_team_hq_has_one_overall_conclusion_not_legacy_a_vs_f(self):
        with patch('services.team_headquarters.intelligence_orchestrator', self.engine):
            view = build_team_headquarters(self.data, 1)
        self.assertEqual(view['competitive_window'], view['assessment'].team.competitive_window)
        self.assertEqual(view['unified_recommendation'].competitive_window, view['competitive_window'])
        self.assertEqual(view['team_intelligence'].overall.grade, 'Unavailable')
        self.assertEqual(view['competitive_window'].classification.value, 'Unavailable')
        self.assertIn('unavailable', view['summary']['Overall Assessment'])
        self.assertTrue(all(p.overall_grade == 'Unavailable' for p in self.engine.analyze(self.data, 1).roster.players.values()))

    def test_real_league_switch_does_not_reuse_same_roster_or_player_ids(self):
        first = self.engine.analyze(self.data, 1)
        second_data = deepcopy(self.data)
        second_data['league']['league_id'] = 'league-2'
        self.snapshot = deepcopy(self.snapshot)
        self.snapshot['league_id'] = 'league-2'
        for row in self.snapshot['players'].values():
            row['weekly_projected_points'] = 7
        second = self.engine.analyze(second_data, 1)
        self.assertEqual(second.team_assessment.league_id, 'league-2')
        self.assertNotEqual(first.team_assessment.generation, second.team_assessment.generation)
        self.assertNotEqual(first.team_assessment.projected_points, second.team_assessment.projected_points)
        self.snapshot['league_id'] = 'league-1'
        for row in self.snapshot['players'].values():
            row['weekly_projected_points'] = 15
        returned = self.engine.analyze(self.data, 1)
        self.assertEqual(first.team_assessment, returned.team_assessment)

    def test_player_adapter_cannot_reintroduce_a_scalar_into_published_cards(self):
        result = self.engine.analyze(self.data, 1)
        for profile in result.player_values.values():
            self.assertIsNone(profile.dtos_dynasty.value)
            self.assertIsNone(profile.contender.value)
            self.assertIsNone(profile.rebuilder.value)
            self.assertIsNone(profile.value_gap)
            self.assertIsNone(profile.intelligence_card.dtos_intrinsic_value)
            self.assertEqual(profile.intelligence_card.trade_value, profile.market_consensus.value)
            self.assertEqual(profile.market_posture, 'Review evidence')
        self.assertTrue(all(card.overall_score is None for card in result.roster.players.values()))

    def test_dossier_renders_unavailable_from_actual_report_path(self):
        from components.asset_intelligence import player_dossier
        player = self.data['teams'][0]['players'][0]
        report = self.engine.player_report(self.data, player, 1)
        self.assertIsNone(report.core_values.dynasty.score)
        self.assertIsNone(report.core_values.redraft.score)
        self.assertIsNone(report.core_values.team_fit.score)
        self.assertIsNone(report.opportunity['2-Year Outlook'].score)
        self.assertIsNone(report.value_profile.dtos_dynasty.value)
        self.assertEqual(report.value_profile.lineup.actual_starter, player['roster_slot'] == 'Starter')
        html = player_dossier(report, self.data['teams'][0], self.data['teams'])
        self.assertIn('Unavailable', html)
        self.assertNotIn('>None', html)
        self.assertNotIn('Strong Buy', html)

    def test_old_generation_card_is_rejected_and_crawl_cache_tracks_generation(self):
        from dataclasses import replace
        from src.core.intelligence.team_assessment import build_team_assessment
        from services.crawl import cached_response
        result = self.engine.analyze(self.data, 1)
        with self.assertRaisesRegex(ValueError, 'generation mismatch'):
            build_team_assessment(result.context, replace(result.team_assessment.team, generation='old'))
        cache = IntelligenceCache()
        with patch('services.crawl.intelligence_cache', cache):
            first = cached_response('league-1:teams', lambda: {'value': 1}, sync_marker='same', evidence_generation='g1')
            same = cached_response('league-1:teams', lambda: {'value': 99}, sync_marker='same', evidence_generation='g1')
            changed = cached_response('league-1:teams', lambda: {'value': 2}, sync_marker='same', evidence_generation='g2')
        self.assertEqual(first['data'], same['data'])
        self.assertTrue(same['cache']['cached'])
        self.assertEqual(changed['data'], {'value': 2})

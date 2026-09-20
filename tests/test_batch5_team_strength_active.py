import tempfile
import unittest
import copy
from pathlib import Path
from unittest.mock import patch

from tests.test_trade_intelligence import fixture_data
from src.core.intelligence.cache import IntelligenceCache
from src.core.intelligence.orchestrator import IntelligenceOrchestrator
from src.core.intelligence.team_strength import prepare_for_data, compatible_profile
from src.core.projection_intelligence.service import ProjectionService
from src.ui.team_strength import strength_panel


class ActiveStrengthTests(unittest.TestCase):
    def test_real_consumer_chain_rejects_stale_profile(self):
        data = fixture_data()
        data['week'] = 2
        data['league'].update(season='2026', sport='nfl', settings={
            'leg': 2, 'last_scored_leg': 1, 'start_week': 1, 'playoff_week_start': 4,
            'playoff_teams': 4, 'playoff_round_type': 0, 'playoff_type': 0})
        league_id = data['league']['league_id']
        players = [p for team in data['teams'] for p in team['players']]
        data['players'] = {p['id']: p for p in players}
        payloads = {w: [{'player_id': p['id'], 'season': 2026, 'week': w,
                        'player': {'position': p['position']}, 'stats': {'pass_yd': 100}}
                       for p in players] for w in range(2, 6)}
        with tempfile.TemporaryDirectory() as directory, patch('services.global_evidence.retained_global_evidence', return_value=None):
            service = ProjectionService(Path(directory) / 'projection.sqlite3')
            service.publish_horizon(payloads, data=data, league_id=league_id, season=2026, current_week=2)
            profile = prepare_for_data(service, data)
            original_league = data['league']['league_id']
            data['league']['league_id'] = 'other-league'
            self.assertIsNone(compatible_profile(data, service.snapshot()))
            data['league']['league_id'] = original_league
            original_scoring = data['league'].get('scoring_settings')
            data['league']['scoring_settings'] = {'rec': 42}
            self.assertIsNone(compatible_profile(data, service.snapshot()))
            data['league']['scoring_settings'] = original_scoring
            self.assertIs(compatible_profile(data, service.snapshot()), profile)
            for mutation in ('scoring', 'slots', 'roster', 'method', 'generation'):
                changed = copy.deepcopy(data)
                if mutation == 'scoring':
                    changed['scoring_settings'] = {'rec': 42}
                    with self.assertRaisesRegex(ValueError, 'scoring'):
                        prepare_for_data(service, changed)
                elif mutation == 'slots':
                    changed['league']['roster_positions'] = ['QB']
                elif mutation == 'roster':
                    changed['teams'][0]['players'][0]['roster_slot'] = 'IR'
                elif mutation == 'method':
                    changed['team_strength']['methodology_version'] = 'old'
                else:
                    changed['team_strength']['projection_generation'] = 'old'
                self.assertIsNone(compatible_profile(changed, service.snapshot()), mutation)
            with patch('src.core.intelligence.team_strength.prepare_team_strength', side_effect=AssertionError('unchanged inputs must reuse')):
                self.assertIs(prepare_for_data(service, data), profile)
            shorter = prepare_for_data(service, data, next_n=2)
            self.assertNotEqual(shorter['semantic_generation'], profile['semantic_generation'])
            bye = {'season': 2026, 'reference': 'schedule-one', 'player_weeks': {players[0]['id']: 3}}
            with_bye = prepare_for_data(service, data, bye_evidence=bye)
            self.assertIsNot(with_bye, shorter)
            changed_bye = dict(bye, player_weeks={players[0]['id']: 4})
            self.assertIsNot(prepare_for_data(service, data, bye_evidence=changed_bye), with_bye)
            profile = prepare_for_data(service, data)
            with patch('src.core.projection_intelligence.projection_service.snapshot', side_effect=service.snapshot):
                engine = IntelligenceOrchestrator(cache=IntelligenceCache())
                result = engine.analyze(data, 1)
                assessment = result.team_assessment
                self.assertEqual(assessment.multi_horizon_strength['generation'], profile['semantic_generation'])
                self.assertEqual(assessment.team.competitive_window.production_profile, assessment.multi_horizon_strength)
                self.assertIsNone(assessment.team.overall.score)
                self.assertIn('Playoff-window strength', strength_panel(assessment.multi_horizon_strength))
                data['league']['settings']['playoff_round_type'] = 1
                self.assertIsNone(compatible_profile(data, service.snapshot()))
                stale = engine.analyze(data, 1)
                self.assertIsNone(stale.team_assessment.multi_horizon_strength)

    def test_partial_display_never_labels_subtotal_complete(self):
        profile = {'horizons': {key: {'total': None, 'weeks_requested': [2, 3],
                     'weeks_supported': [2], 'supported_week_subtotal': 10, 'league_rank': None}
                     for key in ('current_week', 'next_n', 'rest_of_regular_season', 'playoff_window')}, 'weekly': {}}
        html = strength_panel(profile)
        self.assertIn('Partial supported subtotal: 10.00; not a complete horizon.', html)
        self.assertIn('1/2 weeks', html)
        self.assertNotIn('rank: #', html)

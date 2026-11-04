import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_trade_intelligence import fixture_data
from src.core.projection_intelligence.service import ProjectionService
from src.core.intelligence.team_strength import prepare_for_data
from tools.validation.batch5_final_parity import RetainedRead, round_trip


class FinalParityHarnessTests(unittest.TestCase):
    def test_context_round_trip_and_wrong_league_rejection(self):
        inputs = []
        with tempfile.TemporaryDirectory() as directory, patch('services.global_evidence.retained_global_evidence', return_value=None):
            for index, league_id in enumerate(('A', 'B')):
                data = fixture_data()
                data['week'] = 2
                data['league'].update(league_id=league_id, season='2026', sport='nfl',
                    scoring_settings={'pass_yd': .04 + index * .01}, settings={
                        'leg': 2, 'last_scored_leg': 1, 'start_week': 1,
                        'playoff_week_start': 4, 'playoff_teams': 4,
                        'playoff_round_type': 0, 'playoff_type': 0, 'draft_rounds': 4-index})
                players = [p for t in data['teams'] for p in t['players']]
                data['players'] = {p['id']: p for p in players}
                payloads = {week: [{'player_id': p['id'], 'season': 2026, 'week': week,
                    'player': {'position': p['position']}, 'stats': {'pass_yd': 100}}
                    for p in players] for week in range(2, 6)}
                service = ProjectionService(Path(directory) / (league_id + '.sqlite3'))
                service.publish_horizon(payloads, data=data, league_id=league_id, season=2026, current_week=2)
                prepare_for_data(service, data)
                inputs.append((data, RetainedRead(service, range(2, 6))))
            result = round_trip(inputs)
            self.assertTrue(result['exact_restoration'])
            self.assertTrue(result['canonical_inputs_unchanged'])
            self.assertTrue(result['wrong_league_artifact_rejected'])
            self.assertEqual([r['draft_rounds'] for r in result['sequence']], [4, 3, 4])

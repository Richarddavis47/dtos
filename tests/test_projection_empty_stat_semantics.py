import unittest

from src.core.projection_intelligence.service import ProjectionService
from src.core.projection_intelligence.sleeper_provider import parse_projection_feed


class ProjectionEmptyStatTests(unittest.TestCase):
    def test_empty_source_is_missing_but_explicit_zero_is_zero(self):
        payload = [{'player_id': str(i), 'season': 2026, 'week': 1, 'stats': stats}
            for i, stats in enumerate(({}, {'rush_yd': 0}, {'rush_yd': 10}, {'pts_ppr': 4}), 1)]
        rows, _, _ = parse_projection_feed(payload, season=2026, week=1, scoring={'rush_yd': .1})
        self.assertIsNone(rows['1']['league_projection'])
        self.assertEqual(rows['2']['league_projection'], 0)
        self.assertEqual(rows['3']['league_projection'], 1)
        self.assertIsNone(rows['4']['league_projection'])

    def test_old_cached_empty_zero_cannot_leak_into_canonical_output(self):
        result = ProjectionService._canonical_projection({'id': '1', 'status': 'Out'},
            {'league_projection': 0, 'projected_stats': {}}, season=2026, week=1,
            scoring_profile_id='test', sleeper_freshness='Fresh', evidence_fingerprint='test')
        self.assertIsNone(result['weekly_projected_points'])
        self.assertEqual(result['sleeper_zero_state'], 'missing')

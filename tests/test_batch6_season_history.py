import unittest
from src.ui.season_history import season_history_summary


class SeasonHistoryTests(unittest.TestCase):
    def test_bye_and_semifinal_are_canonical_not_week_counts(self):
        archive = {'season': 2025, 'standings': [{'roster_id': 1, 'team_name': 'Historic team', 'gm_name': 'Prior GM'}],
                   'playoffs': {'result': {'first_round_bye_roster_ids': ['1'], 'semifinal_roster_ids': ['1', '1']}}}
        html = season_history_summary(archive)
        self.assertIn('Prior GM', html)
        self.assertIn('First-round bye · playoff qualification', html)
        self.assertEqual(html.count('<span>Final Four</span>'), 1)
        self.assertNotIn('<span>Champion</span>', html)

    def test_head_to_head_excludes_incomplete_and_playoff_components(self):
        base = {'matchup_id': 1, 'teams': [{'roster_id': 1}, {'roster_id': 2}], 'winner_roster_id': 1}
        archive = {'season': 2025, 'weeks': [
            {'week': 1, 'matchups': [base, base]},
            {'week': 2, 'matchups': [{**base, 'winner_roster_id': None}]},
            {'week': 16, 'matchups': [{**base, 'postseason': True}]},
            {'week': 17, 'matchups': [{**base, 'postseason': True}]}]}
        html = season_history_summary(archive)
        self.assertIn('1 retained completed regular-season meetings', html)
        self.assertIn('Not an all-time or manager-tenure record', html)

    def test_missing_achievements_do_not_become_zero_or_bad_results(self):
        html = season_history_summary({'season': 2025})
        self.assertIn('achievements unavailable', html)
        self.assertNotIn('0 championships', html)

    def test_franchise_only_standings_do_not_invent_roster_join(self):
        archive = {'season': 2025,
                   'standings': [{'franchise_id': 'L:franchise:1', 'team_name': 'Historic team'}],
                   'playoffs': {'result': {'champion_roster_id': 1}}}
        html = season_history_summary(archive)
        self.assertIn('Franchise 1', html)
        self.assertNotIn('Historic team', html)

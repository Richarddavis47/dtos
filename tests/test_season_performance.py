"""Native team-score controls
expectations are retained source values."""
import copy
import unittest

from services.matchup_season import METHOD
from services.season_performance import season_performance
from src.core.intelligence.season_calendar import season_calendar
from src.core.player_value_projection.sleeper_actuals import scoring_identity
from src.ui.season_performance import season_panel


def fixture():
    league = dict(league_id='A', season='2026', sport='nfl', status='in_season',
                  scoring_settings={'rec': 1}, settings=dict(leg=5, last_scored_leg=4,
                  start_week=1, playoff_week_start=15, playoff_teams=4,
                  playoff_round_type=0, playoff_type=0, num_teams=2))
    weeks = {str(w): dict(availability='available', observed_at='2026-11-01T12:00:00Z',
                          rows=[dict(roster_id=1, points=p), dict(roster_id=2, points=10)])
             for w, p in [(1, 0), (2, -2), (3, 20), (4, 30), (5, 999)]}
    return dict(league=league, teams=[dict(roster_id=1), dict(roster_id=2)],
                season_matchups=dict(league_id='A', season='2026', methodology=METHOD,
                scoring_fingerprint=scoring_identity(league['scoring_settings']),
                calendar_reference=season_calendar(league)['reference'], weeks=weeks,
                semantic_generation='g1', observed_at='2026-11-01T12:00:00Z'))


class SeasonPerformanceTests(unittest.TestCase):
    def test_native_zero_negative_and_live_boundary(self):
        v = season_performance(fixture(), 1)
        self.assertEqual([r['points'] for r in v['weeks']], [0, -2, 20, 30])
        self.assertEqual(v['average'], 12)
        self.assertEqual(v['league_average'], 11)
        self.assertEqual([r['week'] for r in v['recent']], [2, 3, 4])

    def test_custom_override_and_invalid_override(self):
        d = fixture()
        row = d['season_matchups']['weeks']['1']['rows'][0]
        row['custom_points'] = -4
        self.assertEqual(season_performance(d, 1)['weeks'][0]['points'], -4)
        row['custom_points'] = 'invalid'
        self.assertIn(1, season_performance(d, 1)['missing'])

    def test_repeated_doubleheader_dedup_and_conflict(self):
        d = fixture()
        rows = d['season_matchups']['weeks']['4']['rows']
        rows.append(copy.deepcopy(rows[0]))
        self.assertEqual(season_performance(d, 1)['average'], 12)
        rows[-1]['points'] = 31
        v = season_performance(d, 1)
        self.assertIn(4, v['missing'])
        self.assertIsNone(v['recent'][-1]['points'])

    def test_unequal_coverage_withholds_comparison_not_own_results(self):
        d = fixture()
        d['season_matchups']['weeks']['2']['rows'].pop()
        v = season_performance(d, 1)
        self.assertEqual(v['average'], 12)
        self.assertIsNone(v['league_average'])
        self.assertIn('comparison withheld', season_panel(d, 1))

    def test_missing_latest_week_not_replaced_with_older_week(self):
        d = fixture()
        d['season_matchups']['weeks']['4']['rows'] = []
        v = season_performance(d, 1)
        self.assertEqual([r['week'] for r in v['recent']], [2, 3, 4])
        self.assertIsNone(v['recent'][-1]['points'])

    def test_failed_refresh_retains_qualification(self):
        d = fixture()
        w = d['season_matchups']['weeks']['4']
        w['retained_rows'] = w.pop('rows')
        w['availability'] = 'unavailable'
        self.assertTrue(season_performance(d, 1)['retained'])
        self.assertIn('retained results', season_panel(d, 1, compact=True))

    def test_corrections_and_player_transfers_do_not_reconstruct_scores(self):
        d = fixture()
        d['teams'][0]['players'] = [{'id': 'new-player', 'points': 5000}]
        self.assertEqual(season_performance(d, 1)['average'], 12)
        d['season_matchups']['weeks']['4']['rows'][0]['points'] = 34
        d['season_matchups']['semantic_generation'] = 'g2'
        self.assertEqual(season_performance(d, 1)['average'], 13)
        self.assertIn('g2', season_panel(d, 1))

    def test_identity_scoring_calendar_isolation(self):
        for key, value in [('league_id', 'B'), ('season', '2025'),
                           ('scoring_fingerprint', 'other'), ('calendar_reference', 'other')]:
            d = fixture()
            d['season_matchups'][key] = value
            self.assertIsNone(season_performance(d, 1)['average'])
        self.assertIsNone(season_performance(fixture(), 3)['average'])

    def test_home_and_team_same_values_no_new_action(self):
        d = fixture()
        for compact in [False, True]:
            h = season_panel(d, 1, compact=compact)
            self.assertIn('12.00', h)
            self.assertIn('4/4', h)
            self.assertNotIn('contender', h)
            self.assertNotIn('<form', h)

    def test_complete_empty_and_unacquired_are_not_zero(self):
        for evidence in [dict(availability='available', rows=[]), {},
                         dict(availability='unavailable', rows=[])]:
            d = fixture()
            d['season_matchups']['weeks']['4'] = evidence
            v = season_performance(d, 1)
            self.assertEqual(v['missing'], [4])
            self.assertEqual(v['average'], 6)
            self.assertIn('Missing or conflicting weeks: 4', season_panel(d, 1))

    def test_completed_season_includes_final_regular_week_not_playoffs(self):
        d = fixture()
        d['league']['status'] = 'complete'
        d['league']['settings'].update(leg=17, last_scored_leg=17)
        d['season_matchups']['calendar_reference'] = season_calendar(d['league'])['reference']
        v = season_performance(d, 1)
        self.assertEqual(v['expected_weeks'], list(range(1, 15)))
        self.assertNotIn(15, v['expected_weeks'])

    def test_median_and_ties_do_not_change_score_sample(self):
        d = fixture()
        d['league']['settings']['league_average_match'] = 1
        for team in d['teams']:
            team.update(wins=3, losses=3, ties=2)
        self.assertEqual(season_performance(d, 1)['average'], 12)
        self.assertEqual(len(season_performance(d, 1)['weeks']), 4)

    def test_scoring_and_starter_formats_keep_native_totals(self):
        for slots, coefficients in [(['QB','RB','FLEX','K','DEF'], {'pass_td':4}),
                                    (['QB','SUPER_FLEX'], {'pass_td':6,'rec':1})]:
            d = fixture()
            d['league']['roster_positions'] = slots
            d['league']['scoring_settings'] = coefficients
            d['season_matchups']['scoring_fingerprint'] = scoring_identity(coefficients)
            self.assertEqual(season_performance(d, 1)['average'], 12)

    def test_unknown_franchise_and_duplicate_inventory_withhold(self):
        d = fixture()
        self.assertIsNone(season_performance(d, True)['average'])
        d['teams'].append(dict(roster_id=1))
        self.assertIsNone(season_performance(d, 1)['average'])

    def test_recent_completed_postseason_uses_bracket_not_placeholder_zeros(self):
        d = fixture()
        d['league']['status'] = 'complete'
        d['league']['settings'].update(leg=16, last_scored_leg=16)
        prepared = d['season_matchups']
        prepared['calendar_reference'] = season_calendar(d['league'])['reference']
        prepared['brackets'] = {'winners_bracket': [
            dict(m=1, r=1, t1=1, t2=2, w=1, l=2), dict(m=2, r=2, t1=1, t2=2)]}
        for week, score in [(14, 11), (15, 0), (16, -3)]:
            prepared['weeks'][str(week)] = dict(availability='available', rows=[dict(roster_id=1, points=score)])
        v = season_performance(d, 1)
        self.assertEqual([(r['week'], r['points']) for r in v['recent']], [(14, 11), (15, 0), (16, -3)])
        self.assertNotIn(15, v['expected_weeks'])
        prepared['brackets'] = {}
        v = season_performance(d, 1)
        self.assertEqual(v['recent'], [])
        self.assertIn('participation', v['recent_reason'])

    def test_postseason_bye_does_not_become_completed_team_score(self):
        d = fixture()
        d['league']['settings'].update(leg=16, last_scored_leg=15, playoff_teams=6)
        p = d['season_matchups']
        p['calendar_reference'] = season_calendar(d['league'])['reference']
        p['brackets'] = {'winners_bracket': [dict(m=1, r=1, t1=3, t2=6),
            dict(m=2, r=1, t1=4, t2=5), dict(m=3, r=2, t1=1, t2_from={'w': 1}),
            dict(m=4, r=2, t1=2, t2_from={'w': 2})]}
        p['weeks']['15'] = dict(availability='available', rows=[dict(roster_id=1, points=0)])
        self.assertEqual([r['week'] for r in season_performance(d, 1)['recent']], [12, 13, 14])

    def test_gap_kinds_and_comparison_cohort_are_explicit(self):
        d = fixture()
        d['season_matchups']['weeks'].pop('1')
        d['season_matchups']['weeks']['2'] = dict(availability='available', rows=[])
        d['season_matchups']['weeks']['3'] = dict(availability='unavailable', rows=[])
        d['season_matchups']['weeks']['4']['rows'].append(dict(roster_id=1, points=31))
        v = season_performance(d, 1)
        self.assertEqual(v['cohort_size'], 2)
        self.assertEqual([g['reason'] for g in v['gaps']], [
            'Week not acquired', 'Source returned an empty week; no team score established',
            'Week retrieval failed or is unavailable; no supported retained team score',
            'Conflicting team scores'])

    def test_peer_results_are_independent_of_official_and_median_results(self):
        for record, own, expected in [((4, 0), 20, (4, 8, 0)), ((0, 4), 30, (8, 4, 0))]:
            for median in (0, 1):
                with self.subTest(record=record, median=median):
                    data = fixture()
                    data['league']['settings'].update(num_teams=4, league_average_match=median)
                    data['teams'] = [dict(roster_id=rid) for rid in range(1, 5)]
                    data['teams'][0].update(wins=record[0], losses=record[1])
                    for week in data['season_matchups']['weeks'].values():
                        week['rows'] = [dict(roster_id=rid, points=score)
                                        for rid, score in enumerate((own, 10, 25, 40), 1)]
                    peer = season_performance(data, 1)['peer_record']
                    self.assertEqual(peer['weeks'], [1, 2, 3, 4])
                    self.assertEqual(tuple(peer[k] for k in ('wins', 'losses', 'ties')), expected)

    def test_peer_results_skip_incomplete_weeks_and_apply_native_corrections(self):
        data = fixture()
        weeks = data['season_matchups']['weeks']
        weeks['1']['rows'][1]['custom_points'] = 0  # Explicitly overrides the peer's 10.
        weeks['1']['rows'].append(copy.deepcopy(weeks['1']['rows'][0]))
        weeks['2']['rows'][1]['custom_points'] = -3
        weeks['3']['rows'].pop()
        weeks['4']['rows'].append(dict(roster_id=2, points=11))
        view = season_performance(data, 1)
        self.assertEqual(view['peer_record'], dict(wins=1, losses=0, ties=1, weeks=[1, 2], retained_weeks=[]))
        self.assertEqual(view['missing'], [])  # Own scores still support the season average.
        html = season_panel(data, 1)
        self.assertIn('2/4 completed regular-season weeks used.', html)
        self.assertIn('Skipped weeks without complete league scores: 3, 4.', html)
        weeks['1']['rows'][1]['custom_points'] = 1
        weeks['2']['retained_rows'] = weeks['2'].pop('rows')
        weeks['2']['availability'] = 'unavailable'
        self.assertEqual(season_performance(data, 1)['peer_record'],
                         dict(wins=1, losses=1, ties=0, weeks=[1, 2], retained_weeks=[2]))

    def test_peer_results_withhold_without_a_complete_compatible_cohort(self):
        data = fixture()
        for week in data['season_matchups']['weeks'].values():
            week['rows'][1]['custom_points'] = 'invalid'
        self.assertEqual(season_performance(data, 1)['peer_record']['weeks'], [])
        self.assertIn('0/4 completed regular-season weeks used.', season_panel(data, 1))
        self.assertNotIn('Wins: 0 · Losses: 0', season_panel(data, 1))
        data['season_matchups']['scoring_fingerprint'] = 'foreign'
        self.assertEqual(season_performance(data, 1)['peer_record']['weeks'], [])
        self.assertNotIn('How often did we outscore', season_panel(data, 1, compact=True))

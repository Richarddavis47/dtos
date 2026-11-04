from copy import deepcopy
import unittest
from unittest.mock import patch

from services.weekly_report import weekly_facts
from services.weekly_report_stories import candidates, compose_report, select_stories
from src.core.intelligence.season_calendar import season_calendar
from tests.test_batch6_matchup_season import fixture


class WeeklyFactTests(unittest.TestCase):
    def test_completed_source_calendar_equal_leg_is_historical_only(self):
        data, _, _ = fixture()
        league = data['league']
        league['settings'].update(leg=17, last_scored_leg=17)
        self.assertEqual(season_calendar(league)['availability'], 'unavailable')
        league['status'] = 'complete'
        self.assertEqual(season_calendar(league)['availability'], 'supported')
        self.assertEqual(season_calendar(league)['playoff_rounds'][-1], [16, 17])

    def test_real_view_clamps_completed_round_to_report_week(self):
        data, _, _ = fixture()
        data['league']['settings']['last_scored_leg'] = 17
        data['league']['settings']['leg'] = 18
        data['week'] = 18
        data['season_matchups']['calendar_reference'] = season_calendar(data['league'])['reference']
        data['season_matchups']['brackets'] = {'winners_bracket': [
            {'m': 1, 'r': 3, 't1': 1, 't2': 2, 'w': 2, 'l': 1}]}
        for week, points in ((16, (100, 90)), (17, (10, 60))):
            rows = data['season_matchups']['weeks'][str(week)]['rows']
            for row, score in zip(rows, points):
                row['points'] = score
        before = deepcopy(data)
        first = weekly_facts(data, 16)
        self.assertFalse(first['round_complete'])
        self.assertIsNone(first['matchups'][0]['round_winner'])
        self.assertEqual(first['matchups'][0]['weekly_winner'], 1)
        final = weekly_facts(data, 17)
        self.assertEqual(final['matchups'][0]['round_winner'], 2)
        self.assertEqual(data, before)
        text = compose_report(first)['stories'][0]['text']
        self.assertIn('round is not complete', text)
        self.assertNotIn('won the completed round', text)

    def test_story_trace_dedup_every_franchise_and_determinism(self):
        data, _, _ = fixture()
        data['teams'].append({'roster_id': 3, 'team_name': 'Quiet franchise'})
        facts = weekly_facts(data, 1)
        items = candidates(facts)
        self.assertEqual(select_stories(items + items), items)
        report = compose_report(facts)
        self.assertEqual(len(report['stories']), 1)
        covered = set(report['stories'][0]['franchises']) | {
            row['roster_id'] for row in report['around_the_league']}
        self.assertEqual(covered, {1, 2, 3})
        for row in report['stories'] + report['around_the_league']:
            self.assertTrue(set(row['fact_references']) <= facts['fact_trace'].keys())
        for _ in range(100):
            self.assertEqual(compose_report(facts), report)
        text = str(report).lower()
        for filler in ('bounce back', 'momentum', 'anything can happen', 'big week ahead'):
            self.assertNotIn(filler, text)

    def test_no_fake_lead_when_results_missing(self):
        data, _, _ = fixture()
        data['season_matchups']['weeks']['1']['rows'][0]['points'] = None
        report = compose_report(weekly_facts(data, 1))
        self.assertEqual(report['stories'], [])
        self.assertEqual(len(report['around_the_league']), 2)
        self.assertNotIn('0 points', str(report))

    def test_priority_is_explicit_and_does_not_change_facts(self):
        data, _, _ = fixture()
        facts = weekly_facts(data, 1)
        first = candidates(facts)[0]
        far = {**first, 'identity': 'far', 'priority': {**first['priority'], 'margin': 50}}
        playoff = {**far, 'identity': 'playoff', 'priority': {**far['priority'], 'locked_round_result': True}}
        self.assertEqual([r['identity'] for r in select_stories([far, first, playoff])],
                         ['playoff', first['identity'], 'far'])
        before = deepcopy(facts)
        compose_report(facts, lead_limit=0)
        self.assertEqual(facts, before)

    def test_completed_actual_zero_tie_no_current_projection(self):
        data, service, calls = fixture()
        before = deepcopy(data)
        fact = weekly_facts(data, 1, service)
        self.assertEqual(fact['state'], 'completed')
        self.assertTrue(fact['matchups'][0]['weekly_tie'])
        self.assertIsNone(fact['matchups'][0]['weekly_winner'])
        self.assertEqual(fact['franchises'][0]['actual'], 0)
        self.assertIsNone(fact['franchises'][0]['projection'])
        self.assertEqual(calls, [])
        for _ in range(100):
            self.assertEqual(weekly_facts(data, 1, service), fact)
        self.assertEqual(data, before)

    def test_missing_score_not_zero_and_all_franchises_covered(self):
        data, _, _ = fixture()
        data['season_matchups']['weeks']['1']['rows'][0]['points'] = None
        data['teams'].append({'roster_id': 3, 'team_name': 'No weekly row'})
        fact = weekly_facts(data, 1)
        self.assertFalse(fact['matchups'][0]['weekly_result_available'])
        self.assertEqual(len(fact['franchises']), 3)
        self.assertEqual(fact['franchises'][-1]['status'], 'weekly_evidence_unavailable')

    def test_future_projection_never_winner(self):
        data, service, _ = fixture()
        fact = weekly_facts(data, 3, service)
        self.assertEqual(fact['state'], 'preview')
        self.assertIsNone(fact['matchups'][0]['weekly_winner'])
        self.assertFalse(fact['matchups'][0]['weekly_result_available'])

    def test_foreign_generation_unavailable(self):
        data, _, _ = fixture()
        data['season_matchups']['league_id'] = 'B'
        fact = weekly_facts(data, 1)
        self.assertEqual(fact['state'], 'unavailable')
        self.assertFalse(fact['matchups'])

    def test_in_progress_never_completed_or_preview(self):
        data, _, _ = fixture()
        data['season_matchups']['weeks']['2']['rows'][0]['points'] = 12.5
        fact = weekly_facts(data, 2)
        self.assertEqual(fact['state'], 'in_progress')
        self.assertIsNone(fact['matchups'][0]['weekly_winner'])

    def test_final_winner_and_decimal_margin(self):
        data, _, _ = fixture()
        rows = data['season_matchups']['weeks']['1']['rows']
        rows[0]['points'], rows[1]['points'] = 100.1, 100
        fact = weekly_facts(data, 1)
        self.assertEqual(fact['matchups'][0]['weekly_winner'], 1)
        self.assertEqual(fact['matchups'][0]['margin'], 0.1)
        self.assertTrue(all(r['identity'] in fact['fact_trace'] for r in fact['franchises']))

    def test_retrieval_clock_does_not_change_report_identity(self):
        data, _, _ = fixture()
        first = weekly_facts(data, 1)
        data['season_matchups']['observed_at'] = 'later observation'
        self.assertEqual(weekly_facts(data, 1)['semantic_identity'], first['semantic_identity'])

    def test_multiweek_component_not_round_winner_and_bye(self):
        data, _, _ = fixture()
        base = {'league_id': 'A', 'season': '2026', 'generation': 'g', 'availability': 'available',
                'observed_at': 'observed', 'period': 'historical', 'states': {'1': 'final'},
                'round_weeks': [16, 17], 'round_complete': False, 'bracket_labels': {'1': 'Championship bracket'},
                'byes': [{'roster_id': 2}], 'groups': {'1': [
                    {'roster_id': 1, 'actual': 100, 'round_actual': None, 'lineup': [], 'projection': None, 'coverage': 'unavailable'},
                    {'roster_id': 3, 'actual': 90, 'round_actual': None, 'lineup': [], 'projection': None, 'coverage': 'unavailable'}]}}
        with patch('services.weekly_report.season_week_view', return_value=base):
            fact = weekly_facts(data, 16)
        self.assertEqual(fact['matchups'][0]['weekly_winner'], 1)
        self.assertIsNone(fact['matchups'][0]['round_winner'])
        self.assertFalse(fact['matchups'][0]['round_result_available'])
        self.assertEqual(fact['franchises'][1]['status'], 'qualified_on_bye')

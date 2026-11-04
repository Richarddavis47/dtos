"""Prepared canonical Team HQ evidence, goal precedence and unavailable semantics."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from services.my_team_outlook import prepared_outlook
from services.team_headquarters import build_team_headquarters
from src.core.intelligence.cache import IntelligenceCache
from src.core.intelligence.orchestrator import IntelligenceOrchestrator
from src.core.trade_intelligence.lineup import optimal_legal_lineup
from tests.test_active_roster_grading import ActiveRosterGradingTests


class MyTeamOutlookTests(unittest.TestCase):
    def setUp(self):
        self.f = ActiveRosterGradingTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def view(self, goal=''):
        engine = IntelligenceOrchestrator(cache=IntelligenceCache())
        with patch('services.team_headquarters.intelligence_orchestrator', engine):
            return build_team_headquarters(self.f.data, 1, strategy=goal)

    def format(self, view, assessment=None, goal=''):
        return prepared_outlook(self.f.data, assessment or view['assessment'], view['overview'],
                                self.f.data['teams'][0]['players'], strategy=goal)

    def strong(self, depth):
        players = self.f.data['teams'][0]['players']
        selected = {p.asset_id for p in optimal_legal_lineup(
            [dict(p, projected_points=40) for p in players], self.f.data['league']['roster_positions']).entries}
        for player in players:
            self.f.snapshot['players'][player['id']]['weekly_projected_points'] = 40 if player['id'] in selected else depth

    def test_equal_reserve_counts_different_quality_and_identical_starters(self):
        self.strong(1)
        weak = self.view('WIN NOW')
        self.strong(25)
        strong = self.view('WIN NOW')
        self.assertEqual(weak['assessment'].roster_evidence.optimal_lineup_projection,
                         strong['assessment'].roster_evidence.optimal_lineup_projection)
        self.assertEqual(weak['snapshot']['total_players'], strong['snapshot']['total_players'])
        self.assertNotEqual(weak['outlook']['concern'], strong['outlook']['concern'])
        self.assertNotIn('No material downside', weak['outlook']['concern'])
        self.assertIn('replacement', weak['outlook']['guidance'])

    def test_middle_team_no_automatic_direction_and_neutral_evidence_unchanged(self):
        for team in self.f.data['teams']:
            for p in team['players']:
                self.f.snapshot['players'][p['id']]['weekly_projected_points'] = {1:14, 2:18, 3:10}[team['roster_id']]
        views = [self.view(goal) for goal in ('', 'WIN NOW', 'RETOOL', 'REBUILD')]
        self.assertIn('#2 among 3', views[0]['outlook']['position'])
        self.assertIn('Select a goal', views[0]['outlook']['guidance'])
        self.assertIn('Neutral Market', views[0]['outlook']['guidance'])
        self.assertEqual({v['outlook']['position'] for v in views}, {views[0]['outlook']['position']})
        self.assertEqual(views[1]['outlook']['action'], 'Explore starter upgrades')
        self.assertEqual(views[3]['outlook']['href'], '#draft-capital')
        self.assertTrue(all(v['team_intelligence'].current_window.value == 'Unavailable' for v in views))

    def test_exact_acquired_future_firsts_and_ownership_remain_inventory(self):
        picks = [{'year':year, 'round':1, 'original_roster_id':orig, 'current_owner_id':1}
                 for year, orig in ((2027,1), (2027,2), (2028,1), (2029,1))]
        self.f.data['teams'][0]['picks_owned'] = picks
        before = deepcopy(picks)
        view = self.view('REBUILD')
        self.assertIn('4 owned picks, including 4 first-round picks (2027, 2028, 2029)', view['outlook']['future'])
        self.assertIn('REBUILD:', view['outlook']['guidance'])
        self.assertEqual(self.f.data['teams'][0]['picks_owned'], before)
        self.assertEqual(len(view['team_intelligence'].future_capital_evidence['picks']), 4)
        self.assertIn('unknown pick ranges remain unknown', ' '.join(view['outlook']['details']))

    def test_missing_production_is_not_zero_or_proven_poor_depth(self):
        view = self.view()
        evidence = view['assessment'].roster_evidence
        missing = deepcopy(evidence.positions)
        for row in missing.values():
            if row['reserve_expected']:
                row['reserve_covered'] = 0
        changed = replace(view['assessment'], roster_evidence=replace(evidence, positions=missing))
        text = self.format(view, changed)
        self.assertIn('replacement projections are incomplete', text['concern'])
        for p in self.f.data['teams'][0]['players']:
            self.f.snapshot['players'][p['id']]['weekly_projected_points'] = 0
        zero = self.view()
        self.assertIn('0 points', zero['outlook']['position'])
        self.assertNotIn('comparison unavailable;', zero['outlook']['position'])

    def test_wrong_week_and_missing_projection_identity_withhold_current_comparison(self):
        view = self.view()
        assessment = view['assessment']
        for evidence in (replace(assessment.roster_evidence, projection_week=99),
                         replace(assessment.roster_evidence, projection_generation=None)):
            with self.subTest(evidence=evidence.projection_week):
                text = self.format(view, replace(assessment, roster_evidence=evidence))
                self.assertIn('comparison unavailable', text['position'])
                self.assertIn('unconfirmed', text['concern'])

    def test_stale_retained_diagnostics_are_visibly_provisional(self):
        view = self.view()
        positions = deepcopy(view['assessment'].roster_evidence.positions)
        for row in positions.values():
            row['diagnostic']['conclusion_state'] = 'provisional'
        assessment = replace(view['assessment'], roster_evidence=replace(view['assessment'].roster_evidence, positions=positions))
        text = self.format(view, assessment)
        self.assertIn('Provisional:', text['position'])
        self.assertIn('not a fresh team verdict', ' '.join(text['details']))

    def test_foreign_league_or_generation_cannot_leak_into_summary(self):
        view = self.view()
        for assessment in (replace(view['assessment'], league_id='foreign'),
                           replace(view['assessment'], generation='superseded')):
            with self.subTest(generation=assessment.generation):
                text = self.format(view, assessment)
                self.assertIn('compatible league evidence', text['position'])
                self.assertIn('cannot be confirmed', text['strength'])
                self.assertNotIn('owned picks', text['future'])

    def test_supported_ages_missing_and_conflicting_evidence(self):
        for player in self.f.data['teams'][0]['players']:
            player['age'] = 24
        view = self.view()
        text = ' '.join(view['outlook']['details'])
        self.assertIn('Reported ages cover 7/7', text)
        self.assertIn('not establish years remaining', text)
        for player in self.f.data['teams'][0]['players']:
            self.f.data['players'][player['id']]['metadata'] = {'birth_date_status':'conflicting'}
        text = ' '.join(self.format(view)['details'])
        self.assertIn('starter-age context is unavailable', text)

    def test_formatter_is_pure_and_never_runs_expensive_services(self):
        view = self.view('WIN NOW')
        before = deepcopy(self.f.data)
        with patch('services.sleeper.sleeper_get', side_effect=AssertionError('provider')),\
             patch('src.core.intelligence.team_strength.prepare_for_data', side_effect=AssertionError('prepare')),\
             patch('src.core.trade_intelligence.lineup.optimal_legal_lineup', side_effect=AssertionError('solver')),\
             patch('src.core.fois.service.FOISService._generate_sync', side_effect=AssertionError('FOIS')),\
             patch('src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct', side_effect=AssertionError('history')):
            results = [self.format(view, goal='WIN NOW') for _ in range(25)]
        self.assertTrue(all(row == results[0] for row in results))
        self.assertEqual(self.f.data, before)

    def test_three_superflex_quarterbacks_retain_valuable_qb3_cover(self):
        from tests.test_reserve_quality import ReserveQualityTests
        f = ReserveQualityTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.data['league']['roster_positions'] = ['QB', 'SUPER_FLEX'] + ['BN'] * 6
        f.fixture.points.update(a=30, b=29, e=28, c=27, d=26, f=25)
        f.fixture.publish()
        engine = IntelligenceOrchestrator(cache=IntelligenceCache())
        with patch('src.core.projection_intelligence.projection_service.snapshot', f.fixture.reader.snapshot), \
             patch('services.team_headquarters.intelligence_orchestrator', engine):
            view = build_team_headquarters(f.data, 1, strategy='WIN NOW')
        evidence = view['assessment'].roster_evidence
        self.assertEqual(evidence.optimal_lineup_projection, 59)
        self.assertEqual(evidence.positions['QB']['best_reserve_points'], 28)
        self.assertIn('best supported eligible reserve 28 points', ' '.join(view['outlook']['details']))
        self.assertIn('not automatically expendable', view['outlook']['strength'])

    def test_foreign_capital_and_missing_age_are_not_future_certainty(self):
        view = self.view()
        card = replace(view['assessment'].team, future_capital_evidence={
            'league_id':'foreign', 'roster_id':1, 'generation':view['assessment'].generation,
            'owned_pick_count':99, 'picks':[]})
        text = self.format(view, replace(view['assessment'], team=card))
        self.assertIn('ownership evidence is unavailable', text['future'])
        self.assertNotIn('99', text['future'])
        for player in self.f.data['teams'][0]['players']:
            player.pop('age', None)
            self.f.data['players'][player['id']].pop('age', None)
        self.assertIn('starter-age context is unavailable', ' '.join(self.format(view)['details']))

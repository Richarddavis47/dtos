"""Source-admission and dimensional correctness; no live providers or storage."""
import base64
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from pathlib import Path
import tempfile

from services.strategy_session import selected_strategy, strategy_scope
from services.team_headquarters import build_team_headquarters
from src.core.intelligence.cache import IntelligenceCache
from src.core.intelligence.orchestrator import IntelligenceOrchestrator
from src.core.intelligence.roster_evidence import build_roster_evidence
from src.core.intelligence.roster_grading import PlayerGradingEvidence, grade_roster_evidence
from src.core.front_office_intelligence.engine import _surpluses
from tests.test_roster_evidence_boundary import context
from tests.test_trade_intelligence import fixture_data
from src.core.projection_intelligence.service import ProjectionService


class MyTeamEvidenceTests(TestCase):
    def test_prepared_pick_year_and_unknown_identity_render_truthfully(self):
        from routes.teams import _draft_capital
        for year_field in ('year', 'season'):
            pick = {'season': '2027', 'round': 4, 'original_roster_id': 2,
                    'current_owner_id': 1, 'original_team': 'Original team',
                    'current_owner': 'My franchise', 'is_traded': True}
            prepared = {'identity': {year_field: '2027', 'round': 4, 'original_roster_id': 2},
                        'market': {'normalized_market_price': 0}}
            view = {'team': {'roster_id': 1, 'team_name': 'My franchise'}, 'can_shop': True,
                    'picks_by_year': {'2027': [pick]},
                    'team_intelligence': SimpleNamespace(future_capital_evidence={'picks': [prepared]})}
            rendered = _draft_capital(view)
            self.assertIn('Market: 0', rendered)
            self.assertIn('asset_id=2027-R4-2', rendered)
            self.assertIn('Original franchise: Original team', rendered)
            self.assertIn('Current owner: My franchise', rendered)
            view['picks_by_year']['2027'][0] = {**pick, 'original_roster_id': None}
            view['team_intelligence'].future_capital_evidence = {'picks': [{'identity': {'year': '2027', 'round': 4}, 'market': {}}]}
            unknown = _draft_capital(view)
            self.assertIn('Market: Unavailable', unknown)
            self.assertNotIn('/trades/shop', unknown)

    def test_actual_publisher_rollover_and_material_generation(self):
        data = fixture_data()
        data['week'] = 1
        data['league'].update(season='2026', scoring_settings={'pass_yd': .04})
        players = [p for t in data['teams'] for p in t['players']]
        payloads = {w: [{'player_id': p['id'], 'season': 2026, 'week': w,
                       'player': {'position': p['position']}, 'stats': {'pass_yd': 100 * w}}
                      for p in players] for w in (1, 2)}
        with tempfile.TemporaryDirectory() as folder, patch('services.global_evidence.retained_global_evidence', return_value=None):
            service = ProjectionService(Path(folder) / 'projection.sqlite3')
            service.publish_horizon(payloads, data=data, league_id='league-1', season=2026, current_week=1)
            with patch('src.core.projection_intelligence.projection_service.snapshot', side_effect=service.snapshot), patch('src.core.projection_intelligence.projection_service.week_snapshot', side_effect=service.week_snapshot):
                engine = IntelligenceOrchestrator(cache=IntelligenceCache())
                first = engine.analyze(data, 1).team_assessment.roster_evidence
                data['week'] = 2
                second = engine.analyze(data, 1).team_assessment.roster_evidence
                self.assertEqual((first.projection_week, second.projection_week), (1, 2))
                self.assertEqual((first.actual_lineup_projection, second.actual_lineup_projection), (20, 40))
                # Reuse of published evidence must retain the exact identity.
                self.assertEqual(second, engine.analyze(data, 1).team_assessment.roster_evidence)
                del payloads[2]
                service.publish_horizon(payloads, data=data, league_id='league-1', season=2026, current_week=1)
                missing = engine.analyze(data, 1).team_assessment.roster_evidence
                self.assertIsNone(missing.actual_lineup_projection)
                self.assertNotEqual(second.projection_generation, missing.projection_generation)

    def test_partial_depth_is_not_a_complete_grade(self):
        row = grade_roster_evidence(league_id='a', roster_id=1, generation='g',
            players=(PlayerGradingEvidence('starter', 100, 80, 20, 70, 90),
                     PlayerGradingEvidence('known', 50, 70, 8, 60, 80),
                     PlayerGradingEvidence('unknown', None, None, None, None, 0)),
            actual_starter_ids=('starter',), optimal_starter_ids=('starter',),
            actual_points=20, optimal_points=20, legal_backup_points=8,
            backup_covered=1, backup_expected=2)
        depth = row.dimensions['Useful projected depth']
        self.assertIsNone(depth.value)
        self.assertEqual((depth.covered, depth.expected, depth.known_subtotal), (1, 2, 8))
        self.assertEqual(depth.confidence, 0)
        self.assertEqual(row.dimensions['Optimal projected lineup'].value, 20)

    def test_complete_zero_depth_remains_zero(self):
        row = grade_roster_evidence(league_id='a', roster_id=1, generation='g',
            players=(PlayerGradingEvidence('s', 10, 80, 20, 70, 90),
                     PlayerGradingEvidence('b', 0, 70, 0, 60, 80)),
            actual_starter_ids=('s',), optimal_starter_ids=('s',), actual_points=20,
            optimal_points=20, legal_backup_points=0, backup_covered=1, backup_expected=1)
        self.assertEqual(row.dimensions['Useful projected depth'].value, 0)

    def test_rollover_withholds_old_week_but_keeps_source_identity(self):
        ctx = context()
        ctx.cached_data = {'week': 2}
        row = build_roster_evidence(ctx)
        self.assertIsNone(row.actual_lineup_projection)
        self.assertIsNone(row.optimal_lineup_projection)
        self.assertEqual(row.projection_generation, 'p1')
        self.assertTrue(any('current league week' in reason for reason in row.limitations))

    def test_scoring_and_season_mismatch_withheld(self):
        for mismatch in ({'league': {'season': '2027'}}, {'scoring_settings': {'rec': 2}}):
            ctx = context()
            ctx.cached_data = mismatch
            self.assertIsNone(build_roster_evidence(ctx).actual_lineup_projection)

    def test_superflex_starting_contribution_and_unknown_qb3_are_separate(self):
        ctx = context()
        ctx.roster['players'].append({'id': 'q3', 'position': 'QB', 'roster_slot': 'Bench'})
        row = build_roster_evidence(ctx).positions['QB']
        self.assertEqual(row['starting_count'], 2)
        self.assertEqual(row['starting_points'], 35)
        self.assertEqual((row['required_slots'], row['eligible_flex_slots']), (1, 1))
        self.assertEqual((row['reserve_covered'], row['reserve_expected']), (0, 1))
        self.assertIsNone(row['surplus'])

    def test_three_known_qbs_have_supported_backup_not_count_surplus(self):
        ctx = context()
        ctx.roster['players'].append({'id': 'q3', 'position': 'QB', 'roster_slot': 'Bench'})
        ctx.projection_snapshot['players']['q3'] = {'week': 1, 'weekly_projected_points': 12}
        row = build_roster_evidence(ctx).positions['QB']
        self.assertEqual((row['reserve_covered'], row['reserve_expected']), (1, 1))
        self.assertEqual(row['best_reserve_points'], 12)
        self.assertEqual(row['availability'], 'complete')
        self.assertEqual(_surpluses(SimpleNamespace(profile=SimpleNamespace(position_rooms={'QB': SimpleNamespace(total_players=20)}))), set())

    def test_ir_and_taxi_are_not_eligible_backup(self):
        ctx = context()
        for slot in ('IR', 'Taxi'):
            ctx.roster['players'].append({'id': slot, 'position': 'QB', 'roster_slot': slot})
            ctx.projection_snapshot['players'][slot] = {'week': 1, 'weekly_projected_points': 99}
        row = build_roster_evidence(ctx)
        self.assertEqual(row.optimal_lineup_projection, 35)
        self.assertEqual(row.positions['QB']['reserve_expected'], 0)

    def test_selected_strategy_reused_without_mutating_source_or_prices(self):
        data = fixture_data()
        before = deepcopy(data)
        engine = IntelligenceOrchestrator(cache=IntelligenceCache())
        with patch('services.team_headquarters.intelligence_orchestrator', engine):
            rebuild = build_team_headquarters(data, 1, strategy='REBUILD')
            win = build_team_headquarters(data, 1, strategy='WIN NOW')
        self.assertEqual(rebuild['decision'].profile.strategy, 'REBUILD')
        self.assertEqual(win['decision'].profile.strategy, 'WIN NOW')
        self.assertEqual(data, before)
        self.assertEqual(rebuild['roster_intelligence'].players, win['roster_intelligence'].players)

    def test_missing_record_and_maxpf_not_zero(self):
        data = fixture_data()
        data['teams'][0].update(wins=None, max_points=None)
        view = build_team_headquarters(data, 1)
        self.assertEqual(view['performance']['record'], 'Unavailable')
        self.assertIsNone(view['performance']['max_points'])


class StrategySessionTests(TestCase):
    def encode(self, scope, rows):
        return base64.urlsafe_b64encode(json.dumps({'scope': scope, 'rows': rows}).encode()).decode().rstrip('=')

    def test_account_session_league_and_franchise_scope(self):
        a = SimpleNamespace(account_id='a', session_id='s1', membership=None)
        b = SimpleNamespace(account_id='b', session_id='s2', membership=None)
        with patch('services.strategy_session.current_account', return_value=a):
            saved = self.encode(strategy_scope(), [['A:1', 'REBUILD'], ['B:2', 'WIN NOW']])
            self.assertEqual(selected_strategy(saved, 'A', 1), 'REBUILD')
            self.assertEqual(selected_strategy(saved, 'B', 2), 'WIN NOW')
            self.assertEqual(selected_strategy(saved, 'A', 2), '')
        with patch('services.strategy_session.current_account', return_value=b):
            self.assertEqual(selected_strategy(saved, 'A', 1), '')

    def test_invalid_or_oversized_intent_is_not_admitted(self):
        for raw in ('broken', 'a' * 4000, self.encode(strategy_scope(), [['A:1', 'invented']])):
            self.assertEqual(selected_strategy(raw, 'A', 1), '')


if __name__ == '__main__':
    import unittest
    unittest.main()

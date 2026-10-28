"""Canonical source -> current lineup eligibility; no real account mutations."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from copy import deepcopy

from tests import test_capital_strategy_reconciliation as fixtures
from src.core.intelligence.roster_diagnostics import diagnose_league
from src.core.intelligence.roster_evidence import build_roster_evidence
from src.core.intelligence.team_strength import prepare_for_data


class ProjectionCoverageIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.CapitalStrategyTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        for team in self.f.data['teams']:
            for player in team['players']:
                player.update(status='Active', team='BUF')
                self.f.data['players'][player['id']].update(status='Active', team='BUF')
        self.f.points.update(a=50, b=20, e=10)

    def publish(self, *, missing=None, bye=None):
        self.f.publish()
        if missing:
            self.f.payloads[2] = [r for r in self.f.payloads[2] if r['player_id'] not in missing]
            self.f.reader.publish_horizon(self.f.payloads, data=self.f.data,
                league_id='league-1', season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            return prepare_for_data(self.f.reader, self.f.data, bye_evidence=bye)

    def roster(self):
        return build_roster_evidence(SimpleNamespace(league_id='league-1',
            active_roster_id=1, roster=self.f.data['teams'][0],
            projection_snapshot=self.f.reader.snapshot(), cached_data=self.f.data,
            settings=self.f.data['league'], evidence_generation='fixture', user_preferences={}))

    def test_current_out_projection_is_preserved_but_not_usable_lineup_production(self):
        self.f.data['players']['a']['injury_status'] = 'Out'
        profile = self.publish()
        self.assertEqual(self.f.reader.snapshot()['players']['a']['canonical_projection'], 50)
        self.assertEqual(self.roster().optimal_lineup_projection, 20)
        self.assertEqual(profile['teams']['1']['horizons']['current_week']['total'], 20)

    def test_prepared_source_bye_reaches_current_roster_eligibility(self):
        profile = self.publish(bye={'season': 2026, 'reference': 'disposable-schedule',
                                   'player_weeks': {'a': 2}})
        self.assertEqual(profile['teams']['1']['horizons']['current_week']['total'], 20)
        diagnostics = diagnose_league(self.f.data, self.f.reader.snapshot(),
                                      projection_reader=self.f.reader)
        self.assertIn('a', diagnostics['teams']['1']['excluded_player_ids'])
        self.assertEqual(self.roster().optimal_lineup_projection, 20)

    def test_missing_bench_does_not_erase_supported_legal_lineup(self):
        self.publish(missing={'e'})
        roster = self.roster()
        self.assertEqual(roster.optimal_lineup_projection, 50)
        self.assertEqual(roster.projection_covered, 2)
        self.assertEqual(roster.roster_count, 3)

    def test_genuine_zero_can_fill_a_supported_required_slot(self):
        self.f.points.update(a=0, b=0, e=0)
        profile = self.publish()
        self.assertEqual(self.roster().optimal_lineup_projection, 0)
        self.assertEqual(profile['teams']['1']['horizons']['current_week']['total'], 0)

    def test_current_out_status_does_not_invent_a_permanent_future_absence(self):
        self.f.data['players']['a']['injury_status'] = 'Out'
        profile = self.publish()
        self.assertEqual(profile['teams']['1']['weekly'][2]['optimal']['projected_points'], 20)
        self.assertEqual(profile['teams']['1']['weekly'][3]['optimal']['projected_points'], 50)
        self.assertFalse(profile['teams']['1']['weekly'][3]['reserve_capacity']['qualification']['calculation_supported'])

    def test_preparation_rejects_explicit_row_identity_and_publication_conflicts(self):
        for key, value in [('player_id', 'foreign'), ('scoring_profile_id', 'foreign'),
                           ('projection_snapshot_id', 'foreign')]:
            with self.subTest(field=key):
                self.publish()
                self.f.data.pop('team_strength', None)
                original = self.f.reader.week_snapshot
                def conflicting(week, **kwargs):
                    snapshot = deepcopy(original(week, **kwargs))
                    if snapshot:
                        snapshot['players']['a'][key] = value
                    return snapshot
                with patch.object(self.f.reader, 'week_snapshot', side_effect=conflicting):
                    with self.assertRaisesRegex(ValueError, 'boundary mismatch'):
                        prepare_for_data(self.f.reader, self.f.data)


class FantasyEligibilityTests(unittest.TestCase):
    def test_explicit_receiver_eligibility_survives_different_primary_position(self):
        from src.core.trade_intelligence.lineup import optimal_legal_lineup
        result = optimal_legal_lineup([
            {'id': 'dual', 'position': 'DB', 'fantasy_positions': ['DB', 'WR'],
             'projected_points': 10},
            {'id': 'receiver', 'position': 'WR', 'projected_points': 5},
        ], ['WR', 'FLEX'], week=8)
        self.assertTrue(result.available)
        self.assertEqual(result.projected_points, 15)
        self.assertEqual({e.asset_id for e in result.entries}, {'dual', 'receiver'})
        self.assertTrue(all(e.position == 'WR' for e in result.entries))

    def test_dual_eligible_player_cannot_fill_two_slots_at_once(self):
        from src.core.trade_intelligence.lineup import optimal_legal_lineup
        result = optimal_legal_lineup([
            {'id': 'dual', 'position': 'DB', 'fantasy_positions': ['DB', 'WR'],
             'projected_points': 10},
        ], ['WR', 'FLEX'], week=8)
        self.assertFalse(result.available)
        self.assertEqual(len(result.entries), 1)

    def test_explicit_empty_and_malformed_eligibility_cannot_fill_a_slot(self):
        from src.core.trade_intelligence.lineup import optimal_legal_lineup
        for positions in ([], 'WR', [True], ['WR', None]):
            with self.subTest(positions=positions):
                result = optimal_legal_lineup([{'id': 'x', 'position': 'WR',
                    'fantasy_positions': positions, 'projected_points': 10}], ['WR'])
                self.assertFalse(result.available)

    def test_no_fantasy_eligibility_is_invented_for_a_defender(self):
        from src.core.trade_intelligence.lineup import optimal_legal_lineup
        result = optimal_legal_lineup([
            {'id': 'defender', 'position': 'DB', 'projected_points': 10},
        ], ['WR'], week=8)
        self.assertFalse(result.available)

    def test_superflex_can_use_an_alternate_receiver_without_a_second_qb(self):
        from src.core.trade_intelligence.lineup import optimal_legal_lineup
        result = optimal_legal_lineup([
            {'id': 'qb', 'position': 'QB', 'projected_points': 20},
            {'id': 'dual', 'position': 'DB', 'fantasy_positions': ['DB', 'WR'], 'projected_points': 10},
        ], ['QB', 'SUPER_FLEX'])
        self.assertTrue(result.available)
        self.assertEqual(result.projected_points, 30)

    def test_bounded_memo_does_not_reuse_another_fantasy_eligibility(self):
        from src.core.trade_intelligence.lineup_memo import LineupStore, SearchLineupMemo
        memo = SearchLineupMemo('fixture', store=LineupStore(max_entries=2))
        player = {'id': 'dual', 'position': 'DB', 'fantasy_positions': ['DB'], 'projected_points': 10}
        self.assertFalse(memo.solve([player], ['WR']).available)
        player['fantasy_positions'] = ['DB', 'WR']
        self.assertTrue(memo.solve([player], ['WR']).available)
        self.assertTrue(memo.solve([player], ['WR']).available)
        self.assertEqual((memo.misses, memo.hits), (2, 1))


class SourceToScreenHTTPTests(unittest.TestCase):
    def setUp(self):
        from tests.projection_coverage_fixture import prepared
        self.f, self.data, self.service = prepared(self)
        self.client = self.f.f.f.client

    def test_ten_franchise_publication_keeps_seven_lineups_and_explains_three(self):
        comparison = self.data['team_strength']['current_week_comparison']
        self.assertEqual((comparison['supported_count'], comparison['league_size']), (7, 10))
        self.assertEqual([x['roster_id'] for x in comparison['excluded']], ['8', '9', '10'])
        response = self.client.get('/teams/1')
        self.assertEqual(response.status_code, 200, response.text[:400])
        self.assertIn('7/10 franchises can fill', response.text)
        self.assertIn('Franchise 10: excluded', response.text)
        self.assertIn('1 QB slot', response.text)
        self.assertIn('This counts player-week numbers, including reserve/taxi', response.text)
        self.assertNotIn('0 supported rosters', response.text)

    def test_weekly_http_retains_values_and_specific_participation_context(self):
        for pid, text in [('1-u', 'no usable scoring statistics'),
                          ('1-bye', 'NFL bye in Week 8'),
                          ('1-out', 'Listed OUT at preparation'),
                          ('10-w', 'DB / WR')]:
            with self.subTest(player=pid):
                response = self.client.get(f'/players/{pid}/projections?week=8')
                self.assertEqual(response.status_code, 200)
                self.assertIn(text, response.text)
                self.assertIn('no-store', response.headers.get('cache-control', ''))
        body = self.client.get('/players/1-u/projections?week=8').text
        self.assertIn('No current NFL team is recorded', body)
        self.assertIsNone(self.service.snapshot()['players']['1-u']['canonical_projection'])
        self.assertEqual(self.service.snapshot()['players']['1-bye']['canonical_projection'], 40)
        self.assertEqual(self.service.snapshot()['players']['1-out']['canonical_projection'], 40)

    def test_projection_reads_do_not_prepare_or_solve_or_mutate(self):
        from services.player_projection_view import player_projection_views
        before = deepcopy(self.data)
        targets = ['services.global_evidence.retained_global_evidence',
                   'src.core.intelligence.team_strength.prepare_for_data',
                   'src.core.trade_intelligence.lineup.optimal_legal_lineup',
                   'src.core.projection_intelligence.service.ProjectionService.generate',
                   'src.core.projection_intelligence.service.ProjectionService.publish_horizon']
        from contextlib import ExitStack
        with ExitStack() as stack:
            guards = [stack.enter_context(patch(name, side_effect=AssertionError(name))) for name in targets]
            for _ in range(20):
                result = player_projection_views(self.data, ['1-u', '1-bye', '1-out', '10-w'], self.service, 8)
                self.assertIsNone(result['1-u']['value'])
            self.assertTrue(all(g.call_count == 0 for g in guards))
        self.assertEqual(self.data, before)

    def test_explicit_player_week_season_scoring_and_leaf_conflicts_are_withheld(self):
        from services.player_projection_view import player_projection_view
        for key, value in [('player_id', 'foreign'), ('week', 7), ('season', 2025),
                           ('scoring_profile_id', 'foreign'), ('projection_snapshot_id', 'foreign')]:
            with self.subTest(field=key):
                snapshot = deepcopy(self.service.snapshot())
                snapshot['players']['1-q'][key] = value
                reader = SimpleNamespace(snapshot=lambda: snapshot,
                    week_snapshot=lambda *args, **kwargs: snapshot)
                view = player_projection_view(self.data, '1-q', reader, 8)
                self.assertIsNone(view['value'])
                self.assertIn('conflicts', view['reason'])

    def test_foreign_prepared_schedule_cannot_supply_a_bye_label(self):
        from services.player_projection_view import player_projection_view
        self.data['team_strength']['projection_generation'] = 'foreign'
        view = player_projection_view(self.data, '1-bye', self.service, 8)
        self.assertNotIn('bye', view.get('participation_note') or '')
        self.assertEqual(view['value'], 40)

    def test_league_needs_explains_stricter_evidence_without_erasing_lineups(self):
        from src.core.intelligence import IntelligenceOrchestrator
        from src.core.intelligence.cache import IntelligenceCache
        result = IntelligenceOrchestrator(cache=IntelligenceCache()).analyze(self.data, 1)
        for row in result.league.economy.values():
            self.assertIn('0/10 complete-roster needs assessments', row.explanation)
            self.assertIn('7/10 franchises have supported optimal lineups', row.explanation)

    def test_neutral_market_and_official_records_are_unchanged_by_prepared_reads(self):
        before = deepcopy((self.data.get('market_data'), [
            {k: t.get(k) for k in ('roster_id', 'wins', 'losses', 'ties', 'points_for')}
            for t in self.data['teams']]))
        self.assertEqual(self.client.get('/teams/1').status_code, 200)
        self.assertEqual(self.client.get('/players/10-w/projections?week=8').status_code, 200)
        after = (self.data.get('market_data'), [
            {k: t.get(k) for k in ('roster_id', 'wins', 'losses', 'ties', 'points_for')}
            for t in self.data['teams']])
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()

"""Disposable one-QB/K/DEF source-to-diagnostics controls; no live recovery claim."""
import asyncio
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx

from src.core.intelligence.roster_diagnostics import diagnostic_inputs, diagnose_league, package_diagnostics
from src.core.intelligence.team_strength import prepare_for_data
from src.core.projection_intelligence.service import ProjectionService
from src.core.projection_intelligence.sleeper_provider import SleeperProjectionClient, parse_projection_feed
from src.core.trade_intelligence.horizon_impact import evaluate_horizon_impact
from src.core.trade_intelligence.models import TradeAsset, TradeProposal


class MultiLeagueProjectionTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.service = ProjectionService(Path(tmp.name) / 'p.sqlite3')
        slots = ['QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'FLEX', 'K', 'DEF']
        self.data = {'league': {'league_id': 'one-qb', 'season': 2026,
            'roster_positions': slots + ['BN'] * 10,
            'scoring_settings': {'pass_yd': .04, 'rush_yd': .1, 'rec_yd': .1,
                                 'rec': 1, 'fgm': 3, 'sack': 1, 'int': 2},
            'settings': {'leg': 8, 'start_week': 1, 'playoff_week_start': 15,
                         'playoff_teams': 6, 'playoff_round_type': 0}},
            'week': 8, 'players': {}, 'teams': []}
        self.feed = []
        for rid in range(1, 13):
            players = []
            for i, pos in enumerate(['QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'RB', 'WR', 'K', 'DEF', 'QB']):
                pid = f'{rid}-{i}'
                p = {'id': pid, 'name': f'Example {pid}', 'position': pos,
                     'fantasy_positions': [pos], 'status': 'Active', 'team': 'BUF', 'roster_slot': 'Bench'}
                players.append(p)
                self.data['players'][pid] = p.copy()
                stats = {'QB': {'pass_yd': 500 if i == 10 else 250}, 'RB': {'rush_yd': 100},
                    'WR': {'rec_yd': 100, 'rec': 5}, 'TE': {'rec_yd': 50, 'rec': 5},
                    'K': {'fgm': 2}, 'DEF': {'sack': 2, 'int': 1}}[pos]
                self.feed.append({'player_id': pid, 'season': 2026, 'week': 8,
                    'player': {'position': pos, 'fantasy_positions': [pos]}, 'stats': stats})
            self.data['teams'].append({'roster_id': rid, 'players': players, 'starters': ['0'], 'picks_owned': []})

    def publish(self):
        self.snapshot = self.service.publish_horizon({8: self.feed}, data=self.data,
            league_id='one-qb', season=2026, current_week=8)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            return prepare_for_data(self.service, self.data)

    def test_complete_one_qb_source_to_team_and_package_impact(self):
        profile = self.publish()
        before = deepcopy(self.data)
        self.assertTrue(diagnostic_inputs(self.data, self.snapshot)[3])
        diagnostics = diagnose_league(self.data, self.snapshot, projection_reader=self.service)
        self.assertEqual(len(diagnostics['teams']), 12)
        for rid, team in diagnostics['teams'].items():
            self.assertEqual(team['optimal_points'], 115)
            self.assertEqual(profile['teams'][rid]['weekly'][8]['optimal']['projected_points'], 115)
            slots = {e['slot'] for e in profile['teams'][rid]['weekly'][8]['optimal']['entries']}
            self.assertTrue({'K', 'DEF'}.issubset(slots))
        sent = TradeAsset('1-0', 'player', 'Example 1-0', 'QB', 100, 100, 100, 100, 0, 1)
        received = TradeAsset('2-10', 'player', 'Example 2-10', 'QB', 100, 100, 100, 100, 0, 2)
        proposal = TradeProposal(active_roster_id=1, partner_roster_id=2,
            assets_sent=(sent,), assets_received=(received,), package_type='test')
        impact = evaluate_horizon_impact(self.data, proposal, self.service)
        self.assertEqual(impact['sides']['active']['weekly'][8]['delta'], 0)
        result = package_diagnostics(self.data, proposal, self.snapshot, impact, {}, projection_reader=self.service)
        self.assertEqual(result['sides']['active']['pre_optimal_points'], 115)
        self.assertEqual(result['sides']['active']['post_optimal_points'], 115)
        self.assertEqual(self.data, before)
        self.assertEqual(self.data['teams'][0]['starters'], ['0'])

    def test_missing_k_or_def_never_becomes_zero_or_legal(self):
        for index, position in [(8, 'K'), (9, 'DEF')]:
            with self.subTest(position=position):
                original = self.feed
                self.feed = [r for r in original if r['player_id'] != f'1-{index}']
                profile = self.publish()
                week = profile['teams']['1']['weekly'][8]
                self.assertFalse(week['available'])
                self.assertIsNone(week['optimal']['projected_points'])
                self.assertIn(position, week['optimal']['unsupported_slots'])
                row = diagnose_league(self.data, self.snapshot, projection_reader=self.service)['teams']['1']
                self.assertIn(position, ' '.join(row['limitations']))
                self.assertIn(position, row['positions']['QB']['reason'])
                self.feed = original

    def test_ir_and_canonical_taxi_assets_cannot_fill_required_slots(self):
        for roster_slot in ('IR', 'Taxi'):
            with self.subTest(roster_slot=roster_slot):
                self.data['teams'][0]['players'][8]['roster_slot'] = roster_slot
                self.data['players']['1-8']['roster_slot'] = roster_slot
                profile = self.publish()
                optimal = profile['teams']['1']['weekly'][8]['optimal']
                self.assertFalse(optimal['available'])
                self.assertIn('K', optimal['unsupported_slots'])
                diagnostics = diagnose_league(self.data, self.snapshot, projection_reader=self.service)
                self.assertIsNone(diagnostics['teams']['1']['optimal_points'])
                self.assertIn('K', ' '.join(diagnostics['teams']['1']['limitations']))

    def test_explicit_zero_def_is_supported(self):
        next(r for r in self.feed if r['player_id'] == '1-9')['stats'] = {'sack': 0, 'int': 0}
        profile = self.publish()
        self.assertEqual(self.snapshot['players']['1-9']['canonical_projection'], 0)
        self.assertTrue(profile['teams']['1']['weekly'][8]['available'])
        self.assertEqual(profile['teams']['1']['weekly'][8]['optimal']['projected_points'], 111)

    def test_superflex_without_dedicated_te_preserves_legal_scoring(self):
        self.data['league']['roster_positions'] = [
            'QB', 'RB', 'RB', 'WR', 'WR', 'FLEX', 'FLEX',
            'WRRB_FLEX', 'REC_FLEX', 'SUPER_FLEX', *(['BN'] * 12),
        ]
        self.data['league']['scoring_settings'].update(bonus_rec_te=1, bonus_rec_rb=.5)
        for team in self.data['teams']:
            pid = f"{team['roster_id']}-extra"
            player = dict(id=pid, name='Additional fixture receiver', position='WR',
                          fantasy_positions=['WR'], team='BUF', status='Active', roster_slot='Bench')
            team['players'].append(player)
            self.data['players'][pid] = player.copy()
            self.feed.append(dict(player_id=pid, season=2026, week=8,
                                  player={'position': 'WR'}, stats={'rec_yd': 100, 'rec': 5}))
        profile = self.publish()
        diagnostic = diagnose_league(self.data, self.snapshot, projection_reader=self.service)
        for rid, team in profile['teams'].items():
            optimal = team['weekly'][8]['optimal']
            self.assertTrue(optimal['available'])
            self.assertEqual(optimal['projected_points'], 135)
            self.assertEqual(diagnostic['teams'][rid]['optimal_points'], 135)
            self.assertEqual(len(optimal['entries']), 10)
            self.assertNotIn('TE', [entry['slot'] for entry in optimal['entries']])
            self.assertIn('SUPER_FLEX', [entry['slot'] for entry in optimal['entries']])

    def test_asymmetric_player_trade_reoptimizes_each_side_with_k_and_def(self):
        self.publish()
        before = deepcopy(self.data)
        sent = TradeAsset('1-10', 'player', 'Fixture bench QB', 'QB', 100, 100, 100, 100, 0, 1)
        received = TradeAsset('2-0', 'player', 'Fixture QB', 'QB', 100, 100, 100, 100, 0, 2)
        proposal = TradeProposal(active_roster_id=1, partner_roster_id=2,
            assets_sent=(sent,), assets_received=(received,), package_type='test')
        impact = evaluate_horizon_impact(self.data, proposal, self.service)
        result = package_diagnostics(self.data, proposal, self.snapshot, impact, {}, projection_reader=self.service)
        self.assertEqual(result['sides']['active']['pre_optimal_points'], 115)
        self.assertEqual(result['sides']['active']['post_optimal_points'], 105)
        self.assertEqual(impact['sides']['active']['weekly'][8]['delta'], -10)
        self.assertEqual(impact['sides']['partner']['weekly'][8]['delta'], 0)
        self.assertEqual(self.data, before)

    def test_scoring_refresh_requires_a_new_compatible_publication(self):
        self.publish()
        old = deepcopy(self.snapshot)
        self.data['league']['scoring_settings']['pass_yd'] = .05
        self.assertFalse(diagnostic_inputs(self.data, old)[3])
        profile = self.publish()
        self.assertNotEqual(self.snapshot['projection_snapshot_id'], old['projection_snapshot_id'])
        self.assertTrue(diagnostic_inputs(self.data, self.snapshot)[3])
        self.assertEqual(profile['teams']['1']['weekly'][8]['optimal']['projected_points'], 120)
        self.assertFalse(diagnostic_inputs(self.data, old)[3])

    def test_future_week_cannot_borrow_current_def_projection(self):
        future = [dict(row, week=9) for row in self.feed if row['player_id'] != '1-9']
        self.service.publish_horizon({8: self.feed, 9: future}, data=self.data,
            league_id='one-qb', season=2026, current_week=8)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            profile = prepare_for_data(self.service, self.data)
        self.assertTrue(profile['teams']['1']['weekly'][8]['optimal']['available'])
        future_lineup = profile['teams']['1']['weekly'][9]['optimal']
        self.assertFalse(future_lineup['available'])
        self.assertIsNone(future_lineup['projected_points'])
        self.assertIn('DEF', future_lineup['unsupported_slots'])

    def test_scoring_week_league_and_generation_conflicts_fail_closed(self):
        self.publish()
        for key, value in [('week', 9), ('league_id', 'other'), ('season', 2025), ('scoring_settings', {'rec': .5})]:
            with self.subTest(key=key):
                snapshot = deepcopy(self.snapshot)
                snapshot[key] = value
                self.assertFalse(diagnostic_inputs(self.data, snapshot)[3])
        snapshot = deepcopy(self.snapshot)
        snapshot['players']['1-0']['scoring_profile_id'] = 'other'
        self.assertFalse(diagnostic_inputs(self.data, snapshot)[3])

    def test_source_def_score_is_league_specific_not_ppr_display(self):
        payload = [{'player_id': 'CAR', 'season': 2026, 'week': 8, 'player': {'position': 'DEF'},
            'stats': {'sack': 2.03, 'int': .57, 'pts_allow_21_27': 1, 'pts_ppr': 999}}]
        for scoring, expected in [({'sack': 1, 'int': 2, 'pts_allow_21_27': -1}, 2.17),
                                   ({'sack': 2, 'int': 4}, 6.34)]:
            rows, _, _ = parse_projection_feed(payload, season=2026, week=8, scoring=scoring)
            self.assertEqual(rows['CAR']['league_projection'], expected)
        payload[0]['stats'] = {'adp_dd_ppr': 999}
        rows, _, _ = parse_projection_feed(payload, season=2026, week=8, scoring={'sack': 1})
        self.assertIsNone(rows['CAR']['league_projection'])

    def test_existing_bounded_bulk_fetch_requests_k_and_def(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json=[])
        async def fetch():
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                await SleeperProjectionClient().fetch(client, season=2026, week=8)
        asyncio.run(fetch())
        self.assertEqual(len(requests), 1)
        self.assertTrue({'QB', 'RB', 'WR', 'TE', 'K', 'DEF'}.issubset(requests[0].url.params.get_list('position[]')))

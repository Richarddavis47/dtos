"""Gross/net trade observations over real retained replay and disposable controls."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from services.franchise_timeline import franchise_timeline, _CompletedTradeObservations
from src.ui.franchise_timeline import _completed_trade_observations
from tests import test_completed_trade_observations as controls
from tests import test_history_followthrough as journey


class FranchiseTradeProgressTests(unittest.TestCase):
    def setUp(self):
        self.f = controls.CompletedTradeObservationTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def view(self, roster='2', **kwargs):
        return self.f.view(roster, **kwargs)

    def summary(self, **kwargs):
        return self.view(**kwargs)['completed_trade_observations']

    def test_retained_source_replay_all_movements_and_conversion_boundary(self):
        row = self.view('4', season=2026)['completed_trade_observations']
        self.assertEqual(row['completed_trades'], 2)
        self.assertEqual(row['movements']['player'], dict(acquired=1, sent=3, net=-2, complete_in_sample=True))
        self.assertEqual(row['movements']['pick'], dict(acquired=5, sent=2, net=3, complete_in_sample=True))
        assets = {(a['kind'], a['id']): a for a in row['assets']}
        # This player came from the observed draft conversion, not a trade acquisition.
        self.assertEqual((assets['player', '13346']['acquired'], assets['player', '13346']['sent']), (0, 1))
        pick = assets['pick', journey.PICK]
        self.assertEqual((pick['season'], pick['round'], pick['original_roster'], pick['own']), (2026, 2, '7', False))
        html = _completed_trade_observations(self.view('4', season=2026))
        self.assertIn('/picks/' + journey.PICK + '?from_trade=' + journey.ROOT, html)
        self.assertIn('A draft conversion is not another trade acquisition', html)
        self.assertIn('Beginning/end roster and capital totals are not established', html)

    def test_repeated_player_and_pick_movements_remain_in_both_gross_directions(self):
        first = self.f.trade(transaction_id='first', draft_picks=[self.f.pick()])
        later = self.f.trade(transaction_id='later', adds={'fixture-player': 2}, drops={'fixture-player': 1}, draft_picks=[self.f.pick(9, 2, 1)])
        self.f.f.past({'1': [first, later]})
        row = self.summary(season=2024)
        self.assertEqual(row['completed_trades'], 2)
        for kind, identity in [('player', 'fixture-player'), ('pick', 'PICK-2028-R1-ORIG9')]:
            asset = next(a for a in row['assets'] if a['kind'] == kind and a['id'] == identity)
            self.assertEqual((asset['acquired'], asset['sent'], asset['net']), (1, 1, 0))
            self.assertEqual({r['transaction_id'] for r in asset['references']}, {'first', 'later'})
            self.assertEqual(row['movements'][kind]['net'], 0)

    def test_same_round_exact_picks_keep_own_and_acquired_origins_separate(self):
        trade = self.f.trade(draft_picks=[self.f.pick(2, 1, 2), self.f.pick(9, 1, 2)])
        self.f.f.past({'1': [trade]})
        assets = [a for a in self.summary(season=2024)['assets'] if a['kind'] == 'pick']
        self.assertEqual({a['id']: a['own'] for a in assets}, {'PICK-2028-R1-ORIG2': True, 'PICK-2028-R1-ORIG9': False})
        html = _completed_trade_observations(self.view(season=2024))
        self.assertEqual(html.count('<h5>2028 · round 1</h5>'), 1)
        self.assertIn('Own pick (original franchise)', html)
        self.assertIn('Another franchise’s original pick', html)

    def test_duplicate_events_and_duplicate_pick_legs_are_not_recounted(self):
        t = self.f.trade()
        t['draft_picks'].append(deepcopy(t['draft_picks'][0]))
        self.f.f.past({'1': [t, deepcopy(t)], '2': [deepcopy(t)]})
        row = self.summary(season=2024)
        self.assertEqual(row['completed_trades'], 1)
        self.assertEqual((row['movements']['pick']['acquired'], row['movements']['pick']['sent']), (2, 1))

    def test_statuses_waivers_and_corrections_never_enter_trade_movements(self):
        rows = [self.f.trade(transaction_id=s, status=s) for s in ['pending', 'rejected', 'cancelled', 'failed']]
        rows += [self.f.trade(transaction_id=k, type=k) for k in ['waiver', 'correction']]
        self.f.f.past({'1': rows + [self.f.trade(transaction_id='completed')]})
        row = self.summary(season=2024)
        self.assertEqual(row['completed_trades'], 1)
        self.assertTrue(all(r['transaction_id'] == 'completed' for a in row['assets'] for r in a['references']))

    def test_complete_empty_selected_period_supports_zero_despite_earlier_chain_gap(self):
        self.f.f.past()
        row = self.summary(season=2024)
        self.assertEqual(row['state'], 'complete')
        self.assertEqual(row['completed_trades'], 0)
        self.assertEqual(row['movements']['pick']['net'], 0)

    def test_partial_empty_and_absent_selected_periods_remain_unknown(self):
        self.f.f.past({'1': []})
        for season in [2024, 2040]:
            with self.subTest(season=season):
                view = self.view(season=season)
                row = view['completed_trade_observations']
                self.assertIsNone(row['completed_trades'])
                self.assertIsNone(row['movements']['player']['net'])
                self.assertNotIn('0 completed trades observed', _completed_trade_observations(view))

    def test_partial_pick_evidence_does_not_hide_supported_players(self):
        self.f.f.past({'1': [self.f.trade(draft_picks=[self.f.pick(), self.f.pick(None, 2, 1)])]})
        row = self.summary(season=2024)
        self.assertTrue(row['movements']['player']['complete_in_sample'])
        self.assertFalse(row['movements']['pick']['complete_in_sample'])
        self.assertIsNone(row['movements']['pick']['net'])
        self.assertEqual(row['movements']['player']['sent'], 1)
        html = _completed_trade_observations(self.view(season=2024))
        self.assertIn('Draft-pick transfers:</b> at least 1 acquired · unknown sent', html)
        self.assertIn('observed net unknown; consideration is incomplete', html)
        self.assertNotIn('Acquired 1 · sent 0', html)

    def test_unknown_completion_date_does_not_exclude_supported_season_movements(self):
        self.f.f.past({'1': [self.f.trade(status_updated=None)]})
        row = self.summary(season=2024)
        self.assertEqual((row['completed_trades'], row['dated_trades']), (1, 0))
        self.assertEqual(row['movements']['player']['sent'], 1)
        self.assertIsNone(row['first_completion_at'])

    def test_manager_change_cannot_change_franchise_trade_summary(self):
        self.f.f.past({'1': [self.f.trade()]})
        before = self.summary(season=2024)
        self.f.f.f.data['teams'][1]['owner_id'] = 'changed-current-owner'
        self.assertEqual(before, self.summary(season=2024))
        html = _completed_trade_observations(self.view(season=2024))
        self.assertIn('do not establish the current manager', html)
        self.assertNotIn('changed-current-owner', html)

    def test_source_change_withholds_every_movement_family(self):
        self.f.f.past({'1': [self.f.trade()]})
        graph = self.f.f.graph()
        with patch.object(graph.store, 'dataset_version', side_effect=['before', 'after']):
            row = franchise_timeline(graph, '2', season=2024)['completed_trade_observations']
        self.assertIsNone(row['completed_trades'])
        self.assertEqual(row['assets'], [])
        self.assertIsNone(row['movements']['player']['net'])

    def test_detail_cap_is_bounded_without_changing_transfer_totals(self):
        events = [self.f.trade(transaction_id=str(i), adds={str(i): 2}, drops={str(i): 1}, draft_picks=[]) for i in range(260)]
        self.f.f.past({'1': events})
        row = self.summary(season=2024)
        self.assertEqual((row['completed_trades'], row['movements']['player']['acquired']), (260, 260))
        self.assertEqual(len(row['assets']), 256)
        self.assertTrue(row['details_limited'])
        self.assertEqual(len(row['references']), 12)
        self.assertTrue(all(len(a['references']) <= 4 for a in row['assets']))

    def test_season_selection_and_pagination_agree_and_preserve_scope(self):
        self.f.f.past({'1': [self.f.trade(transaction_id=str(i)) for i in range(31)]})
        first = self.view(season=2024, page=1, per_page=10)
        last = self.view(season=2024, page=4, per_page=10)
        self.assertEqual(first['completed_trade_observations'], last['completed_trade_observations'])
        self.assertEqual([s['season'] for s in last['seasons']], [2024])
        url = '/history/team/' + self.f.f.f.data['league']['league_id'] + ':franchise:2?season=2024'
        response = self.f.f.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('events_page=2&amp;season=2024', response.text)
        self.assertIn('<option value="2024" selected>', response.text)
        self.assertIn('31 completed trades observed', response.text)

    def test_other_league_cannot_receive_day_movements(self):
        self.assertEqual(self.view('4')['completed_trade_observations']['completed_trades'], 2)
        self.f.f.f.data = self.f.f.f.fixture.data[journey.source.ARK]
        row = self.view('4')['completed_trade_observations']
        self.assertIsNone(row['completed_trades'])
        self.assertEqual(row['assets'], [])

    def test_bounded_output_and_deterministic_order_without_new_state_owners(self):
        self.f.f.past({'1': [self.f.trade(transaction_id='b'), self.f.trade(transaction_id='a')]})
        first = self.summary(season=2024)
        self.assertEqual(first, self.summary(season=2024))
        self.assertEqual([r['transaction_id'] for r in first['references']], ['b', 'a'])
        before = self.f.f.f.fixture.store.dataset_version(journey.source.DAY)
        for _ in range(3):
            self.view(season=2024)
        self.assertEqual(before, self.f.f.f.fixture.store.dataset_version(journey.source.DAY))

    def test_completed_empty_helper_remains_backwards_compatible(self):
        row = _CompletedTradeObservations('1').result(seasons=[{'season': 2031, 'state': 'complete'}], stable=True, earlier_gap=False)
        self.assertIn('0 completed trades observed', _completed_trade_observations({'completed_trade_observations': row}))


if __name__ == '__main__':
    unittest.main()

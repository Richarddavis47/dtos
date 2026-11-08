"""Source-linked franchise facts, never a model of manager intent."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from services.franchise_timeline import franchise_timeline, _CompletedTradeObservations
from src.ui.franchise_timeline import _completed_trade_observations
from tests import test_franchise_timeline_coverage as fixtures


class CompletedTradeObservationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.FranchiseTimelineCoverageTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        from src.core.historical_memory.read_model import HistoricalReadModelCache
        self.enterContext(patch('src.core.historical_memory.read_model.historical_read_model_cache', HistoricalReadModelCache()))

    def view(self, roster='2', **kwargs):
        return franchise_timeline(self.f.graph(), roster, **kwargs)

    def row(self, roster='2', **kwargs):
        return self.view(roster, **kwargs)['completed_trade_observations']

    def page(self, roster='2'):
        html = self.f.page(roster)
        return html.split('<section class="card franchise-trades fh-trades"', 1)[1].split('</section>', 1)[0]

    def pick(self, original=9, sender=1, receiver=2, season='2028'):
        return dict(season=season, round=1, roster_id=original, previous_owner_id=sender, owner_id=receiver)

    def trade(self, **updates):
        row = self.f.trade()
        row.update(roster_ids=[1, 2, 3], draft_picks=[self.pick(), self.pick(7, 3, 2, '2029'), self.pick(2, 2, 3, '2027')])
        row.update(updates)
        return row

    def test_retained_day_counts_match_original_directed_consideration(self):
        row = self.row('4')
        self.assertEqual(row['completed_trades'], 2)
        self.assertEqual((row['firsts_received'], row['firsts_sent']), (3, 1))
        self.assertEqual((row['receiving_trades'], row['sending_trades']), (1, 1))
        self.assertEqual(row['dated_trades'], 2)
        self.assertEqual(datetime.fromisoformat(row['first_completion_at'].replace('Z', '+00:00')), datetime.fromtimestamp(1772373665246 / 1000, timezone.utc))
        self.assertEqual(datetime.fromisoformat(row['last_completion_at'].replace('Z', '+00:00')), datetime.fromtimestamp(1791731121347 / 1000, timezone.utc))
        self.assertIn('PICK-2027-R1-ORIG7', next(r for r in row['references'] if r['transaction_id'] == '1333655835015942144')['firsts_received'])
        html = self.page('4')
        self.assertIn('3 pick transfers across 1 completed trade', html)
        self.assertIn('Coverage: partial', html)
        self.assertIn('Franchise history', html)

    def test_multiple_firsts_and_multiteam_directions_count_assets_and_deals_separately(self):
        trade = self.trade()
        trade['draft_picks'].append(deepcopy(trade['draft_picks'][0]))
        self.f.past({'1': [trade, deepcopy(trade)], '2': [deepcopy(trade)]})
        row = self.row()
        self.assertEqual(row['completed_trades'], 1)
        self.assertEqual((row['firsts_received'], row['firsts_sent']), (2, 1))
        self.assertEqual((row['receiving_trades'], row['sending_trades']), (1, 1))
        ref = row['references'][0]
        self.assertEqual(ref['firsts_received'], ['PICK-2028-R1-ORIG9', 'PICK-2029-R1-ORIG7'])
        self.assertEqual(ref['firsts_sent'], ['PICK-2027-R1-ORIG2'])
        self.assertIn('2 pick transfers across 1 completed trade', self.page())

    def test_same_exact_pick_in_later_trade_counts_a_separate_directed_transfer(self):
        self.f.past({'1': [self.trade(transaction_id='first', draft_picks=[self.pick()]),
                            self.trade(transaction_id='later', draft_picks=[self.pick(9, 2, 3)])]})
        row = self.row()
        self.assertEqual((row['completed_trades'], row['firsts_received'], row['firsts_sent']), (2, 1, 1))
        self.assertEqual((row['receiving_trades'], row['sending_trades']), (1, 1))
        self.assertEqual({pick for r in row['references'] for direction in ('firsts_received', 'firsts_sent') for pick in r[direction]}, {'PICK-2028-R1-ORIG9'})

    def test_pending_rejected_waivers_and_corrections_are_not_completed_trades(self):
        rows = [self.trade(transaction_id=state, status=state) for state in ('pending', 'failed', 'rejected', 'cancelled', 'unknown')]
        rows.extend([self.trade(transaction_id=kind, type=kind) for kind in ('waiver', 'correction')])
        rows.append(self.trade(transaction_id='supported'))
        self.f.past({'1': rows})
        row = self.row()
        self.assertEqual(row['completed_trades'], 1)
        self.assertEqual([r['transaction_id'] for r in row['references']], ['supported'])

    def test_empty_partial_history_is_unknown_not_a_zero(self):
        row = self.row()
        self.assertIsNone(row['completed_trades'])
        self.assertIsNone(row['firsts_received'])
        self.assertIn('totals are unknown', self.page())
        self.assertNotIn('0 completed trades observed', self.page())

    def test_supported_zero_is_only_a_zero_within_observed_trades(self):
        self.f.past({'1': [self.trade(draft_picks=[])]})
        row = self.row()
        self.assertEqual((row['completed_trades'], row['firsts_received'], row['firsts_sent']), (1, 0, 0))
        self.assertTrue(row['pick_counts_complete_in_sample'])
        self.assertIn('0 pick transfers across 0 completed trades', self.page())
        self.assertIn('unacquired periods are not zero activity', self.page())

    def test_complete_observed_empty_scope_can_support_zero(self):
        row = _CompletedTradeObservations('1').result(seasons=[{'season': 2031, 'state': 'complete'}], stable=True, earlier_gap=False)
        self.assertEqual((row['completed_trades'], row['firsts_received'], row['firsts_sent']), (0, 0, 0))
        self.assertIn('0 completed trades observed', _completed_trade_observations({'completed_trade_observations': row}))

    def test_incomplete_exact_pick_identity_keeps_only_supported_lower_bounds(self):
        self.f.past({'1': [self.trade(draft_picks=[self.pick(), self.pick(None, 2, 1)])]})
        row = self.row()
        self.assertEqual((row['completed_trades'], row['firsts_received']), (1, 1))
        self.assertIsNone(row['firsts_sent'])
        self.assertFalse(row['pick_counts_complete_in_sample'])
        self.assertIn('At least 1 pick transfer', self.page())
        self.assertIn('Unknown; exact pick consideration is incomplete', self.page())

    def test_conflicting_exact_pick_directions_do_not_invent_a_transfer(self):
        self.f.past({'1': [self.trade(draft_picks=[self.pick(), self.pick(9, 2, 1)])]})
        row = self.row()
        self.assertIsNone(row['firsts_received'])
        self.assertIsNone(row['firsts_sent'])

    def test_manager_change_never_backdates_counts_to_current_manager(self):
        self.f.past({'1': [self.trade()]})
        before = self.row()
        self.f.f.data['teams'][1]['owner_id'] = 'new-current-owner'
        after = self.row()
        self.assertEqual(before, after)
        self.assertIn('do not establish the current manager', self.page())
        self.assertNotIn('new-current-owner', self.page())

    def test_undated_completed_trade_is_not_given_a_creation_based_window(self):
        self.f.past({'1': [self.trade(status_updated=None)]})
        row = self.row()
        self.assertEqual((row['completed_trades'], row['dated_trades']), (1, 0))
        self.assertIsNone(row['first_completion_at'])
        self.assertIn('Completion date window unknown', self.page())

    def test_unlinked_source_season_is_not_current_franchise_behavior(self):
        self.f.past({'1': [self.trade()]})
        current = deepcopy(self.f.f.fixture.sources[0])
        current['league']['previous_league_id'] = None
        self.f.f.data['league']['previous_league_id'] = None
        self.f.f.publish(current)
        row = self.row()
        self.assertIsNone(row['completed_trades'])
        self.assertEqual(row['unattributed_source_trades'], 1)
        self.assertIn('franchise continuity or identity is unconfirmed', self.page())

    def test_future_completion_cannot_establish_an_observed_completed_trade(self):
        self.f.past({'1': [self.trade(status_updated=4102444800000)]})
        self.assertIsNone(self.row()['completed_trades'])

    def test_source_change_withholds_the_whole_numeric_summary(self):
        self.f.past({'1': [self.trade()]})
        graph = self.f.graph()
        calls = []
        def version(*args):
            calls.append(None)
            return 'first' if len(calls) == 1 else 'changed'
        with patch.object(graph.store, 'dataset_version', side_effect=version):
            view = franchise_timeline(graph, '2')
        self.assertFalse(view['stable_source'])
        self.assertIsNone(view['completed_trade_observations']['completed_trades'])
        self.assertIn('Source changed', _completed_trade_observations(view))

    def test_pagination_does_not_recount_a_visible_page_as_the_sample(self):
        self.f.past({'1': [self.trade(transaction_id='sample-'+str(i)) for i in range(31)]})
        first, last = self.row(page=1, per_page=10), self.row(page=4, per_page=10)
        self.assertEqual(first, last)
        self.assertEqual(first['completed_trades'], 31)
        self.assertEqual(len(first['references']), 12)

    def test_other_league_never_receives_day_trade_references(self):
        self.assertEqual(self.row('4')['completed_trades'], 2)
        self.f.f.data = self.f.f.fixture.data[fixtures.fixtures.ARK]
        row = self.row('4')
        self.assertIsNone(row['completed_trades'])
        self.assertEqual(row['references'], [])
        self.assertNotIn('1333655835015942144', self.page('4'))

    def test_reads_do_not_build_intelligence_or_write_history(self):
        store = self.f.f.fixture.store
        before = store.dataset_version(self.f.f.data['league']['league_id'])
        with patch('src.core.intelligence.orchestrator.intelligence_orchestrator.analyze', side_effect=AssertionError('No analytics on render')):
            for _ in range(3):
                self.assertIn('Completed trade observations', self.page('4'))
        self.assertEqual(store.dataset_version(self.f.f.data['league']['league_id']), before)


if __name__ == '__main__':
    unittest.main()

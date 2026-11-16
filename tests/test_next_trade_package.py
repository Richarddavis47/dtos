"""Canonical retained-record package controls; synthetic edits are explicit."""
import copy
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.core.historical_memory.graph import HistoricalAssetGraph
from src.core.historical_memory.read_model import HistoricalReadModelCache
from src.ui.trade_timeline import render_timeline
from tests import test_trade_timeline as fixtures

DAY, ARK = fixtures.DAY, fixtures.ARK

ROOT = '90001'
LATER = '90002'
JAN = 1767225600000
FEB = 1769904000000
MAR = 1772323200000


def trade(identity, stamp, *, adds=None, drops=None, picks=None, parties=None):
    return {'transaction_id': identity, 'type': 'trade', 'status': 'complete',
            'created': stamp, 'status_updated': stamp, 'roster_ids': parties or [1, 2],
            'adds': adds or {}, 'drops': drops or {}, 'draft_picks': picks or [], 'waiver_budget': []}


def player_exchange(identity, stamp, *, package=False):
    return trade(identity, stamp, adds={'100': 2, '200': 1, **({'101': 2} if package else {})},
                 drops={'100': 1, '200': 2, **({'101': 1} if package else {})})


class NextTradePackageTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.TradeTimelineTests()
        self.f.setUp()
        self.f.load()
        self.f.load(1)
        self.facts = copy.deepcopy(self.f.sources[0])
        self.root = trade(ROOT, JAN, adds={'100': 1, '110': 2}, drops={'100': 2, '110': 1})
        self.later = player_exchange(LATER, FEB)

    def tearDown(self):
        self.f.tearDown()

    def publish(self, rows=None, *, current=False):
        facts = copy.deepcopy(self.facts)
        facts['transactions'] = {'1': rows if rows is not None else [self.root, self.later]}
        self.f.cache.write(self.f.cache.normalize(DAY, 2026, facts))
        if current:
            self.f.data[DAY]['season_transactions'] = facts['transactions']
        self.f.store.update_current(DAY, self.f.data[DAY])
        return HistoricalAssetGraph(self.f.store, DAY, self.f.data[DAY], self.f.memory)

    def model(self, rows=None, **kw):
        graph = self.publish(rows, **kw)
        return graph, graph.trade_timeline(ROOT)

    def followed(self, model, asset='DTOS-P-100'):
        return next(b for b in model['branches'] if b['asset_id'] == asset)['next_exchange']

    def test_player_alone_exact_package_from_independent_raw_source(self):
        _, model = self.model()
        self.assertEqual(self.followed(model)['state'], 'observed')
        package = model['next_exchanges'][0]
        # Expected direction comes directly from the fixture's native source maps.
        expected = {(p, str(self.later['drops'][p]), str(r)) for p, r in self.later['adds'].items()}
        actual = {(m['asset_id'].removeprefix('DTOS-P-'), m['sender']['id'].rsplit(':', 1)[1],
                   m['receiver']['id'].rsplit(':', 1)[1]) for m in package['movements']}
        self.assertEqual(actual, expected)
        self.assertTrue(package['complete'])
        self.assertEqual(package['url'], '/trades/history/' + LATER)

    def test_multi_asset_full_return_not_individual_allocation(self):
        self.later = player_exchange(LATER, FEB, package=True)
        graph, model = self.model()
        html = render_timeline(model, graph.trade_dossier(ROOT))
        self.assertIn('The full return was for this package', html)
        self.assertIn('other package asset', html)
        self.assertIn('not attributed to the followed asset alone', html)
        self.assertNotIn('value_total', str(model['next_exchanges']))

    def test_two_original_receipts_share_one_package(self):
        self.root['adds']['101'] = 1
        self.root['drops']['101'] = 2
        self.later = player_exchange(LATER, FEB, package=True)
        _, model = self.model()
        self.assertEqual(len(model['next_exchanges']), 1)
        self.assertEqual({b['asset_id'] for b in model['next_exchanges'][0]['followed_branches']},
                         {'DTOS-P-100', 'DTOS-P-101'})

    def test_retained_exact_pick_conversion_then_complete_package(self):
        graph = self.f.load()
        model = graph.trade_timeline('1333655835015942144')
        package = model['next_exchanges'][0]
        followed = next(b for b in package['followed_branches'] if b['converted'])
        self.assertEqual(followed['asset_id'], 'PICK-2026-R2-ORIG7')
        self.assertEqual(followed['outgoing_asset_id'], 'DTOS-P-13346')
        self.assertEqual(package['transaction_id'], '1414718106177122304')
        self.assertEqual({m['asset_id'] for m in package['movements']},
                         {'DTOS-P-13346', 'DTOS-P-13417', 'PICK-2029-R2-ORIG1'})

    def test_exact_same_round_picks_keep_original_franchises(self):
        self.later['draft_picks'] = [{'season': '2029', 'round': 1, 'roster_id': r,
            'previous_owner_id': 2, 'owner_id': 1} for r in (1, 2)]
        _, model = self.model()
        picks = [m for m in model['next_exchanges'][0]['movements'] if m['kind'] == 'pick']
        self.assertEqual({m['asset_id'] for m in picks}, {'PICK-2029-R1-ORIG1', 'PICK-2029-R1-ORIG2'})
        self.assertTrue(all('originally' in m['label'] for m in picks))

    def test_multi_party_directions_and_counterparties(self):
        self.later = trade(LATER, FEB, parties=[1, 2, 3], adds={'100': 3, '200': 1, '300': 2},
                           drops={'100': 1, '200': 2, '300': 3})
        _, model = self.model()
        package = model['next_exchanges'][0]
        self.assertEqual(len(package['participants']), 3)
        self.assertEqual(len(package['movements']), 3)
        self.assertEqual(next(m for m in package['movements'] if m['asset_id'] == 'DTOS-P-100')['receiver']['id'], DAY + ':franchise:3')

    def test_release_then_reacquisition_stops_original_receipt(self):
        drop = {'transaction_id': 'drop', 'type': 'free_agent', 'status': 'complete',
                'created': JAN + 1000, 'drops': {'100': 1}, 'adds': {}}
        acquire = {**drop, 'transaction_id': 'acquire', 'created': JAN + 2000,
                   'drops': {}, 'adds': {'100': 1}}
        _, model = self.model([self.root, drop, acquire, self.later])
        self.assertFalse(model['next_exchanges'])
        self.assertIn('intervening', self.followed(model)['reason'])

    def test_different_sender_is_not_original_recipient_proceeds(self):
        self.later['drops']['100'] = 3
        self.later['roster_ids'] = [1, 2, 3]
        _, model = self.model()
        self.assertFalse(model['next_exchanges'])
        self.assertIn('ownership', self.followed(model)['reason'])

    def test_fractional_second_later_clock_is_not_sorted_before_original(self):
        self.later['created'] = self.later['status_updated'] = JAN + 1
        _, model = self.model()
        self.assertEqual(model['next_exchanges'][0]['transaction_id'], LATER)
        branch = next(b for b in model['branches'] if b['asset_id'] == 'DTOS-P-100')
        self.assertTrue(any(e['source_record_id'] == LATER for e in branch['events']))

    def test_pick_conversion_overlap_with_later_trade_withholds_continuation(self):
        facts = copy.deepcopy(self.facts)
        for draft in facts['drafts']:
            draft['last_picked'] = 1791657590006 + 1000
        self.f.data[DAY]['drafts'] = facts['drafts']
        self.f.cache.write(self.f.cache.normalize(DAY, 2026, facts))
        self.f.store.update_current(DAY, self.f.data[DAY])
        graph = HistoricalAssetGraph(self.f.store, DAY, self.f.data[DAY], self.f.memory)
        model = graph.trade_timeline('1333655835015942144')
        branch = next(b for b in model['branches'] if b['asset_id'] == 'PICK-2026-R2-ORIG7')
        self.assertEqual(branch['next_exchange']['state'], 'unknown')
        self.assertIn('overlapping', branch['next_exchange']['reason'])

    def test_equal_original_clock_withheld(self):
        self.later['created'] = JAN
        _, model = self.model()
        self.assertFalse(model['next_exchanges'])
        self.assertIn('Equal', self.followed(model)['reason'])

    def test_equal_later_clocks_do_not_choose_by_id(self):
        another = player_exchange('90003', FEB)
        _, model = self.model([self.root, self.later, another])
        self.assertFalse(model['next_exchanges'])

    def test_unknown_clock_withheld_not_assumed_later(self):
        self.later['created'] = self.later['status_updated'] = None
        _, model = self.model()
        self.assertFalse(model['next_exchanges'])
        self.assertIn('Missing event dates', self.followed(model)['reason'])

    def test_exact_duplicate_does_not_duplicate_package(self):
        _, model = self.model([self.root, self.later, copy.deepcopy(self.later)])
        self.assertEqual(len(model['next_exchanges']), 1)

    def test_conflicting_completed_native_rows_withheld_before_key_collapse(self):
        conflict = copy.deepcopy(self.later)
        conflict['adds']['200'] = 3
        conflict['roster_ids'] = [1, 2, 3]
        _, model = self.model([self.root, self.later, conflict])
        self.assertFalse(model['next_exchanges'])
        self.assertIn('Conflicting', self.followed(model)['reason'])

    def test_conflicting_current_publication_also_withheld(self):
        conflict = copy.deepcopy(self.later)
        conflict['adds']['200'] = 2
        _, model = self.model([self.root, self.later, conflict], current=True)
        self.assertFalse(model['next_exchanges'])

    def test_original_transaction_conflict_withholds_receipt(self):
        conflict = copy.deepcopy(self.root)
        conflict['drops']['100'] = 3
        conflict['roster_ids'] = [1, 2, 3]
        _, model = self.model([self.root, conflict, self.later])
        self.assertFalse(model['next_exchanges'])

    def test_pending_rejected_and_cancelled_do_not_replace_completed(self):
        rows = [self.root, self.later]
        for n, status in enumerate(('pending', 'rejected', 'cancelled', 'failed')):
            rows.append({**player_exchange(str(91000 + n), JAN + 1000 + n), 'status': status})
        _, model = self.model(rows)
        self.assertEqual(model['next_exchanges'][0]['transaction_id'], LATER)

    def test_partial_consideration_keeps_supported_movements(self):
        self.later['adds']['missing-sender'] = 1
        graph, model = self.model()
        package = model['next_exchanges'][0]
        self.assertFalse(package['complete'])
        self.assertEqual(len(package['movements']), 2)
        html = render_timeline(model, graph.trade_dossier(ROOT))
        self.assertIn('full package return is unknown', html)
        self.assertNotIn('The full return was for this package', html)

    def test_missing_outgoing_identity_cannot_be_inferred(self):
        self.later['drops'].pop('100')
        _, model = self.model()
        self.assertFalse(model['next_exchanges'])

    def test_first_exchange_only_even_if_later_record_more_complete(self):
        later2 = player_exchange('90003', MAR)
        self.later['adds']['missing-sender'] = 1
        _, model = self.model([self.root, self.later, later2])
        self.assertEqual(model['next_exchanges'][0]['transaction_id'], LATER)
        self.assertFalse(model['next_exchanges'][0]['complete'])

    def test_bounded_event_limit_withholds_first_claim(self):
        rows = [self.root] + [player_exchange(str(92000 + n), FEB + n * 1000) for n in range(101)]
        _, model = self.model(rows)
        self.assertFalse(model['next_exchanges'])
        self.assertIn('limit', self.followed(model)['reason'])

    def test_bounded_package_does_not_claim_truncated_full_return(self):
        for n in range(50):
            self.later['adds'][str(500 + n)] = 1
            self.later['drops'][str(500 + n)] = 2
        _, model = self.model()
        self.assertFalse(model['next_exchanges'])
        self.assertIn('limit', self.followed(model)['reason'])

    def test_other_league_cannot_supply_transaction(self):
        graph, model = self.model()
        foreign = HistoricalAssetGraph(self.f.store, ARK, self.f.data[ARK], self.f.memory)
        self.assertIsNone(foreign.trade_timeline(ROOT))
        self.assertEqual(model['league_id'], DAY)

    def test_source_generation_invalidates_read_model(self):
        self.publish()
        cache = HistoricalReadModelCache()
        before = cache.get(self.f.store, DAY, self.f.data[DAY])
        first = before.trade_timeline(ROOT)
        self.later['draft_picks'] = [{'season': '2029', 'round': 1, 'roster_id': 2,
                                    'previous_owner_id': 2, 'owner_id': 1}]
        self.publish()
        after = cache.get(self.f.store, DAY, self.f.data[DAY])
        self.assertIsNot(before, after)
        self.assertNotEqual(first['next_exchanges'], after.trade_timeline(ROOT)['next_exchanges'])

    def test_generation_changes_during_read_withhold_packages(self):
        graph = self.publish()
        from src.core.historical_memory.timeline import timeline
        changed = False
        version = self.f.store.dataset_version
        def read_and_replace(*args):
            nonlocal changed
            result = timeline(*args)
            changed = True
            return result
        with patch('src.core.historical_memory.timeline.timeline', side_effect=read_and_replace), patch.object(
                self.f.store, 'dataset_version', side_effect=lambda league: version(league) + ('-replacement' if changed else '')):
            model = graph.trade_timeline(ROOT)
        self.assertFalse(model['next_exchanges'])
        self.assertFalse(graph._timelines)

    def test_rendered_route_exact_packages_retained_labels_no_provider_work(self):
        self.publish()
        with patch('routes.historical_assets.historical_store', self.f.store), TestClient(self.f.app()) as client:
            response = client.get('/trades/history/' + ROOT)
            self.assertEqual(response.status_code, 200)
            self.assertIn('See the later trade’s package', response.text)
            self.assertIn('RETAINED / NOT REVALIDATED', response.text)
            later = client.get('/trades/history/' + LATER + '?from_trade=' + ROOT)
            self.assertIn('Back to original trade timeline', later.text)
            self.assertIn('href="/trades/history/' + ROOT + '"', later.text)

    def test_held_graph_does_not_reuse_package_after_source_update(self):
        graph, model = self.model()
        self.assertTrue(model['next_exchanges'])
        self.later['draft_picks'] = [{'season': '2029', 'round': 1, 'roster_id': 2,
                                    'previous_owner_id': 2, 'owner_id': 1}]
        self.publish()
        held = graph.trade_timeline(ROOT)
        self.assertFalse(held['next_exchanges'])
        self.assertIn('Source evidence changed', self.followed(held)['reason'])

    def test_unlinked_source_league_cannot_supply_recipient_return(self):
        graph = self.publish()
        events = graph.events
        def foreign_events(*args, **kwargs):
            return [{**e, 'source_league_id': ARK} if e['source_record_id'] == LATER else e
                    for e in events(*args, **kwargs)]
        with patch.object(graph, 'events', side_effect=foreign_events):
            model = graph.trade_timeline(ROOT)
        self.assertFalse(model['next_exchanges'])
        self.assertIn('source league-season chain', self.followed(model)['reason'])

    def test_faab_is_original_consideration_separate_from_asset_valuation(self):
        self.later['waiver_budget'] = [{'sender': 2, 'receiver': 1, 'amount': 0},
                                      {'sender': 1, 'receiver': 2, 'amount': 12}]
        _, model = self.model()
        cash = [m for m in model['next_exchanges'][0]['movements'] if m['kind'] == 'faab']
        self.assertEqual({m['label'] for m in cash}, {'0 FAAB', '12 FAAB'})
        self.assertFalse(any('market_value' in m for m in cash))

    def test_semantic_duplicate_order_does_not_create_conflict(self):
        duplicate = copy.deepcopy(self.later)
        duplicate['roster_ids'].reverse()
        duplicate['adds'] = dict(reversed(list(duplicate['adds'].items())))
        _, model = self.model([self.root, self.later, duplicate])
        self.assertEqual(len(model['next_exchanges']), 1)

    def test_repeated_expansion_reads_do_not_create_storage_or_runtime_owners(self):
        graph = self.publish()
        first = graph.trade_timeline(ROOT)
        with patch.object(self.f.store, 'records', wraps=self.f.store.records) as reads:
            for _ in range(12):
                self.assertEqual(graph.trade_timeline(ROOT)['next_exchanges'], first['next_exchanges'])
            self.assertEqual(reads.call_count, 0)
        self.assertLessEqual(len(graph._timelines), 32)


if __name__ == '__main__':
    unittest.main()

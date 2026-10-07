"""Exact mathematical reuse, scope changes and preserved discovery intelligence."""
import copy
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

from services import trade_intelligence as trade
from src.core.trade_intelligence.lineup import optimal_legal_lineup
from src.core.trade_intelligence.lineup_memo import LineupStore, SearchLineupMemo, lineup_store
from tests import test_trade_discovery_repair as discovery_fixtures
from tests import test_batch5_lineup_state_equivalence as lineup_references


def business(value):
    if isinstance(value, dict):
        return {k: business(v) for k, v in value.items() if k != 'reuse'
                and not str(k).endswith('_seconds') and k != 'timings_seconds'
                and not str(k).endswith('_duration_ms')}
    if isinstance(value, (tuple, list)):
        return [business(v) for v in value]
    return value


class LineupMemoTests(unittest.TestCase):
    def setUp(self):
        self.players = [{'id': 'a', 'position': 'QB', 'projected_points': 10},
                        {'id': 'b', 'position': 'QB', 'projected_points': 8}]
        self.store = LineupStore(max_entries=8)

    def test_optimizer_retains_prior_transition_eligibility_and_symmetry_results(self):
        # These frozen/randomized function fixtures predate unittest discovery.
        # Invoke them here so the release validator and product CI run them.
        lineup_references.test_lazy_tie_keys_preserve_pre_correction_assignments()
        lineup_references.test_eligibility_reuse_preserves_exact_pre_reuse_solver()
        lineup_references.test_repeated_slot_symmetry_preserves_complete_and_partial_assignments()

    def test_exact_result_and_generation_session_scoring_roster_invalidation(self):
        memo = SearchLineupMemo(('session-a', 'generation-a'), self.store)
        expected = optimal_legal_lineup(self.players, ['QB'], week=3)
        self.assertEqual(memo.solve(self.players, ['QB'], week=3), expected)
        self.assertEqual(memo.solve(copy.deepcopy(self.players), ['QB'], week=3), expected)
        self.assertEqual((memo.hits, memo.misses), (1, 1))
        for scope in (('session-b', 'generation-a'), ('session-a', 'generation-b')):
            other = SearchLineupMemo(scope, self.store)
            self.assertEqual(other.solve(self.players, ['QB'], week=3), expected)
            self.assertEqual(other.hits, 0)
        for players, slots, week in ((self.players, ['SUPER_FLEX'], 3), (self.players, ['QB'], 4),
                                    ([dict(self.players[0], projected_points=5), self.players[1]], ['QB'], 3),
                                    ([dict(self.players[0], lineup_eligible=False), self.players[1]], ['QB'], 3),
                                    ([dict(self.players[0], bye_week=3), self.players[1]], ['QB'], 3),
                                    ([dict(self.players[0], name='New label'), self.players[1]], ['QB'], 3)):
            self.assertEqual(memo.solve(players, slots, week=week), optimal_legal_lineup(players, slots, week=week))
        self.assertEqual(memo.misses, 6)

    def test_missing_zero_and_nonfinite_evidence_preserve_exact_solver_results(self):
        memo = SearchLineupMemo('scope', self.store)
        for value in (None, 0, -1, float('nan'), float('inf')):
            players = [dict(self.players[0], projected_points=value)]
            self.assertEqual(memo.solve(players, ['QB']), optimal_legal_lineup(players, ['QB']))
        with self.assertRaises(ValueError):
            memo.solve([self.players[0], self.players[0]], ['QB'])
        self.assertEqual(len(self.store.entries), 5)

    def test_byte_entry_ttl_and_disabled_bounds(self):
        now = [0]
        store = LineupStore(max_entries=2, max_bytes=4096, ttl=3, clock=lambda: now[0])
        for i in range(20):
            memo = SearchLineupMemo(i, store)
            memo.solve(self.players, ['QB'])
            self.assertLessEqual(store.status()['entries'], 2)
            self.assertLessEqual(store.status()['retained_bytes'], 4096)
        now[0] = 4
        SearchLineupMemo('expired', store)
        self.assertEqual(store.status()['retained_bytes'], 0)
        for disabled in (LineupStore(max_entries=0), LineupStore(max_bytes=0), LineupStore(ttl=0)):
            SearchLineupMemo('disabled', disabled).solve(self.players, ['QB'])
            self.assertEqual(disabled.status()['entries'], 0)

    def test_concurrent_reads_are_immutable_and_bounded(self):
        def solve(_):
            return SearchLineupMemo('same', self.store).solve(self.players, ['QB'])
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(solve, range(24)))
        self.assertTrue(all(row == results[0] for row in results))
        self.assertEqual(self.store.status()['entries'], 1)
        with self.assertRaises(AttributeError):
            results[0].projected_points = 999


class TradeSearchReuseTests(unittest.TestCase):
    def setUp(self):
        fixture = discovery_fixtures.DiscoveryRepairTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture, self.data = fixture, fixture.data
        lineup_store.clear()
        self.addCleanup(lineup_store.clear)

    def test_all_workflows_exact_assessments_and_near_misses_equal_uncached(self):
        original_reader = trade._search_reader
        def uncached(*args):
            reader = original_reader(*args)
            reader.lineup_solver = None
            return reader
        for flow, extra in (('recommended', {}), ('shop', {'asset_id': '1q'}),
                            ('trade_for', {'asset_id': '2w'}), ('cheaper', {})):
            payload = dict(workflow=flow, active_roster_id=1, strategy='RETOOL', **extra)
            if flow == 'cheaper':
                payload.update(partner_roster_id=2, assets_sent=['1q', '1qb'], assets_received=['2w'], instruction='make it cheaper')
            operation = trade.assist_trade_request if flow == 'cheaper' else trade.generate_trade_workflow
            with self.subTest(workflow=flow):
                with patch('services.trade_intelligence._search_reader', side_effect=uncached):
                    reference = operation(self.data, payload)
                cached = operation(self.data, payload)
                self.assertEqual(business(cached), business(reference))
                self.assertGreater(cached['search_evidence']['reuse']['lineup_hits'], 0)

    def test_warm_next_five_exact_locks_diversity_and_generation_invalidation(self):
        first = self.fixture.search('recommended', protected_assets=['1q'])
        warm = self.fixture.search('recommended', protected_assets=['1q'])
        self.assertEqual(business(first), business(warm))
        self.assertEqual(warm['search_evidence']['reuse']['lineup_misses'], 0)
        families = [row['family_id'] for row in first['results']]
        next_page = self.fixture.search('recommended', protected_assets=['1q'], excluded_recommendation_families=families)
        self.assertFalse(set(families) & {row['family_id'] for row in next_page['results']})
        self.assertGreater(next_page['search_evidence']['reuse']['lineup_hits'], 0)
        self.assertTrue(all('1q' not in r['proposal']['assets_sent'] for r in next_page['results']))
        self.data['market_data']['generation'] = 'changed-canonical-generation'
        refreshed = self.fixture.search('recommended', protected_assets=['1q'])
        self.assertGreater(refreshed['search_evidence']['reuse']['lineup_misses'], 0)

    def test_strategy_reassessed_without_refetching_prices_or_solving_same_lineups(self):
        first = self.fixture.search('recommended')
        from src.core.valuation.calibration import cached_market_facts
        with patch('services.trade_intelligence.cached_market_facts', wraps=cached_market_facts) as prices:
            changed = trade.generate_trade_workflow(self.data, dict(workflow='recommended', active_roster_id=1, strategy='WIN NOW'))
        self.assertEqual(prices.call_count, 1)
        self.assertGreater(changed['search_evidence']['reuse']['lineup_hits'], 0)
        by_package = {tuple(r['proposal']['assets_sent'] + r['proposal']['assets_received']): r for r in first['results']}
        for row in changed['results']:
            previous = by_package.get(tuple(row['proposal']['assets_sent'] + row['proposal']['assets_received']))
            if previous:
                self.assertEqual(row['evaluation']['values'], previous['evaluation']['values'])

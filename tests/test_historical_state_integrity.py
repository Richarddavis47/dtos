"""Historical state admission, not revalidation of retained FOIS grades."""
import unittest

from src.core.historical_franchise_state import HistoricalBoundary, HistoricalFranchiseStateService
from src.core.historical_intelligence import GlobalMarketCheckpoint, HistoricalIntelligenceService
from src.core.historical_transaction_intelligence import HistoricalTransactionIntelligenceService
from tests.test_historical_franchise_state import FixtureStore
from tests.historical_market_fixture import canonical_quote




class CoveredStore(FixtureStore):
    def __init__(self):
        super().__init__()
        self.complete_periods = True
        for row in self.rows:
            if row['entity_type'] == 'roster_snapshot':
                row['occurred_at'] = '2025-12-31T00:00:00Z'

    def source_coverage(self, league_id, *, season=None):
        return {'league_id': league_id, 'seasons': [{'season': 2025,
            'transactions': {'complete_acquisition': self.complete_periods,
                             'acquired': list(range(19)) if self.complete_periods else [0, 1],
                             'unacquired': [] if self.complete_periods else list(range(2, 19))}}]}


class HistoricalStateIntegrityTests(unittest.TestCase):
    def state(self, store=None, quotes=None):
        store = store or CoveredStore()
        quotes = quotes if quotes is not None else [canonical_quote(p) for p in ('player-old', 'player-new', 'player-stay')]
        service = HistoricalFranchiseStateService(HistoricalIntelligenceService(store, quotes))
        return service, service.reconstruct(store.league, '1', HistoricalBoundary(
            2025, occurred_at='2025-10-01T12:00:00Z', week=5))

    def test_native_100_and_10000_units_neither_establish_canonical_window(self):
        for value in (100, 10000):
            store = CoveredStore()
            players = [f'p{i}' for i in range(31)]
            store.rows[1]['payload']['players'] = players
            store.rows = [r for r in store.rows if r['entity_type'] != 'trade']
            quotes = [GlobalMarketCheckpoint.create(asset_id=p, occurred_at='2025-09-30T00:00:00Z',
                provider='DynastyProcess', normalized_value=value, confidence=100,
                classification='historical', reason_codes=('trade',)) for p in players]
            with self.subTest(value=value):
                _, state = self.state(store, quotes)
                self.assertIsNone(state.roster_market_value)
                self.assertIsNone(state.competitive_window.classification)
                self.assertEqual(state.market_coverage_ratio, 0)

    def test_compatible_canonical_observations_and_zero_are_usable(self):
        _, state = self.state(quotes=[canonical_quote('player-new', 0), canonical_quote('player-stay', 500), canonical_quote('PICK-2027-R1-ORIG2', 200)])
        self.assertEqual(state.roster_market_value, 500)
        self.assertEqual(state.market_coverage_ratio, 1)
        self.assertEqual(next(p.market_value for p in state.players if p.asset_id == 'player-new'), 0)
        self.assertIsNotNone(state.competitive_window.classification)

    def test_missing_identity_units_method_and_source_fail_closed(self):
        for changes in ({'normalization_version': None}, {'value_concept': None},
                        {'comparison_identity': ()}, {'normalization_version': 'raw-10000'},
                        {'provider': 'unknown-source'}, {'source_reference': None},
                        {'source_reference': 'unknown'}, {'market_context_id': 'unavailable'},
                        {'comparison_identity': ('external_market_normalized_index', '0-10000', 'x', 'x', 'DynastyProcess')},
                        {'normalized_value': 10000}, {'normalized_value': float('nan')}):
            with self.subTest(changes=changes):
                _, state = self.state(quotes=[canonical_quote('player-new', **changes), canonical_quote('player-stay')])
                self.assertIsNone(state.roster_market_value)
                self.assertIsNone(state.competitive_window.classification)

    def test_mixed_comparison_contexts_cannot_be_summed(self):
        _, state = self.state(quotes=[canonical_quote('player-new'), canonical_quote('player-stay', market_context_id='different')])
        self.assertIsNone(state.roster_market_value)
        self.assertEqual(state.known_market_value, 0)
        self.assertIsNone(state.competitive_window.classification)

    def test_future_quotes_and_provider_knowledge_cannot_enter_decision(self):
        for changes in ({'occurred_at': '2025-10-02T00:00:00Z'},
                        {'provider_observations': ({'observed_at': '2025-09-30T00:00:00Z',
                          'source_identity': 'source', 'metadata': {'known_at': '2025-10-02T00:00:00Z'}},)}):
            _, state = self.state(quotes=[canonical_quote('player-new', **changes), canonical_quote('player-stay')])
            self.assertIsNone(state.roster_market_value)
            self.assertIsNone(state.competitive_window.classification)

    def test_stale_price_remains_numeric_but_not_supported_window(self):
        _, state = self.state(quotes=[canonical_quote(p, occurred_at='2025-09-01T00:00:00Z') for p in ('player-new', 'player-stay')])
        self.assertEqual(state.roster_market_value, 1000)
        self.assertEqual(state.coverage['market'].availability.value, 'partial')
        self.assertLessEqual(state.coverage['market'].confidence, 35)
        self.assertIsNone(state.competitive_window.classification)

    def test_later_knowledge_clock_does_not_refresh_an_old_quote(self):
        providers = ({'observed_at': '2025-09-01T00:00:00Z', 'source_identity': 'source',
                      'metadata': {'known_at': '2025-09-30T12:00:00Z'}},)
        _, state = self.state(quotes=[canonical_quote(p, provider_observations=providers)
                                     for p in ('player-new', 'player-stay')])
        self.assertEqual(state.roster_market_value, 1000)
        self.assertEqual(state.coverage['market'].availability.value, 'partial')
        self.assertLessEqual(state.coverage['market'].confidence, 35)
        self.assertIsNone(state.competitive_window.classification)

    def test_missing_dart_fannin_trade_is_not_complete_acquisition_history(self):
        store = CoveredStore()
        store.complete_periods = False
        store.rows = [r for r in store.rows if r['entity_type'] != 'trade']
        _, state = self.state(store)
        self.assertEqual(state.coverage['transactions'].availability.value, 'partial')
        self.assertEqual(state.coverage['ownership'].availability.value, 'partial')
        self.assertLessEqual(state.coverage['ownership'].confidence, 40)
        self.assertLessEqual(state.confidence, 40)
        self.assertIsNone(state.competitive_window.classification)

    def test_untimed_roster_is_not_complete_historical_anchor(self):
        store = CoveredStore()
        store.rows[1]['occurred_at'] = None
        _, state = self.state(store)
        self.assertEqual(state.coverage['roster_anchor'].availability.value, 'partial')
        self.assertEqual(state.coverage['ownership'].availability.value, 'partial')
        self.assertIsNone(state.competitive_window.classification)

    def test_missing_movement_fields_cannot_certify_acquisition_disposal_coverage(self):
        store = CoveredStore()
        trade = next(row for row in store.rows if row['entity_type'] == 'trade')
        for field in ('adds', 'drops', 'draft_picks'):
            trade['payload'].pop(field)
        _, state = self.state(store)
        self.assertEqual(state.coverage['transactions'].availability.value, 'partial')
        self.assertIn('incomplete_acquisition_disposal_records', state.warnings)
        self.assertLessEqual(state.confidence, 40)

    def test_source_revision_recovers_and_cache_is_reused(self):
        store = CoveredStore()
        store.complete_periods = False
        service, first = self.state(store)
        self.assertIs(first, service.reconstruct(store.league, '1', first.boundary))
        store.complete_periods = True
        store.generation = 'recovered'
        recovered = service.reconstruct(store.league, '1', first.boundary)
        self.assertEqual(recovered.coverage['transactions'].availability.value, 'complete')
        self.assertEqual(recovered.coverage['ownership'].availability.value, 'complete')
        self.assertNotEqual(first.state_id, recovered.state_id)

    def test_fois_context_contains_limits_without_revalidating_grades(self):
        from src.core.fois.decision_context import roster_context
        store = CoveredStore()
        store.complete_periods = False
        service, _ = self.state(store)
        context = roster_context(service, store.league, 1, {'season': 2025, 'occurred_at': '2025-10-01T12:00:00Z'})
        self.assertEqual(context['ownership_availability'], 'partial')
        self.assertIn('transactions', context['coverage'])
        self.assertTrue(context['reasons'])

    def test_downstream_process_cannot_promote_incomplete_ownership(self):
        store = CoveredStore()
        store.complete_periods = False
        service, _ = self.state(store)
        event = service.history.transaction_history(store.league)[0]
        before, after = service.around_event(store.league, '1', event.event_id)
        process = HistoricalTransactionIntelligenceService._process(before, after)
        self.assertEqual(process.classification.value, 'insufficient_evidence')
        self.assertEqual(process.confidence.value, 'low')
        self.assertTrue(any('reconstruction' in x.lower() for x in process.explanation))

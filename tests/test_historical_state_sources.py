"""Real retained producers and captured Day/Arkham facts, not live FOIS grades."""
from copy import deepcopy
import hashlib
from pathlib import Path
from time import perf_counter
import unittest

from src.core.historical_franchise_state import HistoricalBoundary, HistoricalFranchiseStateService
from src.core.historical_intelligence import HistoricalIntelligenceService
from tests import test_historical_tracker_phase2 as routes


def files(root):
    return {str(p.relative_to(root)): (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob('*') if p.is_file()}


class HistoricalStateSourceTests(unittest.TestCase):
    def setUp(self):
        self.journey = routes.TrackerPhase2Tests()
        self.journey.setUp()
        self.addCleanup(self.journey.tearDown)
        self.fixture = self.journey.fixture

    def service(self):
        return HistoricalFranchiseStateService(HistoricalIntelligenceService(
            self.fixture.store, checkpoint_reader=self.fixture.memory))

    def test_actual_day_dart_fannin_trade_removal_qualifies_coverage_and_preserves_arkham(self):
        service = self.service()
        event = next(e for e in service.history.transaction_history(routes.DAY)
                     if e.source_record_id == '1414718106177122304')
        self.assertEqual(set(event.player_ids), {'13346', '13417'})
        self.assertIn('PICK-2029-R2-ORIG1', event.pick_ids)
        before, after = service.around_event(routes.DAY, '1', event.event_id)
        delta = service.difference(before, after)
        self.assertEqual(delta.players_added, ('13346',))
        self.assertEqual(delta.players_removed, ('13417',))
        self.assertNotEqual(before.coverage['ownership'].availability.value, 'complete')
        ark_before = service.reconstruct(routes.ARK, '1', HistoricalBoundary(2026, occurred_at=event.occurred_at))
        source = deepcopy(self.fixture.sources[0])
        source['transactions'].pop('5')
        self.journey.publish(source)
        missing = service.reconstruct(routes.DAY, '1', before.boundary)
        self.assertEqual(missing.coverage['transactions'].availability.value, 'partial')
        self.assertEqual(missing.coverage['ownership'].availability.value, 'partial')
        self.assertLessEqual(missing.confidence, 40)
        self.assertIsNone(missing.competitive_window.classification)
        self.assertEqual(service.reconstruct(routes.ARK, '1', ark_before.boundary), ark_before)
        page = self.journey.client.get('/history/2026')
        self.assertEqual(page.status_code, 200)
        self.assertIn('coverage', page.text.lower())
        response = self.journey.client.get('/api/history/coverage')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['source_acquisition_status'], 'partial_or_unavailable')
        self.assertNotEqual(response.json()['status'], 'complete')

    def test_actual_canonical_quote_producer_recovers_warm_market_state_without_writes(self):
        service = self.service()
        boundary = HistoricalBoundary(2026, occurred_at='2026-10-12T00:00:00Z', week=5)
        first = service.reconstruct(routes.DAY, '1', boundary)
        self.assertIsNone(next(p.market_value for p in first.players if p.asset_id == '13346'))
        self.fixture.capture('player:13346', '2026-10-08T00:00:00Z', event='2026-10-08T00:00:00Z', value=500)
        recovered = service.reconstruct(routes.DAY, '1', boundary)
        asset = next(p for p in recovered.players if p.asset_id == '13346')
        self.assertEqual(asset.market_value, 500)
        self.assertEqual(asset.market_value_concept, 'canonical_market')
        self.assertEqual(asset.market_comparison_identity[:2], ('external_market_normalized_index', '0-1000'))
        self.assertNotEqual(first.state_id, recovered.state_id)
        self.assertIsNone(recovered.roster_market_value)
        baseline = files(Path(self.fixture.temp.name))
        start = perf_counter()
        for _ in range(40):
            self.assertIs(service.reconstruct(routes.DAY, '1', boundary), recovered)
            self.assertEqual(self.journey.client.get('/api/history/trades/coverage').status_code, 200)
        self.assertEqual(files(Path(self.fixture.temp.name)), baseline)
        self.assertEqual(service.metrics()['provider_calls'], 0)
        print({'historical_settled_reads': 40, 'source_and_database_files': len(baseline),
               'durable_bytes_before_after': sum(item[0] for item in baseline.values()),
               'all_file_hashes_unchanged': True, 'elapsed_ms': round((perf_counter() - start) * 1000, 3),
               'provider_calls': service.metrics()['provider_calls']})

    def test_recorded_exact_picks_and_distinct_league_ownership_remain_accessible(self):
        for league in (routes.DAY, routes.ARK):
            self.journey.data = self.fixture.data[league]
            response = self.journey.client.get('/api/history/franchises/1')
            self.assertEqual(response.status_code, 200)
            self.assertIn(league, response.text)
            other = routes.ARK if league == routes.DAY else routes.DAY
            self.assertNotIn(other + ':franchise:', response.text)
        self.journey.data = self.fixture.data[routes.DAY]
        pick = self.journey.client.get('/picks/PICK-2026-R2-ORIG7')
        self.assertEqual(pick.status_code, 200)
        self.assertIn('2026', pick.text)

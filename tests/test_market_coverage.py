"""Production-shaped quote availability regressions, without network calls."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from src.core.valuation.calibration import cached_market_results
from src.core.valuation.normalization import normalize_cached_value
from src.core.valuation.quote_eligibility import exclusion_reason


class MarketCoverageTests(unittest.TestCase):
    def setUp(self):
        self.row = {'value': 6000, 'confidence': 85, 'format': 'dynasty_2qb',
                    'format_details': {'num_teams': 12, 'ppr': 1},
                    'retrieved_at': datetime.now(timezone.utc).isoformat(), 'source_updated_at': None}
        self.data = {'providers': {'FantasyCalc': {'p': self.row},
                                  'DynastyProcess': {'p': {**self.row, 'value': 2000, 'format_details': {}}}}}

    def test_incompatible_secondary_never_erases_valid_primary(self):
        result = cached_market_results(self.data, ['p'])['p']
        single = cached_market_results({'providers': {'FantasyCalc': {'p': self.row}}}, ['p'])['p']
        self.assertEqual(result.market_consensus, single.market_consensus)
        self.assertEqual(result.confidence_score, single.confidence_score)
        self.assertEqual(result.evidence_state, 'SINGLE-PROVIDER MARKET')
        self.assertEqual([p.provider for p in result.providers_used], ['FantasyCalc'])

    def test_missing_has_no_scalar_fallback(self):
        result = cached_market_results(self.data, ['missing'])['missing']
        self.assertIsNone(result.market_consensus)

    def test_ineligible_current_quotes_stay_unavailable(self):
        for changes, reason in (
            ({'identity_status': 'ambiguous'}, 'AMBIGUOUS_UNRESOLVED_PLAYER_IDENTITY'),
            ({'retrieval_mode': 'historical_snapshot'}, 'HISTORICAL_ONLY_EVIDENCE'),
            ({'availability': 'expired'}, 'STALE_BEYOND_USABLE_POLICY'),
            ({'confidence': 0}, 'ZERO_CONFIDENCE_INVALID_QUOTE'),
            ({'format': 'redraft_1qb'}, 'INCOMPATIBLE_PROVIDER_FORMAT'),
            ({'format_details': {'ppr': 0}}, 'INCOMPATIBLE_PROVIDER_FORMAT')):
            with self.subTest(changes=changes):
                row = {**self.row, **changes}
                self.assertEqual(exclusion_reason('FantasyCalc', row), reason)
                result = cached_market_results({'providers': {'FantasyCalc': {'p': row}}}, ['p'])['p']
                self.assertIsNone(result.market_consensus)

    def test_old_provider_time_not_refreshed_by_retrieval(self):
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        normalized = normalize_cached_value('FantasyCalc', {**self.row, 'source_updated_at': old})
        self.assertEqual(normalized.freshness, 'stale')
        self.assertLess(normalized.confidence_score, normalize_cached_value('FantasyCalc', self.row).confidence_score)

    def test_global_price_independent_of_league_and_invalidation(self):
        other = deepcopy(self.data)
        other['league_id'] = 'other'
        self.assertEqual(cached_market_results(self.data, ['p']), cached_market_results(other, ['p']))
        before = cached_market_results(self.data, ['p'])
        other['providers']['FantasyCalc']['p']['value'] = 9000
        self.assertNotEqual(before, cached_market_results(other, ['p']))
        self.assertEqual(before, cached_market_results(self.data, ['p']))

    def test_input_evidence_not_mutated(self):
        before = deepcopy(self.data)
        cached_market_results(self.data, ['p'])
        self.assertEqual(self.data, before)

    def test_active_trade_and_universe_use_same_acquisition_price(self):
        from tests.test_trade_intelligence import fixture_data
        from services.trade_intelligence import build_trade_workspace
        from src.core.valuation.universe import ValuationUniverse
        data = fixture_data()
        data['market_data']['providers']['DynastyProcess'] = {
            key: {'value': 2000, 'confidence': 75} for key in data['players']}
        expected = cached_market_results(data['market_data'], data['players'])
        workspace = build_trade_workspace(data, 1)
        for pool in workspace['pools'].values():
            for asset in pool:
                if asset.kind == 'player':
                    self.assertEqual(asset.trade_value, expected[asset.asset_id.removeprefix('player:')].market_consensus)
        for asset in ValuationUniverse(data, {}).assets:
            if asset['asset_type'] == 'player':
                self.assertEqual(asset['layers']['market_value']['value'], expected[asset['asset_id'].removeprefix('player:')].market_consensus)

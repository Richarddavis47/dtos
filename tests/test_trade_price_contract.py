from types import SimpleNamespace
import unittest

from src.core.valuation.packages import adjusted_package_value, neutral_trade_value


class TradePriceContractTests(unittest.TestCase):
    def test_zero_market_price_does_not_fall_back_to_intrinsic(self):
        asset = SimpleNamespace(trade_value=0, dynasty_value=999, redraft_value=999, team_fit_value=999)
        self.assertEqual(adjusted_package_value((asset,)).raw_total, 0)

    def test_missing_market_price_is_explicit_not_unrelated_number(self):
        for asset in (SimpleNamespace(trade_value=None, dynasty_value=999), SimpleNamespace(dynasty_value=999)):
            with self.assertRaisesRegex(ValueError, 'acquisition value unavailable'):
                adjusted_package_value((asset,))

    def test_intrinsic_does_not_influence_market_balance(self):
        self.assertEqual(adjusted_package_value((SimpleNamespace(trade_value=600, dynasty_value=None),)),
            adjusted_package_value((SimpleNamespace(trade_value=600, dynasty_value=1000),)))

    def test_invalid_price_is_not_clamped_or_silently_used(self):
        for value in (-1, True, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                neutral_trade_value(SimpleNamespace(trade_value=value))

    def test_missing_selected_price_is_expected_evidence_rejection(self):
        from services.trade_intelligence import TradeInputError, _require_acquisition_prices
        with self.assertRaises(TradeInputError) as raised:
            _require_acquisition_prices((SimpleNamespace(asset_id="p1", trade_value=None),))
        self.assertEqual(raised.exception.code, "market_evidence_unavailable")
        self.assertEqual(raised.exception.assets, ("p1",))
        _require_acquisition_prices((SimpleNamespace(asset_id="p1", trade_value=0),))

    def test_adjustment_excludes_unpriced_options_without_losing_owned_assets(self):
        from services.trade_intelligence import _bounded_adjustment_candidates
        from tests.test_trade_intelligence import asset
        from dataclasses import replace
        outgoing, incoming = asset("a", "player", 50), asset("b", "player", 50, 2)
        unpriced = replace(asset("missing", "player", 999), trade_value=None)
        workspace = {"pools": {1: (outgoing, unpriced), 2: (incoming,)}}
        results = _bounded_adjustment_candidates(workspace, {
            "active_roster_id": 1, "partner_roster_id": 2,
            "assets_sent": ["a"], "assets_received": ["b"],
        })
        self.assertTrue(results)
        self.assertTrue(all(item.asset_id != "missing" for proposal in results
                            for item in (*proposal.assets_sent, *proposal.assets_received)))
        self.assertIn(unpriced, workspace["pools"][1])

    def test_missing_price_api_error_is_not_engine_crash(self):
        from routes.trades import _trade_failure
        from services.trade_intelligence import TradeInputError
        error = _trade_failure(TradeInputError(
            "market_evidence_unavailable", "Acquisition price unavailable", ("p1",),
        ))
        self.assertEqual(error.status_code, 422)
        self.assertEqual(error.detail["code"], "market_evidence_unavailable")

    def test_unified_recommendation_does_not_call_missing_intrinsic_negative(self):
        from src.core.intelligence.recommendations import resolve_recommendation
        outlook = SimpleNamespace(grade="B", score=70, summary="Separate supported dimension")
        result = resolve_recommendation(
            decision=SimpleNamespace(current_outlook=outlook, future_outlook=outlook, competitive_window=None),
            trade=SimpleNamespace(recommendation=SimpleNamespace(expected_value=None, acceptance_likelihood=None)),
            front_office=None, market=None, evidence=(), confidence=None,
        )
        self.assertEqual(result.title, "Additional evidence needed")
        self.assertIn("intrinsic improvement is unavailable", result.recommendation)

"""Smoke acceptance distinguishes navigation from generated recommendations."""
import unittest

from tools.validation.smoke_http import validate_trade_navigation_contract


class TradeNavigationSmokeTests(unittest.TestCase):
    def setUp(self):
        self.body = ('<header data-dtos-component="page-header"></header>'
                     '<button data-dtos-action="primary">Create</button>' + ''.join(
                         f'<a href="/trades/{workflow}?front_office=2">Go</a>'
                         for workflow in ('create', 'trade-for', 'shop', 'recommended')
                     )).encode()
        self.payload = dict(availability='not_started', decision_confidence=None,
                            count=0, opportunities=[], canonical_bilateral_evaluations=[])

    def test_navigation_without_fake_recommendation_passes(self):
        validate_trade_navigation_contract(self.body, self.payload, 2)

    def test_wrong_context_or_missing_workflow_fails(self):
        with self.assertRaises(AssertionError):
            validate_trade_navigation_contract(self.body, self.payload, 3)
        with self.assertRaises(AssertionError):
            validate_trade_navigation_contract(self.body.replace(b'/trades/shop?', b'/wrong?'), self.payload, 2)

    def test_premature_evaluation_or_default_confidence_fails(self):
        for changes in ({'decision_confidence': 0}, {'count': 1},
                        {'availability': 'available'}, {'opportunities': [{}]},
                        {'canonical_bilateral_evaluations': [{}]}):
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                validate_trade_navigation_contract(self.body, {**self.payload, **changes}, 2)

"""First six-surface contract proof, not production acceptance or new grading."""
from dataclasses import asdict, replace
import unittest

from src.core.explanations import (
    Availability as A, EvidenceContext, EvidenceItem, EvidenceKind as K,
    Explanation, Statement,
)
from src.ui.explanations import explanation_panel
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult


def context(family, scope='league:A/season:2026/week:2', league='A'):
    return EvidenceContext(family, scope, 'accepted-generation', 'accepted-method', league)


def item(key, label, value, ctx, kind=K.DERIVED, state=A.AVAILABLE, unit='classification'):
    return EvidenceItem(key, label, kind, ctx, f'accepted:{key}', unit, state, value)


def statement(code, text, *keys):
    return Statement(code, text, keys)


class ExplanationContractTests(unittest.TestCase):
    def test_six_surface_accepted_evidence_contract(self):
        trade = context('trade')
        projection = context('projection')
        strength = context('team_strength')
        market = context('market', 'global:12-team/2QB/PPR', None)
        pick = context('pick', 'league:A/year:2027/original:1/round:1')
        fois = context('fois', 'league:A/franchise:1/tenure:owner')
        # Actual accepted FOIS engine: Results-only evidence cannot create an
        # overall score. The explanation must preserve the unavailable result.
        score = FOISEngine().evaluate(FOISFacts('A', '1', 'owner',
            (SeasonResult(2025, 9, 5, 3, league_size=10),)), generated_at='fixed')
        self.assertIsNone(score.overall_score)
        cases = [
            Explanation('Trade', 'A', (trade,), (
                item('now', 'Current-week optimal-lineup change', '+2.5', trade, unit='fantasy points'),
                item('later', 'Next-N optimal-lineup change', '-3.0', trade, unit='fantasy points'),
                item('reason', 'Accepted weekly assessment', 'MIXED', trade, K.INTERPRETATION),
            ), statement('MIXED_WEEKLY_EFFECTS', 'Supported weekly effects are mixed.', 'reason'),
                why=(statement('CURRENT_WEEK_CHANGE', 'The current-week lineup improves.', 'now'),),
                tradeoffs=(statement('NEXT_N_CHANGE', 'Next-N gives back projected points.', 'later'),)),
            Explanation('Player', 'A', (projection,), (
                item('projection', 'Week 2 Sleeper projection', '27.33', projection, K.SOURCE, unit='fantasy points'),
            ), statement('PREPARED_PROJECTION', 'Week 2 source projection.', 'projection')),
            Explanation('Team Strength', 'A', (strength,), (
                item('total', 'Complete ROS total', None, strength, state=A.UNAVAILABLE, unit='fantasy points'),
                item('coverage', 'Supported/requested weeks', '2/4', strength, state=A.PARTIAL, unit='weeks'),
            ), statement('INCOMPLETE_WEEKLY_LINEUPS', 'ROS evidence is incomplete.', 'coverage', 'total'),
                limitations=(statement('INCOMPLETE_WEEKLY_LINEUPS', 'Unsupported weeks are not extrapolated.', 'coverage'),)),
            Explanation('Market', 'A', (market,), (
                item('price', 'Acquisition-price evidence', 'Single-provider Market', market),
                item('trend', 'Market movement', None, market, state=A.NO_COMPARABLE_EVIDENCE),
            ), statement('SINGLE_PROVIDER', 'One compatible external provider.', 'price'),
                limitations=(statement('NO_COMPARABLE_TREND', 'No comparable trend is established.', 'trend'),)),
            Explanation('Pick', 'A', (pick, market), (
                item('range', 'Original-franchise projected range', 'UNKNOWN', pick),
                item('confidence', 'Range evidence confidence', 'LOW', pick),
                item('quote', 'Market quote concept', 'GENERIC', market, K.SOURCE),
            ), statement('RANGE_UNKNOWN', 'The future slot remains uncertain.', 'range'),
                confidence=(statement('RANGE_CONFIDENCE', 'Low support for narrowing the range.', 'confidence'),),
                advanced=(statement('GENERIC_QUOTE', 'The generic Market quote is not an Early/Mid/Late forecast.', 'quote'),)),
            Explanation('FOIS', 'A', (fois,), (
                item('overall', 'Overall FOIS', None, fois, state=A.UNAVAILABLE, unit='FOIS score'),
            ), statement('INSUFFICIENT_CATEGORY_COVERAGE', 'Overall FOIS is unavailable.', 'overall'),
                limitations=(statement('INSUFFICIENT_CATEGORY_COVERAGE', 'Missing category evidence is not poor performance.', 'overall'),)),
        ]
        for view in cases:
            with self.subTest(surface=view.subject):
                before = asdict(view)
                rendered = explanation_panel(view)
                self.assertIn(view.conclusion.text, rendered)
                for _ in range(100):
                    self.assertEqual(explanation_panel(view), rendered)
                self.assertEqual(asdict(view), before)
                self.assertNotIn('accepted-generation', rendered)
                self.assertNotIn('accepted:', rendered)
        self.assertIn('+2.5', explanation_panel(cases[0]))
        self.assertIn('-3.0', explanation_panel(cases[0]))
        self.assertNotIn('27.34', explanation_panel(cases[1]))
        self.assertNotIn('0.00', explanation_panel(cases[-1]))

    def test_partial_market_does_not_become_complete_or_intrinsic(self):
        ctx = context('trade')
        view = Explanation('Market Balance', 'A', (ctx,), (
            item('balance', 'Complete acquisition-price balance', None, ctx, state=A.UNAVAILABLE),
            item('coverage', 'Assets with supported prices', '1/2', ctx, state=A.PARTIAL, unit='assets'),
        ), statement('PARTIAL_MARKET_EVIDENCE', 'Market evidence is partial.', 'balance', 'coverage'))
        rendered = explanation_panel(view)
        self.assertIn('Unavailable', rendered)
        self.assertIn('; partial', rendered)
        self.assertNotIn('fair trade', rendered.lower())
        self.assertNotIn('intrinsic', rendered.lower())

    def test_true_zero_and_missing_remain_distinct(self):
        ctx = context('projection')
        zero = item('zero', 'Week 2', '0.00', ctx, K.SOURCE, unit='fantasy points')
        missing = item('missing', 'Week 3', None, ctx, K.SOURCE, A.UNAVAILABLE, 'fantasy points')
        view = Explanation('Player', 'A', (ctx,), (zero, missing), statement('COVERAGE', 'Source coverage.', 'zero', 'missing'))
        self.assertIn('0.00', explanation_panel(view))
        self.assertIn('Unavailable', explanation_panel(view))
        with self.assertRaises(ValueError):
            replace(missing, display='0.00')

    def test_cross_league_stale_generation_and_unknown_reference_rejected(self):
        ctx = context('projection')
        evidence = item('p', 'Projection', '1.23', ctx, K.SOURCE, unit='fantasy points')
        view = Explanation('Player', 'A', (ctx,), (evidence,), statement('SOURCE', 'Prepared source.', 'p'))
        for changes in (
            {'league_id': 'B'},
            {'contexts': (replace(ctx, generation='other'),)},
            {'contexts': (ctx, replace(ctx, methodology='other'))},
            {'conclusion': statement('SOURCE', 'Unsupported statement.', 'absent')},
            {'evidence': (evidence, evidence)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(view, **changes)

    def test_escaped_content_and_no_confidence_probability_inference(self):
        ctx = context('trade')
        view = Explanation('<script>alert(1)</script>', 'A', (ctx,), (
            item('confidence', 'Evidence confidence', 'MEDIUM', ctx),
        ), statement('CONFIDENCE', 'Evidence support only.', 'confidence'),
            confidence=(statement('SUPPORT', '<b>Not an acceptance probability.</b>', 'confidence'),))
        rendered = explanation_panel(view)
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;b&gt;', rendered)
        self.assertNotIn('%', rendered)

    def test_mutable_collections_cannot_bypass_later_generation_validation(self):
        ctx = context('projection')
        evidence = item('p', 'Projection', '1.23', ctx, K.SOURCE)
        with self.assertRaises(ValueError):
            Statement('SOURCE', 'Source evidence.', ['p'])
        with self.assertRaises(ValueError):
            Explanation('Player', 'A', [ctx], (evidence,), statement('SOURCE', 'Source evidence.', 'p'))


if __name__ == '__main__':
    unittest.main()

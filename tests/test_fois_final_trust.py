"""Final trust wording and independent production-path verification."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from services.team_fois_explanations import strengths_context
from src.core.front_office_intelligence import build_league_model
from src.core.front_office_intelligence.engine import _compatibility
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts
from tests.test_trade_intelligence import fixture_data


class TrustWordingTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture_data()
        model = build_league_model(self.data)
        self.first, self.second = model.reports[1], model.reports[2]

    def report(self, first=None, second=None):
        return _compatibility(self.data, first or self.first, second or self.second)

    def test_no_need_does_not_claim_one_or_historical_preference(self):
        def neutral(report):
            evaluations = {k: replace(v, score=65) for k, v in report.decision.position_evaluations.items()}
            return replace(report, decision=replace(report.decision, position_evaluations=evaluations))
        result = self.report(neutral(self.first), neutral(self.second))
        self.assertEqual(result.shared_interests, ())
        self.assertIn('No specific need-based negotiation angle', result.forecast.opening_recommendation)
        self.assertNotIn('observed roster need', result.forecast.opening_recommendation)
        self.assertIsNone(result.forecast.acceptance_probability)
        self.assertIn('holdings do not establish', result.forecast.expected_counter)

    def test_specific_supported_need_identifies_both_teams(self):
        decision = self.first.decision
        evaluation = next(iter(decision.position_evaluations.values()))
        first = replace(self.first, decision=replace(decision, position_evaluations={'WR': replace(evaluation, score=30)}))
        rooms = dict(self.second.decision.profile.position_rooms)
        rooms['WR'] = replace(rooms['WR'], total_players=8)
        second = replace(self.second, decision=replace(self.second.decision, profile=replace(self.second.decision.profile, position_rooms=rooms)))
        result = self.report(first, second)
        self.assertIn('WR', result.shared_interests)
        self.assertIn(first.team_name, result.forecast.opening_recommendation)
        self.assertIn(second.team_name, result.forecast.opening_recommendation)
        self.assertIn('supported WR need', result.forecast.opening_recommendation)
        reversed_result = _compatibility(self.data, second, first)
        self.assertIn(first.team_name + "'s supported WR need", reversed_result.forecast.opening_recommendation)

    def test_missing_need_evidence_is_unavailable_not_none(self):
        missing = replace(self.first, decision=replace(self.first.decision, position_evaluations={}))
        other = replace(self.second, decision=replace(self.second.decision, position_evaluations={}))
        result = self.report(missing, other)
        self.assertIn('unavailable or incomplete', result.forecast.opening_recommendation)
        self.assertFalse(result.evidence[0].available)
        self.assertEqual(result.evidence[0].observed_value, 'Unavailable')
        unknown = replace(self.first, decision=replace(self.first.decision, position_evaluations={k: replace(v, score=None) for k,v in self.first.decision.position_evaluations.items()}))
        self.report(unknown, other)  # None is missing, never a numeric need.

    def test_historical_behavior_does_not_invent_current_need(self):
        first = replace(self.first, front_office_evidence={'partner_counts': {'2': 20}}, decision=replace(self.first.decision, position_evaluations={}))
        second = replace(self.second, decision=replace(self.second.decision, position_evaluations={}))
        result = self.report(first, second)
        self.assertEqual(result.bilateral_trades, 20)
        self.assertEqual(result.shared_interests, ())
        self.assertIn('no specific need-based', result.forecast.opening_recommendation)
        self.assertIsNone(result.forecast.acceptance_probability)

    def test_current_recommended_rank_has_no_direct_historical_fit_tiebreak(self):
        from copy import deepcopy
        from services.trade_search_policy import rank_key
        original = {'evaluation': {'recommendation': 'FAIR / OPTIONAL',
                    'values': {'ratio': 1}, 'provenance': {'evaluation_id': 'same'},
                    'dimensions': {'historical_counterparty_evidence': {'score': 0}}}}
        matched = deepcopy(original)
        matched['evaluation']['dimensions']['historical_counterparty_evidence']['score'] = 3
        self.assertEqual(rank_key(original), rank_key(matched))
        # Context may enrich explanations; no claim of a direct active rank boost.

    def test_zero_single_tied_unequal_and_established_strength_context(self):
        score = FOISEngine().evaluate(FOISFacts('league', 'franchise', 'owner', ()))
        self.assertIn('unavailable', strengths_context(score))
        category = replace(score.category_scores[0], normalized_score=76.05, category_name='Results')
        single = replace(score, category_scores=(category,), strongest_category=None, strengths=())
        self.assertIn('Results findings are supported', strengths_context(single))
        self.assertIn('more comparable category evidence', strengths_context(single))
        second = replace(category, category_key='trading', category_name='Trading')
        tied = replace(single, category_scores=(category, second))
        self.assertIn('equal scores', strengths_context(tied))
        unequal = replace(tied, category_scores=(category, replace(second, normalized_score=65)))
        self.assertIn('not established in this assessment', strengths_context(unequal))
        established = replace(unequal, strongest_category='Results', strengths=('Three playoff appearances',))
        self.assertIn('identifies Results', strengths_context(established))
        self.assertEqual(established.strengths, ('Three playoff appearances',))
        retained = replace(single, evidence_integrity_version=None)
        self.assertEqual(strengths_context(retained), strengths_context(single))
        self.assertEqual(retained.category_scores[0].normalized_score, 76.05)


class IndependentHistoricalPathTests(unittest.TestCase):
    def test_raw_source_to_full_and_actual_spawn_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            result = subprocess.run([sys.executable, '-m', 'tools.validation.verify_fois_historical', '--output', str(output)],
                                    capture_output=True, text=True, timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(len(report['cases']), 24)
            self.assertTrue(all(row['passed'] for row in report['cases']))
            self.assertTrue(report['worker_reaped'])
            self.assertLess(report['parent_rss_bytes'], 2 * 1024**3)
            self.assertTrue(all(row['execution']['child_peak_rss_bytes'] < 2 * 1024**3 for row in report['cases']))

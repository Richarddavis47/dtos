"""Existing Shop and Adjust consumers retain supported reserve production facts."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from services.shop_asset_search import preference, rank_returns, ranking_evidence
from services.trade_intelligence import assist_trade_request, build_trade_workspace
from src.core.trade_intelligence.models import TradeProposal
from tests.test_batch5_trade_strategy import asset
from tests.test_trade_intelligence import fixture_data


def quality(delta, *, complete=True, weeks=(2,)):
    return {'mean_weekly_delta': delta, 'material_gain': delta is not None and delta >= 1,
            'material_loss': delta is not None and delta <= -1, 'complete': complete,
            'supported_weeks': list(weeks) if delta is not None else []}


def report(identifier, *, delta=5, reserve_delta=0, slots=0, complete=True):
    reserve = quality(reserve_delta, complete=complete)
    return {'generated_trade_eligible': True, 'recommendation': 'WORTH PURSUING',
            'values': {'ratio': 1}, 'provenance': {'evaluation_id': identifier},
            'dimensions': {'confidence': {'assessment': 'MEDIUM'},
                'counterparty_plausibility': {'assessment': 'PLAUSIBLE'},
                'package_quality': {'active': {'assessment': 'SUPPORTED CONSOLIDATION',
                    'reserve_quality': reserve, 'incoming_lineup_contributors': []}},
                'strategic_fit': {'active': {
                    'production_evidence': {'mean_weekly_delta': delta},
                    'horizons': {name: {'availability': 'complete', 'delta': delta}
                                 for name in ('current_week', 'next_n', 'rest_of_regular_season', 'playoff_window')},
                    'reserve_slot_changes': {2: slots}, 'future_capital': {'received': []}}}}}


class ReserveShopConsumerTests(unittest.TestCase):
    def setUp(self):
        self.assets = {name: replace(asset(name, 100, 2), position='WR', age=25)
                       for name in ('a-loss', 'z-quality')}

    def row(self, name, **kwargs):
        return {'proposal': {'assets_received': [name]}, 'evaluation': report(name, **kwargs)}

    def test_equal_slots_prefer_supported_replacement_production(self):
        rows = [self.row('a-loss', reserve_delta=-39), self.row('z-quality', reserve_delta=4)]
        before = deepcopy(rows)
        for pref in ({}, {'shop_preference': 'win_now'},
                     {'shop_preference': 'position_need', 'shop_position': 'WR'}):
            with self.subTest(pref=pref):
                ranked = rank_returns(rows, self.assets, preference(pref))
                self.assertEqual(ranked[0][0], rows[1])
                self.assertEqual(len(ranked), 2)  # A disclosed cost is not a new eligibility veto.
        self.assertEqual(rows, before)

    def test_more_weak_slots_do_not_outrank_better_supported_quality(self):
        rows = [self.row('a-loss', reserve_delta=-39, slots=1),
                self.row('z-quality', reserve_delta=4, slots=0)]
        self.assertEqual(rank_returns(rows, self.assets, preference({}))[0][0], rows[1])

    def test_meaningful_starter_consolidation_remains_first(self):
        rows = [self.row('a-loss', delta=12, reserve_delta=-39),
                self.row('z-quality', delta=5, reserve_delta=4)]
        self.assertEqual(rank_returns(rows, self.assets, preference({'shop_preference': 'win_now'}))[0][0], rows[0])

    def test_missing_quality_is_not_zero_or_a_material_loss(self):
        row = self.row('a-loss', reserve_delta=None, complete=False)
        evidence = ranking_evidence(row, self.assets)
        self.assertIsNone(evidence['reserve_quality']['mean_weekly_delta'])
        self.assertFalse(evidence['reserve_quality']['material_loss'])
        known = self.row('z-quality', reserve_delta=0)
        self.assertEqual(rank_returns([row, known], self.assets, preference({}))[0][0], known)

    def test_legacy_slot_only_evidence_remains_rankable(self):
        row = self.row('a-loss')
        del row['evaluation']['dimensions']['package_quality']['active']['reserve_quality']
        self.assertEqual(len(rank_returns([row], self.assets, preference({}))), 1)
        self.assertEqual(ranking_evidence(row, self.assets)['reserve_quality'], {})

    def test_partial_quality_subtotal_is_not_ranked_as_complete_gain(self):
        partial = self.row('a-loss', reserve_delta=8, complete=False)
        known = self.row('z-quality', reserve_delta=0)
        self.assertEqual(rank_returns([partial, known], self.assets, preference({}))[0][0], known)
        self.assertEqual(len(rank_returns([partial], self.assets, preference({}))), 1)


class ReserveAdjustConsumerTests(unittest.TestCase):
    def run_adjust(self, candidates):
        data = fixture_data()
        before = deepcopy(data)
        workspace = build_trade_workspace(data, 1)
        by_id = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
        payload = {'active_roster_id': 1, 'partner_roster_id': 2,
                   'assets_sent': ['1-QB-0'], 'assets_received': ['2-QB-0'],
                   'instruction': 'improve win now', 'origin_workflow': 'trade_for',
                   'origin_asset_id': '2-QB-0'}
        proposals = tuple(TradeProposal(1, 2, (by_id[pid],), (by_id['2-QB-0'],), 'fixture')
                          for pid in candidates)

        def evaluate(source, candidate, **kwargs):
            pid = candidate['assets_sent'][0]
            values = candidates.get(pid) or {'delta': 0, 'reserve_delta': 0}
            return {'proposal': deepcopy(candidate), 'evaluation': report(pid, **values)}

        with patch('services.trade_intelligence._bounded_adjustment_candidates', return_value=proposals), \
                patch('services.trade_intelligence.evaluate_trade_request', side_effect=evaluate):
            result = assist_trade_request(data, payload)
        self.assertEqual(data, before)
        return result

    def test_quality_loss_is_disclosed_without_vetoing_starter_upgrade(self):
        result = self.run_adjust({'1-QB-1': {'delta': 12, 'reserve_delta': -39}})
        self.assertEqual(result['count'], 1)
        row = result['results'][0]
        self.assertTrue(result['target_preserved'])
        comparison = row['adjustment_evidence']['reserve_quality_comparison']
        self.assertEqual(comparison['availability'], 'supported')
        self.assertEqual(comparison['candidate_mean_weekly_delta'], -39)
        self.assertTrue(comparison['material_regression'])
        self.assertIn('tradeoff', row['adjustment_evidence']['concept'])

    def test_equivalent_adjustments_prefer_preserving_replacement_production(self):
        result = self.run_adjust({'1-QB-1': {'delta': 5, 'reserve_delta': -39},
                                  '1-RB-2': {'delta': 5, 'reserve_delta': 0}})
        self.assertEqual(result['count'], 2)
        self.assertEqual(result['results'][0]['proposal']['assets_sent'], ['1-RB-2'])

    def test_unavailable_quality_remains_qualified(self):
        result = self.run_adjust({'1-QB-1': {'delta': 5, 'reserve_delta': None, 'complete': False}})
        self.assertEqual(result['count'], 1)
        comparison = result['results'][0]['adjustment_evidence']['reserve_quality_comparison']
        self.assertEqual(comparison['availability'], 'unavailable')
        self.assertIsNone(comparison['candidate_mean_weekly_delta'])
        self.assertIsNone(comparison['material_regression'])

    def test_existing_slot_regression_gate_is_preserved(self):
        result = self.run_adjust({'1-QB-1': {'delta': 5, 'reserve_delta': 4, 'slots': -1}})
        self.assertEqual(result['count'], 0)


if __name__ == '__main__':
    unittest.main()

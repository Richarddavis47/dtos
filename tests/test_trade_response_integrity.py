"""Same-package reuse without weaker projection, eligibility or freshness checks."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from services import trade_intelligence as trade
from src.core.intelligence import TradeProposal, evaluate_horizon_impact
from src.core.intelligence import roster_diagnostics as diagnostics
from tests import test_capital_strategy_reconciliation as capital


class TradeResponseIntegrityTests(unittest.TestCase):
    def fixture(self):
        f = capital.CapitalStrategyTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        return f

    def package(self, f, sent=('a',), received=('c',), strategies=None, snapshot=None):
        workspace = trade.build_trade_workspace(f.data, 1)
        assets = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
        proposal = TradeProposal(1, 2, tuple(assets[k] for k in sent), tuple(assets[k] for k in received), 'control')
        reader = trade._SearchProjectionReader(f.reader)
        impact = evaluate_horizon_impact(f.data, proposal, reader)
        return diagnostics.package_diagnostics(f.data, proposal, snapshot or reader.snapshot(), impact,
            strategies or {'1': 'REBUILD', '2': 'WIN NOW'}, projection_reader=reader)

    def test_one_package_prepares_pre_and_post_inputs_once_without_heavy_source_work(self):
        f = self.fixture()
        before = deepcopy(f.data)
        guards = ('services.sleeper.sleeper_get',
                  'src.core.projection_intelligence.service.ProjectionService.generate',
                  'src.core.fois.service.FOISService._generate_sync',
                  'src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct')
        spies = [self.enterContext(patch(name, side_effect=AssertionError('Unexpected source work'))) for name in guards]
        workspace = trade.build_trade_workspace(f.data, 1)
        assets = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
        proposal = TradeProposal(1, 2, (assets['a'],), (assets['c'],), 'control')
        reader = trade._SearchProjectionReader(f.reader)
        impact = evaluate_horizon_impact(f.data, proposal, reader)
        with patch.object(diagnostics, 'diagnostic_inputs', wraps=diagnostics.diagnostic_inputs) as inputs:
            result = diagnostics.package_diagnostics(f.data, proposal, reader.snapshot(), impact,
                {'1': 'REBUILD', '2': 'WIN NOW'}, projection_reader=reader)
        self.assertEqual(inputs.call_count, 2)  # Exact unchanged pre-rosters and independently constructed post-rosters.
        self.assertEqual(f.data, before)
        self.assertFalse(any(spy.call_count for spy in spies))
        self.assertEqual(set(result['sides']), {'active', 'partner'})
        if os.getenv('DTOS_TRADE_RESPONSE_EVIDENCE'):
            root = Path(os.environ['DTOS_TRADE_RESPONSE_EVIDENCE'])
            root.mkdir(parents=True, exist_ok=True)
            (root / 'package-work.json').write_text(json.dumps({'pre_post_input_preparations': inputs.call_count,
                'guarded_source_calls': dict.fromkeys(guards, 0), 'canonical_source_unchanged': True}, indent=2))

    def test_each_strategy_preserves_the_public_team_view_and_package_points(self):
        f = self.fixture()
        snapshot = f.reader.snapshot()
        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
            for sent, received in ((('a',), ('c',)), (('b',), ('c',)), (('a',), ('d', '2028-R2-4'))):
                with self.subTest(strategy=strategy, sent=sent, received=received):
                    result = self.package(f, sent, received, {'1': strategy, '2': 'WIN NOW'})
                    for side, rid, choice in (('active', '1', strategy), ('partner', '2', 'WIN NOW')):
                        expected = diagnostics.team_diagnostics(f.data, rid, snapshot, strategy=choice, projection_reader=f.reader)
                        actual = result['sides'][side]
                        self.assertEqual(actual['strategy'], expected['strategy'])
                        self.assertEqual(actual['pre_evidence'], expected['evidence'])
                        self.assertEqual(actual['pre_eligibility'], expected['eligibility'])
                        self.assertEqual(actual['available_pre_optimal_points'], expected['optimal_points'])
                        for position, facts in expected['positions'].items():
                            self.assertEqual(actual['positions'][position]['pre'], facts)

    def test_post_trade_out_player_is_requalified_independently_of_shared_pre_evidence(self):
        f = self.fixture()
        next(p for p in f.data['teams'][1]['players'] if p['id'] == 'c')['status'] = 'Out'
        result = self.package(f)
        incoming = next(row for row in result['sides']['active']['post_eligibility'] if row['player_id'] == 'c')
        self.assertTrue(incoming['excluded'])
        self.assertIn('Incoming players excluded', ' '.join(result['sides']['active']['post_evidence']['limitations']))
        self.assertNotEqual(result['sides']['active']['numeric_impact_state'], 'supported')

    def test_incompatible_publication_stays_unavailable_and_real_zero_stays_numeric(self):
        f = self.fixture()
        for field, value in (('league_id', 'foreign'), ('scoring_settings', {'pass_yd': 99}), ('week', 17)):
            with self.subTest(field=field):
                result = self.package(f, snapshot={**f.reader.snapshot(), field: value})
                self.assertFalse(result['evidence']['calculation_supported'])
                self.assertTrue(all(row['coverage'] == 'partial / unavailable' for row in result['sides'].values()))
        f.points['a'] = 0
        f.publish()
        result = self.package(f)
        self.assertEqual(f.reader.snapshot()['players']['a']['canonical_projection'], 0)
        self.assertIsNotNone(result['sides']['active']['available_pre_optimal_points'])

    def test_retained_freshness_and_returned_view_mutations_cannot_poison_shared_facts(self):
        f = self.fixture()
        with patch.object(f.reader, 'refresh_evidence', return_value={'retained_publication': True}):
            retained = self.package(f)
        self.assertTrue(retained['evidence']['refresh']['retained_publication'])
        self.assertNotEqual(retained['sides']['active']['pre_evidence']['conclusion_state'], 'current')
        first = self.package(f)
        original = deepcopy(first)
        first['sides']['active']['positions']['QB']['pre']['reason'] = 'altered returned view'
        self.assertEqual(self.package(f), original)

    def test_refresh_failure_during_package_keeps_both_pre_views_qualified(self):
        f = self.fixture()
        calls = []
        def changed_refresh(_snapshot):
            calls.append(1)
            return {'retained_publication': len(calls) > 1}
        with patch.object(f.reader, 'refresh_evidence', side_effect=changed_refresh):
            result = self.package(f)
        self.assertTrue(result['evidence']['refresh']['retained_publication'])
        for side in result['sides'].values():
            self.assertTrue(side['pre_evidence']['refresh']['retained_publication'])
            self.assertNotEqual(side['numeric_impact_state'], 'supported')

    def test_missing_snapshot_preserves_original_resolution_without_inventing_points(self):
        f = self.fixture()
        workspace = trade.build_trade_workspace(f.data, 1)
        assets = {a.asset_id: a for pool in workspace['pools'].values() for a in pool}
        proposal = TradeProposal(1, 2, (assets['a'],), (assets['c'],), 'control')
        reader = trade._SearchProjectionReader(f.reader)
        impact = evaluate_horizon_impact(f.data, proposal, reader)
        with patch.object(diagnostics, 'projection_snapshot', return_value=f.reader.snapshot()):
            expected = diagnostics.diagnose_league(f.data, None, projection_reader=reader)
            result = diagnostics.package_diagnostics(f.data, proposal, None, impact,
                {'1': 'REBUILD', '2': 'WIN NOW'}, projection_reader=reader)
        for field in ('generation', 'projection_generation'):
            self.assertEqual(result[field], expected[field])
        self.assertFalse(result['evidence']['calculation_supported'])
        for side in result['sides'].values():
            self.assertIsNone(side['available_pre_optimal_points'])
            self.assertEqual(side['coverage'], 'partial / unavailable')

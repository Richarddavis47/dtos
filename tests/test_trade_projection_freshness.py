"""Actual disposable Sleeper publication → canonical lineup → Trade provenance."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from services.trade_intelligence import evaluate_trade_request, generate_trade_workflow, TradeInputError
from src.core.intelligence.team_strength import prepare_for_data
from src.core.projection_intelligence.service import ProjectionService, canonical_projection_identity
from tests import test_capital_strategy_reconciliation as fixtures


class PublishedTradeEvidence:
    def __init__(self, owner):
        self.fixture = fixtures.CapitalStrategyTests()
        self.fixture.setUp()
        owner.addCleanup(self.fixture.doCleanups)
        self.data, self.service = self.fixture.data, self.fixture.reader
        owner.enterContext(patch('services.trade_intelligence._trade_projection_service', return_value=self.service))

    def assess(self, sent=None, received=None):
        return evaluate_trade_request(self.data, {'workflow': 'trade_for', 'active_roster_id': 1,
            'partner_roster_id': 2, 'strategy': 'WIN NOW', 'assets_sent': sent or ['a'],
            'assets_received': received or ['c']}, projection_reader=self.service)

    def publish(self, points=25):
        self.fixture.points['c'] = points
        self.fixture.publish()


class ProjectionFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.source = PublishedTradeEvidence(self)

    def test_scout_publication_changes_identity_and_actual_assessment(self):
        old = self.source.assess()['evaluation']
        self.assertEqual(old['lineup_impact']['active']['delta'], -2)
        self.assertEqual(old['recommendation'], 'NOT WORTH IT')
        self.source.publish()
        new = self.source.assess()['evaluation']
        self.assertEqual(new['lineup_impact']['active']['delta'], 15)
        self.assertEqual(new['recommendation'], 'SMASH ACCEPT')
        before, after = (e['provenance']['inputs'] for e in (old, new))
        self.assertNotEqual(before['projection_generation'], after['projection_generation'])
        self.assertEqual(after['projection_generation'], self.source.service.snapshot()['projection_snapshot_id'])
        self.assertNotEqual(after['projection_generation'], 'current')
        self.assertEqual(old['values'], new['values'])

    def test_same_evidence_other_offer_and_retrieval_do_not_change_source_identity(self):
        first = self.source.assess()['evaluation']['provenance']
        different = self.source.assess(['b'], ['d'])['evaluation']['provenance']
        self.assertNotEqual(first['evaluation_id'], different['evaluation_id'])
        self.assertEqual(first['inputs']['projection_generation'], different['inputs']['projection_generation'])
        before = canonical_projection_identity(self.source.service.snapshot(), 'league-1')
        self.source.fixture.publish()
        after = canonical_projection_identity(self.source.service.snapshot(), 'league-1')
        self.assertEqual(before, after)
        self.assertEqual(first['inputs']['projection_generation'], self.source.assess()['evaluation']['provenance']['inputs']['projection_generation'])

    def test_missing_foreign_and_partial_evidence_are_not_zero(self):
        self.assertIsNone(canonical_projection_identity(None, 'league-1')['generation'])
        self.assertIsNone(canonical_projection_identity(self.source.service.snapshot(), 'other-league')['generation'])
        payloads = copy.deepcopy(self.source.fixture.payloads)
        # Before has a supported QB; after has no supported eligible QB.
        # Remaining supported backups must not accidentally fill the slot.
        payloads[2] = [p for p in payloads[2] if p['player_id'] == 'a']
        self.source.service.publish_horizon(payloads, data=self.source.data, league_id='league-1', season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.source.service, self.source.data)
        e = self.source.assess()['evaluation']
        self.assertIsNone(e['lineup_impact']['active']['delta'])
        self.assertIsNone(self.source.service.snapshot()['players']['c']['canonical_projection'])

    def test_two_scoring_contexts_preserve_exact_sleeper_points_and_isolation(self):
        original = self.source.service.snapshot()
        data = copy.deepcopy(self.source.data)
        data['league']['league_id'] = 'league-2'
        data['league']['scoring_settings'] = {'pass_yd': .5}
        second = ProjectionService(Path(self.source.fixture.tmp.name) / 'second.sqlite3')
        snapshot = second.publish_horizon(self.source.fixture.payloads, data=data, league_id='league-2', season=2026, current_week=2)
        self.assertEqual(original['players']['a']['canonical_projection'], 10)
        self.assertEqual(snapshot['players']['a']['canonical_projection'], 5)
        self.assertEqual(snapshot['players']['a']['canonical_projection'], snapshot['players']['a']['sleeper_projection'])
        self.assertNotEqual(original['projection_snapshot_id'], snapshot['projection_snapshot_id'])
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(second, data)
        e = evaluate_trade_request(data, {'workflow': 'trade_for', 'active_roster_id': 1,
            'partner_roster_id': 2, 'strategy': 'WIN NOW', 'assets_sent': ['a'], 'assets_received': ['c']}, projection_reader=second)['evaluation']
        self.assertEqual(e['lineup_impact']['active']['delta'], -1)
        self.assertEqual(e['provenance']['inputs']['projection_generation'], snapshot['projection_snapshot_id'])
        self.assertEqual(self.source.service.snapshot(), original)

    def test_pinned_read_and_search_publication_race_fail_closed(self):
        from services import trade_intelligence as trade
        original = trade.evaluate_trade_request
        changed = False

        def during(*args, **kwargs):
            nonlocal changed
            result = original(*args, **kwargs)
            if not changed:
                changed = True
                self.source.publish()
            return result

        with patch.object(trade, 'evaluate_trade_request', side_effect=during):
            with self.assertRaises(TradeInputError) as error:
                generate_trade_workflow(self.source.data, {'workflow': 'trade_for', 'active_roster_id': 1,
                    'asset_id': 'c', 'partner_roster_id': 2, 'strategy': 'WIN NOW'})
        self.assertEqual(error.exception.code, 'canonical_evidence_changed')

    def test_publication_during_manual_evaluation_cannot_return_obsolete_result(self):
        from services import trade_intelligence as trade
        original = trade.evaluate_bilateral

        def during(*args, **kwargs):
            result = original(*args, **kwargs)
            self.source.publish()
            return result

        with patch.object(trade, 'evaluate_bilateral', side_effect=during):
            with self.assertRaises(TradeInputError) as error:
                self.source.assess()
        self.assertEqual(error.exception.code, 'canonical_evidence_changed')

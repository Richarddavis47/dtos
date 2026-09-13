import unittest
from unittest.mock import Mock

from src.core.historical_memory.graph import HistoricalAssetGraph


class PickOwnershipChainTests(unittest.TestCase):
    def dossier(self, league, transfers):
        graph = HistoricalAssetGraph(Mock(), league, {'pick_ledger': [
            {'season': 2027, 'round': 1, 'original_roster_id': 1, 'current_owner_id': 99}]})
        graph.events = Mock(return_value=[{
            'event_id': str(i), 'event_type': 'pick_trade', 'event_status': status,
            'from_franchise_id': f'{league}:franchise:{a}',
            'to_franchise_id': f'{league}:franchise:{b}',
        } for i, (a, b, status) in enumerate(transfers)])
        return graph.pick_dossier('PICK-2027-R1-ORIG1')

    def test_return_trade_preserves_original_and_return_without_current_rewrite(self):
        row = self.dossier('A', [(1, 2, 'complete'), (2, 1, 'complete')])
        self.assertEqual(row['owner_chain'], ['A:franchise:1', 'A:franchise:2', 'A:franchise:1'])
        self.assertEqual(row['current_owner'], 'A:franchise:1')
        self.assertEqual(row['original_franchise_id'], 'A:franchise:1')
        self.assertEqual(row['slot_status'], 'unknown')

    def test_failed_transfer_cannot_change_owner(self):
        row = self.dossier('A', [(1, 2, 'complete'), (2, 3, 'failed')])
        self.assertEqual(row['current_owner'], 'A:franchise:2')

    def test_missing_transition_is_not_verified(self):
        row = self.dossier('A', [(1, 2, 'complete'), (3, 4, 'complete')])
        self.assertEqual(row['reconciliation_status'], 'ownership_chain_gap')
        self.assertEqual(row['ownership_chain_gaps'], ['1'])

    def test_same_pick_identity_remains_league_scoped(self):
        for league in ('A', 'B'):
            row = self.dossier(league, [(1, 2, 'complete')])
            self.assertTrue(all(owner.startswith(league + ':') for owner in row['owner_chain']))

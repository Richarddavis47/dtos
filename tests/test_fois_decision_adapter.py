"""Exercise decision coverage through the active history adapter."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from src.core.fois.history import load_results_history
from src.core.fois.facts import DraftFact, WaiverFact


class DecisionAdapterTests(unittest.TestCase):
    def test_only_completed_waiver_actions_and_exact_selection_identity(self):
        class Store:
            def dataset_version(self, league_id):
                return 'fixture'

            def records(self, league_id, entity_type, limit, **filters):
                rows = []
                if entity_type == 'franchise_identity':
                    rows = [{'season': 2024, 'payload': {'sleeper_roster_id': '1', 'owner_id': 'gm'}}]
                elif entity_type == 'draft_pick':
                    rows = [{'season': 2024, 'source_record_id': 'selection',
                             'occurred_at': '2024-08-01T00:00:00+00:00',
                             'payload': {'roster_id': 1, 'draft_id': 'draft', 'pick_no': 3, 'player_id': 'p'}}]
                elif entity_type == 'transaction':
                    rows = [{'season': 2024, 'source_record_id': str(i),
                             'occurred_at': '2024-09-01T00:00:00+00:00',
                             'payload': {'type': kind, 'status': status, 'roster_ids': [1],
                                         'adds': {'p': 1}, 'drops': {'q': 1},
                                         'settings': {'waiver_bid': bid} if bid is not None else {}}}
                            for i, (kind, status, bid) in enumerate([
                                ('trade', 'complete', None), ('waiver', 'failed', 5),
                                ('waiver', 'complete', 0), ('free_agent', 'complete', None)])]
                return len(rows), rows

        class Reader:
            def global_market_checkpoints(self, *, asset_id, limit):
                return [SimpleNamespace(checkpoint_id='old', occurred_at='2024-07-01T00:00:00+00:00',
                                        normalized_value=500, market_context_id='fixture', normalization_version='v1'),
                        SimpleNamespace(checkpoint_id='future', occurred_at='2025-07-01T00:00:00+00:00',
                                        normalized_value=900, market_context_id='fixture', normalization_version='v1')]

        with patch('src.core.intelligence_memory.intelligence_checkpoint_store.checkpoints', return_value=()), \
             patch('src.core.historical_intelligence.HistoricalIntelligenceService.events_for_league', return_value=()):
            history = load_results_history(Store(), 'league', checkpoint_reader=Reader())['1']
        self.assertEqual(len(history['waivers']), 2)
        self.assertEqual([row['faab_bid'] for row in history['waivers']], [0, None])
        self.assertEqual(history['waivers'][0]['adds'], ('p',))
        self.assertEqual(history['waivers'][0]['drops'], ('q',))
        self.assertEqual(history['drafts'][0]['player_id'], 'p')
        self.assertEqual(history['drafts'][0]['decision_time_market_references'], ('old',))
        self.assertNotIn('future', history['waivers'][0]['decision_time_market_references'])
        draft = DraftFact(**history['drafts'][0])
        waiver = WaiverFact(**history['waivers'][0])
        self.assertEqual(draft.player_id, 'p')
        self.assertEqual(draft.decision_time_market_references, ('old',))
        self.assertEqual(waiver.faab_bid, 0)
        self.assertEqual(waiver.adds, ('p',))
        outcome = draft.decision_evaluation['outcome']
        self.assertEqual(outcome['evaluability'], 'partially_evaluable')
        self.assertEqual(outcome['assessment'][0]['change'], 400)
        self.assertEqual(outcome['assessment'][0]['horizon_days'], 334)
        self.assertEqual(draft.decision_evaluation['process']['evaluability'], 'insufficient')
        coverage = history['decision_coverage']
        self.assertEqual(coverage['waivers']['discovered'], 2)
        self.assertEqual(coverage['waivers']['process_partially_evaluable'], 2)
        self.assertEqual(coverage['drafting']['process_insufficient'], 1)
        self.assertNotIn('exact_selection', coverage['drafting']['by_manager_season'][0]['missing_process_requirements'])


if __name__ == '__main__':
    unittest.main()

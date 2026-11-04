"""Fail-closed GM attribution at the active service boundary."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.fois.attribution import belongs_to_manager
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService


class AttributionTests(unittest.TestCase):
    def test_unknown_and_conflicting_owner_do_not_transfer(self):
        self.assertFalse(belongs_to_manager({'season': 2025}, 'new', {}))
        self.assertFalse(belongs_to_manager({'season': 2025, 'owner_id': 'old'}, 'new', {'2025': 'new'}))
        self.assertTrue(belongs_to_manager({'season': 2025, 'owner_id': 'new'}, 'new', {'2025': 'old'}))
        self.assertFalse(belongs_to_manager({'season': 2025}, None, {'2025': 'old'}))

    def test_active_service_filters_all_decision_categories_without_mutating_history(self):
        with tempfile.TemporaryDirectory() as directory:
            service = FOISService(FOISRepository(Path(directory) / 'fois.sqlite3'))
            history = {
                'owner_by_season': {'2023': 'old', '2024': 'new'},
                'seasons': [{'season': y, 'wins': 9, 'losses': 5, 'finish': 2}
                            for y in (2023, 2024, 2025)],
                'trades': [{'transaction_id': str(y), 'season': y, 'strategically_productive': True}
                           for y in (2023, 2024, 2025)],
                'drafts': [{'draft_id': str(y), 'season': y, 'pick_number': 1, 'value_over_expected': None}
                           for y in (2023, 2024, 2025)],
                'waivers': [{'transaction_id': str(y), 'season': y, 'value_created': None}
                            for y in (2023, 2024, 2025)],
                'roster_metrics': {'depth': 99}, 'roster_metrics_owner_id': 'old',
            }
            data = {'league': {'league_id': 'A', 'season': '2025'},
                    'teams': [{'roster_id': 1, 'owner_id': 'new', 'players': []}],
                    'fois_history': {'1': history}}
            with patch.object(service.engine, 'evaluate', wraps=service.engine.evaluate) as evaluate:
                service._generate_sync(data)
            facts = evaluate.call_args.args[0]
            for records in (facts.seasons, facts.trades, facts.drafts, facts.waivers):
                self.assertEqual([row.season for row in records], [2024])
            self.assertEqual(facts.roster_metrics, {})
            self.assertEqual(len(history['seasons']), 3)

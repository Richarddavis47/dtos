"""One FOIS work unit owns its canonical source only for that work unit."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.fois import process_execution
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService
from src.core.history_context.store import CanonicalHistoryStore
from src.core.intelligence_memory.store import IntelligenceCheckpointStore


class FOISWorkerResidencyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = CanonicalHistoryStore()
        self.checkpoints = IntelligenceCheckpointStore(self.root / 'checkpoints.db')
        for target, value in (
            ('src.core.history_context.canonical_history_store', self.store),
            ('src.core.intelligence_memory.intelligence_checkpoint_store', self.checkpoints),
            ('src.core.fois.service.intelligence_checkpoint_store', self.checkpoints),
        ):
            manager = patch(target, value)
            manager.start()
            self.addCleanup(manager.stop)

    def payload(self, league='A'):
        data = {
            'league': {'league_id': league, 'season': '2026'}, 'teams': [],
            'normalized_players': {'1': {'dtos_id': '1', 'name': 'Fixture',
                'position': 'QB', 'provider_ids': {'Sleeper': '1'}, 'birthdate': '2000-01-02'}},
            'fois_history': {},
        }
        path = self.root / f'{league}.json'
        path.write_text(json.dumps({'data': data}))
        repository = FOISRepository(self.root / f'{league}.db')
        return {'league_id': league, 'cache_file': str(path),
                'fois_database': str(repository.path)}

    def test_success_releases_only_completed_flight_source_and_keeps_shared_identities(self):
        unrelated = {'league': {'league_id': 'other'}}
        self.store.update_current('other', unrelated)
        observed = []

        def generate(service, data):
            self.assertIs(self.store._current['A'], data)
            observed.append(data)
            return ()

        payload = self.payload()
        before = Path(payload['cache_file']).read_bytes()
        with patch.object(FOISService, '_generate_sync', generate):
            result = process_execution._compute_fois_payload(payload)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['records'], 0)
        self.assertNotIn('A', self.store._current)
        self.assertNotIn('A', self.store._current_digests)
        self.assertIs(self.store._current['other'], unrelated)
        self.assertEqual(self.store._identities['1']['metadata']['birth_date'], '2000-01-02')
        self.assertEqual(Path(payload['cache_file']).read_bytes(), before)
        self.assertEqual(len(observed), 1)

    def test_failed_computation_releases_source_without_hiding_failure(self):
        payload = self.payload()
        with patch.object(FOISService, '_generate_sync', side_effect=RuntimeError('controlled engine failure')):
            with self.assertRaisesRegex(RuntimeError, 'controlled engine failure'):
                process_execution._compute_fois_payload(payload)
        self.assertNotIn('A', self.store._current)
        self.assertNotIn('A', self.store._current_digests)

    def test_failed_source_preparation_releases_only_its_published_reference(self):
        original = self.store.update_current

        def fail_after_update(league, data):
            original(league, data)
            raise RuntimeError('controlled preparation failure')

        with patch.object(self.store, 'update_current', fail_after_update):
            with self.assertRaisesRegex(RuntimeError, 'controlled preparation failure'):
                process_execution._compute_fois_payload(self.payload())
        self.assertNotIn('A', self.store._current)

    def test_cleanup_cannot_remove_a_newer_same_league_source(self):
        newer = {'league': {'league_id': 'A'}, 'normalized_players': {}}

        def generate(service, data):
            self.assertIs(self.store._current['A'], data)
            self.store.update_current('A', newer)
            return ()

        with patch.object(FOISService, '_generate_sync', generate):
            process_execution._compute_fois_payload(self.payload())
        self.assertIs(self.store._current['A'], newer)

    def test_distinct_completed_flights_do_not_accumulate_current_league_sources(self):
        with patch.object(FOISService, '_generate_sync', return_value=()):
            for league in ('A', 'B', 'C', 'A'):
                process_execution._compute_fois_payload(self.payload(league))
                self.assertEqual(self.store._current, {})
                self.assertEqual(self.store._current_digests, {})

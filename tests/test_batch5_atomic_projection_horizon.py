from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from src.core.projection_intelligence.service import ProjectionService
from src.core.projection_intelligence import state_storage


class AtomicProjectionHorizonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'projection.sqlite3'
        self.service = ProjectionService(self.path, league_id='a')
        self.data = {'league': {'league_id': 'a', 'season': 2026, 'scoring_settings': {'pass_yd': .04}},
                     'week': 1, 'players': [{'id': 'q', 'position': 'QB'}]}

    def feed(self, week, yards):
        return [{'player_id': 'q', 'week': week, 'season': 2026, 'stats': {'pass_yd': yards}}]

    def publish(self, yards=200, future=None):
        return self.service.publish_horizon({1: self.feed(1, yards), 2: self.feed(2, yards) if future is None else future},
                    data=self.data, league_id='a', season=2026, current_week=1)

    def test_changed_withdrawn_replay_restart_and_pinned_old_generation(self):
        old = self.publish()
        new = self.publish(300, [])
        self.assertNotEqual(old['horizon_generation'], new['horizon_generation'])
        self.assertEqual(new['weeks_supported'], [1])
        self.assertIsNone(self.service.week_snapshot(2)['players']['q']['canonical_projection'])
        self.assertEqual(self.service.week_snapshot(2, generation_snapshot=old)['players']['q']['canonical_projection'], 8)
        self.assertEqual(self.service.player('q')['canonical_projection'], 12)
        with closing(sqlite3.connect(self.path)) as db:
            counts = [db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in
                      ('projection_snapshots', 'projection_player_states', 'projection_source_history')]
        size = self.path.stat().st_size
        for _ in range(10):
            self.assertEqual(self.publish(300, [])['horizon_generation'], new['horizon_generation'])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(counts, [db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in
                      ('projection_snapshots', 'projection_player_states', 'projection_source_history')])
        self.assertEqual(size, self.path.stat().st_size)
        restored = ProjectionService(self.path, league_id='a')
        self.assertEqual(restored.snapshot()['horizon_generation'], new['horizon_generation'])
        self.assertIsNone(restored.week_snapshot(2)['players']['q']['canonical_projection'])

    def test_failure_rolls_back_durable_head_and_preserves_old_read(self):
        old = self.publish()
        with patch.object(state_storage, 'encode', side_effect=RuntimeError('controlled failure')):
            with self.assertRaisesRegex(RuntimeError, 'controlled failure'):
                self.publish(300)
        self.assertEqual(self.service.snapshot(), old)

        restored = ProjectionService(self.path, league_id='a')
        self.assertEqual(restored.snapshot(), old)
        self.assertEqual(restored.week_snapshot(2)['players']['q']['canonical_projection'], 8)

    def test_expansion_contraction_and_cross_league_pinned_handle(self):
        old = self.publish()
        expanded = self.service.publish_horizon(
            {1: self.feed(1, 200), 2: self.feed(2, 200), 3: self.feed(3, 250)},
            data=self.data, league_id='a', season=2026, current_week=1)
        self.assertEqual(expanded['weeks_supported'], [1, 2, 3])
        self.assertIsNone(self.service.week_snapshot(3, generation_snapshot=old))
        self.assertEqual(self.service.week_snapshot(3)['players']['q']['canonical_projection'], 10)
        self.service.publish_horizon({1: self.feed(1, 200), 2: []},
            data=self.data, league_id='a', season=2026, current_week=1)
        self.assertIsNone(self.service.week_snapshot(3))
        self.assertIsNone(self.service.week_snapshot(1, generation_snapshot={**expanded, 'league_id': 'b'}))
    def test_reader_sees_last_valid_during_replacement(self):
        old = self.publish()
        entered, release = threading.Event(), threading.Event()
        encode = state_storage.encode
        def pause(connection, snapshot):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release missing')
            return encode(connection, snapshot)
        with ThreadPoolExecutor(max_workers=2) as executor:
            with patch.object(state_storage, 'encode', side_effect=pause):
                future = executor.submit(self.publish, 300)
                try:
                    self.assertTrue(entered.wait(5))
                    self.assertEqual(self.service.snapshot(), old)
                    self.assertEqual(self.service.player('q')['canonical_projection'], 8)
                    # Windows' established storage fence serializes connections.
                    # A pending read still resolves its pinned old manifest.
                    reader = executor.submit(self.service.week_snapshot, 2, generation_snapshot=old)
                finally:
                    release.set()
                new = future.result(timeout=5)
                self.assertEqual(reader.result(timeout=5)['players']['q']['canonical_projection'], 8)
        self.assertEqual(self.service.week_snapshot(2)['horizon_generation'], new['horizon_generation'])

    def test_invalid_scope_or_payload_cannot_publish(self):
        old = self.publish()
        with self.assertRaises(ValueError):
            self.service.publish_horizon({1: []}, data=self.data, league_id='b', season=2026, current_week=1)
        with self.assertRaises(ValueError):
            self.service.publish_horizon({1: self.feed(1, 300), 2: {'invalid': True}},
                data=self.data, league_id='a', season=2026, current_week=1)
        self.assertEqual(self.service.snapshot(), old)

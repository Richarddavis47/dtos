from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.platform import storage_accounting
from src.platform.durable_storage_monitor import DurableStorageMonitor


class StorageAccountingTests(unittest.TestCase):
    def test_committed_readonly_collection_and_league_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            projection, fois, events = (root / name for name in ('p.db', 'f.db', 'e.db'))
            with closing(sqlite3.connect(projection)) as db, db:
                db.executescript('CREATE TABLE projection_snapshots(snapshot_id TEXT,league_id TEXT,payload TEXT);'
                                 'CREATE TABLE projection_publication_heads(snapshot_id TEXT);'
                                 'CREATE TABLE projection_source_history(payload TEXT);')
                for league in ('A', 'B'):
                    db.execute('INSERT INTO projection_snapshots VALUES (?,?,?)', (league, league, json.dumps({'league_id': league})))
                    db.execute('INSERT INTO projection_publication_heads VALUES (?)', (league,))
            with closing(sqlite3.connect(fois)) as db, db:
                for table in ('fois_scores_v2', 'fois_snapshot_history', 'fois_semantic_states'):
                    db.execute(f'CREATE TABLE {table}(league_id TEXT,payload TEXT)')
                    db.execute(f'INSERT INTO {table} VALUES (?,?)', ('A', '123'))
            with closing(sqlite3.connect(events)) as db, db:
                db.execute('CREATE TABLE intelligence_checkpoints(league_id TEXT, observations_json TEXT)')
                db.execute('INSERT INTO intelligence_checkpoints VALUES (?,?)', ('B', '12345'))
            before = {path: path.read_bytes() for path in (projection, fois, events)}
            totals, leagues = storage_accounting.collect(projection=projection, fois=fois, events=events,
                                                         cache_paths=[], disk_root=root)
            self.assertEqual(totals['projection_rows'], 2)
            self.assertEqual(totals['fois_observations'], 1)
            self.assertEqual(totals['event_count'], 1)
            self.assertEqual(leagues['A']['canonical_history_bytes'], 6)
            self.assertEqual(leagues['B']['canonical_history_bytes'], 5)
            self.assertEqual(leagues['A']['event_count'], 0)
            self.assertEqual(leagues['B']['event_count'], 1)
            self.assertEqual(before, {path: path.read_bytes() for path in before})
            monitor = DurableStorageMonitor(root / 'monitor.json')
            monitor.record(totals, leagues, now=datetime(2026, 9, 1, tzinfo=timezone.utc))
            self.assertEqual(len(monitor.review(monitor.read())['leagues']), 2)

    def test_missing_store_is_not_healthy_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                storage_accounting.collect(projection=root / 'absent', fois=root / 'absent',
                                           events=root / 'absent', cache_paths=[], disk_root=root)
            self.assertEqual(list(root.iterdir()), [])

    def test_maintenance_failure_is_visible_without_failing_publication(self):
        import config
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(config, 'HISTORY_STORAGE_ROOT', Path(folder)), \
                 patch.object(storage_accounting, 'collect', side_effect=OSError('private path must not leak')):
                with self.assertLogs('dtos.storage', 'WARNING'):
                    storage_accounting.periodic_storage_accounting()
                self.assertEqual(storage_accounting.health()['status'], 'collection_failed')
                self.assertNotIn('private path', str(storage_accounting.health()))

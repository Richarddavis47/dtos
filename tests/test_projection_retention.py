from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.core.projection_intelligence import retention, state_storage
from src.core.projection_intelligence.service import ProjectionService
from tools.projection_retention_migration import build_copy, verify_copy


class ProjectionRetentionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "source.sqlite3"
        self.service = ProjectionService(self.path, league_id="a")

    def publish(self, n, league="a"):
        data = {
            "league": {
                "league_id": league,
                "season": 2026,
                "scoring_settings": {"pass_yd": 0.04},
            },
            "week": 1,
            "players": [{"id": "q", "position": "QB"}],
        }
        feed = {
            week: [
                {
                    "player_id": "q",
                    "season": 2026,
                    "week": week,
                    "stats": {"pass_yd": n},
                }
            ]
            for week in (1, 2, 3)
        }
        with patch(
            "src.core.projection_intelligence.service._now",
            return_value=f"2026-09-01T{n // 60:02}:{n % 60:02}:00+00:00",
        ):
            service = (
                self.service
                if league == "a"
                else ProjectionService(self.path, league_id=league)
            )
            return service.publish_horizon(
                feed, data=data, league_id=league, season=2026, current_week=1
            )

    def test_event_survives_many_refreshes_without_full_history(self):
        first = self.publish(1)
        with closing(sqlite3.connect(self.path)) as db:
            retention.pin_snapshot(
                db, event_id="trade-1", snapshot_id=first["projection_snapshot_id"]
            )
            oid = db.execute(
                "SELECT min(observation_id) FROM projection_source_history"
            ).fetchone()[0]
            retention.pin_source(db, event_id="trade-1-source", observation_id=oid)
            db.commit()
        for n in range(2, 31):
            latest = self.publish(n)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertLessEqual(
                db.execute("SELECT count(*) FROM projection_snapshots").fetchone()[0],
                12,
            )
            # Three weeks * eight recent source universes, plus one event source,
            # and the small current/previous/event league-derived states.
            self.assertLessEqual(
                db.execute("SELECT count(*) FROM projection_player_states").fetchone()[
                    0
                ],
                40,
            )
            old = db.execute(
                "SELECT payload FROM projection_snapshots WHERE snapshot_id=?",
                (first["projection_snapshot_id"],),
            ).fetchone()[0]
            self.assertEqual(state_storage.decode(db, old), first)
        self.assertIsNone(
            self.service.source_as_of(
                season=2026, week=2, observed_as_of="2026-09-01T00:02:30+00:00"
            )
        )
        pinned = self.service.source_as_of(
            season=2026, week=1, observed_as_of="2026-09-01T00:01:30+00:00"
        )
        self.assertEqual(pinned["players"]["q"]["projected_stats"]["pass_yd"], 1)
        restored = ProjectionService(self.path, league_id="a")
        self.assertEqual(restored.snapshot(), latest)
        before = self.path.read_bytes()
        for _ in range(10):
            self.publish(30)
        self.assertEqual(before, self.path.read_bytes())

    def test_legacy_store_is_not_automatically_cleaned_and_copy_is_equal(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("DELETE FROM projection_retention_policy")
            db.commit()
        for n in range(1, 31):
            self.publish(n)
        self.publish(31, "b")
        before = self.path.read_bytes()
        restored = ProjectionService(self.path, league_id="a")
        self.assertEqual(before, self.path.read_bytes())
        target = Path(self.folder.name) / "compact.sqlite3"
        report = build_copy(self.path, target, maximum_bytes=4 * 1048576)
        self.assertTrue(verify_copy(self.path, target)['retained_evidence_equal'])
        self.assertEqual(before, self.path.read_bytes())
        self.assertTrue(report["retained_outputs_equal"])
        self.assertGreater(report["reclaimed_bytes"], 0)
        for league in ("a", "b", "a"):
            original = ProjectionService(self.path, league_id=league)
            compact = ProjectionService(target, league_id=league)
            self.assertEqual(original.snapshot(), compact.snapshot())
            for week in (1, 2, 3):
                self.assertEqual(
                    original.week_snapshot(week), compact.week_snapshot(week)
                )
        target_before = target.read_bytes()
        ProjectionService(target, league_id="a")
        self.assertEqual(target.read_bytes(), target_before)
        self.assertEqual(
            restored.snapshot(), ProjectionService(target, league_id="a").snapshot()
        )

    def test_invalid_graph_never_publishes_or_discards_current(self):
        first = self.publish(1)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute(
                "INSERT INTO projection_checkpoint_roots VALUES ('bad','absent')"
            )
            db.commit()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "Missing retained"):
            self.publish(2)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(self.service.snapshot(), first)

    def test_independent_copy_verification_rejects_changed_source_metadata(self):
        self.publish(1)
        target = Path(self.folder.name) / 'compact.sqlite3'
        build_copy(self.path, target, maximum_bytes=4 * 1048576)
        before = self.path.read_bytes()
        with closing(sqlite3.connect(target)) as db:
            db.execute("UPDATE projection_source_history SET season=2025")
            db.commit()
        with self.assertRaisesRegex(ValueError, 'evidence changed'):
            verify_copy(self.path, target)
        self.assertEqual(before, self.path.read_bytes())

    def test_independent_copy_verification_rejects_extra_or_missing_states(self):
        self.publish(1)
        target = Path(self.folder.name) / 'compact.sqlite3'
        build_copy(self.path, target, maximum_bytes=4 * 1048576)
        with closing(sqlite3.connect(target)) as db:
            db.execute('DELETE FROM projection_player_states')
            db.commit()
        with self.assertRaisesRegex(ValueError, 'state set changed'):
            verify_copy(self.path, target)

    def test_independent_copy_verification_rejects_wrong_policy(self):
        self.publish(1)
        target = Path(self.folder.name) / 'compact.sqlite3'
        build_copy(self.path, target, maximum_bytes=4 * 1048576)
        with closing(sqlite3.connect(target)) as db:
            db.execute("UPDATE projection_retention_policy SET version='unknown'")
            db.commit()
        with self.assertRaisesRegex(ValueError, 'Wrong projection retention policy'):
            verify_copy(self.path, target)

    def test_legacy_without_retention_tables_is_inert_on_startup_and_refresh(self):
        first = self.publish(1)
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('projection_retention_policy', 'projection_previous_heads',
                          'projection_checkpoint_roots', 'projection_source_roots'):
                db.execute(f'DROP TABLE {table}')
            db.commit()
        before = self.path.read_bytes()
        restored = ProjectionService(self.path, league_id='a')
        self.assertEqual(restored.snapshot(), first)
        self.assertEqual(self.path.read_bytes(), before)
        self.publish(2)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertFalse(retention.enabled(db))
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='projection_retention_policy'").fetchone())
            self.assertIsNotNone(db.execute('SELECT 1 FROM projection_snapshots WHERE snapshot_id=?',
                                           (first['projection_snapshot_id'],)).fetchone())
        target = Path(self.folder.name) / 'explicitly-migrated.sqlite3'
        build_copy(self.path, target, maximum_bytes=4 * 1048576)
        self.assertTrue(verify_copy(self.path, target)['retained_evidence_equal'])

    def test_event_cannot_be_reassigned_and_missing_source_not_fabricated(self):
        first = self.publish(1)
        second = self.publish(2)
        with closing(sqlite3.connect(self.path)) as db:
            retention.pin_snapshot(
                db, event_id="trade", snapshot_id=first["projection_snapshot_id"]
            )
            with self.assertRaisesRegex(ValueError, "rewritten"):
                retention.pin_snapshot(
                    db, event_id="trade", snapshot_id=second["projection_snapshot_id"]
                )
            with self.assertRaises(ValueError):
                retention.pin_source(db, event_id="none", observation_id=999)

    def test_unknown_table_blocks_retention_and_copy(self):
        self.publish(1)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('CREATE TABLE future_canonical_evidence(value TEXT)')
            db.commit()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.publish(2)
        self.assertEqual(before, self.path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            build_copy(self.path, Path(self.folder.name) / 'unknown.sqlite3', maximum_bytes=1048576)
        self.assertEqual(before, self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()

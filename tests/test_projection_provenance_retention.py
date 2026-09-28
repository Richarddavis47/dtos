"""Reachability and historical-gap regressions; entirely temporary stores."""
from contextlib import closing
import sqlite3
import unittest

from tests.test_projection_retention import ProjectionRetentionTests
from src.core.projection_intelligence import provenance_retention as policy, retention


class ProjectionProvenanceTests(ProjectionRetentionTests):
    # Reuse the production publication fixture, not its inherited test inventory.
    def admit(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            snapshots, _ = retention.plan(db)
            report = policy.plan(db, snapshots)
            policy.admit(db, expected_digest=report['digest'])
            retention.collect(db)
            return report

    def test_read_only_plan_and_stale_admission(self):
        self.publish(1)
        before = self.path.read_bytes()
        with closing(sqlite3.connect(self.path)) as db:
            roots, _ = retention.plan(db)
            report = policy.plan(db, roots)
        self.assertEqual(before, self.path.read_bytes())
        self.publish(2)
        with closing(sqlite3.connect(self.path)) as db, db:
            with self.assertRaisesRegex(ValueError, 'stale'):
                policy.admit(db, expected_digest=report['digest'])
            self.assertFalse(policy.enabled(db))

    def test_changed_refreshes_bounded_and_pinned_interval_not_extended(self):
        first = self.publish(1)
        with closing(sqlite3.connect(self.path)) as db, db:
            retention.pin_snapshot(db, event_id='required-assessment', snapshot_id=first['projection_snapshot_id'])
        self.admit()
        for n in range(2, 90):
            self.publish(n)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertLessEqual(db.execute('SELECT count(*) FROM projection_source_history').fetchone()[0], 12)
            self.assertEqual(db.execute('SELECT count(*) FROM projection_source_expiry').fetchone()[0],
                             db.execute('SELECT count(*) FROM projection_source_history').fetchone()[0])
        value = self.service.source_as_of(season=2026, week=1, observed_as_of='2026-09-01T00:01:30+00:00')
        self.assertEqual(value['players']['q']['projected_stats']['pass_yd'], 1)
        self.assertIsNone(self.service.source_as_of(season=2026, week=1, observed_as_of='2026-09-01T00:30:30+00:00'))
        self.assertIsNone(self.service.source_as_of(season=2026, week=1, observed_as_of='2026-09-01T00:02:00+00:00'))

    def test_unchanged_publication_and_restart_do_not_grow(self):
        self.publish(1)
        self.admit()
        self.publish(2)
        before = self.path.read_bytes()
        for _ in range(100):
            self.publish(2)
        self.assertEqual(before, self.path.read_bytes())
        from src.core.projection_intelligence.service import ProjectionService
        self.assertEqual(ProjectionService(self.path, league_id='a').snapshot(), self.service.snapshot())
        self.assertEqual(before, self.path.read_bytes())

    def test_cross_league_roots_survive(self):
        self.publish(1, 'b')
        self.publish(2)
        self.admit()
        for n in range(3, 16):
            self.publish(n)
        from src.core.projection_intelligence.service import ProjectionService
        self.assertEqual(ProjectionService(self.path, league_id='b').week_snapshot(1)['players']['q']['canonical_projection'], .04)

    def test_unknown_source_root_fails_before_deletion(self):
        self.publish(1)
        self.admit()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO projection_source_roots VALUES ('broken',999999)")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Missing source event root'):
            self.publish(2)
        self.assertEqual(before, self.path.read_bytes())

    def test_invalid_time_not_admitted(self):
        self.publish(1)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE projection_source_history SET observed_at='not-a-time'")
        with self.assertRaises(ValueError):
            self.admit()


if __name__ == '__main__':
    unittest.main()

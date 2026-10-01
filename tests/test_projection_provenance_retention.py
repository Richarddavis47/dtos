"""Reachability and historical-gap regressions; entirely temporary stores."""
from contextlib import closing
import json
import sqlite3
import unittest
from unittest.mock import patch

from tests.test_projection_retention import ProjectionRetentionTests
from src.core.projection_intelligence import provenance_retention as policy, retention
from src.core.projection_intelligence import state_storage


class ProjectionProvenanceTests(ProjectionRetentionTests):
    def test_season_rollover_keeps_previous_and_event_source_scope(self):
        first = self.publish(1)
        with closing(sqlite3.connect(self.path)) as db, db:
            retention.pin_snapshot(db, event_id='season-close', snapshot_id=first['projection_snapshot_id'])
        self.admit()
        data = {'league': {'league_id': 'a', 'season': 2027, 'scoring_settings': {'pass_yd': .04}},
                'players': [{'id': 'q', 'position': 'QB'}], 'week': 1}
        with patch('src.core.projection_intelligence.service._now', return_value='2027-09-01T00:00:00+00:00'):
            current = self.service.publish_horizon(
                {1: [{'player_id': 'q', 'season': 2027, 'week': 1, 'stats': {'pass_yd': 300}}]},
                data=data, league_id='a', season=2027, current_week=1)
        self.assertEqual(current['season'], 2027)
        with closing(sqlite3.connect(self.path)) as db:
            roots, _ = retention.plan(db)
            report = policy.plan(db, roots)
            self.assertIn(first['projection_snapshot_id'], roots)
            retained_seasons = {db.execute('SELECT season FROM projection_source_history WHERE observation_id=?',
                                           (oid,)).fetchone()[0] for oid in report['retained']}
            self.assertEqual(retained_seasons, {2026, 2027})
        old = self.service.source_as_of(season=2026, week=1, observed_as_of='2026-09-01T00:01:30+00:00')
        self.assertEqual(old['players']['q']['projected_stats']['pass_yd'], 1)

    def test_missing_legacy_source_stays_blocked_without_mutation(self):
        self.publish(1)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DELETE FROM projection_source_history WHERE week=1')
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'no valid source provenance'):
            self.admit()
        self.assertEqual(before, self.path.read_bytes())

    def test_plain_legacy_source_is_valid_without_rewriting_time_or_scoring(self):
        first = self.publish(1)
        with closing(sqlite3.connect(self.path)) as db, db:
            for oid, payload in db.execute('SELECT observation_id,payload FROM projection_source_history').fetchall():
                original = state_storage.decode(db, payload)
                db.execute('UPDATE projection_source_history SET payload=? WHERE observation_id=?',
                           (json.dumps(original), oid))
        self.admit()
        self.assertEqual(self.service.snapshot(), first)
        self.assertIsNone(self.service.source_as_of(season=2026, week=1,
                                                  observed_as_of='2026-09-01T00:00:59+00:00'))

    def test_wrong_source_identity_scope_or_future_time_cannot_be_substituted(self):
        for assignment in ("fingerprint='other'", 'season=2025', 'week=18',
                           "observed_at='2026-09-02T00:00:00+00:00'"):
            with self.subTest(assignment=assignment):
                self.publish(1)
                with closing(sqlite3.connect(self.path)) as db:
                    db.execute('BEGIN')
                    db.execute('UPDATE projection_source_history SET ' + assignment + ' WHERE week=1')
                    roots, _ = retention.plan(db)
                    with self.assertRaisesRegex(ValueError, 'no valid source provenance'):
                        policy.plan(db, roots)
                    db.rollback()

    def test_later_equal_fingerprint_does_not_backdate_knowledge(self):
        self.publish(1)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE projection_source_history SET observed_at='2026-09-02T00:00:00+00:00'")
        with self.assertRaisesRegex(ValueError, 'no valid source provenance'):
            self.admit()

    def test_horizon_child_scoring_scope_is_not_repaired_by_matching_source(self):
        first = self.publish(1)
        child = first['horizon_snapshot_ids']['2']
        with closing(sqlite3.connect(self.path)) as db, db:
            value = state_storage.decode(db, db.execute(
                'SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (child,)).fetchone()[0])
            value['scoring_profile_id'] = 'another-league-scoring'
            db.execute('UPDATE projection_snapshots SET payload=? WHERE snapshot_id=?',
                       (json.dumps(value), child))
        with self.assertRaisesRegex(ValueError, 'scope mismatch'):
            self.admit()

    def test_base_policy_preserves_sources_reachable_from_snapshot_without_source_pin(self):
        first = self.publish(1, 'b')
        with closing(sqlite3.connect(self.path)) as db, db:
            retention.pin_snapshot(db, event_id='historical-trade', snapshot_id=first['projection_snapshot_id'])
        for n in range(2, 15):
            self.publish(n)
        # Admission must still be possible after the base policy's eight-source
        # window rolls over. A snapshot root transitively pins its sources.
        self.admit()
        value = self.service.source_as_of(season=2026, week=1,
                                         observed_as_of='2026-09-01T00:01:30+00:00')
        self.assertEqual(value['players']['q']['projected_stats']['pass_yd'], 1)

    def test_quiet_active_and_rollback_sources_survive_other_league_refreshes(self):
        previous = self.publish(1, 'b')
        active = self.publish(2, 'b')
        for n in range(3, 20):
            self.publish(n)
        from src.core.projection_intelligence.service import ProjectionService
        restarted = ProjectionService(self.path, league_id='b')
        self.assertEqual(restarted.snapshot(), active)
        with closing(sqlite3.connect(self.path)) as db:
            roots, sources = retention.plan(db)
            self.assertIn(previous['projection_snapshot_id'], roots)
            self.assertIn(active['projection_snapshot_id'], roots)
            for oid in sources:
                payload = db.execute('SELECT payload FROM projection_source_history WHERE observation_id=?', (oid,)).fetchone()[0]
                self.assertNotEqual(json.loads(payload).get('$storage'), retention.PROVENANCE)
                # Decode validates every source state identity and payload.
                state_storage.decode(db, payload)
        self.admit()

    def test_shared_source_reclaimed_only_after_last_root_expires(self):
        first = self.publish(1)
        shared = self.publish(1, 'b')
        with closing(sqlite3.connect(self.path)) as db, db:
            retention.pin_snapshot(db, event_id='a-event', snapshot_id=first['projection_snapshot_id'])
            retention.pin_snapshot(db, event_id='b-event', snapshot_id=shared['projection_snapshot_id'])
            oid = db.execute('SELECT min(observation_id) FROM projection_source_history WHERE week=1').fetchone()[0]
        for n in range(2, 15):
            self.publish(n)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM projection_checkpoint_roots WHERE event_id='a-event'")
        self.publish(15, 'b')
        self.publish(16, 'b')
        with closing(sqlite3.connect(self.path)) as db, db:
            payload = db.execute('SELECT payload FROM projection_source_history WHERE observation_id=?', (oid,)).fetchone()[0]
            self.assertNotEqual(json.loads(payload).get('$storage'), retention.PROVENANCE)
            db.execute("DELETE FROM projection_checkpoint_roots WHERE event_id='b-event'")
            retention.collect(db)
            payload = db.execute('SELECT payload FROM projection_source_history WHERE observation_id=?', (oid,)).fetchone()[0]
            self.assertEqual(json.loads(payload).get('$storage'), retention.PROVENANCE)
        before = self.path.read_bytes()
        with closing(sqlite3.connect(self.path)) as db, db:
            retention.collect(db)
        self.assertEqual(self.path.read_bytes(), before)

    def test_expired_source_blocks_admission_not_existing_prepared_reads(self):
        previous = self.publish(1)
        active = self.publish(2)
        with closing(sqlite3.connect(self.path)) as db, db:
            for oid, payload in db.execute('SELECT observation_id,payload FROM projection_source_history').fetchall():
                envelope, _ = retention.unpack(payload)
                receipt = json.dumps({'$storage': retention.PROVENANCE, 'envelope': envelope},
                                     sort_keys=True, separators=(',', ':'))
                db.execute('UPDATE projection_source_history SET payload=? WHERE observation_id=?', (receipt, oid))
        before = self.path.read_bytes()
        from src.core.projection_intelligence.service import ProjectionService
        restarted = ProjectionService(self.path, league_id='a')
        self.assertEqual(restarted.snapshot(), active)
        with closing(sqlite3.connect(self.path)) as db:
            original = db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?',
                                  (previous['projection_snapshot_id'],)).fetchone()[0]
            self.assertEqual(state_storage.decode(db, original), previous)
            roots, _ = retention.plan(db)
            with self.assertRaisesRegex(ValueError, 'already expired'):
                policy.plan(db, roots)
        self.assertEqual(before, self.path.read_bytes())

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

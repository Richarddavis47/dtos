from contextlib import closing
import hashlib
import json
import sqlite3

from tests.test_projection_retention import ProjectionRetentionTests
from src.core.projection_intelligence import quarantine as q, retention, provenance_retention as p, state_storage
from src.core.projection_intelligence.service import ProjectionService, snapshot_compatibility


class ProjectionQuarantineTests(ProjectionRetentionTests):
    def test_receipt_only_active_and_rollback_cannot_be_quarantined(self):
        """Historical exclusion must not silently remove live operational reads."""
        self.publish(1)
        self.publish(2)
        with closing(sqlite3.connect(self.path)) as db:
            protected = {row[0] for table in ('projection_publication_heads', 'projection_previous_heads')
                         for row in db.execute(f'SELECT snapshot_id FROM {table}')}
            rows = list(db.execute('SELECT snapshot_id,payload FROM projection_snapshots'))
            manifest = []
            for sid, payload in rows:
                envelope, _ = retention.unpack(payload)
                manifest.append({'snapshot_id': sid, 'payload_sha256': hashlib.sha256(payload.encode()).hexdigest(),
                                 **{key: envelope.get(key) for key in ('league_id', 'season', 'week', 'scoring_profile_id', 'sleeper_evidence_snapshot_id')}})
            db.execute('BEGIN')
            for oid, payload in db.execute('SELECT observation_id,payload FROM projection_source_history').fetchall():
                envelope, _ = retention.unpack(payload)
                db.execute('UPDATE projection_source_history SET payload=? WHERE observation_id=?',
                           (json.dumps({'$storage': retention.PROVENANCE, 'envelope': envelope}), oid))
            with self.assertRaisesRegex(ValueError, 'protected'):
                q.plan(db, manifest)
            self.assertFalse(q.identities(db))
            for sid, payload in rows:
                if sid in protected:
                    self.assertTrue(state_storage.decode(db, payload)['players'])
            db.rollback()

    def test_publication_guard_rejects_missing_fingerprint_and_disappeared_source(self):
        first = self.publish(1)
        sid = first['projection_snapshot_id']
        with closing(sqlite3.connect(self.path)) as db:
            q.validate_publication(db, sid)
            db.execute('BEGIN')
            db.execute('DELETE FROM projection_source_history WHERE week=1')
            with self.assertRaisesRegex(ValueError, 'no valid source'):
                q.validate_publication(db, sid)
            db.rollback()
            db.execute('BEGIN')
            value = dict(first)
            value.pop('sleeper_evidence_snapshot_id')
            db.execute('UPDATE projection_snapshots SET payload=? WHERE snapshot_id=?', (json.dumps(value), sid))
            with self.assertRaisesRegex(ValueError, 'requires source'):
                q.validate_publication(db, sid)
            db.rollback()

    def test_compact_copy_preserves_quarantine_and_original_audit_payloads(self):
        from pathlib import Path
        from tools.projection_retention_migration import build_copy, verify_copy
        _, manifest = self.unsupported()
        with closing(sqlite3.connect(self.path)) as db:
            report = q.plan(db, manifest)
            db.execute('BEGIN')
            q.apply(db, manifest, expected_digest=report['digest'])
            db.commit()
        target = Path(self.folder.name) / 'quarantine-copy.sqlite3'
        build_copy(self.path, target, maximum_bytes=4 * 1048576)
        self.assertTrue(verify_copy(self.path, target)['retained_evidence_equal'])
        with closing(sqlite3.connect(target)) as db:
            self.assertEqual(q.identities(db), {item['snapshot_id'] for item in manifest})

    def unsupported(self):
        first = self.publish(1, 'legacy')
        with closing(sqlite3.connect(self.path)) as db, db:
            # Model the observed legacy shape: standalone, no active head,
            # original source absent; all original payloads remain preserved.
            db.execute("DELETE FROM projection_publication_heads WHERE league_id='legacy'")
            db.execute('DELETE FROM projection_source_history')
            db.execute('DELETE FROM sleeper_projection_snapshots')
            for sid, payload in db.execute('SELECT snapshot_id,payload FROM projection_snapshots').fetchall():
                value = state_storage.decode(db, payload)
                value.pop('horizon_snapshot_ids', None)
                value.pop('horizon_generation', None)
                db.execute('UPDATE projection_snapshots SET payload=? WHERE snapshot_id=?', (json.dumps(value), sid))
        self.publish(2)
        with closing(sqlite3.connect(self.path)) as db:
            rows = list(db.execute("SELECT snapshot_id,payload FROM projection_snapshots WHERE league_id='legacy'"))
            manifest = []
            for sid, payload in rows:
                e, _ = retention.unpack(payload)
                manifest.append({'snapshot_id': sid, 'payload_sha256': hashlib.sha256(payload.encode()).hexdigest(),
                                 **{key: e.get(key) for key in ('league_id','season','week','scoring_profile_id','sleeper_evidence_snapshot_id')}})
        return first, manifest

    def test_exact_reversible_classification_readers_gc_and_replay(self):
        _, manifest = self.unsupported()
        with closing(sqlite3.connect(self.path)) as db:
            original = list(db.execute('SELECT * FROM projection_snapshots ORDER BY snapshot_id'))
            report = q.plan(db, manifest)
            db.execute('BEGIN')
            q.apply(db, manifest, expected_digest=report['digest'])
            db.commit()
            self.assertEqual(original, list(db.execute('SELECT * FROM projection_snapshots ORDER BY snapshot_id')))
            roots, _ = retention.plan(db)
            self.assertFalse(roots & q.identities(db))
            self.assertTrue(p.plan(db, roots)['retained'])
            for item in manifest:
                payload = db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (item['snapshot_id'],)).fetchone()[0]
                self.assertEqual(state_storage.decode(db, payload)['players'], {})
                self.assertEqual(snapshot_compatibility(state_storage.decode(db, payload))[0], 'unsupported_provenance')
                self.assertTrue(state_storage.decode(db, payload, audit=True)['players'])
            before = self.path.read_bytes()
            for _ in range(100):
                db.execute('BEGIN')
                q.apply(db, manifest, expected_digest=report['digest'])
                db.commit()
            self.assertEqual(before, self.path.read_bytes())
            db.execute('BEGIN')
            retention.collect(db)
            db.commit()
            self.assertTrue(all(db.execute('SELECT 1 FROM projection_snapshots WHERE snapshot_id=?',
                                          (item['snapshot_id'],)).fetchone() for item in manifest))
            db.execute('BEGIN')
            q.rollback(db, manifest, expected_digest=report['digest'])
            db.commit()
            self.assertFalse(q.identities(db))
            for sid, *rest in original:
                self.assertEqual(tuple([sid, *rest]), db.execute('SELECT * FROM projection_snapshots WHERE snapshot_id=?', (sid,)).fetchone())

    def test_exact_identity_and_protected_root_guards(self):
        _, manifest = self.unsupported()
        with closing(sqlite3.connect(self.path)) as db:
            with self.assertRaisesRegex(ValueError, 'payload identity'):
                q.plan(db, [{**manifest[0], 'payload_sha256': 'changed'}, *manifest[1:]])
            db.execute('INSERT INTO projection_checkpoint_roots VALUES (?,?)', ('event', manifest[0]['snapshot_id']))
            with self.assertRaisesRegex(ValueError, 'protected'):
                q.plan(db, manifest)

    def test_restart_and_missing_source_checkpoint_rejected(self):
        _, manifest = self.unsupported()
        with closing(sqlite3.connect(self.path)) as db:
            with self.assertRaisesRegex(ValueError, 'no valid source'):
                retention.pin_snapshot(db, event_id='invalid', snapshot_id=manifest[0]['snapshot_id'])
            report = q.plan(db, manifest)
            db.execute('BEGIN')
            q.apply(db, manifest, expected_digest=report['digest'])
            db.commit()
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                retention.pin_snapshot(db, event_id='invalid', snapshot_id=manifest[0]['snapshot_id'])
        self.assertIsNone(ProjectionService(self.path, league_id='legacy').snapshot())
        self.assertEqual(ProjectionService(self.path, league_id='a').snapshot(), self.service.snapshot())

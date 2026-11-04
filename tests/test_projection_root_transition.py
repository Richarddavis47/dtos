from contextlib import closing
import json
import sqlite3
from unittest.mock import patch

from tests.test_projection_retention import ProjectionRetentionTests
from src.core.projection_intelligence import root_transition as rt, retention, state_storage
from src.core.projection_intelligence.service import ProjectionService


class ProjectionRootTransitionTests(ProjectionRetentionTests):
    def test_unrelated_receipt_cannot_make_valid_snapshot_quarantine_eligible(self):
        import hashlib
        from src.core.projection_intelligence import quarantine, provenance_retention
        values, _ = self.pair()
        with patch('src.core.projection_intelligence.service._now', return_value='2026-09-30T00:09:00+00:00'):
            self.service.cache_sleeper_week([{'player_id': 'q', 'season': 2026, 'week': 8, 'stats': {'pass_yd': 50}}], scoring={'pass_yd': .04}, season=2026, week=8)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DELETE FROM projection_previous_heads')
            for oid, payload in db.execute('SELECT observation_id,payload FROM projection_source_history WHERE week=8').fetchall():
                envelope, _ = retention.unpack(payload)
                db.execute('UPDATE projection_source_history SET payload=? WHERE observation_id=?', (json.dumps({'$storage': retention.PROVENANCE, 'envelope': envelope}), oid))
            db.commit()
            sid = values[0]['projection_snapshot_id']
            payload = db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (sid,)).fetchone()[0]
            envelope, _ = retention.unpack(payload)
            manifest = [{'snapshot_id': sid, 'payload_sha256': hashlib.sha256(payload.encode()).hexdigest(),
                         **{k: envelope.get(k) for k in ('league_id', 'season', 'week', 'scoring_profile_id', 'sleeper_evidence_snapshot_id')}}]
            proof = provenance_retention.plan(db, {sid}, snapshot_only=True)
            self.assertEqual(proof['scope'], 'snapshot_closure')
            with self.assertRaises(ValueError):
                quarantine.plan(db, manifest)
            db.execute('INSERT OR IGNORE INTO projection_retention_policy VALUES (?)', (provenance_retention.VERSION,))
            with self.assertRaisesRegex(ValueError, 'Snapshot-only proof'):
                provenance_retention.collect(db, proof)

    def test_nineteen_receipt_only_horizon_nodes_transition_without_audit_loss(self):
        import hashlib
        from src.core.projection_intelligence import quarantine, provenance_retention
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DELETE FROM projection_retention_policy')
        data = {'league': {'league_id': 'a', 'season': 2026, 'scoring_settings': {'pass_yd': .04}},
                'players': [{'id': 'q', 'position': 'QB'}], 'week': 3}
        def publish(current, n, changing_week, base):
            feeds = {week: [{'player_id': 'q', 'season': 2026, 'week': week, 'position': 'QB',
                             'stats': {'pass_yd': n if week == changing_week else base}}] for week in range(current, 19)}
            with patch('src.core.projection_intelligence.service._now', return_value=f'2026-09-30T00:0{n}:00+00:00'):
                return self.service.publish_horizon(feeds, data={**data, 'week': current}, league_id='a', season=2026, current_week=current)
        first, second = publish(3, 1, 3, 100), publish(3, 2, 3, 100)
        old_ids = {first['projection_snapshot_id'], second['projection_snapshot_id']}
        old_ids.update(first['horizon_snapshot_ids'].values())
        old_ids.update(second['horizon_snapshot_ids'].values())
        self.assertEqual(len(old_ids), 19)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM projection_source_history').fetchone()[0], 17)
        # Model the real separately retained current week-3 raw observations.
        for n in (3, 4):
            with patch('src.core.projection_intelligence.service._now', return_value=f'2026-09-30T00:0{n}:00+00:00'):
                self.service.cache_sleeper_week([{'player_id': 'q', 'season': 2026, 'week': 3, 'stats': {'pass_yd': n}}], scoring={'pass_yd': .04}, season=2026, week=3)
        # As in the production inventory, cache scopes have independently full
        # recent observations; the damaged receipts are not recent cache truth.
        with patch('src.core.projection_intelligence.service._now', return_value='2026-09-30T00:04:30+00:00'):
            for week in range(5, 19):
                self.service.cache_sleeper_week([{'player_id': 'q', 'season': 2026, 'week': week, 'stats': {'pass_yd': 150}}], scoring={'pass_yd': .04}, season=2026, week=week)
        previous, active = publish(4, 5, 4, 200), publish(4, 6, 4, 200)
        manifest = []
        with closing(sqlite3.connect(self.path)) as db:
            for sid in old_ids:
                payload = db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (sid,)).fetchone()[0]
                envelope, _ = retention.unpack(payload)
                manifest.append({'snapshot_id': sid, 'payload_sha256': hashlib.sha256(payload.encode()).hexdigest(),
                                 **{k: envelope.get(k) for k in ('league_id', 'season', 'week', 'scoring_profile_id', 'sleeper_evidence_snapshot_id')}})
            for oid, payload in db.execute('SELECT observation_id,payload FROM projection_source_history WHERE observation_id<=17').fetchall():
                envelope, _ = retention.unpack(payload)
                db.execute('UPDATE projection_source_history SET payload=? WHERE observation_id=?', (json.dumps({'$storage': retention.PROVENANCE, 'envelope': envelope}), oid))
            db.execute('UPDATE projection_publication_heads SET snapshot_id=?,published_at=? WHERE league_id=?', (second['projection_snapshot_id'], second['generated_at'], 'a'))
            db.execute('INSERT OR REPLACE INTO projection_previous_heads VALUES (?,?)', ('a', first['projection_snapshot_id']))
            db.commit()
            pending = rt.switch(db, league='a', active=active['projection_snapshot_id'], previous=previous['projection_snapshot_id'], expected_old=rt.roots(db, 'a'), transition_id='nineteen')
            self.assertTrue(old_ids <= retention.plan(db)[0])
            def classify(db):
                candidate = quarantine.plan(db, manifest)
                quarantine.apply(db, manifest, expected_digest=candidate['digest'])
            rt.finish(db, pending, accept=True, reviewed_reclassification=classify)
            self.assertEqual(quarantine.identities(db), old_ids)
            self.assertFalse(old_ids & retention.plan(db)[0])
            with db:
                db.execute('INSERT INTO projection_retention_policy VALUES (?)', (retention.POLICY,))
                provenance_retention.admit(db, expected_digest=provenance_retention.plan(db, retention.plan(db)[0])['digest'])
                retention.collect(db)
            stable = self.path.read_bytes()
            for _ in range(100):
                with db:
                    retention.collect(db)
            self.assertEqual(stable, self.path.read_bytes())
            for item in manifest:
                payload = db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (item['snapshot_id'],)).fetchone()[0]
                self.assertEqual(hashlib.sha256(payload.encode()).hexdigest(), item['payload_sha256'])
                self.assertTrue(state_storage.decode(db, payload, audit=True)['players'])
            rt.validate_pair(db, 'a', active['projection_snapshot_id'], previous['projection_snapshot_id'])
        self.assertEqual(ProjectionService(self.path, league_id='a').snapshot()['projection_snapshot_id'], active['projection_snapshot_id'])

    def pair(self):
        # Simulate offline preparation/import without collecting the old roots.
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DELETE FROM projection_retention_policy')
        values = [self.publish(n) for n in (1, 2, 3, 4)]
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT OR REPLACE INTO projection_publication_heads VALUES (?,?,?)', ('a', values[1]['projection_snapshot_id'], values[1]['generated_at']))
            db.execute('INSERT OR REPLACE INTO projection_previous_heads VALUES (?,?)', ('a', values[0]['projection_snapshot_id']))
            old = rt.roots(db, 'a')
        return values, old

    def transition(self, db, values, old, check=None):
        return rt.switch(db, league='a', active=values[3]['projection_snapshot_id'],
                         previous=values[2]['projection_snapshot_id'], expected_old=old,
                         transition_id='test', check_read=check)

    def test_atomic_switch_restart_and_preacceptance_reverse(self):
        values, old = self.pair()
        with closing(sqlite3.connect(self.path)) as db:
            manifest = self.transition(db, values, old)
        restart = ProjectionService(self.path, league_id='a')
        self.assertEqual(restart.snapshot()['projection_snapshot_id'], values[3]['projection_snapshot_id'])
        with closing(sqlite3.connect(self.path)) as db:
            keep, _ = retention.plan(db)
            self.assertTrue({v['projection_snapshot_id'] for v in values} <= keep)
            rt.finish(db, manifest, accept=False)
            self.assertEqual(rt.roots(db, 'a'), old)
        self.assertEqual(ProjectionService(self.path, league_id='a').snapshot()['projection_snapshot_id'], values[1]['projection_snapshot_id'])

    def test_invalid_active_is_noop(self):
        values, old = self.pair()
        values[3]['projection_snapshot_id'] = 'missing'
        with closing(sqlite3.connect(self.path)) as db:
            with self.assertRaises(ValueError):
                self.transition(db, values, old)
            self.assertEqual(rt.roots(db, 'a'), old)

    def test_invalid_rollback_is_noop(self):
        values, old = self.pair()
        values[2]['projection_snapshot_id'] = 'missing'
        with closing(sqlite3.connect(self.path)) as db:
            with self.assertRaises(ValueError):
                self.transition(db, values, old)
            self.assertEqual(rt.roots(db, 'a'), old)

    def test_duplicate_and_reversed_pair_rejected(self):
        values, old = self.pair()
        with closing(sqlite3.connect(self.path)) as db:
            for active, previous in ((values[3], values[3]), (values[2], values[3])):
                with self.assertRaises(ValueError):
                    rt.validate_pair(db, 'a', active['projection_snapshot_id'], previous['projection_snapshot_id'])
            self.assertEqual(rt.roots(db, 'a'), old)

    def test_provenance_failure_is_noop(self):
        values, old = self.pair()
        with closing(sqlite3.connect(self.path)) as db:
            payload = db.execute('SELECT payload FROM projection_source_history ORDER BY observation_id DESC LIMIT 1').fetchone()[0]
            envelope, _ = retention.unpack(payload)
            db.execute('UPDATE projection_source_history SET payload=? WHERE observation_id=(SELECT MAX(observation_id) FROM projection_source_history)', (json.dumps({'$storage': retention.PROVENANCE, 'envelope': envelope}),))
            db.commit()
            with self.assertRaises(ValueError):
                self.transition(db, values, old)
            self.assertEqual(rt.roots(db, 'a'), old)

    def test_interrupted_second_root_update_rolls_back_first(self):
        values, old = self.pair()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TRIGGER failure BEFORE UPDATE ON projection_previous_heads BEGIN SELECT RAISE(ABORT,'injected root failure'); END")
            with self.assertRaises(sqlite3.DatabaseError):
                self.transition(db, values, old)
            self.assertEqual(rt.roots(db, 'a'), old)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM projection_checkpoint_roots').fetchone()[0], 0)

    def test_consumer_failure_rolls_back_and_external_read_sees_old_pair(self):
        values, old = self.pair()
        def fail(db, proof):
            self.assertEqual(rt.roots(db, 'a')['active'][0], proof['active']['projection_snapshot_id'])
            with closing(sqlite3.connect(self.path)) as reader:
                self.assertEqual(rt.roots(reader, 'a'), old)
            raise RuntimeError('injected consumer failure')
        with closing(sqlite3.connect(self.path)) as db:
            with self.assertRaises(RuntimeError):
                self.transition(db, values, old, fail)
            self.assertEqual(rt.roots(db, 'a'), old)

    def test_acceptance_gc_and_unchanged_growth(self):
        values, old = self.pair()
        with closing(sqlite3.connect(self.path)) as db:
            manifest = self.transition(db, values, old)
            rt.finish(db, manifest, accept=True)
            db.execute('INSERT INTO projection_retention_policy VALUES (?)', (retention.POLICY,))
            db.commit()
            with db:
                retention.collect(db)
            size = self.path.stat().st_size
            counts = [db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('projection_snapshots', 'projection_source_history', 'projection_player_states')]
            for _ in range(100):
                with db:
                    retention.collect(db)
            self.assertEqual(size, self.path.stat().st_size)
            self.assertEqual(counts, [db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('projection_snapshots', 'projection_source_history', 'projection_player_states')])
            proof = rt.validate_pair(db, 'a', manifest['new']['active'][0], manifest['new']['previous'])
            self.assertTrue(proof['sources'])
            self.assertEqual(state_storage.decode(db, db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (values[3]['projection_snapshot_id'],)).fetchone()[0])['players']['q']['canonical_projection'], 0.16)

    def test_stale_review_cannot_switch(self):
        values, old = self.pair()
        old['previous'] = 'stale'
        with closing(sqlite3.connect(self.path)) as db:
            with self.assertRaises(ValueError):
                self.transition(db, values, old)

    def test_acceptance_classification_failure_keeps_pending_protection(self):
        values, old = self.pair()
        def fail(db):
            self.assertEqual(db.execute('SELECT COUNT(*) FROM projection_checkpoint_roots').fetchone()[0], 0)
            raise RuntimeError('injected reviewed classification failure')
        with closing(sqlite3.connect(self.path)) as db:
            pending = self.transition(db, values, old)
            with self.assertRaises(RuntimeError):
                rt.finish(db, pending, accept=True, reviewed_reclassification=fail)
            self.assertEqual(rt.roots(db, 'a'), pending['new'])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM projection_checkpoint_roots').fetchone()[0], 2)
            rt.finish(db, pending, accept=False)
            self.assertEqual(rt.roots(db, 'a'), old)

    def test_cross_league_pair_rejected(self):
        values, old = self.pair()
        with closing(sqlite3.connect(self.path)) as db:
            with self.assertRaises(ValueError):
                rt.validate_pair(db, 'b', values[3]['projection_snapshot_id'], values[2]['projection_snapshot_id'])

    def test_receipt_only_old_roots_become_quarantine_eligible_only_after_acceptance(self):
        import hashlib
        from src.core.projection_intelligence import quarantine
        values, old = self.pair()
        manifest = []
        with closing(sqlite3.connect(self.path)) as db:
            old_ids = {v['projection_snapshot_id'] for v in values[:2]}
            old_ids.update(sid for v in values[:2] for sid in v['horizon_snapshot_ids'].values())
            for sid in old_ids:
                payload = db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (sid,)).fetchone()[0]
                envelope, _ = retention.unpack(payload)
                manifest.append({'snapshot_id': sid, 'payload_sha256': hashlib.sha256(payload.encode()).hexdigest(),
                                 **{k: envelope.get(k) for k in ('league_id', 'season', 'week', 'scoring_profile_id', 'sleeper_evidence_snapshot_id')}})
            for oid, payload in db.execute('SELECT observation_id,payload FROM projection_source_history WHERE observation_id<=6').fetchall():
                envelope, _ = retention.unpack(payload)
                db.execute('UPDATE projection_source_history SET payload=? WHERE observation_id=?', (json.dumps({'$storage': retention.PROVENANCE, 'envelope': envelope}), oid))
            db.commit()
            with self.assertRaises(ValueError):
                quarantine.plan(db, manifest)
            pending = self.transition(db, values, old)
            with self.assertRaises(ValueError):
                quarantine.plan(db, manifest)
            def reviewed_classification(db):
                review = quarantine.plan(db, manifest)
                quarantine.apply(db, manifest, expected_digest=review['digest'])
            rt.finish(db, pending, accept=True, reviewed_reclassification=reviewed_classification)
            self.assertEqual(quarantine.identities(db), old_ids)
            for sid in old_ids:
                payload = db.execute('SELECT payload FROM projection_snapshots WHERE snapshot_id=?', (sid,)).fetchone()[0]
                self.assertTrue(state_storage.decode(db, payload, audit=True)['players'])
                self.assertFalse(state_storage.decode(db, payload)['players'])

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.core.fois import retention, state_storage
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts
from src.core.fois.repository import FOISRepository
from src.core.fois.working_storage import prepare, publish


class FOISRetentionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'fois.sqlite3'
        self.repo = FOISRepository(self.path)
        self.score = FOISEngine().evaluate(FOISFacts('a', 'a:1', 'gm', ()), generated_at='2026-09-01T00:00:00+00:00')

    def admit(self):
        with self.repo._connection() as db, db:
            retention.admit(db, expected_digest=retention.inventory_digest(db))

    def test_changed_fingerprint_same_quality_has_bounded_operational_history(self):
        self.admit()
        for n in range(100):
            self.repo.save(replace(self.score, brain_snapshot_id=str(n)), str(n))
        with self.repo._connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM fois_assessment_roots').fetchone()[0], 1)
            self.assertLessEqual(db.execute('SELECT count(*) FROM fois_snapshot_history').fetchone()[0], 9)
            self.assertEqual(db.execute('SELECT count(*) FROM fois_semantic_states').fetchone()[0], 1)
        before = self.path.read_bytes()
        for _ in range(100):
            self.assertFalse(self.repo.save(self.score, '99'))
        self.assertEqual(before, self.path.read_bytes())

    def test_existing_history_is_never_reclassified_as_disposable(self):
        for n in range(20):
            self.repo.save(self.score, str(n))
        with self.repo._connection() as db:
            old = list(db.execute('SELECT snapshot_id,payload FROM fois_snapshot_history ORDER BY rowid'))
        self.admit()
        for n in range(20, 60):
            self.repo.save(self.score, str(n))
        with self.repo._connection() as db:
            for identity, value in old:
                self.assertEqual(db.execute('SELECT payload FROM fois_snapshot_history WHERE snapshot_id=?', (identity,)).fetchone()[0], value)

    def test_material_changes_are_roots_not_operational_churn(self):
        self.admit()
        self.repo.save(replace(self.score, overall_score=70, overall_letter_grade='C'), 'first')
        self.repo.save(replace(self.score, overall_score=71, overall_letter_grade='C'), 'minor')
        self.repo.save(replace(self.score, overall_score=75, overall_letter_grade='C'), 'material')
        with self.repo._connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM fois_assessment_roots').fetchone()[0], 2)

    def test_summary_time_and_minor_magnitude_drift_are_not_events(self):
        base = {'method': 'fois-scoped-quality-1', 'activity': 10,
                'process': {'mean_magnitude': 60, 'supported_magnitudes': 4},
                'outcome': {'observation_horizon_days': {'maximum': 10}}}
        drift = {**base, 'process': {**base['process'], 'mean_magnitude': 60.01},
                 'outcome': {'observation_horizon_days': {'maximum': 1000}}}
        self.assertFalse(retention._details_material(base, drift))
        self.assertTrue(retention._details_material(base, {**drift, 'activity': 11}))
        material = {**drift, 'process': {**drift['process'], 'mean_magnitude': 65}}
        self.assertTrue(retention._details_material(base, material))
        self.assertTrue(retention._details_material(base, {**base, 'method': 'new'}))

    def test_tenure_and_season_boundaries_are_material(self):
        self.assertTrue(retention._material({'tenure_id': 'a'}, {'tenure_id': 'b'}))
        self.assertTrue(retention._material({'evaluation_end_season': 2026}, {'evaluation_end_season': 2027}))

    def test_broken_root_aborts_save_without_deletion(self):
        self.admit()
        self.repo.save(self.score, 'first')
        with self.repo._connection() as db, db:
            db.execute("INSERT INTO fois_assessment_roots VALUES ('missing','required')")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Missing canonical'):
            self.repo.save(self.score, 'second')
        self.assertEqual(before, self.path.read_bytes())

    def test_worker_publication_uses_active_retention(self):
        self.admit()
        self.repo.save(self.score, 'first')
        scratch = Path(self.folder.name) / 'scratch.sqlite3'
        prepare(self.path, scratch, 'a')
        worker = FOISRepository(scratch)
        for n in range(30):
            worker.save(self.score, f'changed-{n}')
        publish(scratch, self.repo, 'a')
        with self.repo._connection() as db:
            self.assertLessEqual(db.execute('SELECT count(*) FROM fois_snapshot_history').fetchone()[0], 9)
            for (payload,) in db.execute('SELECT payload FROM fois_snapshot_history'):
                self.assertEqual(state_storage.decode(db, payload)['league_id'], 'a')

    def test_stale_admission_does_not_activate(self):
        with self.repo._connection() as db:
            digest = retention.inventory_digest(db)
        self.repo.save(self.score, 'new')
        with self.repo._connection() as db:
            with self.assertRaisesRegex(ValueError, 'stale'):
                retention.admit(db, expected_digest=digest)
            self.assertFalse(retention.enabled(db))


if __name__ == '__main__':
    unittest.main()

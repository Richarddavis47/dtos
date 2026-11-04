import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.core.data_platform.global_evidence import GlobalEvidenceStore, GlobalFact, IngestionCheckpoint
from src.core.data_platform.ingestion import ingest


class GlobalIngestionTests(unittest.TestCase):
    def test_interruption_resume_and_completed_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / "facts.sqlite3")
            base = GlobalFact("production", "p", "fixture", "1", "2025-01-01T00:00:00Z", None, {"rec": 0})
            rows = [replace(base, source_record_id=str(i)) for i in range(5)]
            def broken():
                yield from rows[:3]
                raise OSError("provider interrupted")
            arguments = dict(key="fixture/2025", source_identity="sha-a", retrieved_at="2026-01-01T00:00:00Z", batch_size=2)
            with self.assertRaises(OSError):
                ingest(store, facts=broken, **arguments)
            self.assertEqual(store.ingestion_checkpoint("fixture/2025")["offset"], 2)
            self.assertEqual(store.counts(), {"production": 2})
            self.assertEqual(store.read('production', 'p', as_of=arguments['retrieved_at']), [])
            with self.assertRaisesRegex(ValueError, "incomplete checkpoint"):
                ingest(store, facts=lambda: iter(rows[:2]), **arguments)
            self.assertFalse(store.ingestion_checkpoint("fixture/2025")["complete"])
            result = ingest(store, facts=lambda: iter(rows), **arguments)
            self.assertEqual(result["resumed_at"], 2)
            self.assertEqual(store.counts(), {"production": 5})
            self.assertEqual(len(store.read('production', 'p', as_of=arguments['retrieved_at'])), 5)
            before = store.path.read_bytes()
            def forbidden():
                raise AssertionError("completed revision must not be read again")
            ingest(store, facts=forbidden, **arguments)
            self.assertEqual(store.path.read_bytes(), before)
            with self.assertRaises(RuntimeError):
                store.publish([], retrieved_at=arguments["retrieved_at"],
                              checkpoint=IngestionCheckpoint("fixture/2025", "sha-a", 0, 1))

    def test_new_revision_reuses_unchanged_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / "facts.sqlite3")
            fact = GlobalFact("production", "p", "fixture", "1", "2025-01-01T00:00:00Z", None, {"rec": 0})
            for revision in ("a", "b"):
                result = ingest(store, key="production", source_identity=revision,
                                facts=lambda: iter([fact]), retrieved_at="2026-01-01T00:00:00Z")
            self.assertEqual(result["created"], 0)
            self.assertEqual(store.counts(), {"production": 1})

    def test_refresh_keeps_complete_prior_generation_until_atomic_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / 'facts.sqlite3')
            base = GlobalFact('production', 'p', 'fixture', '1', '2025-01-01T00:00:00Z', None, {'rec': 1})
            rows = [replace(base, source_record_id=str(i)) for i in range(5)]
            common = dict(key='fixture/2025', batch_size=2)
            ingest(store, source_identity='a', facts=lambda: iter(rows),
                   retrieved_at='2026-01-01T00:00:00Z', **common)
            changed = [replace(row, values={'rec': 2}) for row in rows]
            def interrupted():
                yield from changed[:3]
                raise OSError('interrupted')
            with self.assertRaises(OSError):
                ingest(store, source_identity='b', facts=interrupted,
                       retrieved_at='2026-01-02T00:00:00Z', **common)
            reader = GlobalEvidenceStore(store.path, readonly=True)
            self.assertEqual([row['values']['rec'] for row in reader.read(
                'production', 'p', as_of='2026-01-03T00:00:00Z')], [1] * 5)
            ingest(store, source_identity='b', facts=lambda: iter(changed),
                   retrieved_at='2026-01-02T00:00:00Z', **common)
            self.assertEqual([row['values']['rec'] for row in reader.read(
                'production', 'p', as_of='2026-01-03T00:00:00Z')], [2] * 5)
            self.assertEqual([row['values']['rec'] for row in reader.read(
                'production', 'p', as_of='2026-01-01T00:00:00Z')], [1] * 5)

    def test_replaced_incomplete_source_never_publishes_abandoned_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / 'facts.sqlite3')
            base = GlobalFact('production', 'p', 'fixture', '1', '2025-01-01T00:00:00Z', None, {'rec': 1})
            def interrupted():
                for i in range(3):
                    yield replace(base, source_record_id=str(i))
                raise OSError('interrupted')
            common = dict(key='fixture', retrieved_at='2026-01-01T00:00:00Z', batch_size=2)
            with self.assertRaises(OSError):
                ingest(store, source_identity='a', facts=interrupted, **common)
            ingest(store, source_identity='b', facts=lambda: iter([replace(base, source_record_id='new')]), **common)
            rows = store.read('production', 'p', as_of=common['retrieved_at'])
            self.assertEqual([row['source_record_id'] for row in rows], ['new'])
            self.assertEqual(store.counts(), {'production': 1})

    def test_bounded_read_never_silently_discards_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / 'facts.sqlite3')
            base = GlobalFact('production', 'p', 'fixture', '1', '2025-01-01T00:00:00Z', None, {'rec': 1})
            store.publish([base, replace(base, source_record_id='2')], retrieved_at='2026-01-01T00:00:00Z')
            with self.assertRaisesRegex(ValueError, 'silent truncation'):
                store.read('production', 'p', as_of='2026-01-01T00:00:00Z', limit=1)

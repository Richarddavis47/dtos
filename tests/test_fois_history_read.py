"""Retained timeline read preservation, bounded reuse and snapshot isolation."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zlib
from unittest.mock import patch

from src.core.fois import state_storage
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult
from src.core.fois.models import FOIS_MODEL_VERSION
from src.core.fois.repository import FOISRepository


class FOISHistoryReadTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.repository = FOISRepository(Path(self.folder.name) / 'fois.db')
        score = FOISEngine().evaluate(FOISFacts('A', 'A:1', 'gm',
            (SeasonResult(2025, 9, 5, 2, league_size=10),), gm_id='gm', tenure_id='A:gm'))
        self.base = replace(score, evidence_integrity_version=None,
            front_office_evidence={'refs': [{'id':str(n), 'value':n} for n in range(80)]})
        self.envelopes = []
        previous = None
        with self.repository._connection() as db:
            for n in range(3):
                value = json.loads(json.dumps(asdict(replace(self.base, confidence=50+n,
                    generated_at=f'2026-09-01T12:0{n}:00Z'))))
                envelope = state_storage.encode(db, value, base_payload=previous)
                for r in range(3):
                    item = json.loads(envelope)
                    item['observation']['generated_at'] = f'2026-09-01T12:0{n}:0{r}Z'
                    encoded = json.dumps(item)
                    self.envelopes.append(encoded)
                    db.execute('INSERT INTO fois_snapshot_history VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (f'{n}-{r}', score.score_key, score.tenure_id, 'A', 'gm', FOIS_MODEL_VERSION,
                         None, item['observation']['generated_at'], f'source-{n}-{r}', encoded))
                previous = value
            db.commit()

    def test_timeline_reuses_identical_states_without_skipping_delta_validation(self):
        before = self.repository.path.read_bytes()
        with patch.object(state_storage, '_state', wraps=state_storage._state) as decoder:
            values = self.repository.timeline('A', 'gm')
        self.assertEqual(len(values), 9)
        # Three distinct roots require 1+2+3 recursive validations, not 3*(1+2+3).
        self.assertEqual(decoder.call_count, 6)
        self.assertEqual([s.confidence for s in values], [50]*3+[51]*3+[52]*3)
        self.assertEqual(len({s.generated_at for s in values}), 9)
        self.assertTrue(all(not s.evidence_revalidated for s in values))
        self.assertTrue(all('RETAINED_ASSESSMENT_NOT_REVALIDATED' in ' '.join(s.warnings) for s in values))
        self.assertEqual(self.repository.path.read_bytes(), before)

    def test_reads_are_independent_and_next_read_revalidates_changed_storage(self):
        first = self.repository.timeline('A', 'gm')
        first[0].front_office_evidence['refs'][0]['value'] = 'local-mutation'
        self.assertEqual(first[1].front_office_evidence['refs'][0]['value'], 0)
        self.assertEqual(self.repository.timeline('A', 'gm')[0].front_office_evidence['refs'][0]['value'], 0)
        with self.repository._connection() as db:
            db.execute('UPDATE fois_semantic_states SET payload=?', (b'corrupt',))
            db.commit()
        with self.assertRaises((ValueError, zlib.error)):
            self.repository.timeline('A', 'gm')

    def test_no_foreign_league_or_unknown_manager_history(self):
        self.assertEqual(self.repository.timeline('B', 'gm'), ())
        self.assertEqual(self.repository.timeline('A', 'other'), ())

    def test_memo_bound_and_oversize_fallback_preserve_exact_payloads(self):
        before = hashlib.sha256(self.repository.path.read_bytes()).hexdigest()
        with self.repository._connection() as db:
            db.execute('BEGIN')
            reader = state_storage.SnapshotDecoder(db, max_entries=1, max_bytes=1)
            expected = [state_storage.decode(db, x) for x in self.envelopes]
            self.assertEqual([reader.decode(x) for x in self.envelopes], expected)
            self.assertEqual(reader.retained_bytes, 0)
            reader = state_storage.SnapshotDecoder(db, max_entries=1, max_bytes=1024*1024)
            self.assertEqual([reader.decode(x) for x in self.envelopes], expected)
            self.assertLessEqual(len(reader._states), 1)
            self.assertLessEqual(reader.retained_bytes, 1024*1024)
            self.assertEqual(reader.decode(json.dumps(expected[0])), expected[0])
            malformed = json.loads(self.envelopes[0])
            malformed['observation']['unsupported'] = 1
            with self.assertRaisesRegex(ValueError, 'metadata'):
                reader.decode(json.dumps(malformed))
            db.rollback()
        self.assertEqual(hashlib.sha256(self.repository.path.read_bytes()).hexdigest(), before)

    def test_cached_content_identity_remains_exact_and_does_not_block_writer(self):
        import sqlite3
        with self.repository._connection() as reader:
            envelope = reader.execute('SELECT payload FROM fois_snapshot_history ORDER BY snapshot_id LIMIT 1').fetchone()[0]
            expected = state_storage.decode(reader, envelope)
            decoder = state_storage.SnapshotDecoder(reader)
            self.assertEqual(decoder.decode(envelope), expected)
            # DELETE-journal SQLite writer can commit while the read memo lives.
            with sqlite3.connect(self.repository.path, timeout=.2) as writer:
                writer.execute('UPDATE fois_semantic_states SET payload=?', (b'invalid replacement',))
            # An already-verified root still describes its original identity.
            self.assertEqual(decoder.decode(envelope), expected)
            self.assertEqual(state_storage.split(expected)[0], json.loads(envelope)['state_id'])
            # A different root is never admitted by the memo and fails closed.
            with self.assertRaises((ValueError, zlib.error)):
                decoder.decode(self.envelopes[-1])
        with self.assertRaises((ValueError, zlib.error)):
            self.repository.timeline('A', 'gm')


if __name__ == '__main__':
    unittest.main()

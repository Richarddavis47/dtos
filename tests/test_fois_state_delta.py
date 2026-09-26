import copy
from contextlib import closing
import hashlib
import json
import sqlite3
import unittest
import zlib
from dataclasses import replace
from pathlib import Path
import tempfile

from src.core.fois import state_storage as storage


class FOISDeltaTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript(storage.SCHEMA)
        self.addCleanup(self.db.close)
        self.base = {'score_key': 'a:gm:t:m', 'league_id': 'a', 'tenure_id': 't', 'model_version': 'm',
                     'generated_at': '1', 'overall': None, 'process': 0,
                     'evidence': [{'id': str(i), 'reference': hashlib.sha256(str(i).encode()).hexdigest()}
                                  for i in range(200)]}

    def test_exact_history_replay_and_bounded_dependency_depth(self):
        previous = None
        envelopes = []
        for i in range(40):
            value = {**self.base, 'process': i, 'generated_at': str(i)}
            encoded = storage.encode(self.db, value, base_payload=previous)
            envelopes.append((encoded, copy.deepcopy(value)))
            previous = value
        for encoded, expected in envelopes:
            self.assertEqual(storage.decode(self.db, encoded), expected)
        formats = dict(self.db.execute('SELECT format,count(*) FROM fois_semantic_states GROUP BY format'))
        self.assertGreater(formats[storage.DELTA_FORMAT], 30)
        self.assertGreater(formats[storage.FORMAT], 1)
        size = self.db.execute('SELECT sum(length(payload)) FROM fois_semantic_states').fetchone()[0]
        full_size = sum(len(zlib.compress(storage.split(value)[1].encode())) for _, value in envelopes)
        self.assertLess(size, full_size / 4)
        before = self.db.total_changes
        for _ in range(100):
            storage.encode(self.db, previous, base_payload=previous)
        self.assertEqual(self.db.total_changes, before)

    def test_missing_null_zero_and_unknown_fields_remain_distinct(self):
        previous = self.base
        for value in ({**self.base, 'overall': 0}, {**self.base, 'overall': False},
                      {**self.base, 'unknown': {'x': [None, 0, 1]}},
                      {key: value for key, value in self.base.items() if key != 'overall'}):
            encoded = storage.encode(self.db, value, base_payload=previous)
            self.assertEqual(storage.decode(self.db, encoded), value)
            previous = value

    def test_cross_scope_never_forms_delta(self):
        storage.encode(self.db, self.base)
        for field in ('score_key', 'league_id', 'tenure_id', 'model_version'):
            value = {**self.base, field: 'other'}
            encoded = storage.encode(self.db, value, base_payload=self.base)
            row = self.db.execute('SELECT format FROM fois_semantic_states WHERE state_id=?',
                                  (json.loads(encoded)['state_id'],)).fetchone()
            self.assertEqual(row[0], storage.FORMAT)

    def test_corrupt_base_fails_closed(self):
        encoded = storage.encode(self.db, {**self.base, 'process': 8}, base_payload=self.base)
        self.db.execute('DELETE FROM fois_semantic_states WHERE state_id=?', (storage.split(self.base)[0],))
        with self.assertRaisesRegex(ValueError, 'Missing'):
            storage.decode(self.db, encoded)

    def test_worker_cannot_publish_other_league_storage(self):
        from src.core.fois.repository import FOISRepository
        from src.core.fois.working_storage import prepare, publish
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repository = FOISRepository(root / 'source.sqlite3')
            flight = root / 'flight.sqlite3'
            prepare(repository.path, flight, 'A')
            with closing(sqlite3.connect(flight)) as db:
                with db:
                    storage.encode(db, {**self.base, 'league_id': 'B'})
            with self.assertRaisesRegex(RuntimeError, 'league mismatch'):
                publish(flight, repository, 'A')
            with repository._connection() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM fois_semantic_states').fetchone()[0], 0)

    def test_active_worker_publication_preserves_bounded_chain(self):
        from src.core.fois.models import FOIS_MODEL_VERSION
        from src.core.fois.repository import FOISRepository
        from src.core.fois.service import FOISService
        from src.core.fois.working_storage import prepare, publish
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repository = FOISRepository(root / 'fois.sqlite3')
            FOISService(repository)._generate_sync({
                'league': {'league_id': 'A', 'season': '2026'},
                'teams': [{'roster_id': 1, 'owner_id': 'gm', 'players': []}], 'fois_history': {},
            })
            score = repository.league('A', FOIS_MODEL_VERSION)[0]
            score = replace(score, front_office_evidence={'references': self.base['evidence']})
            repository.save(score, 'initial-delta-fixture')
            for n in range(20):
                flight = root / f'flight-{n}.sqlite3'
                prepare(repository.path, flight, 'A')
                expected = replace(score, confidence=n)
                FOISRepository(flight).save(expected, f'source-{n}')
                publish(flight, repository, 'A')
                self.assertEqual(repository.league('A', FOIS_MODEL_VERSION)[0], expected)
                with repository._connection() as db:
                    for (payload,) in db.execute('SELECT payload FROM fois_snapshot_history'):
                        storage.decode(db, payload)


if __name__ == '__main__':
    unittest.main()

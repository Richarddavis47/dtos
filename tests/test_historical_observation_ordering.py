"""Real sparse producer -> historical lookup: clocks, cutoffs and identity."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from tests.test_market_observation_producer_identity import checkpoint, prepared


class HistoricalObservationOrderingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'observations.db'
        self.store = IntelligenceCheckpointStore(self.path)

    def publish(self, identity, at, value=9000, *, known=None, asset='player:1', context='test'):
        data, player = prepared(value)
        evidence = tuple(replace(row, observed_at=at, metadata={
            **row.metadata, 'source_knowledge_at': known or at,
        }) for row in CheckpointPipeline._market_observations(data, 'player:1'))
        point = replace(checkpoint(identity, player['layers']['market_value']['value'],
                                  '2026-09-02T00:00:00Z'), asset_id=asset)
        saved, *_ = self.store.put_sparse(point, market_context_id=context, provider_evidence=evidence)
        with self.store._connect() as db:
            row = db.execute('SELECT * FROM global_market_observations WHERE observation_id=?',
                             (saved.global_market_observation_id,)).fetchone()
        return self.store._decode_observation(row)

    def lookup(self, cutoff='2026-09-01T12:00:01Z', **scope):
        return self.store.observation_at_or_before(
            asset_id=scope.get('asset', 'player:1'), market_context_id=scope.get('context', 'test'), event_at=cutoff)

    def test_original_subsecond_reproduction(self):
        early = self.publish('earlier', '2026-09-01T12:00:00Z')
        later = self.publish('later', '2026-09-01T12:00:00.100000Z', 3000)
        self.assertNotEqual(early.observation_id, later.observation_id)
        self.assertEqual(self.lookup().observation_id, later.observation_id)

    def test_mixed_precision_and_offset_cutoffs(self):
        self.publish('earlier', '2026-09-01T12:00:00Z')
        later = self.publish('later', '2026-09-01T14:00:00.100000+02:00', 3000)
        for cutoff in ('2026-09-01T12:00:00.1Z', '2026-09-01T07:00:00.100000-05:00',
                       '2026-09-01T12:00:00.100001+00:00'):
            self.assertEqual(self.lookup(cutoff).observation_id, later.observation_id)

    def test_observation_and_knowledge_are_independent_cutoffs(self):
        early = self.publish('earlier', '2026-09-01T12:00:00Z')
        late = self.publish('later', '2026-09-01T12:00:00.1Z', 3000,
                            known='2026-09-01T12:00:00.9Z')
        self.assertEqual(self.lookup('2026-09-01T12:00:00.5Z').observation_id, early.observation_id)
        self.assertEqual(self.lookup().observation_id, late.observation_id)
        self.assertIsNone(self.lookup('2026-09-01T11:59:59Z'))

    def test_equal_instants_have_stable_identity_tie_break_without_date_rewrites(self):
        a = self.publish('a', '2026-09-01T12:00:00Z')
        b = self.publish('b', '2026-09-01T14:00:00.000000+02:00', 3000)
        expected = max(a.observation_id, b.observation_id)
        with self.store._connect() as db:
            db.execute("UPDATE global_market_observations SET created_at='2099-01-01' WHERE observation_id=?", (min(a.observation_id, b.observation_id),))
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        for _ in range(3):
            self.assertEqual(self.lookup().observation_id, expected)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)

    def test_future_malformed_missing_and_naive_provider_clocks_withheld(self):
        early = self.publish('earlier', '2026-09-01T12:00:00Z')
        future = self.publish('later', '2026-09-01T12:00:00.1Z', 3000)
        original = json.dumps([r.__dict__ for r in future.provider_evidence])
        for quote, known in [('2026-09-01T12:00:02Z', None), ('bad', None), (None, None),
                             ('2026-09-01T12:00:00.1', None),
                             ('2026-09-01T12:00:00.1Z', 'bad'),
                             ('2026-09-01T12:00:00.1Z', '2026-09-01T12:00:02Z')]:
            rows = json.loads(original)
            for row in rows:
                row['observed_at'] = quote
                row['metadata']['source_knowledge_at'] = known
            with self.store._connect() as db:
                db.execute('UPDATE global_market_observations SET provider_evidence_json=? WHERE observation_id=?', (json.dumps(rows), future.observation_id))
            self.assertEqual(self.lookup().observation_id, early.observation_id)
        for cutoff in (None, 'bad', '2026-09-01T12:00:01', True):
            self.assertIsNone(self.lookup(cutoff))

    def test_zero_and_exact_scope_and_source_identity_survive_selection(self):
        self.publish('earlier', '2026-09-01T12:00:00Z')
        zero = self.publish('zero', '2026-09-01T12:00:00.1Z', 0)
        self.publish('foreign-asset', '2026-09-01T12:00:00.2Z', 3000, asset='player:other')
        self.publish('foreign-context', '2026-09-01T12:00:00.3Z', 6000, context='other')
        selected = self.lookup()
        self.assertEqual(selected.canonical_value, 0)
        for field in ('observation_id', 'asset_id', 'market_context_id', 'semantic_fingerprint',
                      'provider_evidence', 'normalization_version', 'model_version', 'canonical_value'):
            self.assertEqual(getattr(selected, field), getattr(zero, field), field)

    def test_future_rows_cannot_hide_eligible_history_behind_textual_limit(self):
        early = self.publish('earlier', '2026-09-01T12:00:00Z')
        with self.store._connect() as db:
            original = dict(db.execute('SELECT * FROM global_market_observations').fetchone())
            columns = ','.join(original)
            placeholders = ','.join('?' for _ in original)
            for n in range(501):
                row = {**original, 'observation_id': f'future-{n}', 'observed_at': '2027-01-01T00:00:00Z'}
                evidence = json.loads(row['provider_evidence_json'])
                for quote in evidence:
                    quote['observed_at'] = '2027-01-01T00:00:00Z'
                row['provider_evidence_json'] = json.dumps(evidence)
                db.execute(f'INSERT INTO global_market_observations ({columns}) VALUES ({placeholders})', tuple(row.values()))
        self.assertEqual(self.lookup().observation_id, early.observation_id)


if __name__ == '__main__':
    unittest.main()

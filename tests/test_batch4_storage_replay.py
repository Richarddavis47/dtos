"""Batch 4 derived history must not grow on unchanged evidence replay."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts
from src.core.fois.repository import FOISRepository


class Batch4StorageReplayTests(unittest.TestCase):
    def test_unchanged_evidence_replay_has_zero_durable_growth(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fois.sqlite3'
            repository = FOISRepository(path)
            score = FOISEngine().evaluate(
                FOISFacts('league-a', 'league-a:franchise:1', 'gm-a', ()),
                generated_at='2026-09-01T00:00:00+00:00',
            )
            score = replace(score, evidence_references=('trade:source-id', 'draft:source-id'))
            self.assertTrue(repository.save(score, 'same-canonical-evidence'))

            def footprint():
                with repository._connection() as connection:
                    counts = tuple(connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                                   for table in ('fois_scores_v2', 'fois_snapshot_history',
                                                 'fois_semantic_states', 'fois_evidence_links'))
                    pages = connection.execute('PRAGMA page_count').fetchone()[0]
                physical = sum(item.stat().st_size for item in path.parent.glob('fois.sqlite3*'))
                return counts, pages, physical

            before = footprint()
            for index in range(100):
                observed = replace(score, generated_at=f'2026-09-02T00:00:{index % 60:02}+00:00')
                self.assertFalse(repository.save(observed, 'same-canonical-evidence'))
            self.assertEqual(footprint(), before)
            self.assertEqual(before[0], (1, 1, 1, 2))


if __name__ == '__main__':
    unittest.main()

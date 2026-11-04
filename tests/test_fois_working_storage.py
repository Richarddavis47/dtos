"""Bounded scratch publication must preserve history and concurrent leagues."""
import tempfile
import unittest
from pathlib import Path

from src.core.fois.models import GMTenure
from src.core.fois.repository import FOISRepository
from src.core.fois.working_storage import prepare, publish


class WorkingStorageTests(unittest.TestCase):
    def test_history_not_copied_other_league_advance_preserved_handles_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = FOISRepository(root / 'source.sqlite3')
            repository.ensure_tenure(GMTenure('a', 'A', '1', 'a', 'A', '2026'))
            # Irrelevant historical growth must not affect scratch size.
            with repository._connection() as connection:
                connection.execute('CREATE TABLE irrelevant_history(payload BLOB)')
                connection.execute('INSERT INTO irrelevant_history VALUES (zeroblob(2000000))')
                connection.commit()
            target = root / 'working.sqlite3'
            prepare(repository.path, target, 'A')
            self.assertLess(target.stat().st_size, 300000)
            repository.ensure_tenure(GMTenure('b', 'B', '1', 'b', 'B', '2026'))
            publish(target, repository, 'A')
            self.assertEqual(len(repository.tenures('B')), 1)
            with repository._connection() as connection:
                self.assertEqual(connection.execute('SELECT length(payload) FROM irrelevant_history').fetchone()[0], 2000000)
            # Windows forbids this when prepare leaked a source connection.
            renamed = root / 'renamed.sqlite3'
            repository.path.rename(renamed)

    def test_same_league_advance_rejected_without_lost_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = FOISRepository(root / 'source.sqlite3')
            repository.ensure_tenure(GMTenure('a', 'A', '1', 'a', 'A', '2026'))
            target = root / 'working.sqlite3'
            prepare(repository.path, target, 'A')
            repository.ensure_tenure(GMTenure('new', 'A', '1', 'new', 'New', '2027'))
            with self.assertRaisesRegex(RuntimeError, 'advanced'):
                publish(target, repository, 'A')
            self.assertEqual(repository.tenure_for_gm('A', 'new').tenure_id, 'new')

    def test_cross_league_worker_output_rejected_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = FOISRepository(root / 'source.sqlite3')
            target = root / 'working.sqlite3'
            prepare(repository.path, target, 'A')
            FOISRepository(target).ensure_tenure(GMTenure('b', 'B', '1', 'b', 'B', '2026'))
            with self.assertRaisesRegex(RuntimeError, 'league mismatch'):
                publish(target, repository, 'A')
            self.assertEqual(repository.tenures('B'), ())

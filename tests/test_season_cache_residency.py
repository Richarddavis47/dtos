"""Bounded disposable residency, without changing retained source evidence."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from src.core.history_context.season_cache import SleeperSeasonCache


def facts(league, value=0):
    return {'league': {'league_id': str(league), 'season': '2025'},
            'rosters': [{'roster_id': 1, 'owner_id': str(league), 'players': ['123']}],
            'transactions': {'1': [{'transaction_id': str(league), 'points': value}]}}


class SeasonCacheResidencyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cache = SleeperSeasonCache(Path(self.directory.name))

    def write(self, league, value=0):
        self.cache.write(self.cache.normalize(str(league), 2025, facts(league, value)))

    def test_production_consumers_share_one_canonical_owner(self):
        import services.history
        import src.core.history_context
        import src.core.intelligence_memory
        import routes.weekly_report
        cache = src.core.history_context.sleeper_season_cache
        self.assertIs(services.history.sleeper_season_cache, cache)
        self.assertIs(src.core.intelligence_memory.sleeper_season_cache, cache)
        self.assertIs(routes.weekly_report.sleeper_season_cache, cache)

    def test_distinct_leagues_have_bounded_sections_and_checksum_metadata(self):
        for league in range(25):
            self.write(league)
        self.assertLessEqual(len(self.cache._section_cache), 36)
        self.assertLessEqual(len(self.cache._checksum_cache), 12)
        self.assertGreater(self.cache.residency()['evictions'], 0)

    def test_evicted_active_reader_keeps_exact_objects_and_rebuild_is_verified(self):
        self.write('first')
        held = self.cache.sections('first', 2025, ('league', 'rosters', 'transactions'))
        for league in range(25):
            self.write(league)
        self.assertNotIn((self.cache.path('first', 2025), 'transactions'), self.cache._section_cache)
        rebuilt = self.cache.sections('first', 2025, tuple(held))
        self.assertEqual(held, rebuilt)
        self.assertIsNot(held['transactions'], rebuilt['transactions'])
        self.assertEqual(held['transactions']['1'][0]['points'], 0)

    def test_warm_read_reuses_sections_without_decode_or_provider(self):
        self.write('a')
        with patch.object(self.cache, 'read', side_effect=AssertionError('unexpected decode')):
            first = self.cache.sections('a', 2025, ('league', 'transactions'))
            again = self.cache.sections('a', 2025, ('league', 'transactions'))
        self.assertIs(first['transactions'], again['transactions'])

    def test_byte_budget_and_oversized_bypass_preserve_complete_output(self):
        with patch.object(SleeperSeasonCache, 'MAX_RESIDENT_BYTES', 1024):
            source = facts('large')
            source['transactions']['1'] *= 1000
            self.cache.write(self.cache.normalize('large', 2025, source))
            result = self.cache.sections('large', 2025, ('transactions',))
            self.assertEqual(len(result['transactions']['1']), 1000)
            self.assertLessEqual(self.cache.residency()['resident_bytes'], 1024)
            self.assertGreater(self.cache.residency()['oversized'], 0)

    def test_publication_and_rollback_invalidate_all_old_sections(self):
        self.write('a', 7.92)
        first = self.cache.section('a', 2025, 'transactions')
        self.write('a', 123.45)
        self.assertEqual(self.cache.section('a', 2025, 'transactions')['1'][0]['points'], 123.45)
        self.write('a', 7.92)
        self.assertEqual(self.cache.section('a', 2025, 'transactions'), first)

    def test_external_replacement_cannot_reuse_old_generation(self):
        self.write('a', 7.92)
        other = SleeperSeasonCache(self.cache.root)
        other.write(other.normalize('a', 2025, facts('a', 123.45)))
        result = self.cache.sections('a', 2025, ('league', 'transactions'))
        self.assertEqual(result['transactions']['1'][0]['points'], 123.45)

    def test_late_writer_cannot_label_old_objects_as_a_new_publication(self):
        entered, resume = threading.Event(), threading.Event()
        original = self.cache._remember

        def pause(path, identity, archive, epoch, *args, **kwargs):
            if archive.facts['transactions']['1'][0]['points'] == 7.92:
                entered.set()
                self.assertTrue(resume.wait(5))
            return original(path, identity, archive, epoch, *args, **kwargs)

        with patch.object(self.cache, '_remember', side_effect=pause), ThreadPoolExecutor(1) as pool:
            old = pool.submit(self.write, 'a', 7.92)
            self.assertTrue(entered.wait(5))
            self.write('a', 123.45)
            resume.set()
            old.result()
        self.assertEqual(self.cache.section('a', 2025, 'transactions')['1'][0]['points'], 123.45)
        self.assertEqual(self.cache.prepared_checksum('a', 2025),
                         self.cache.normalize('a', 2025, facts('a', 123.45)).checksum)

    def test_active_reader_and_publication_never_wait_for_cold_decode(self):
        self.write('a')
        held = self.cache.sections('a', 2025, ('league', 'transactions'))
        entered, resume = threading.Event(), threading.Event()
        original = self.cache.normalize

        def pause(league, *args):
            if league == 'b':
                entered.set()
                self.assertTrue(resume.wait(5))
            return original(league, *args)

        self.write('b')
        with patch.object(self.cache, 'normalize', side_effect=pause), ThreadPoolExecutor(1) as pool:
            cold = pool.submit(self.cache.read, 'b', 2025)
            self.assertTrue(entered.wait(5))
            self.write('a', 5)
            self.assertEqual(self.cache.section('a', 2025, 'transactions')['1'][0]['points'], 5)
            self.assertEqual(held['transactions']['1'][0]['points'], 0)
            resume.set()
            cold.result()

    def test_concurrent_cold_readers_share_one_decode_and_keep_leagues_separate(self):
        for league in ('a', 'b'):
            self.write(league)
        self.cache.clear_resident()
        barrier = threading.Barrier(8)
        before = self.cache.residency()['decodes']

        def read(index):
            league = 'a' if index % 2 else 'b'
            barrier.wait(timeout=5)
            result = self.cache.sections(league, 2025, ('league', 'rosters', 'transactions'))
            self.assertEqual(result['league']['league_id'], league)
            return result

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(read, range(8)))
        self.assertEqual(self.cache.residency()['decodes'] - before, 2)
        self.assertEqual(self.cache.residency()['maximum_active_decodes'], 1)
        self.assertIs(results[0]['transactions'], results[2]['transactions'])

    def test_clear_during_active_read_cannot_repopulate_retired_residency(self):
        self.write('a')
        self.cache.clear_resident()
        entered, resume = threading.Event(), threading.Event()
        original = self.cache.normalize

        def pause(*args):
            entered.set()
            self.assertTrue(resume.wait(5))
            return original(*args)

        with patch.object(self.cache, 'normalize', side_effect=pause), ThreadPoolExecutor(1) as pool:
            reader = pool.submit(self.cache.read, 'a', 2025)
            self.assertTrue(entered.wait(5))
            self.cache.clear_resident()
            resume.set()
            self.assertEqual(reader.result().facts['league']['league_id'], 'a')
        self.assertEqual(self.cache.residency()['sections'], 0)

    def test_corrupt_or_missing_source_never_reuses_cached_sections(self):
        self.write('a')
        path = self.cache.path('a', 2025)
        path.write_bytes(b'not a gzip archive')
        with self.assertRaises(ValueError):
            self.cache.section('a', 2025, 'transactions')
        path.unlink()
        self.assertEqual(self.cache.sections('a', 2025, ('transactions',)), {})
        self.assertEqual(self.cache.residency()['sections'], 0)

    def test_read_only_rebuilds_do_not_change_durable_files(self):
        for league in range(25):
            self.write(league)

        def hashes():
            return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in self.cache.root.rglob('*') if p.is_file()}

        before = hashes()
        for _ in range(2):
            for league in range(25):
                self.cache.sections(str(league), 2025, ('league', 'rosters', 'transactions'))
        self.assertEqual(hashes(), before)
        self.assertLessEqual(self.cache.residency()['sections'], 36)

    def test_transaction_consumer_pins_source_across_eviction_and_replacement(self):
        from src.core.history_context.store import CanonicalHistoryStore
        source = facts('source-a')
        source['transactions'] = {'1': [
            {'type': 'trade', 'transaction_id': str(i), 'roster_ids': [1, 2],
             'draft_picks': [{'season': '2029', 'round': 1, 'roster_id': 2,
                              'owner_id': 1, 'previous_owner_id': 2}]}
            for i in range(3)]}
        self.cache.write(self.cache.normalize('root', 2025, source))
        store = CanonicalHistoryStore()
        original, calls = store._record, []

        def record(*args, **kwargs):
            if not calls:
                newer = {**source, 'league': {**source['league'], 'league_id': 'source-b'}}
                self.cache.write(self.cache.normalize('root', 2025, newer))
                for league in range(25):
                    self.write(league)
            calls.append(True)
            return original(*args, **kwargs)

        with patch('src.core.history_context.store.sleeper_season_cache', self.cache), \
                patch.object(store, '_record', side_effect=record):
            rows = store._transaction_records('root', 2025, 'trade')
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row['payload']['source_league_id'] == 'source-a' for row in rows))
        self.assertTrue(all(row['payload']['draft_picks'][0]['roster_id'] == 2 for row in rows))


if __name__ == '__main__':
    unittest.main()

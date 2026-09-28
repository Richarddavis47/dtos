import os
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.platform.cache_budget import CacheBudget, inspect, require, reusable, CacheAdmissionError
from src.core.history_context.season_cache import SleeperSeasonCache


class CacheBudgetTests(unittest.TestCase):
    def test_replacement_counts_old_bytes_once_and_scratch_twice(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'cache.json'
            target.write_bytes(b'x' * 100)
            budget = CacheBudget(120, 120, 3600, reserve_bytes=0)
            report = inspect(target, entries=[target], budget=budget, incoming_bytes=110)
            self.assertTrue(report['admitted'])
            self.assertEqual(report['expected_bytes'], 110)
            self.assertEqual(report['replacement_peak_bytes'], 210)

    def test_entry_and_aggregate_fail_before_modifying_previous_cache(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'cache.json'
            target.write_bytes(b'previous')
            budget = CacheBudget(10, 10, 3600, reserve_bytes=0)
            with self.assertRaises(CacheAdmissionError):
                require(target, entries=[target], budget=budget, incoming_bytes=11)
            self.assertEqual(target.read_bytes(), b'previous')

    def test_expiry_is_not_permission_to_delete(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'cache.json'
            target.write_bytes(b'previous')
            os.utime(target, (1, 1))
            self.assertFalse(reusable(target, CacheBudget(10, 10, 100), now=1000))
            self.assertEqual(target.read_bytes(), b'previous')

    def test_headroom_accounts_for_complete_replacement(self):
        with tempfile.TemporaryDirectory() as root:
            with patch('src.platform.cache_budget.shutil.disk_usage') as usage:
                usage.return_value.free = 199
                report = inspect(Path(root) / 'cache.json', entries=[],
                                 budget=CacheBudget(1000, 1000, 100, reserve_bytes=100), incoming_bytes=100)
                self.assertEqual(report['reasons'], ['CACHE_REPLACEMENT_HEADROOM_INSUFFICIENT'])

    def test_season_count_bound_never_deletes_older_history(self):
        with tempfile.TemporaryDirectory() as root:
            cache = SleeperSeasonCache(Path(root))
            for season in range(2021, 2027):
                cache.write(cache.normalize('league', season, {'league': {'season': season}}))
            with self.assertRaisesRegex(CacheAdmissionError, 'VERIFIED_REFETCH'):
                cache.write(cache.normalize('league', 2027, {'league': {'season': 2027}}))
            self.assertEqual(cache.available_seasons('league'), tuple(range(2021, 2027)))
            self.assertIsNotNone(cache.read('league', 2021))

    def test_season_replacement_does_not_count_as_new_generation(self):
        with tempfile.TemporaryDirectory() as root:
            cache = SleeperSeasonCache(Path(root))
            for _ in range(100):
                cache.write(cache.normalize('league', 2026, {'league': {'season': 2026}}))
            self.assertEqual(len(list(Path(root).glob('*/*.json.gz'))), 1)

    def test_json_restart_and_stale_cache_do_not_relabel_old_data_as_current(self):
        from services import sleeper
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'cache.json'
            state = {'data': {'league': {'league_id': 'A'}}, 'syncing': False}
            with patch.object(sleeper, 'CACHE_FILE', path), patch.object(sleeper, 'LEAGUE_ID', 'A'):
                sleeper.save_cache(state=state, league_id='A')
                restarted = {}
                sleeper.load_cache(state=restarted, league_id='A')
                self.assertEqual(restarted['data'], state['data'])
                os.utime(path, (1, 1))
                stale_restart = {}
                sleeper.load_cache(state=stale_restart, league_id='A')
                self.assertEqual(stale_restart, {})
                self.assertTrue(path.exists())

    def test_season_refetch_contract_retains_checksum_without_automatic_eviction(self):
        with tempfile.TemporaryDirectory() as root:
            cache = SleeperSeasonCache(Path(root))
            facts = {'league': {'season': 2025}, 'rosters': [{'roster_id': 1}]}
            original = cache.normalize('A', 2025, facts)
            cache.write(original)
            restarted = SleeperSeasonCache(Path(root))
            self.assertEqual(restarted.read('A', 2025).checksum, original.checksum)
            # Explicit removal is confined to this temporary fixture, not an
            # assertion that the real provider preserves every old season.
            restarted.delete('A', 2025)
            async def refetch(league, season):
                self.assertEqual((league, season), ('A', 2025))
                return facts
            rebuilt = asyncio.run(restarted.get_or_rebuild('A', 2025, refetch))
            self.assertEqual(rebuilt.checksum, original.checksum)

    def test_market_build_cap_preserves_last_valid_and_cleans_failed_candidate(self):
        import sqlite3
        from src.core.asset_market.read_model import build_read_model
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / '.history.asset-market-test.sqlite3'
            target.write_bytes(b'last-valid')
            budget = CacheBudget(65536, 1048576, 0, reserve_bytes=0)
            summary = {'asset_id': 'player:1', 'asset_type': 'player',
                       'display_name': 'Player', 'availability': 'available'}
            with patch('src.platform.cache_budget.MARKET_BUDGET', budget):
                with self.assertRaises(sqlite3.DatabaseError):
                    build_read_model(target, 'new', iter([(summary, {'large': 'x' * 100000})]), {})
            self.assertEqual(target.read_bytes(), b'last-valid')
            self.assertEqual(list(Path(root).glob('*.partial')), [])

    def test_market_orphan_candidates_count_towards_admission_not_silently_ignored(self):
        from src.platform.cache_budget import market_admission
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / '.history.asset-market-new.sqlite3'
            orphan = Path(root) / '..history.asset-market-old.sqlite3.123.partial'
            orphan.write_bytes(b'x' * 30)
            # Existing incomplete candidates must count too. Production partial
            # files have an extra leading dot because they are hidden scratch.
            with patch('src.platform.cache_budget.MARKET_BUDGET', CacheBudget(20, 40, 0, reserve_bytes=0)):
                with self.assertRaises(CacheAdmissionError):
                    with market_admission(target):
                        pass
            self.assertEqual(orphan.stat().st_size, 30)


if __name__ == '__main__':
    unittest.main()

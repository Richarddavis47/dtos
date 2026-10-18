"""Bulk synchronization reads preserve exact individual player evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from services.history import player_history_evidence, player_history_evidence_batch
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.history_context.store import CanonicalHistoryStore


class PlayerHistoryBatchTests(unittest.TestCase):
    def test_canonical_multi_season_equivalence_and_league_isolation(self):
        with TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            for league in ("A", "B"):
                for season in (2024, 2025):
                    cache.write(cache.normalize(league, season, {
                        "league": {"league_id": f"{league}-{season}", "season": str(season),
                                   "status": "complete", "scoring_settings": {"rec": 1}},
                        "matchups": {str(week): [{
                            "matchup_id": 1, "roster_id": 1,
                            "players_points": {"p1": week if league == "A" else -week, "p2": 0},
                            "starters": ["p1"], "points": week,
                        }] for week in range(1, 19)},
                    }))
            store = CanonicalHistoryStore()
            with patch("src.core.history_context.store.sleeper_season_cache", cache), patch(
                "services.history.historical_store", store,
            ):
                for league in ("A", "B", "A"):
                    expected = {pid: player_history_evidence(league, pid) for pid in ("p1", "p2", "missing")}
                    with patch.object(store, "records", wraps=store.records) as reads:
                        actual = player_history_evidence_batch(league, set(expected))
                    self.assertEqual(actual, expected)
                    self.assertEqual(actual["p1"]["weekly_record_count"], 36)
                    self.assertEqual(reads.call_count, 1)
                    self.assertTrue(all(call.args[0] == league for call in reads.call_args_list))

    def test_large_published_batch_preserves_individual_limit_and_total_count(self):
        # Pagination is independently stressed with 1,202 already-published
        # observations, not physically impossible Weeks 19–601 in two seasons.
        class PublishedRecords:
            def records(self, league, entity, *, player_id=None, limit=100):
                rows = [{'season': 1960 + index // 18, 'week': 1 + index % 18,
                         'league_id': league, 'player_id': pid,
                         'payload': {'fantasy_points': (index if league == 'A' else -index) if pid == 'p1' else 0}}
                        for index in range(1202) for pid in ('p1', 'p2') if player_id in (None, pid)]
                return len(rows), rows if limit is None else rows[:limit]
        store = PublishedRecords()
        with patch('services.history.historical_store', store):
            for league in ('A', 'B', 'A'):
                expected = {pid: player_history_evidence(league, pid) for pid in ('p1', 'p2', 'missing')}
                with patch.object(store, 'records', wraps=store.records) as reads:
                    actual = player_history_evidence_batch(league, set(expected))
                self.assertEqual(actual, expected)
                self.assertEqual(actual['p1']['weekly_record_count'], 1202)
                self.assertEqual(actual['p2']['weekly_record_count'], 1202)
                self.assertEqual(actual['p2']['season_total'], 0)
                self.assertEqual(reads.call_count, 1)
                self.assertTrue(all(call.args[0] == league for call in reads.call_args_list))

    def test_empty_roster_does_not_scan_history(self):
        with patch("services.history.historical_store") as store:
            self.assertEqual(player_history_evidence_batch("A", set()), {})
        store.records.assert_not_called()

"""Published stat-schema aliases and missing-not-zero evidence contracts."""
import unittest

from src.core.historical_memory.providers import normalize_nflverse_row


class CanonicalProductionNormalizationTests(unittest.TestCase):
    def test_source_first_downs_and_sacks_preserve_real_zero_and_missing(self):
        row = normalize_nflverse_row({'passing_first_downs': '12',
            'rushing_first_downs': '0', 'receiving_first_downs': '', 'sacks_suffered': '3'})
        self.assertEqual(row['raw_stats']['pass_fd'], 12)
        self.assertEqual(row['raw_stats']['rush_fd'], 0)
        self.assertIsNone(row['raw_stats']['rec_fd'])
        self.assertEqual(row['raw_stats']['pass_sack'], 3)

    def test_current_published_fields_and_game_identity(self):
        row = normalize_nflverse_row({
            "player_id": "00-1", "season": "2025", "week": "1",
            "game_id": "2025_01_A_B", "passing_interceptions": "0",
            "fumbles_total": "2", "fumbles_lost_total": "1",
        })
        self.assertEqual(row["raw_stats"]["pass_int"], 0)
        self.assertEqual(row["raw_stats"]["fumbles"], 2)
        self.assertEqual(row["raw_stats"]["fumbles_lost"], 1)
        self.assertEqual(row["game_id"], "2025_01_A_B")
        self.assertEqual(row["metric_status"]["pass_int"], "observed")

    def test_legacy_fields_preserved_and_explicit_current_missing_not_backfilled(self):
        self.assertEqual(normalize_nflverse_row({"interceptions": "2"})["raw_stats"]["pass_int"], 2)
        self.assertIsNone(normalize_nflverse_row({"interceptions": "2", "passing_interceptions": ""})["raw_stats"]["pass_int"])

    def test_nonfinite_and_missing_values_are_not_zero(self):
        for value in (None, "", "NA", "nan", "inf", "-inf"):
            row = normalize_nflverse_row({"passing_yards": value})
            self.assertIsNone(row["raw_stats"]["pass_yd"])
            self.assertEqual(row["metric_status"]["pass_yd"], "unavailable")

    def test_two_point_and_provider_usage_values_are_preserved(self):
        row = normalize_nflverse_row({'passing_2pt_conversions': '0',
            'receiving_2pt_conversions': '1', 'target_share': '0.25'})
        self.assertEqual(row['raw_stats']['pass_2pt'], 0)
        self.assertEqual(row['raw_stats']['rec_2pt'], 1)
        self.assertEqual(row['raw_stats']['target_share'], .25)
        self.assertIsNone(row['raw_stats']['rush_2pt'])

"""One raw global fact stream supports reference quality and league scoring."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from services.player_evidence import prepare_player_production
from src.core.data_platform.global_evidence import GlobalEvidenceStore
from src.core.valuation.player_methodology import assess_prepared_intrinsic
from tests.test_player_production_stream import fact


class ReferenceProductionMethodologyTests(unittest.TestCase):
    def test_league_scoring_changes_do_not_change_reference_model(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "global.sqlite3"
            store = GlobalEvidenceStore(path, reserve_bytes=0)
            values = {"pass_yd": 0, "pass_td": 0, "pass_int": 0, "rush_yd": 0,
                "rush_td": 0, "rec": 5, "rec_yd": 100, "rec_td": 1,
                "fumbles_lost": 0, "rec_tgt": 8, "rush_att": 0, "season_type": "REG"}
            store.publish([replace(fact("1", 5), values=values)], retrieved_at="2025-09-02T00:00:00Z")
            def prepare(league, ppr):
                return prepare_player_production({"league": {"league_id": league, "season": "2026"},
                    "scoring_settings": {"rec": ppr}, "players": {"1": {}}}, expected_league_id=league,
                    as_of="2026-09-09T00:00:00Z", path=path)
            first, second = prepare("A", 1), prepare("B", 2)
            self.assertNotEqual(first["generation"], second["generation"])
            self.assertEqual(first["reference_generation"], second["reference_generation"])
            for row in (first, second):
                windows = row["players"]["1"]["reference_production"]["windows"]
                self.assertEqual(windows[-1]["fantasy_points"], 21)
            def evaluate(row, league):
                return assess_prepared_intrinsic(prepared=row, league_id=league, player_id="1", position="WR", age=25)
            self.assertEqual(evaluate(first, "A"), evaluate(second, "B"))
            with self.assertRaises(ValueError):
                evaluate(first, "B")
            self.assertEqual(store.counts(), {"production": 1})

    def test_eight_season_summaries_are_bounded_temporal_and_replay_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'global.sqlite3'
            store = GlobalEvidenceStore(path, reserve_bytes=0)
            values = {'pass_yd': 0, 'pass_td': 0, 'pass_int': 0, 'rush_yd': 0,
                'rush_td': 0, 'rec': 5, 'rec_yd': 100, 'rec_td': 1,
                'fumbles_lost': 0, 'rec_tgt': 8, 'rush_att': 0, 'season_type': 'REG'}
            facts = [replace(fact('1', 5, year), source_record_id=f'game:{year}', values=values)
                for year in range(2018, 2026) if year != 2023]
            store.publish(facts, retrieved_at='2026-01-01T00:00:00Z')
            data = {'league': {'league_id': 'A', 'season': 2026},
                'players': {'1': {}}, 'scoring_settings': {'rec': 1}}
            def prepare(boundary):
                return prepare_player_production(data, expected_league_id='A', as_of=boundary, path=path)
            first = prepare('2026-02-01T00:00:00Z')
            rows = first['players']['1']['reference_seasons']
            self.assertEqual([row['season'] for row in rows], [2019, 2020, 2021, 2022, 2024, 2025])
            self.assertTrue(all(row['ppg'] == 21 for row in rows))
            self.assertEqual(first, prepare('2026-02-02T00:00:00Z'))
            self.assertEqual(first['players']['1']['current_sample_count'], 0)
            self.assertEqual(first['players']['1']['previous_sample_count'], 1)
            revision = replace(facts[-1], values={**values, 'rec': 10})
            store.publish([revision], retrieved_at='2026-03-01T00:00:00Z')
            self.assertEqual(first, prepare('2026-02-01T00:00:00Z'))
            later = prepare('2026-04-01T00:00:00Z')
            self.assertNotEqual(first['reference_generation'], later['reference_generation'])
            self.assertEqual(later['players']['1']['reference_seasons'][-1]['ppg'], 26)
            self.assertEqual(store.counts(), {'production': len(facts) + 1})

    def test_unknown_or_postseason_does_not_silently_enter_reference_cohort(self):
        from services.player_evidence import _reference_summary
        self.assertIsNone(_reference_summary(2025, [
            {'availability': 'unavailable', 'fantasy_points': None, 'targets': None, 'carries': 0}
        ])['ppg'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'global.sqlite3'
            store = GlobalEvidenceStore(path, reserve_bytes=0)
            store.publish([fact('1', 5), replace(fact('1', 7), source_record_id='postseason',
                values={'rec': 7, 'season_type': 'POST'})], retrieved_at='2025-09-02T00:00:00Z')
            result = prepare_player_production({'league': {'league_id': 'A', 'season': 2026},
                'players': {'1': {}}, 'scoring_settings': {'rec': 1}}, expected_league_id='A',
                as_of='2026-02-01T00:00:00Z', path=path)
            self.assertEqual(result['players']['1']['reference_seasons'], [])
            self.assertIsNone(assess_prepared_intrinsic(prepared=result, league_id='A',
                player_id='1', position='WR', age=25).value)

import tempfile
import unittest
from pathlib import Path

from src.core.data_platform.global_evidence import GlobalEvidenceStore
from src.core.data_platform.global_production import GlobalProduction
from src.core.data_platform.normalization.identity import PlayerIdentityResolver


class GlobalProductionTests(unittest.TestCase):
    def test_explicit_fumble_and_te_aliases_do_not_invent_long_touchdowns(self):
        from src.core.historical_memory.scoring import calculate_fantasy_points
        stats = GlobalProduction.scoring_components({'position': 'TE', 'rec': 5, 'fumbles_lost': 1})
        scored = calculate_fantasy_points(stats, {'rec': 1, 'bonus_rec_te': .5, 'fum_lost': -2})
        self.assertEqual(scored['fantasy_points'], 5.5)
        self.assertEqual(scored['availability'], 'calculated')
        partial = calculate_fantasy_points(stats, {'rec_td_40p': 2})
        self.assertEqual(partial['availability'], 'incomplete')
        self.assertIn('rec_td_40p', partial['missing_components'])
        canonical = GlobalProduction.score_game(stats, {'rec_td_40p': 2, 'rec': 1})
        self.assertIsNone(canonical['fantasy_points'])
        self.assertEqual(canonical['known_component_points'], 5)

    def test_two_leagues_score_one_global_row_without_durable_duplication(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / "facts.sqlite3")
            service = GlobalProduction(store)
            identity = PlayerIdentityResolver({"1": {"gsis_id": "00-1"}})
            row = {"provider": "nflverse", "provider_player_id": "00-1", "game_id": "game-1",
                   "season": 2025, "week": 1, "raw_stats": {"rec": 5, "rec_yd": 100}}
            result = service.publish_batch([row], identities=identity,
                game_dates={"game-1": "2025-09-01T00:00:00Z"}, retrieved_at="2026-01-01T00:00:00Z")
            self.assertEqual(result["created"], 1)
            a = service.league_scored("1", league_id="A", scoring_settings={"rec": 1, "rec_yd": .1}, as_of="2026-02-01T00:00:00Z")
            b = service.league_scored("1", league_id="B", scoring_settings={"rec": 0, "rec_yd": .1}, as_of="2026-02-01T00:00:00Z")
            self.assertEqual((a["ppg"], b["ppg"]), (15, 10))
            self.assertEqual(store.counts(), {"production": 1})
            self.assertEqual(a["games"][0]["evidence_fingerprint"], b["games"][0]["evidence_fingerprint"])
            past = service.league_scored("1", league_id="A", scoring_settings={"rec": 1}, as_of="2025-10-01T00:00:00Z")
            self.assertIsNone(past["ppg"])
            partial = service.league_scored('1', league_id='A', scoring_settings={'rec': 1, 'rec_td_40p': 2},
                                           as_of='2026-02-01T00:00:00Z')
            self.assertEqual(partial['availability'], 'cached')
            self.assertEqual(partial['scoring_availability'], 'incomplete')
            self.assertIsNone(partial['ppg'])
            self.assertEqual(partial['games'][0]['raw_stats']['rec'], 5)

    def test_many_leagues_reuse_global_evidence_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GlobalEvidenceStore(Path(directory) / 'facts.sqlite3')
            service = GlobalProduction(store)
            identity = PlayerIdentityResolver({'1': {'gsis_id': '00-1'}})
            service.publish_batch([{'provider': 'nflverse', 'provider_player_id': '00-1',
                'game_id': 'g1', 'season': 2025, 'week': 1,
                'raw_stats': {'rec': 5, 'rec_yd': 100}}], identities=identity,
                game_dates={'g1': '2025-09-01T00:00:00Z'}, retrieved_at='2026-01-01T00:00:00Z')
            before = store.path.read_bytes()
            fingerprints = set()
            for index in range(500):
                multiplier = (index % 3) * .5
                report = service.league_scored('1', league_id=f'league-{index}',
                    scoring_settings={'rec': multiplier, 'rec_yd': .1}, season=2025,
                    as_of='2026-01-02T00:00:00Z')
                self.assertEqual(report['league_id'], f'league-{index}')
                self.assertEqual(report['ppg'], 10 + 5 * multiplier)
                fingerprints.add(report['games'][0]['evidence_fingerprint'])
            self.assertEqual(len(fingerprints), 1)
            self.assertEqual(store.path.read_bytes(), before)

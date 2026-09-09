import tempfile
import unittest
from pathlib import Path

import httpx

from src.core.data_platform.global_evidence import GlobalEvidenceStore
from src.core.data_platform.global_evidence import GlobalFact
from src.core.data_platform.schedule_ingestion import ingest_schedule, kickoff


class ScheduleIngestionTests(unittest.TestCase):
    def test_known_future_schedule_is_not_historical_lookahead(self):
        with tempfile.TemporaryDirectory() as root:
            store = GlobalEvidenceStore(Path(root) / 'global.sqlite3')
            fact = GlobalFact('schedule', 'nfl-game:g1', 'nflverse', 'g1',
                '2027-09-07T17:00:00Z', None, {'kickoff': '2027-09-07T17:00:00Z'})
            store.publish([fact], retrieved_at='2027-05-01T00:00:00Z')
            self.assertEqual(len(store.read('schedule', 'nfl-game:g1', as_of='2027-06-01T00:00:00Z')), 1)
            self.assertEqual(store.read('schedule', 'nfl-game:g1', as_of='2027-04-01T00:00:00Z'), [])

    def test_eastern_daylight_and_standard_time_and_missing(self):
        self.assertEqual(kickoff({"gameday": "2025-09-07", "gametime": "13:00"}), "2025-09-07T17:00:00+00:00")
        self.assertEqual(kickoff({"gameday": "2026-01-04", "gametime": "13:00"}), "2026-01-04T18:00:00+00:00")
        self.assertIsNone(kickoff({"gameday": "2026-01-04", "gametime": "NA"}))

    def test_global_schedule_repeat_and_missing_time(self):
        body = b"game_id,season,week,gameday,gametime,home_team,away_team,game_type\ng1,2025,1,2025-09-07,13:00,NYJ,BUF,REG\ng2,2025,2,2025-09-14,NA,BUF,NYJ,REG\n"
        with tempfile.TemporaryDirectory() as root:
            store = GlobalEvidenceStore(Path(root) / "facts.sqlite3")
            with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))) as client:
                kwargs = dict(season=2025, retrieved_at="2026-01-01T00:00:00Z", temporary_directory=Path(root) / "tmp")
                report, times = ingest_schedule(client, store, **kwargs)
                self.assertEqual(report["kickoff_unavailable"], 1)
                self.assertEqual(list(times), ["g1"])
                before = store.path.read_bytes()
                ingest_schedule(client, store, **kwargs)
                self.assertEqual(store.path.read_bytes(), before)

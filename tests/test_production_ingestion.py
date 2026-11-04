import tempfile
import unittest
from pathlib import Path

import httpx

from src.core.data_platform.global_evidence import GlobalEvidenceStore
from src.core.data_platform.normalization.identity import PlayerIdentityResolver
from src.core.data_platform.production_ingestion import ingest_production


class ProductionIngestionTests(unittest.TestCase):
    def test_actual_adapter_boundary_replay_and_crosswalk_change(self):
        body = b"player_id,season,week,game_id,receptions,receiving_yards\n00-1,2025,1,g1,5,100\n00-2,2025,1,g1,0,0\n"
        identities = PlayerIdentityResolver({"1": {"gsis_id": "00-1"}})
        with tempfile.TemporaryDirectory() as root:
            store = GlobalEvidenceStore(Path(root) / "facts.sqlite3")
            temporary = Path(root) / "temporary"
            arguments = dict(season=2025, identities=identities,
                             game_dates={"g1": "2025-09-01T00:00:00Z"},
                             retrieved_at="2026-01-01T00:00:00Z", temporary_directory=temporary)
            with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))) as client:
                first = ingest_production(client, store, **arguments)
                self.assertEqual(first["coverage"]["identity_unresolved"], 1)
                self.assertEqual(first["created"], 1)
                before = store.path.read_bytes()
                replay = ingest_production(client, store, **arguments)
                self.assertTrue(replay["unchanged_revision"])
                self.assertEqual(replay["source_rows_examined"], 0)
                self.assertEqual(store.path.read_bytes(), before)
                identities.register("2", {"gsis_id": "00-2"})
                updated = ingest_production(client, store, **arguments)
                self.assertFalse(updated["unchanged_revision"])
                self.assertEqual(updated["created"], 1)
                self.assertEqual(store.counts(), {"production": 2})
            self.assertEqual(list(temporary.iterdir()), [])

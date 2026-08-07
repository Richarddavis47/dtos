from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from collections import namedtuple
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.core.historical_memory.enrichment import build_identity_context
from src.core.historical_memory.jobs import ImportJob
from src.core.historical_memory.store import HistoricalStore


class BoundedIdentityContextTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = HistoricalStore(Path(self.temp.name) / "history.sqlite3")

    async def asyncTearDown(self) -> None:
        self.temp.cleanup()

    def add_identity(
        self, player_id: str = "sleeper-1", gsis_id: str = "gsis-1",
        observed_at: str = "2026-01-01T00:00:00+00:00",
    ) -> bool:
        return self.store.upsert_identity(
            player_id, "Sleeper", player_id, "Player", 100, observed_at,
            {"provider_ids": {"GSIS": gsis_id}, "aliases": ["Player"]},
        )

    def test_unchanged_observation_is_noop_and_generations_are_stable(self) -> None:
        self.assertTrue(self.add_identity())
        generations = self.store.identity_generations()
        self.assertFalse(self.add_identity(observed_at="2026-02-01T00:00:00+00:00"))
        self.assertEqual(self.store.identity_generations(), generations)
        self.assertEqual(len(self.store.identities()), 1)

    def test_equivalent_metadata_ordering_is_noop(self) -> None:
        metadata = {
            "aliases": ["Player"],
            "provider_ids": {"GSIS": "gsis-1", "other": "x"},
        }
        self.store.upsert_identity(
            "sleeper-1", "Sleeper", "sleeper-1", "Player", 100,
            "2026-01-01T00:00:00+00:00", metadata,
        )
        reordered = {
            "provider_ids": {"other": "x", "GSIS": "gsis-1"},
            "aliases": ["Player"],
        }
        self.assertFalse(self.store.upsert_identity(
            "sleeper-1", "Sleeper", "sleeper-1", "Player", 100,
            "2026-02-01T00:00:00+00:00", reordered,
        ))

    def test_real_semantic_and_mapping_changes_advance_correct_generations(self) -> None:
        self.add_identity()
        initial = self.store.identity_generations()
        self.assertTrue(self.store.upsert_identity(
            "sleeper-1", "Sleeper", "sleeper-1", "New Name", 100,
            "2026-02-01T00:00:00+00:00",
            {"provider_ids": {"GSIS": "gsis-1"}, "aliases": ["Player"]},
        ))
        renamed = self.store.identity_generations()
        self.assertEqual(renamed["semantic"], initial["semantic"] + 1)
        self.assertEqual(renamed["mapping"], initial["mapping"])
        self.assertTrue(self.store.upsert_identity(
            "sleeper-1", "Sleeper", "sleeper-1", "New Name", 100,
            "2026-03-01T00:00:00+00:00",
            {"provider_ids": {"GSIS": "gsis-2"}, "aliases": ["Player"]},
        ))
        changed = self.store.identity_generations()
        self.assertEqual(changed["semantic"], renamed["semantic"] + 1)
        self.assertEqual(changed["mapping"], renamed["mapping"] + 1)

    def test_compact_projection_streams_one_latest_mapping_per_identity(self) -> None:
        connection = sqlite3.connect(self.store.path)
        rows = []
        for version in range(200):
            for player in range(100):
                metadata = json.dumps({
                    "provider_ids": {"GSIS": f"gsis-{player}"},
                    "unused": "x" * 256,
                })
                rows.append((
                    f"sleeper-{player}", "Sleeper", f"sleeper-{player}",
                    f"Player {player}", 100, f"2026-01-{version + 1:04d}",
                    metadata,
                ))
        connection.executemany(
            """INSERT INTO player_identity(
            dtos_player_id,provider,provider_player_id,display_name,confidence,
            valid_from,metadata) VALUES (?,?,?,?,?,?,?)""",
            rows,
        )
        connection.commit()
        connection.close()
        self.store.rebuild_current_identity_projection()
        with patch.object(
            self.store, "identities",
            side_effect=AssertionError("full identity hydration is forbidden"),
        ):
            context = build_identity_context(self.store)
        self.assertEqual(context.canonical_count, 100)
        self.assertEqual(context.gsis_count, 100)
        self.assertEqual(context.gsis_to_dtos["gsis-99"], "sleeper-99")
        self.assertEqual(self.store.current_identity_count(), 100)

    async def test_completed_and_pending_segments_skip_context_and_provider(self) -> None:
        import services.history as history_service

        self.add_identity()
        job = ImportJob(self.store, "L", (2022,), ("player_week",))
        job.create()
        self.store.checkpoint(
            checkpoint_key="L:2022:player_week:nflverse:1.2",
            job_id=job.job_id, league_id="L", season=2022, week=None,
            data_type="player_week", provider="nflverse",
            importer_version="1.2", status="completed",
        )
        with (
            patch.object(history_service, "historical_store", self.store),
            patch.object(
                history_service, "build_identity_context",
                side_effect=AssertionError("context must not be built"),
            ),
            patch(
                "services.history.NflverseProvider.weekly_batches",
                side_effect=AssertionError("provider must not be requested"),
            ),
        ):
            result = await history_service.enrich_player_history(
                "L", seasons={2022, 2026}, today=date(2026, 7, 28),
                skip_current=True,
            )
        self.assertEqual(result["status"], "completed_with_pending")
        self.assertEqual(result["identity_context"]["state"], "not_required")
        latest = self.store.jobs("L")[0]
        self.assertEqual(latest["skipped_seasons"], [2022])
        self.assertEqual(latest["pending_seasons"], [2026])
        self.assertEqual(latest["eligible_seasons"], [])

    async def test_job_and_lease_exist_before_context_construction(self) -> None:
        import services.history as history_service

        self.add_identity()

        def inspected_context(store: HistoricalStore):
            job = store.jobs("L")[0]
            self.assertEqual(job["status"], "running")
            self.assertEqual(job["context_build_state"], "building")
            self.assertTrue(store.locks())
            return build_identity_context(store)

        async def batches(_provider, season: int, batch_size: int):
            self.assertEqual((season, batch_size), (2022, 250))
            if False:
                yield []

        with (
            patch.object(history_service, "historical_store", self.store),
            patch.object(
                history_service, "build_identity_context", inspected_context,
            ),
            patch(
                "services.history.NflverseProvider.weekly_batches", batches,
            ),
        ):
            result = await history_service.enrich_player_history(
                "L", seasons={2022}, today=date(2023, 7, 1),
            )
        self.assertEqual(result["status"], "complete")
        self.assertFalse(self.store.locks())
        latest = self.store.jobs("L")[0]
        self.assertEqual(latest["context_build_state"], "complete")

    async def test_context_failure_is_diagnosed_and_releases_lease(self) -> None:
        import services.history as history_service

        self.add_identity()
        with (
            patch.object(history_service, "historical_store", self.store),
            patch.object(
                history_service, "build_identity_context",
                side_effect=MemoryError("simulated bounded failure"),
            ),
        ):
            with self.assertRaises(MemoryError):
                await history_service.enrich_player_history(
                    "L", seasons={2022}, today=date(2023, 7, 1),
                )
        latest = self.store.jobs("L")[0]
        self.assertEqual(latest["status"], "failed")
        self.assertEqual(latest["last_error_context"], "identity_context")
        self.assertFalse(self.store.locks())

    def test_disk_safety_gate_fails_before_metadata_migration(self) -> None:
        usage = namedtuple("usage", "total used free")
        with patch(
            "src.core.historical_memory.store.shutil.disk_usage",
            return_value=usage(1024, 1024, 0),
        ):
            with self.assertRaisesRegex(RuntimeError, "at least 16 MiB"):
                self.store._require_migration_capacity()


if __name__ == "__main__":
    unittest.main()

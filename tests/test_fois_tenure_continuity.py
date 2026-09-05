"""History arrival must update the current GM, not create unreachable scores."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.fois.models import FOIS_MODEL_VERSION, GMTenure, TakeoverSnapshot
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService


class FOISTenureContinuityTests(unittest.TestCase):
    def test_same_id_can_receive_its_initial_takeover_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = FOISRepository(Path(directory) / "fois.sqlite3")
            tenure = GMTenure("first", "A", "A:franchise:1", "owner", "GM", "2026-01-01")
            repository.ensure_tenure(tenure)
            snapshot = TakeoverSnapshot(
                "snapshot", "first", "2026-01-01", None, None, (), (), (), {},
            )
            repository.ensure_tenure(tenure, snapshot)
            self.assertEqual(repository.takeover("first"), snapshot)

    def test_normal_generation_recovers_preexisting_unlinked_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = FOISRepository(Path(directory) / "fois.sqlite3")
            service = FOISService(repository)
            data = {
                "league": {"league_id": "secondary", "season": "2026"},
                "teams": [{"roster_id": 1, "owner_id": "owner", "players": []}],
                "fois_history": {},
            }
            initial = service._generate_sync(data)[0]
            data["fois_history"] = {"1": {"seasons": [
                {"season": year, "wins": 9, "losses": 5,
                 "finish": 2, "league_size": 10, "complete": True}
                for year in range(2022, 2026)
            ]}}
            # Reproduce the prior ignored insert using only a disposable DB.
            with patch.object(repository, "ensure_tenure", side_effect=lambda tenure, _snapshot: tenure):
                unlinked = service._generate_sync(data)[0]
            self.assertNotEqual(initial.tenure_id, unlinked.tenure_id)
            corrected = service._generate_sync(data)[0]
            current = repository.score_for_gm("secondary", "secondary:gm:owner", FOIS_MODEL_VERSION)
            self.assertEqual(current.score_key, corrected.score_key)
            self.assertEqual(current.tenure_id, initial.tenure_id)
            self.assertEqual(current.overall_score, unlinked.overall_score)
            self.assertEqual(current.confidence, unlinked.confidence)
            with repository._connection() as connection:
                retained = connection.execute(
                    "SELECT COUNT(*) FROM fois_scores_v2 WHERE score_key=?",
                    (unlinked.score_key,),
                ).fetchone()[0]
            self.assertEqual(retained, 1)

    def test_same_owner_reuses_tenure_without_rewriting_takeover(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = FOISRepository(Path(directory) / "fois.sqlite3")
            first = GMTenure("first", "A", "A:franchise:1", "owner", "GM", "2026-01-01")
            snapshot = TakeoverSnapshot(
                "snapshot", "first", "2026-01-01", None, None, (), (), (), {},
            )
            repository.ensure_tenure(first, snapshot)
            proposed = GMTenure("inferred", "A", "A:franchise:1", "owner", "GM", "2022-01-01")
            self.assertEqual(repository.ensure_tenure(proposed), first)
            self.assertEqual(repository.takeover("first"), snapshot)
            self.assertEqual(len(repository.tenures("A")), 1)
            other = GMTenure("other", "B", "B:franchise:1", "owner", "GM", "2022-01-01")
            self.assertEqual(repository.ensure_tenure(other), other)
            self.assertEqual(len(repository.tenures("B")), 1)

    def test_history_arrival_keeps_current_score_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = FOISRepository(Path(directory) / "fois.sqlite3")
            service = FOISService(repository)
            data = {
                "league": {"league_id": "secondary", "season": "2026"},
                "teams": [{"roster_id": 1, "owner_id": "owner", "players": []}],
                "fois_history": {},
            }
            initial = service._generate_sync(data)[0]
            self.assertIsNone(initial.overall_score)
            data["fois_history"] = {"1": {"seasons": [
                {"season": year, "wins": 9, "losses": 5,
                 "finish": 2, "league_size": 10, "complete": True}
                for year in range(2022, 2026)
            ]}}
            published = service._generate_sync(data)[0]
            current = repository.score_for_gm(
                "secondary", "secondary:gm:owner", FOIS_MODEL_VERSION,
            )
            self.assertIsNotNone(published.overall_score)
            self.assertEqual(current.score_key, published.score_key)
            self.assertEqual(current.seasons_evaluated, 4)
            self.assertEqual(len(repository.league("secondary", FOIS_MODEL_VERSION)), 1)
            self.assertEqual(initial.tenure_id, published.tenure_id)
            replay = service._generate_sync(data)[0]
            self.assertEqual(replay.score_key, published.score_key)
            with repository._connection() as connection:
                missing = connection.execute(
                    "SELECT COUNT(*) FROM fois_scores_v2 s LEFT JOIN fois_gm_tenures t "
                    "ON s.tenure_id=t.tenure_id WHERE t.tenure_id IS NULL"
                ).fetchone()[0]
            self.assertEqual(missing, 0)


if __name__ == "__main__":
    unittest.main()

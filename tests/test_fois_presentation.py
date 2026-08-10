"""FOIS v1.9.1 presentation and canonical league-selection contracts."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.fois import create_fois_router
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService
from src.ui.design_system import page_header


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(page_header(
        title, league_name="Day Traders", last_updated="2026-08-09T12:00:00Z",
    ) + body)


class FOISPresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = FOISRepository(Path(self.directory.name) / "fois.sqlite3")
        self.service = FOISService(self.repository)
        self.data = {"league": {"league_id": "active-league", "name": "Day Traders"}}

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _persist_profiles(self, league_id: str, count: int) -> tuple[object, ...]:
        scores = []
        for index in range(count):
            facts = FOISFacts(
                league_id, f"franchise-{index}", f"owner-{index}",
                (SeasonResult(2025, 9, 5, index + 1, league_size=10),),
                gm_id=f"gm-{index}", gm_name=f"Executive {index + 1}",
                tenure_id=f"tenure-{index}",
            )
            score = FOISEngine().evaluate(facts)
            self.repository.save(score, f"source-{league_id}-{index}")
            scores.append(score)
        return tuple(scores)

    def _client(self, require_data: Mock | None = None) -> TestClient:
        app = FastAPI()
        app.include_router(create_fois_router(
            service=self.service,
            require_data=require_data or Mock(return_value=self.data),
            page=_page,
        ))
        return TestClient(app)

    def test_default_loaded_league_renders_all_persisted_profiles(self) -> None:
        scores = self._persist_profiles("active-league", 10)
        require_data = Mock(return_value=self.data)
        with patch.object(self.service, "generate") as generate:
            response = self._client(require_data).get("/fois")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text.count("Executive Profile</a>"), 10)
        self.assertTrue(all(score.gm_name in response.text for score in scores))
        require_data.assert_called_once_with()
        generate.assert_not_called()

    def test_shared_header_primary_action_and_navigation_contract(self) -> None:
        self._persist_profiles("active-league", 1)
        html = self._client().get("/fois").text
        self.assertIn('data-dtos-component="page-header"', html)
        self.assertIn("Front Office Intelligence System", html)
        self.assertIn("Evaluate General Manager performance", html)
        self.assertIn('class="ds-action primary" href="#gm-rankings"', html)
        self.assertIn('id="gm-rankings"', html)
        self.assertIn('id="executive-profiles"', html)
        self.assertIn('href="/history"', html)

    def test_explicit_valid_league_overrides_loaded_default(self) -> None:
        self._persist_profiles("active-league", 1)
        self._persist_profiles("other-league", 1)
        response = self._client().get("/fois?league_id=other-league")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Executive 1", response.text)
        self.assertIn("/api/fois/leagues/other-league/gms/gm-0", response.text)
        self.assertNotIn("/api/fois/leagues/active-league/gms/gm-0", response.text)

    def test_invalid_explicit_league_is_safe(self) -> None:
        self._persist_profiles("active-league", 1)
        response = self._client().get("/fois?league_id=not-loaded")
        self.assertEqual(response.status_code, 200)
        self.assertIn("League unavailable", response.text)
        self.assertNotIn("Executive Profile</a>", response.text)

    def test_no_loaded_league_has_honest_empty_state(self) -> None:
        response = self._client(Mock(return_value={})).get("/fois")
        self.assertEqual(response.status_code, 200)
        self.assertIn("No valid league is loaded", response.text)
        self.assertNotIn("FOIS is ready", response.text)

    def test_single_persisted_league_is_safe_fallback(self) -> None:
        self._persist_profiles("persisted-league", 1)
        response = self._client(Mock(return_value={})).get("/fois")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Executive 1", response.text)
        self.assertIn("/api/fois/leagues/persisted-league/gms/gm-0", response.text)

    def test_pending_generation_is_distinct_from_missing_data(self) -> None:
        response = self._client().get("/fois")
        self.assertEqual(response.status_code, 200)
        self.assertIn("FOIS generation pending", response.text)
        self.assertNotIn("FOIS data unavailable", response.text)

    def test_rendering_does_not_change_score_output(self) -> None:
        before = self._persist_profiles("active-league", 1)[0]
        response = self._client().get("/fois")
        after = self.repository.league("active-league", before.model_version)[0]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

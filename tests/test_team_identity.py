"""Canonical team identity and rendered-label validation regressions."""
from __future__ import annotations

import unittest

from src.core.team_identity import canonical_team_name, team_name_for, team_name_map
from src.core.inspection.discovery import discover_pages
from tools.validation.smoke_http import validate_team_identity


class TeamIdentityTests(unittest.TestCase):
    def test_canonical_name_precedence_and_fallback(self) -> None:
        self.assertEqual(canonical_team_name({"team_name": "The Champions", "owner": "Owner"}), "The Champions")
        self.assertEqual(canonical_team_name({"owner": "Owner"}), "Owner")
        self.assertEqual(canonical_team_name({"roster_id": 4}), "Unassigned Franchise")

    def test_mapping_uses_canonical_names(self) -> None:
        data = {"teams": [{"roster_id": 1, "team_name": "Alpha"}, {"roster_id": 2, "owner": "Bravo"}]}
        self.assertEqual(team_name_map(data), {1: "Alpha", 2: "Bravo"})
        self.assertEqual(team_name_for(data, 2), "Bravo")
        self.assertEqual(team_name_for(data, 99), "Unassigned Franchise")

    def test_rendered_generic_numbered_labels_are_rejected(self) -> None:
        with self.assertRaisesRegex(AssertionError, "generic team label"):
            validate_team_identity(b"<h1>Team 4</h1>", "/teams/4")
        with self.assertRaisesRegex(AssertionError, "generic team label"):
            validate_team_identity(b"<h1>Roster 10</h1>", "/teams/10")

    def test_canonical_rendered_names_pass(self) -> None:
        validate_team_identity(b"<h1>The Champions</h1>", "/teams/4")

    def test_inspection_discovery_names_team_headquarters_canonically(self) -> None:
        from fastapi import APIRouter
        from fastapi.responses import HTMLResponse

        router = APIRouter()

        @router.get("/teams/{roster_id}", response_class=HTMLResponse)
        async def team_detail_page(roster_id: int) -> HTMLResponse:
            return HTMLResponse(str(roster_id))

        pages = discover_pages(router.routes, {"data": {"teams": [{"roster_id": 4, "team_name": "The Champions"}]}})
        self.assertEqual(pages[0].page_name, "The Champions Headquarters")


if __name__ == "__main__":
    unittest.main()

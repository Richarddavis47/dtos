"""Presentation routes must preserve context and honest actionable identity."""
import unittest

from routes.market import _market_query
from routes.matchups import _franchise_identity
from src.ui.design_system import manager_navigation, page_header
from urllib.parse import parse_qs, urlsplit


class PremiumNavigationTests(unittest.TestCase):
    def test_my_team_uses_mapped_franchise_not_a_fixed_team(self):
        for roster_id in (1, 7, 500):
            self.assertIn(f'href="/teams/{roster_id}"', manager_navigation("Home", roster_id=roster_id))
        for roster_id in (None, 0, -1):
            self.assertIn('href="/teams"', manager_navigation("Home", roster_id=roster_id))

    def test_fois_full_title_selects_league_navigation(self):
        self.assertIn('href="/league" aria-current="page"', manager_navigation("Front Office Intelligence System"))
        self.assertIn('href="/league" aria-current="page"', manager_navigation("Manager — Executive Profile"))
        self.assertIn('href="/fois"', page_header("Manager — Executive Profile", league_name="A", last_updated="now"))

    def test_market_query_keeps_active_filters_and_franchise(self):
        query = _market_query(q="A Player", position="WR", availability="rostered", sort="value", direction="desc", front_office=7, offset=40, limit=20)
        values = parse_qs(urlsplit(query).query or query.lstrip("?"))
        for key, value in {"q": "A Player", "position": "WR", "availability": "rostered", "sort": "value", "direction": "desc", "front_office": "7", "offset": "40", "limit": "20"}.items():
            self.assertEqual(values[key], [value])

    def test_known_franchise_links_to_its_identity(self):
        self.assertEqual(_franchise_identity({"roster_id": 7, "team": "A & B"}), '<a href="/teams/7">A &amp; B</a>')

    def test_unknown_franchise_never_links_to_team_zero(self):
        for identity in (None, "", 0, -1, "unknown"):
            self.assertEqual(_franchise_identity({"roster_id": identity, "team": "Unknown"}), "Unknown")

    def test_page_guidance_is_available_without_duplicating_a_large_intro(self):
        header = page_header("Trade Intelligence", league_name="League A", last_updated="boundary-A")
        self.assertIn('<details class="ds-page-guide">', header)
        self.assertNotIn("<details open", header)
        self.assertIn("boundary-A", header)
        self.assertIn("League A", header)
        self.assertIn('class="ds-action primary"', header)


if __name__ == "__main__":
    unittest.main()

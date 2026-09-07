"""Focused mobile/desktop Matchups interaction proof; no capture artifacts."""
import unittest

from playwright.sync_api import sync_playwright

from tests import test_matchup_evidence_contract as evidence
from tools.validation.browser_fixture_images import image_bytes


class MatchupBrowserTests(unittest.TestCase):
    def test_player_identity_keyboard_touch_and_team_navigation(self):
        from dtos_app import CSS
        proof = evidence.MatchupEvidenceTests()
        args = evidence.fixture()
        body = proof.render(args[0], proof.summary(*args))
        html = f'<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style></head><body><main class="wrap"><h1>Matchup</h1>{body}</main></body></html>'
        image = image_bytes("matchup-navigation")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                for viewport in ({"width": 390, "height": 844}, {"width": 1280, "height": 900}):
                    with browser.new_context(viewport=viewport) as context:
                        def transport(route):
                            url = route.request.url
                            if url.startswith("https://sleepercdn.com/content/nfl/players/A"):
                                route.fulfill(status=200, content_type="image/png", body=image)
                            elif url == "https://dtos.test/matchups/1":
                                route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
                            elif url in {"https://dtos.test/players/A0", "https://dtos.test/teams/1", "https://dtos.test/matchups"}:
                                route.fulfill(status=200, content_type="text/html", body="<h1>Existing destination</h1>")
                            else:
                                route.abort()
                        context.route("**/*", transport)
                        page = context.new_page()
                        page.goto("https://dtos.test/matchups/1")
                        self.assertFalse(page.evaluate("document.documentElement.scrollWidth > innerWidth"))
                        player = page.get_by_role("link", name="Open A Player 0 player dossier", exact=True)
                        box = player.bounding_box()
                        self.assertGreaterEqual(box["height"], 44)
                        self.assertGreaterEqual(box["width"], 44)
                        player.focus()
                        self.assertTrue(player.evaluate("e => e === document.activeElement"))
                        player.press("Enter")
                        self.assertEqual(page.url, "https://dtos.test/players/A0")
                        page.goto("https://dtos.test/matchups/1")
                        page.get_by_role("link", name="Open A Player 0 player dossier", exact=True).click()
                        self.assertEqual(page.url, "https://dtos.test/players/A0")
                        page.goto("https://dtos.test/matchups/1")
                        page.get_by_role("link", name="A Team 0", exact=True).click()
                        self.assertEqual(page.url, "https://dtos.test/teams/1")
                        page.goto("https://dtos.test/matchups/1")
                        page.get_by_role("link", name="← All Matchups", exact=True).click()
                        self.assertEqual(page.url, "https://dtos.test/matchups")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()

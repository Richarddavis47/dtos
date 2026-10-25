"""Released producers and private HTTP in controlled Chromium, not device acceptance."""

from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from routes.transactions import create_transactions_router
from src.core.data_platform import data_platform
from src.core.data_platform.storage import SnapshotWarehouse
from tests import test_product_browser_journey as journey
from tests import test_roster_diagnostic_http as prepared
from tests import test_market_trend_current_integration as market_fixture
from tools.validation.browser_runtime import launch_chromium

VIEWPORTS = ((320, 432), (375, 667), (390, 844), (1280, 900))


def capture(page, name, width, height, *, persist=True, **facts):
    row = page.evaluate("""() => {
      const box=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y+scrollY,width:r.width,height:r.height};};
      const selectors={shell:'.ds-shell',heading:'.ds-page-header',insight:'#home-opportunity-cards article',search:'#market-search',searchHeading:'.market-filters h3',summary:'.ai-context',takeaway:'.ai-takeaway',concern:'.ai-summary-limit',shortcuts:'nav[aria-label="Roster sections"]'};
      return {overflow:document.documentElement.scrollWidth-innerWidth,scrollY,
        boxes:Object.fromEntries(Object.entries(selectors).filter(([k,s])=>document.querySelector(s)).map(([k,s])=>[k,box(document.querySelector(s))])),
        controls:[...document.querySelectorAll('nav[aria-label="Roster sections"] a,.ds-shell .top button,.ds-shell .secondary-nav>summary')].filter(e=>e.getClientRects().length).map(e=>({text:e.innerText,...box(e)}))};
    }""")
    row.update(
        name=name,
        width=width,
        height=height,
        browser=page.context.browser.version,
        collected_at=datetime.now(timezone.utc).isoformat(),
        source_head=os.environ.get("DTOS_EXPECTED_HEAD")
        or os.environ.get("GITHUB_SHA")
        or "local working tree; see run manifest",
        **facts,
    )
    output = os.environ.get("DTOS_PREMIUM_EVIDENCE")
    if output and persist:
        folder = Path(output)
        folder.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(folder / f"{name}-{width}.png"), full_page=False)
        (folder / f"{name}-{width}.json").write_text(json.dumps(row, indent=2))
    return row


def keyboard_disclosure(case, page, locator):
    page.keyboard.press("Tab")
    locator.focus()
    case.assertTrue(
        locator.evaluate("e=>e===document.activeElement && e.matches(':focus-visible')")
    )
    case.assertEqual(locator.evaluate("e=>getComputedStyle(e).outlineStyle"), "solid")
    case.assertGreaterEqual(
        locator.evaluate("e=>parseFloat(getComputedStyle(e).outlineWidth)"), 2
    )
    locator.press("Enter")
    case.assertTrue(locator.evaluate("e=>e.parentElement.open"))
    locator.press("Enter")
    case.assertFalse(locator.evaluate("e=>e.parentElement.open"))


class PremiumSharedJourneyTests(journey.ProductBrowserJourneyTests):
    viewports = tuple({"width": w, "height": h} for w, h in VIEWPORTS)

    def configure_data(self, data, league):
        if league == "200":
            data["league"]["name"] = (
                "A deliberately long league name with unmistakable source context and no abbreviation"
            )

    def audit_page(self, page, path, viewport):
        # The inherited journey checks every account/context, route, label and denial.
        page.evaluate("scrollTo(0,0)")
        width, height = viewport["width"], viewport["height"]
        key = (width, path)
        seen = getattr(self, "_captured_views", set())
        persist = key not in seen
        seen.add(key)
        self._captured_views = seen
        row = capture(
            page,
            "journey-" + ("home" if path == "/" else path.strip("/").replace("/", "-")),
            width,
            height,
            persist=persist,
        )
        self.assertEqual(row["overflow"], 0)
        for control in row["controls"]:
            self.assertGreaterEqual(control["height"], 44)
            self.assertGreaterEqual(control["x"], 0)
            self.assertLessEqual(control["x"] + control["width"], width + 0.5)
        if path == "/market":
            # All real search/filter state remains in the existing GET form.
            self.assertLess(
                row["boxes"]["searchHeading"]["y"], 400 if width < 760 else 560
            )
            keyboard_disclosure(self, page, page.locator(".ds-page-guide>summary"))
        if path in ("/", "/market", "/teams/1", "/fois"):
            keyboard_disclosure(
                self, page, page.locator(".ds-shell .secondary-nav>summary")
            )
        if path == "/teams/1":
            nav = page.locator('nav[aria-label="Roster sections"]')
            self.assertEqual(nav.evaluate("e=>e.scrollWidth>e.clientWidth"), False)
            for fragment in ("#full-roster", "#positional-depth", "#draft-capital"):
                link = nav.locator(
                    'a[href="' + fragment + '"]:not(#my-team-outlook-action)'
                )
                self.assertEqual(link.count(), 1)
                link.focus()
                self.assertTrue(
                    link.evaluate(
                        """e=>{const r=e.getBoundingClientRect(); const bottom=document.querySelector('.manager-nav').getBoundingClientRect().top;return r.top>=0 && (innerWidth>760 || r.bottom<=bottom+.5)}"""
                    )
                )


class PremiumPreparedBrowserTests(unittest.TestCase):
    def fixture(self):
        import dtos_app

        f = prepared.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.publish(datetime.now(timezone.utc).isoformat())
        data = f.f.f.data
        f.f.f.client.app.include_router(
            create_transactions_router(
                ensure_fresh=AsyncMock(),
                require_data=lambda: data,
                refresh_transactions=AsyncMock(),
                state={},
                page=dtos_app.page,
            )
        )
        self.enterContext(patch.object(data_platform, "warehouse", SnapshotWarehouse()))
        self.assertEqual(f.f.f.client.get("/teams/1").status_code, 200)
        f.f.seed()
        return f

    def test_prepared_brief_identity_cost_action_and_wrapped_shortcuts(self):
        f = self.fixture()
        baseline = {320: 523.265625, 375: 510.265625, 390: 510.265625}
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in VIEWPORTS:
                    page = f.f.browser_page(browser, width, height)
                    requests = []
                    page.on("request", lambda r: requests.append(r.url))
                    page.goto("https://dtos.test/")
                    page.locator(".home-opportunity").wait_for()
                    self.assertEqual(
                        page.locator("#home-opportunity-cards>article").count(), 2
                    )
                    row = capture(page, "prepared-home", width, height)
                    if width < 760:
                        self.assertGreaterEqual(
                            baseline[width] - row["boxes"]["insight"]["y"], 120
                        )
                    self.assertIn(
                        "Cost and uncertainty:",
                        page.locator(".home-opportunity").inner_text(),
                    )
                    self.assertIn(
                        "WORTH PURSUING", page.locator(".home-opportunity").inner_text()
                    )
                    self.assertIn(
                        "2028", page.locator(".home-opportunity").inner_text()
                    )
                    self.assertLess(
                        page.locator("#home-opportunities").bounding_box()["y"],
                        page.locator(".league-trade-news").bounding_box()["y"],
                    )
                    self.assertFalse(any("/api/trades/generate" in u for u in requests))
                    keyboard_disclosure(
                        self, page, page.locator("#home-brief-more>summary")
                    )
                    page.goto("https://dtos.test/teams/1")
                    nav = page.locator('nav[aria-label="Roster sections"]')
                    self.assertEqual(
                        nav.evaluate("e=>e.scrollWidth>e.clientWidth"), False
                    )
                    for fragment in (
                        "#full-roster",
                        "#positional-depth",
                        "#draft-capital",
                    ):
                        link = nav.locator(
                            f'a[href="{fragment}"]:not(#my-team-outlook-action)'
                        )
                        link.focus()
                        self.assertGreaterEqual(link.bounding_box()["height"], 44)
                        self.assertTrue(
                            link.evaluate(
                                """e=>{const r=e.getBoundingClientRect();const h=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return h===e||e.contains(h)}"""
                            )
                        )
                        link.press("Enter")
                        self.assertTrue(page.url.endswith(fragment))
                    page.evaluate("scrollTo(0,0)")
                    capture(page, "prepared-my-team", width, height)
                    page.goto("https://dtos.test/players/a?front_office=1&from_team=1")
                    self.assertIn("a", page.locator(".ai-player-identity").inner_text())
                    self.assertTrue(page.locator(".ai-takeaway").is_visible())
                    self.assertTrue(page.locator(".ai-summary-limit").is_visible())
                    row = capture(page, "prepared-dossier", width, height)
                    self.assertLess(
                        row["boxes"]["summary"]["y"], 300 if width < 760 else 450
                    )
                    keyboard_disclosure(
                        self,
                        page,
                        page.locator(
                            ".ai-evidence>summary",
                            has_text="Valuation, fit and source evidence",
                        ),
                    )
                    page.get_by_text("← Back to My Team roster", exact=True).click()
                    self.assertIn("/teams/1#full-roster", page.url)
                    page.close()
            finally:
                browser.close()

    def test_canonical_market_search_filters_and_neutral_price(self):
        import dtos_app

        f = market_fixture.CurrentMarketHTTPTests()
        f.page_renderer = dtos_app.page
        f.setUp()
        self.addCleanup(f.doCleanups)
        before = deepcopy(f.client.get("/api/market/assets/player:1").json())
        with patch.dict(dtos_app.STATE, {"data": f.data}), sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in VIEWPORTS:
                    page = browser.new_page(viewport={"width": width, "height": height})

                    def transport(route):
                        url = urlsplit(route.request.url)
                        if url.hostname != "fixture":
                            return route.abort()
                        response = f.client.get(
                            url.path + ("?" + url.query if url.query else "")
                        )
                        route.fulfill(
                            status=response.status_code,
                            content_type=response.headers.get(
                                "content-type", "text/html"
                            ),
                            body=response.content,
                        )

                    page.route("**/*", transport)
                    page.goto(
                        "http://fixture/market?position=QB&sort=market&front_office=1"
                    )
                    row = capture(page, "canonical-market", width, height)
                    self.assertEqual(row["overflow"], 0)
                    self.assertLess(
                        row["boxes"]["search"]["y"], 400 if width < 760 else 560
                    )
                    self.assertEqual(
                        page.locator("#market-position").input_value(), "QB"
                    )
                    self.assertEqual(
                        page.locator(".market-mode [aria-current=page]").inner_text(),
                        "Neutral DTOS",
                    )
                    self.assertIn(
                        "200", page.locator(".market-value").first.inner_text()
                    )
                    page.locator("#market-search").fill("Player")
                    page.get_by_role("button", name="Search market", exact=True).click()
                    self.assertIn("position=QB", page.url)
                    self.assertIn("front_office=1", page.url)
                    self.assertEqual(
                        page.locator("#market-search").input_value(), "Player"
                    )
                    keyboard_disclosure(
                        self, page, page.locator(".market-view-evidence>summary")
                    )
                    page.close()
            finally:
                browser.close()
        after = f.client.get("/api/market/assets/player:1").json()
        self.assertEqual(after["asset"]["values"], before["asset"]["values"])
        self.assertEqual(after["market_trend"], before["market_trend"])

    def test_pure_formatters_preserve_facts_and_start_no_heavy_work(self):
        from components.asset_intelligence import player_dossier
        from src.core.asset_intelligence import AssetContext, evaluate_player
        from src.ui.front_office_brief import cards
        from src.ui.my_team_outlook import outlook_panel
        from services.my_team_outlook import goal_options

        report = evaluate_player(
            {"id": "p", "full_name": "Quarterback", "position": "QB", "team": "BUF"},
            AssetContext("league", 1, {}),
        )
        original = deepcopy(report)
        owner = {"roster_id": 1, "owner": "Manager", "team_name": "Franchise"}
        outlook = {
            "position": "Unavailable",
            "strength": "Unavailable",
            "concern": "Depth evidence is missing, not zero.",
            "future": "Exact picks",
            "brief": "Missing evidence",
            "href": "#full-roster",
            "action": "View roster",
            "guidance": "Choose a goal",
            "details": [],
        }
        boundaries = (
            "services.sleeper.sleeper_get",
            "services.trade_intelligence.generate_trade_workflow",
            "src.core.fois.service.FOISService._generate_sync",
            "src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct",
            "src.core.trade_intelligence.lineup.optimal_legal_lineup",
            "sqlite3.connect",
        )
        with ExitStack() as stack:
            guards = {
                name: stack.enter_context(patch(name, side_effect=AssertionError(name)))
                for name in boundaries
            }
            for _ in range(10):
                self.assertIn(
                    "Player decision summary", player_dossier(report, owner, [owner])
                )
                self.assertEqual(cards([]), "")
                self.assertIn(
                    "Roster sections",
                    outlook_panel(outlook, editable=True, roster_id=1),
                )
                self.assertTrue(goal_options(1))
            self.assertTrue(all(g.call_count == 0 for g in guards.values()))
        self.assertEqual(report, original)

"""Normal product navigation, plain default copy and phone focus safety.

Input is the existing disposable source fixture. Account middleware, league
switching, HTML routers and dark/green page theme execute normally. No owner
session, provider acquisition, search, owner-preference write or physical Safari claim.
"""

import json
import os
from pathlib import Path

from starlette.staticfiles import StaticFiles

from routes.navigation import create_navigation_router
from tests import test_product_browser_journey as journeys


class CustomerExperienceJourneyTests(journeys.ProductBrowserJourneyTests):
    viewports = (
        {"width": 320, "height": 432},
        {"width": 375, "height": 667},
        {"width": 390, "height": 844},
        {"width": 1280, "height": 900},
    )

    def configure_app(self, app, common):
        app.include_router(create_navigation_router())
        app.mount(
            "/static",
            StaticFiles(directory=Path(__file__).resolve().parents[1] / "static"),
        )

    def audit_page(self, page, path, viewport):
        visible = page.locator("body").inner_text()
        for wording in (
            "Find Bilateral Options",
            "Advanced DTOS analysis",
            "disjoint reserve cover",
            "Canonical Market",
            "classified as Unavailable",
            "MARKET UNAVAILABLE · Unavailable · Unavailable",
        ):
            self.assertNotIn(wording, visible, (path, wording))
        if path in ("/trades/trade-for", "/trades/shop"):
            self.assertEqual(page.locator("#trade-find").inner_text(), "Find offers")
        self.assertGreaterEqual(
            page.locator("body").evaluate(
                "e => parseFloat(getComputedStyle(e).fontSize)"
            ),
            14,
            "Default copy must not be made compact by shrinking baseline text",
        )
        self.assertGreater(page.get_by_role("heading", level=1).count(), 0)
        self.assertEqual(
            page.get_by_role("navigation", name="Primary navigation")
            .get_by_role("link")
            .all_text_contents(),
            ["Home", "My Team", "Trade", "League", "Market"],
        )
        if path.startswith('/trades/'):
            for header in page.locator('.tw-owner-header').all():
                if not header.is_visible():
                    continue
                title, action = header.locator('h3'), header.locator('a')
                if not action.count():
                    continue
                original = title.inner_text()
                title.evaluate("e => e.textContent = 'A very long franchise name with an equally long owner label'")
                a, b = title.bounding_box(), action.bounding_box()
                self.assertIsNotNone(a)
                self.assertIsNotNone(b)
                self.assertTrue(a['x'] + a['width'] <= b['x'] or
                                a['y'] + a['height'] <= b['y'] or
                                b['y'] + b['height'] <= a['y'])
                self.assertGreaterEqual(action.bounding_box()['height'], 44)
                title.evaluate('(e, text) => e.textContent = text', original)
        resources = page.evaluate(
            "performance.getEntriesByType('resource').map(e=>new URL(e.name).pathname)"
        )
        for resource in resources:
            self.assertNotIn(
                resource,
                (
                    "/api/trades/generate",
                    "/api/trades/evaluate",
                    "/api/trades/repair",
                    "/sync",
                ),
                "Ordinary page navigation must not start expensive trade/source work",
            )
        if path == "/teams/1":
            identities = page.locator(".thq-player .player-summary").evaluate_all("""rows => rows.map(row => {
                const portrait = row.querySelector('.player-portrait').getBoundingClientRect();
                const fallback = row.querySelector('.player-headshot-fallback').getBoundingClientRect();
                const name = row.querySelector('.player-summary-copy b').getBoundingClientRect();
                return {portraitWidth: portrait.width, portraitHeight: portrait.height,
                    fallbackWidth: fallback.width, fallbackHeight: fallback.height,
                    fallbackRight: fallback.right, nameLeft: name.left};
            })""")
            self.assertGreater(len(identities), 0, "Check actual roster identities, not an empty selector")
            for identity in identities:
                self.assertLessEqual(identity["fallbackWidth"], identity["portraitWidth"] + 0.5)
                self.assertLessEqual(identity["fallbackHeight"], identity["portraitHeight"] + 0.5)
                self.assertLessEqual(identity["fallbackRight"], identity["nameLeft"],
                    "Fallback portrait must not cover the player's name")
        summaries = page.locator("main details > summary:visible")
        if summaries.count():
            summary = summaries.last
            # Native focus/Enter scroll is exercised, not only a DOM presence
            # assertion. A fixed bottom nav must leave the focused action clear.
            initial = summary.locator("..").evaluate("e => e.open")
            summary.focus()
            summary.press("Enter")
            self.assertEqual(summary.locator("..").evaluate("e => e.open"), not initial)
            summary.press("Enter")
            self.assertEqual(summary.locator("..").evaluate("e => e.open"), initial)
            box = summary.bounding_box()
            nav = page.get_by_role("navigation", name="Primary navigation")
            position = nav.evaluate("e => getComputedStyle(e).position")
            nav_box = nav.bounding_box()
            if position == "fixed" and nav_box and box:
                self.assertLessEqual(
                    box["y"] + box["height"],
                    nav_box["y"] + 1,
                    (path, "Focused disclosure is covered by primary navigation"),
                )
            self.assertNotEqual(
                summary.evaluate("e => getComputedStyle(e).outlineStyle"), "none"
            )
            if viewport["width"] == 390:
                touch = page.context.new_cdp_session(page)
                touch.send("Emulation.setTouchEmulationEnabled", {"enabled": True})
                box = summary.bounding_box()
                self.assertIsNotNone(box)
                touch.send(
                    "Input.dispatchTouchEvent",
                    {
                        "type": "touchStart",
                        "touchPoints": [
                            {
                                "x": box["x"] + box["width"] / 2,
                                "y": box["y"] + box["height"] / 2,
                            }
                        ],
                    },
                )
                touch.send(
                    "Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}
                )
                self.assertEqual(
                    summary.locator("..").evaluate("e => e.open"), not initial
                )
                summary.press("Enter")
                self.assertEqual(summary.locator("..").evaluate("e => e.open"), initial)
                touch.send("Emulation.setTouchEmulationEnabled", {"enabled": False})
                touch.detach()
        self.assertLessEqual(
            page.evaluate("document.documentElement.scrollWidth"), viewport["width"]
        )
        folder = os.environ.get("DTOS_CUSTOMER_EXPERIENCE_EVIDENCE")
        # Keep one source-labelled visual per route/viewport rather than adding
        # duplicate captures for each account and round-trip league activation.
        if folder and "Franchise 100" in visible:
            root = Path(folder)
            root.mkdir(parents=True, exist_ok=True)
            name = "home" if path == "/" else path.strip("/").replace("/", "-")
            target = root / f"{name}-{viewport['width']}.json"
            if not target.exists():
                page.evaluate("scrollTo(0, 0)")
                page.screenshot(
                    path=str(root / f"{name}-{viewport['width']}.png"), full_page=True
                )
                target.write_text(
                    json.dumps(
                        dict(
                            path=path,
                            viewport=viewport,
                            scope="Actual authenticated routers; existing disposable sparse source fixture",
                            physical_safari=False,
                            body_font=page.locator("body").evaluate(
                                "e=>getComputedStyle(e).fontSize"
                            ),
                            ordinary_navigation_resources=resources,
                            default_text=visible,
                            no_overflow=True,
                            keyboard_and_touch_emulation=True,
                        ),
                        indent=2,
                    )
                    + "\n"
                )

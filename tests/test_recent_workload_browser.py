"""Real dossier HTML and Chromium; disposable evidence, never live owner proof."""

from dataclasses import replace
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from routes.transactions import create_transactions_router
from tests import test_recent_workload as fixtures
from tools.validation.browser_runtime import launch_chromium


class RecentWorkloadBrowserTests(unittest.TestCase):
    def test_dossier_complete_partial_missing_phone_keyboard_and_touch(self):
        import dtos_app

        f = fixtures.RecentWorkloadRenderedTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        data = f.fixture.data
        data["players"]["player one"]["full_name"] = (
            "Alexanderson Montgomery Long Player Name"
        )
        app = FastAPI()
        app.include_router(
            create_transactions_router(
                ensure_fresh=AsyncMock(),
                refresh_transactions=AsyncMock(),
                require_data=lambda: data,
                state=f.fixture.state,
                page=dtos_app.page,
            )
        )
        measurements = []
        folder = os.environ.get("DTOS_WORKLOAD_EVIDENCE")
        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)
        with (
            TestClient(app) as client,
            patch.dict(dtos_app.STATE, {"data": data}),
            sync_playwright() as pw,
        ):
            browser = launch_chromium(pw, headless=True)
            try:
                for state in ("complete", "partial", "missing"):
                    if state == "partial":
                        f.store.publish(
                            [
                                replace(
                                    f.rows[-1],
                                    values={**f.rows[-1].values, "rec_tgt": None},
                                )
                            ],
                            retrieved_at="2026-10-22T00:00:00Z",
                        )
                    if state == "missing":
                        data["nfl_state"]["season_type"] = "post"
                    for width, height in (
                        (320, 432),
                        (375, 667),
                        (390, 844),
                        (1280, 900),
                    ):
                        page = browser.new_page(
                            viewport={"width": width, "height": height},
                            has_touch=width < 1000,
                        )
                        requests = []

                        def transport(route):
                            u = urlsplit(route.request.url)
                            requests.append(u.path)
                            if u.netloc != "fixture":
                                route.fulfill(status=404)
                                return
                            if u.path.startswith("/static/"):
                                p = Path(u.path.lstrip("/"))
                                if p.is_file():
                                    route.fulfill(path=str(p))
                                    return
                            r = client.get(u.path + "?" + u.query)
                            route.fulfill(
                                status=r.status_code,
                                body=r.content,
                                content_type=r.headers.get("content-type", "text/html"),
                            )

                        page.route("**/*", transport)
                        r = page.goto(
                            "http://fixture/players/player%20one?front_office=1&from_team=1"
                        )
                        self.assertEqual(r.status, 200)
                        panel = page.locator(".recent-workload")
                        panel.scroll_into_view_if_needed()
                        visible = panel.inner_text()
                        self.assertNotIn("Comparison generation:", visible)
                        if state == "complete":
                            self.assertIn(
                                "Targets increased from 2 to 5 per observed game.",
                                visible,
                            )
                        if state == "partial":
                            self.assertIn("Targets comparison unavailable.", visible)
                            self.assertIn("Carries decreased from 12 to 6", visible)
                        if state == "missing":
                            self.assertIn(
                                "completed NFL week is not confirmed", visible
                            )
                        self.assertLessEqual(
                            page.evaluate("document.documentElement.scrollWidth"), width
                        )
                        if folder:
                            page.screenshot(
                                path=str(Path(folder) / f"{state}-{width}-default.png")
                            )
                        summary = panel.locator("summary")
                        summary.focus()
                        self.assertNotEqual(
                            summary.evaluate("e=>getComputedStyle(e).outlineStyle"),
                            "none",
                        )
                        summary.press("Enter")
                        self.assertTrue(panel.locator("details").evaluate("e=>e.open"))
                        self.assertIn(
                            "separate from Sleeper fantasy scores", panel.inner_text()
                        )
                        if folder:
                            page.screenshot(
                                path=str(Path(folder) / f"{state}-{width}-expanded.png")
                            )
                        if width < 1000:
                            summary.tap()
                        else:
                            summary.press("Enter")
                        self.assertFalse(panel.locator("details").evaluate("e=>e.open"))
                        self.assertLessEqual(
                            page.evaluate("document.documentElement.scrollWidth"), width
                        )
                        self.assertFalse(
                            any("generate" in p or "sync" in p for p in requests)
                        )
                        back = page.get_by_role("link", name="← Back to My Team roster")
                        self.assertIn("/teams/1", back.get_attribute("href"))
                        measurements.append(
                            dict(
                                state=state,
                                width=width,
                                height=height,
                                text=visible,
                                panel_height=panel.bounding_box()["height"],
                                document_width=page.evaluate(
                                    "document.documentElement.scrollWidth"
                                ),
                                keyboard=True,
                                touch=width < 1000,
                                requests=requests,
                                source_calls=0,
                            )
                        )
                        page.close()
            finally:
                browser.close()
        if folder:
            (Path(folder) / "measurements.json").write_text(
                json.dumps(measurements, indent=2) + "\n"
            )

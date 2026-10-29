"""Display-only ordering over prepared neutral workspace DTOs."""

import os
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_trade_workspace_batch1 as boundary


class TradePickerOrderTests(unittest.TestCase):
    def test_actual_js_comparator_zero_missing_ties_other_positions_and_picks(self):
        source = Path("static/js/trade_workspace.js").read_text()
        helper = source[
            source.index("  function pickerGroup(") : source.index(
                "  function assetRow("
            )
        ]
        rows = [
            dict(asset_id=key, kind="player", position=pos, trade_value=value)
            for key, pos, value in [
                ("wr", "WR", 999),
                ("qb-missing", "QB", None),
                ("qb-zero", "QB", 0),
                ("qb-b", "QB", 10),
                ("qb-a", "QB", 10),
                ("rb", "RB", 1),
                ("te", "TE", 2),
                ("k", "K", 5),
                ("dst", "DEF", 9),
            ]
        ]
        rows.extend(
            [
                dict(
                    asset_id="pick:2028:1:2",
                    kind="pick",
                    season=2028,
                    round=1,
                    original_roster_id=2,
                    trade_value=None,
                ),
                dict(
                    asset_id="pick:2027:1:1",
                    kind="pick",
                    season=2027,
                    round=1,
                    original_roster_id=1,
                    trade_value=20,
                ),
            ]
        )
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = browser.new_page()
                result = page.evaluate(
                    "(rows)=>{"
                    + helper
                    + "; const before=JSON.stringify(rows); return {ids:pickerAssets(rows).map(a=>a.asset_id),unchanged:JSON.stringify(rows)===before};}",
                    rows,
                )
            finally:
                browser.close()
        self.assertEqual(
            result["ids"],
            [
                "qb-a",
                "qb-b",
                "qb-zero",
                "qb-missing",
                "rb",
                "wr",
                "te",
                "dst",
                "k",
                "pick:2027:1:1",
                "pick:2028:1:2",
            ],
        )
        self.assertTrue(result["unchanged"])

    def test_http_workspace_to_browser_boards_and_selected_order(self):
        f = boundary.AuthenticatedTradeBoundaryTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        # Actual producer supplies prices; display permutations must not alter it.
        expected = f.client.get("/api/trades/workspace?front_office=1").json()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
                    page = browser.new_page(
                        viewport={"width": width, "height": height},
                        has_touch=width < 760,
                    )
                    requests = []

                    def transport(route):
                        req = route.request
                        u = urlsplit(req.url)
                        if u.netloc != "dtos.test":
                            route.abort()
                            return
                        requests.append((req.method, u.path))
                        response = f.client.request(
                            req.method,
                            u.path + ("?" + u.query if u.query else ""),
                            content=req.post_data,
                            headers={
                                k: v
                                for k, v in req.headers.items()
                                if k in ["content-type", "x-csrf-token"]
                            },
                        )
                        route.fulfill(
                            status=response.status_code,
                            body=response.content,
                            headers=dict(response.headers),
                        )

                    page.route("**/*", transport)
                    page.goto("https://dtos.test/trades/create")
                    board = page.locator("#trade-sent-board")
                    board.locator(".tw-asset").first.wait_for()
                    ids = board.locator("button[data-asset-id]").evaluate_all(
                        "(nodes)=>nodes.map(n=>n.dataset.assetId)"
                    )
                    assets = next(
                        t["assets"] for t in expected["teams"] if t["roster_id"] == 1
                    )

                    def key(a):
                        if a["kind"] == "pick":
                            return (
                                1,
                                int(a["season"]),
                                int(a["round"]),
                                str(a["original_roster_id"]),
                                a["asset_id"],
                            )
                        order = {"QB": 0, "RB": 1, "WR": 2, "TE": 3}
                        v = a["trade_value"]
                        return (
                            0,
                            order.get(a["position"], 4),
                            a["position"] or "Other positions",
                            v is None,
                            -v if v is not None else 0,
                            a["asset_id"],
                        )

                    self.assertEqual(
                        ids, [a["asset_id"] for a in sorted(assets, key=key)]
                    )
                    self.assertEqual(
                        board.locator("[data-picker-group]").all_text_contents(),
                        ["QB", "RB", "WR", "TE", "Draft picks"],
                    )
                    chosen = [ids[1], ids[0]]
                    for asset_id in chosen:
                        button = board.locator(
                            'button[data-asset-id="' + asset_id + '"]'
                        )
                        button.focus()
                        page.keyboard.press("Enter")
                    self.assertEqual(
                        page.locator(
                            "#trade-sent-chips .tw-selected button[data-asset-id]"
                        ).evaluate_all("(ns)=>ns.map(n=>n.dataset.assetId)"),
                        chosen,
                    )
                    board.get_by_role(
                        "button", name="PICKS", exact=True
                    ).tap() if width < 760 else board.get_by_role(
                        "button", name="PICKS", exact=True
                    ).click()
                    self.assertTrue(
                        board.get_by_text("Draft picks", exact=True).is_visible()
                    )
                    for a in [a for a in assets if a["kind"] == "pick"]:
                        self.assertIn(str(a["season"]), board.inner_text())
                        self.assertIn("Round " + str(a["round"]), board.inner_text())
                    self.assertFalse(
                        page.evaluate("document.documentElement.scrollWidth>innerWidth")
                    )
                    self.assertFalse(
                        any(
                            path.endswith(("/generate", "/evaluate", "/assist"))
                            for _, path in requests
                        )
                    )
                    out = os.getenv("DTOS_PICKER_EVIDENCE")
                    if out:
                        p = Path(out)
                        p.mkdir(exist_ok=True, parents=True)
                        page.screenshot(path=str(p / f"picker-{width}.png"))
                    if width == 390:
                        for workflow in [
                            "calculator",
                            "trade-for",
                            "shop",
                            "recommended",
                        ]:
                            # Each workflow starts from a fresh disposable draft;
                            # package retention is asserted separately above.
                            page.evaluate("sessionStorage.clear()")
                            page.goto("https://dtos.test/trades/" + workflow)
                            if workflow == "recommended":
                                page.locator("#trade-asset-options > summary").click()
                            board.locator(".tw-asset").first.wait_for(state="attached")
                            your_assets = page.get_by_role(
                                "button", name="My assets", exact=True
                            )
                            if your_assets.is_visible():
                                your_assets.click()
                            board.locator(".tw-asset").first.wait_for()
                            board.get_by_role("button", name="ALL", exact=True).click()
                            self.assertEqual(
                                board.locator("button[data-asset-id]").evaluate_all(
                                    "(ns)=>ns.map(n=>n.dataset.assetId)"
                                ),
                                ids,
                            )
                            options = page.locator(
                                "#trade-constraint-asset option"
                            ).evaluate_all("(ns)=>ns.map(n=>n.value).filter(Boolean)")
                            self.assertEqual(options, ids)
                            if workflow == "shop":
                                self.assertEqual(
                                    page.locator("#shop-protected option").evaluate_all(
                                        "(ns)=>ns.map(n=>n.value)"
                                    ),
                                    ids,
                                )
                    page.close()
            finally:
                browser.close()
        self.assertEqual(
            f.client.get("/api/trades/workspace?front_office=1").json(), expected
        )

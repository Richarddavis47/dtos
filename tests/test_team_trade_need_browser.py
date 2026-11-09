"""Authenticated prepared-source handoff controls; no physical Safari claim."""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_contextual_back as back
from src.core.intelligence.roster_diagnostics import diagnose_league
from src.core.intelligence.team_strength import prepare_for_data


class TeamTradeNeedBrowserTests(unittest.TestCase):
    def fixture(self, *, superflex=False, depth=False):
        helper = back.ContextualBackTests()
        self.addCleanup(helper.doCleanups)
        f = helper.fixture()
        data = f.editor.data
        slots = (
            ["QB", "RB", "WR", "FLEX", "BN"]
            if superflex
            else ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "K", "DEF", "BN"]
        )
        if superflex:
            slots.insert(1, "SUPER_FLEX")
        data["roster_positions"] = slots
        data["league"].update(
            roster_positions=slots,
            scoring_settings={
                "pass_yd": 1,
                "rush_yd": 1,
                "rec_yd": 1,
                "fgm": 1,
                "sack": 1,
            },
        )
        data["scoring_settings"] = data["league"]["scoring_settings"]
        stats = {
            "QB": "pass_yd",
            "RB": "rush_yd",
            "WR": "rec_yd",
            "TE": "rec_yd",
            "K": "fgm",
            "DEF": "sack",
        }
        self.rows = []
        for team in data["teams"]:
            rid = team["roster_id"]
            for player in team["players"]:
                player.update(status="Active", fantasy_positions=["QB"])
                data["players"][player["id"]].update(
                    status="Active", fantasy_positions=["QB"]
                )
                self.rows.append(
                    {
                        "player_id": player["id"],
                        "player": {"position": "QB"},
                        "stats": {"pass_yd": 30},
                    }
                )
            for pos in ("RB", "WR", "TE", "K", "DEF"):
                for n in range(4):
                    pid = f"{rid}-{pos}-{n}"
                    player = {
                        "id": pid,
                        "name": pid,
                        "position": pos,
                        "fantasy_positions": [pos],
                        "status": "Active",
                        "roster_slot": "Bench",
                    }
                    team["players"].append(player)
                    data["players"][pid] = {**player, "full_name": pid, "age": 25}
                    points = 20 if rid == 1 else 10
                    if pos == "RB":
                        points = (2 if not depth or n > 0 else 20) if rid == 1 else 12
                    self.rows.append(
                        {
                            "player_id": pid,
                            "player": {"position": pos},
                            "stats": {stats[pos]: points},
                        }
                    )
        self.enterContext(
            patch(
                "src.core.projection_intelligence.projection_service", f.capital.reader
            )
        )
        self.publish(f)
        return helper, f

    def publish(self, f, *, age=0):
        stamp = (datetime.now(timezone.utc) - timedelta(hours=age)).isoformat()
        rows = [
            {**row, "season": 2026, "week": 2, "updated_at": stamp} for row in self.rows
        ]
        f.capital.reader.publish_horizon(
            {2: rows},
            data=f.editor.data,
            league_id="league-1",
            season=2026,
            current_week=2,
        )
        with patch(
            "services.global_evidence.retained_global_evidence", return_value=None
        ):
            prepare_for_data(f.capital.reader, f.editor.data)
        diagnose_league(f.editor.data, f.capital.reader.snapshot())

    def record(self, name, observations):
        folder = os.environ.get("DTOS_TEAM_NEED_EVIDENCE")
        if folder:
            dest = Path(folder)
            dest.mkdir(parents=True, exist_ok=True)
            (dest / (name + ".json")).write_text(
                json.dumps(
                    {
                        "commit": subprocess.check_output(
                            ["git", "rev-parse", "HEAD"], text=True
                        ).strip(),
                        "tree": subprocess.check_output(
                            ["git", "rev-parse", "HEAD^{tree}"], text=True
                        ).strip(),
                        "source": "disposable authenticated prepared Sleeper fixture",
                        "physical_safari_tested": False,
                        "observations": observations,
                    },
                    indent=2,
                )
                + "\n"
            )

    def test_phone_handoff_edit_clear_reload_and_back_preserves_evaluate(self):
        helper, f = self.fixture()
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        rows = []
        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
            page, requests, _, _, errors = helper.page(browser, f, width, height)
            self.addCleanup(page.close)
            helper.ready(page)
            helper.choose(page)
            page.locator("#trade-valuation-mode").select_option("custom")
            before = helper.draft(page)
            page.goto(helper.origin + "/teams/1", wait_until="networkidle")
            action = page.locator("#my-team-trade-need")
            self.assertEqual(action.inner_text(), "Explore RB trades")
            self.assertIn(
                "starting lineup", page.locator("#my-team-outlook").inner_text()
            )
            posts = [r for r in requests if r[0] == "POST"]
            href = action.get_attribute("href")
            action.focus()
            action.press("Enter")
            page.wait_for_function(
                "document.querySelector('#trade-context') && !document.querySelector('#trade-context').textContent.includes('Loading')"
            )
            self.assertEqual(
                page.locator("#recommendation-position").input_value(), "RB"
            )
            self.assertIn(
                "From My Team",
                page.locator("#recommendation-position-origin").inner_text(),
            )
            self.assertEqual(
                helper.draft(page)["currentProposal"], before["currentProposal"]
            )
            self.assertEqual(helper.draft(page)["valuationMode"], "custom")
            self.assertEqual(helper.draft(page)["strategy"], before["strategy"])
            for pos in ("WR", ""):
                if pos:
                    page.locator("#recommendation-position").select_option(pos)
                else:
                    page.locator("#recommendation-position-clear").click()
                page.reload(wait_until="networkidle")
                page.wait_for_function(
                    "document.querySelector('#trade-context') && !document.querySelector('#trade-context').textContent.includes('Loading')"
                )
                self.assertEqual(
                    page.locator("#recommendation-position").input_value(), pos
                )
                self.assertNotIn(
                    "From My Team",
                    page.locator("#recommendation-position-origin").inner_text(),
                )
                self.assertEqual(
                    helper.draft(page)["currentProposal"], before["currentProposal"]
                )
            self.assertEqual(posts, [r for r in requests if r[0] == "POST"])
            self.assertLessEqual(
                page.evaluate("document.documentElement.scrollWidth-innerWidth"), 0
            )
            helper.back(page, "/teams/1")
            self.assertEqual(
                page.locator("#my-team-trade-need").get_attribute("href"), href
            )
            self.assertFalse(errors, errors)
            rows.append(
                {
                    "width": width,
                    "height": height,
                    "handoff": "RB starter",
                    "draft_and_custom_preserved": True,
                    "changed_and_cleared_after_reload": True,
                    "no_automatic_search": True,
                    "back": "My Team",
                    "overflow": 0,
                }
            )
            folder = os.environ.get("DTOS_TEAM_NEED_EVIDENCE")
            if folder:
                page.screenshot(
                    path=str(Path(folder) / f"my-team-{width}.png"), full_page=True
                ) if Path(folder).exists() else None
            page.close()
        self.record("phone-round-trips", rows)

    def test_superflex_depth_stale_and_unprepared_controls(self):
        helper, f = self.fixture(superflex=True, depth=True)
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        self.addCleanup(page.close)
        page.goto(helper.origin + "/teams/1", wait_until="networkidle")
        action = page.locator("#my-team-trade-need")
        self.assertEqual(action.inner_text(), "Explore RB trades")
        self.assertIn(
            "depth need, not a starter-upgrade",
            page.locator("#my-team-outlook").inner_text(),
        )
        href = action.get_attribute("href")
        self.publish(f, age=8)
        page.goto(helper.origin + href, wait_until="networkidle")
        page.wait_for_function(
            "document.querySelector('#trade-context') && !document.querySelector('#trade-context').textContent.includes('Loading')"
        )
        self.assertEqual(page.locator("#recommendation-position").input_value(), "")
        self.assertIn(
            "No roster-need filter was applied",
            page.locator("#recommendation-position-origin").inner_text(),
        )
        page.goto(helper.origin + "/teams/1", wait_until="networkidle")
        self.assertEqual(page.locator("#my-team-trade-need").count(), 0)
        page.locator("#my-team-outlook-evidence").evaluate("e=>e.open=true")
        self.assertEqual(
            page.get_by_role("link", name="Trade opportunities", exact=True).count(), 1
        )
        self.assertFalse([r for r in requests if r[0] == "POST"])
        self.assertFalse(errors, errors)
        self.record(
            "superflex-depth-and-stale",
            {
                "depth_distinct": True,
                "stale_hint_rejected": True,
                "general_shortcut": True,
                "no_automatic_search": True,
            },
        )

    def test_existing_real_results_stay_separate_and_search_is_explicit(self):
        helper = back.ContextualBackTests()
        self.addCleanup(helper.doCleanups)
        f = helper.fixture()
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        self.addCleanup(page.close)
        helper.ready(page, "/trades/recommended?front_office=1")
        page.locator("#trade-strategy").select_option("REBUILD")
        page.locator("#trade-find").click()
        page.wait_for_function(
            "document.querySelector('#trade-result').innerText.includes('Search position: all positions')"
        )
        prior = helper.draft(page)["recommendedSearch"]
        self.assertGreater(len(prior["offers"]), 0)
        posts = len([r for r in requests if r[0] == "POST"])
        page.locator("#recommendation-position").select_option("QB")
        self.assertTrue(page.locator("#trade-result").is_hidden())
        self.assertTrue(page.locator("#recommendation-previous").is_visible())
        page.locator("#recommendation-previous").evaluate("e=>e.open=true")
        self.assertIn(
            "Earlier offers have not been searched with the current filter",
            page.locator("#recommendation-previous").inner_text(),
        )
        page.reload(wait_until="networkidle")
        page.wait_for_function(
            "document.querySelector('#trade-context') && !document.querySelector('#trade-context').textContent.includes('Loading')"
        )
        self.assertEqual(helper.draft(page)["recommendedSearch"], prior)
        self.assertEqual(len([r for r in requests if r[0] == "POST"]), posts)
        self.assertEqual(page.locator("#recommendation-position").input_value(), "QB")
        page.locator("#trade-find").click()
        page.wait_for_function(
            "document.querySelector('#trade-result').innerText.includes('Search position: QB')"
        )
        self.assertEqual(helper.draft(page)["recommendedSearch"]["position"], "QB")
        self.assertFalse(errors, errors)
        self.record(
            "real-search-and-prior-context",
            {
                "real_evaluations": True,
                "prior_contexts": len(prior["offers"]),
                "position_applied_only_on_generate": True,
                "old_results_separate": True,
            },
        )

    def test_league_switch_discards_need_and_old_draft(self):
        helper, f = self.fixture()
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        self.addCleanup(page.close)
        helper.ready(page)
        helper.choose(page)
        before = helper.draft(page)
        page.goto(helper.origin + "/teams/1", wait_until="networkidle")
        href = page.locator("#my-team-trade-need").get_attribute("href")
        f.editor.store.upsert_membership(
            "account-a",
            {"league_id": "league-2", "name": "Other"},
            "account-a",
            1,
            "Other",
            "active",
        )
        f.editor.store.activate("account-a", "league-2")
        f.editor.data["league"]["league_id"] = "league-2"
        page.goto(helper.origin + href, wait_until="networkidle")
        page.wait_for_function(
            "document.querySelector('#trade-context') && !document.querySelector('#trade-context').textContent.includes('Loading')"
        )
        self.assertEqual(page.locator("#recommendation-position").input_value(), "")
        self.assertIn(
            "No roster-need filter was applied",
            page.locator("#recommendation-position-origin").inner_text(),
        )
        self.assertNotEqual(
            helper.draft(page)["currentProposal"], before["currentProposal"]
        )
        self.assertFalse([r for r in requests if r[0] == "POST"])
        self.assertFalse(errors, errors)
        self.record(
            "league-switch",
            {
                "hint_discarded": True,
                "old_draft_not_loaded": True,
                "no_automatic_search": True,
            },
        )

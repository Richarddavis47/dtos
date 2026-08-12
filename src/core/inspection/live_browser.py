"""Shared Playwright primitive for bounded Live Visual captures."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from src.core.inspection.live_visual import CaptureRequest, LIVE_VIEWPORTS
from tools.inspection.capture import DOM_SCRIPT


def capture_page(base_url: str, request: CaptureRequest, output: Path) -> dict[str, Any]:
    """Render the real public route once and return compact presentation metadata."""
    viewport = LIVE_VIEWPORTS[request.viewport]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport=viewport, color_scheme="dark", reduced_motion="reduce")
            page.set_extra_http_headers({"X-DTOS-Inspection": "deterministic"})
            response = page.goto(base_url.rstrip("/") + request.human_url, wait_until="networkidle", timeout=90000)
            if response is None or not response.ok:
                raise RuntimeError("Live visual route did not return HTTP 200")
            page.add_style_tag(content="*,*::before,*::after{animation:none!important;transition:none!important}")
            dom = page.evaluate(DOM_SCRIPT)
            page.screenshot(path=str(output), full_page=True)
            visible = str(dom.get("visible_text") or "")
            semantic_response = page.request.get(
                base_url.rstrip("/") + request.semantic_url,
                headers={"X-DTOS-Inspection": "deterministic"}, timeout=60000,
            )
            if not semantic_response.ok:
                raise RuntimeError("Live visual semantic route did not return HTTP 200")
            semantic = semantic_response.json()
            mismatches = []
            expected_starters = 0
            starter_cards = page.locator(".battle-side:not(.vacant)").all_inner_texts()
            for team in semantic.get("teams") or []:
                if str(team.get("team_name")) not in visible:
                    mismatches.append("team_name_missing")
                expected_starters += len(team.get("starters") or [])
                for starter in team.get("starters") or []:
                    displayed = starter.get("canonical") or {}
                    sleeper = displayed.get("sleeper_projection")
                    dtos = displayed.get("dtos_projection")
                    matching_cards = [text for text in starter_cards
                                      if str(starter.get("player_name")) in text]
                    if not matching_cards:
                        mismatches.append("starter_card_missing")
                        continue
                    card_text = " ".join(matching_cards)
                    if sleeper is not None and ("Sleeper Projection" not in card_text or
                                                f"{float(sleeper):.2f}" not in card_text):
                        mismatches.append("sleeper_projection_mismatch")
                    if dtos is not None and ("DTOS Projection" not in card_text or
                                             f"{float(dtos):.2f}" not in card_text):
                        mismatches.append("dtos_projection_mismatch")
                    if sleeper is None and dtos is None and "Projection unavailable" not in card_text:
                        mismatches.append("missing_projection_state_missing")
                totals = team.get("canonical_totals") or {}
                for source in ("sleeper_projection", "dtos_projection"):
                    if f"{float(totals.get(source) or 0):.1f}" not in visible:
                        mismatches.append(f"{source}_total_mismatch")
            if mismatches:
                raise RuntimeError("Rendered matchup does not match canonical presentation")
            nodes = dom.get("nodes") or []
            cards = [row for row in nodes if row.get("tag") == "article"]
            result = {
                "visible_text": visible[:20000],
                "cards": [{"text": row.get("text"), "geometry": row.get("geometry")} for row in cards],
                "presentation_contract": {
                    "sleeper_projection_visible": "Sleeper Projection" in visible,
                    "dtos_projection_visible": "DTOS Projection" in visible,
                    "starter_count": expected_starters,
                    "canonical_dom_mismatches": mismatches,
                    "team_totals_reconciled": not mismatches,
                    "horizontal_overflow": page.evaluate("document.documentElement.scrollWidth > innerWidth"),
                },
                "dimensions": {"width": page.evaluate("document.documentElement.scrollWidth"), "height": page.evaluate("document.documentElement.scrollHeight")},
                "content_digest": __import__("hashlib").sha256(json.dumps(dom, sort_keys=True).encode()).hexdigest(),
            }
            return result
        finally:
            browser.close()

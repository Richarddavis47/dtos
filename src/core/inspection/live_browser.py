"""Shared Playwright primitive for bounded Live Visual captures."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from src.core.inspection.live_visual import CaptureRequest, LIVE_VIEWPORTS
from tools.inspection.capture import DOM_SCRIPT


def projection_total_mismatches(
    team: dict[str, Any], team_cards: list[str], *, projection_expected: bool = True,
) -> list[str]:
    """Reconcile one team total against its explicit availability contract."""
    name = str(team.get("team_name") or "")
    matches = [text for text in team_cards if name and name in text]
    if not matches:
        return ["projection_team_card_missing"]
    if not projection_expected:
        return []
    card_text = " ".join(matches)
    total = (team.get("canonical_totals") or {}).get("canonical_projection")
    availability = str((team.get("canonical_totals") or {}).get("availability") or "")
    if availability == "unavailable" or total is None:
        return [] if "Projection unavailable" in card_text else ["missing_projection_total_state_missing"]
    if "Projection unavailable" in card_text:
        return ["available_projection_total_rendered_unavailable"]
    value = float(total)
    accepted = {str(total), f"{value:g}", f"{value:.1f}", f"{value:.2f}"}
    return [] if any(candidate in card_text for candidate in accepted) else ["canonical_projection_total_mismatch"]


def matchup_projection_mismatches(
    semantic: dict[str, Any], visible: str, starter_cards: list[Any], team_cards: list[str],
) -> list[str]:
    """Reconcile projection evidence only where the game-state contract presents it."""
    mismatches: list[str] = []
    state = str(semantic.get("presentation_state") or "pregame")
    unavailable_aggregate = True
    for team in semantic.get("teams") or []:
        if str(team.get("team_name")) not in visible:
            mismatches.append("team_name_missing")
        total = (team.get("canonical_totals") or {}).get("canonical_projection")
        unavailable_aggregate = unavailable_aggregate and total is None
        projection_expected = state == "pregame" or total is not None
        for starter in team.get("starters") or []:
            displayed = starter.get("canonical") or {}
            canonical = displayed.get("canonical_projection")
            matching_cards = [card for card in starter_cards if str(starter.get("player_name")) in _card_text(card)]
            if not matching_cards:
                mismatches.append("starter_card_missing")
                continue
            contracts = [
                field for card in matching_cards for field in _card_semantic_fields(card)
                if field.get("field") == "pregame_projection"
            ]
            if canonical is not None:
                expected = f"{float(canonical):.2f}"
                if not any(
                    field.get("availability") == "available"
                    and field.get("value") == expected
                    and "Pregame projection" in str(field.get("text") or "")
                    and expected in str(field.get("text") or "")
                    for field in contracts
                ):
                    mismatches.append("canonical_projection_mismatch")
            elif not any(
                field.get("availability") == "unavailable"
                and "Projection unavailable" in str(field.get("text") or "")
                for field in contracts
            ):
                mismatches.append("missing_projection_state_missing")
        mismatches.extend(projection_total_mismatches(
            team, team_cards, projection_expected=projection_expected,
        ))
    if state != "pregame" and unavailable_aggregate and "Pregame projections unavailable" not in visible:
        mismatches.append("aggregate_projection_unavailable_state_missing")
    return mismatches


def _card_text(card: Any) -> str:
    return str(card.get("text") or "") if isinstance(card, dict) else str(card)


def _card_semantic_fields(card: Any) -> list[dict[str, Any]]:
    if not isinstance(card, dict):
        return []
    return list(card.get("semantic_fields") or [])


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
            starter_cards = page.locator(".battle-side:not(.vacant)").evaluate_all("""cards => cards.map(card => ({
                text: card.innerText,
                semantic_fields: Array.from(card.querySelectorAll('[data-dtos-semantic-field]')).map(field => ({
                    field: field.dataset.dtosSemanticField,
                    availability: field.dataset.dtosAvailability,
                    value: field.dataset.dtosValue || null,
                    text: field.innerText,
                })),
            }))""")
            team_cards = page.locator(".scoreboard-side, .matchup-team").all_inner_texts()
            for team in semantic.get("teams") or []:
                expected_starters += len(team.get("starters") or [])
            mismatches.extend(matchup_projection_mismatches(
                semantic, visible, starter_cards, team_cards,
            ))
            if mismatches:
                raise RuntimeError("Rendered matchup does not match canonical presentation")
            nodes = dom.get("nodes") or []
            cards = [row for row in nodes if row.get("tag") == "article"]
            result = {
                "visible_text": visible[:20000],
                "cards": [{"text": row.get("text"), "geometry": row.get("geometry")} for row in cards],
                "presentation_contract": {
                    "canonical_sleeper_projection_visible": "Sleeper canonical projection" in visible,
                    "manager_visible_pregame_label": "Pregame projection" in visible,
                    "requires_internal_provider_label": False,
                    "legacy_dtos_projection_visible": "DTOS Projection" in visible,
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

"""Shared Playwright primitive for bounded Live Visual captures."""
from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from src.core.inspection.live_visual import CaptureRequest, LIVE_VIEWPORTS
from tools.inspection.capture import DOM_SCRIPT

LIVE_VISUAL_CHROMIUM_ARGS = ("--no-zygote",)


def browser_launch_options() -> dict[str, Any]:
    """Avoid one-shot Chromium zygotes while preserving the render pipeline."""
    return {"headless": True, "args": list(LIVE_VISUAL_CHROMIUM_ARGS)}


def _inspection_headers() -> dict[str, str]:
    headers = {"X-DTOS-Inspection": "deterministic"}
    token = os.getenv("DTOS_INSPECTION_AUTH_TOKEN", "")
    if token:
        headers["X-DTOS-Inspection-Auth"] = token
    return headers


def normalized_manager_text(value: Any) -> str:
    """Normalize browser-rendered manager copy without weakening its semantics."""
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(normalized.split()).casefold()


def normalized_visible_identity(value: Any) -> str:
    """Trim presentation-only surrounding whitespace while preserving identity text."""
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def projection_total_mismatches(
    team: dict[str, Any], team_cards: list[str], *, projection_expected: bool = True,
) -> list[str]:
    """Reconcile one team total against its explicit availability contract."""
    name = normalized_visible_identity(team.get("team_name"))
    matches = [text for text in team_cards if name and name in normalized_visible_identity(text)]
    if not matches:
        return ["projection_team_card_missing"]
    if not projection_expected:
        return []
    card_text = " ".join(matches)
    total = (team.get("canonical_totals") or {}).get("canonical_projection")
    availability = str((team.get("canonical_totals") or {}).get("availability") or "")
    normalized_card_text = normalized_manager_text(card_text)
    unavailable_label = normalized_manager_text("Projection unavailable")
    if availability == "unavailable" or total is None:
        return [] if unavailable_label in normalized_card_text else ["missing_projection_total_state_missing"]
    if unavailable_label in normalized_card_text:
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
        team_name = normalized_visible_identity(team.get("team_name"))
        if team_name not in normalized_visible_identity(visible):
            mismatches.append("team_name_missing")
        total = (team.get("canonical_totals") or {}).get("canonical_projection")
        unavailable_aggregate = unavailable_aggregate and total is None
        projection_expected = state == "pregame" or total is not None
        for starter in team.get("starters") or []:
            displayed = starter.get("canonical") or {}
            canonical = displayed.get("canonical_projection")
            player_name = normalized_visible_identity(starter.get("player_name"))
            matching_cards = [
                card for card in starter_cards
                if player_name and player_name in normalized_visible_identity(_card_text(card))
            ]
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
                    and normalized_manager_text("Pregame projection")
                    in normalized_manager_text(field.get("text"))
                    and expected in str(field.get("text") or "")
                    for field in contracts
                ):
                    mismatches.append("canonical_projection_mismatch")
            elif not any(
                field.get("availability") == "unavailable"
                and normalized_manager_text("Projection unavailable")
                in normalized_manager_text(field.get("text"))
                for field in contracts
            ):
                mismatches.append("missing_projection_state_missing")
        mismatches.extend(projection_total_mismatches(
            team, team_cards, projection_expected=projection_expected,
        ))
    if (
        state != "pregame"
        and unavailable_aggregate
        and normalized_manager_text("Pregame projections unavailable")
        not in normalized_manager_text(visible)
    ):
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
        browser = playwright.chromium.launch(**browser_launch_options())
        try:
            page = browser.new_page(viewport=viewport, color_scheme="dark", reduced_motion="reduce")
            page.set_extra_http_headers(_inspection_headers())
            response = page.goto(base_url.rstrip("/") + request.human_url, wait_until="networkidle", timeout=90000)
            if response is None or not response.ok:
                raise RuntimeError("Live visual route did not return HTTP 200")
            page.add_style_tag(content="*,*::before,*::after{animation:none!important;transition:none!important}")
            dom = page.evaluate(DOM_SCRIPT)
            page.screenshot(path=str(output), full_page=True)
            visible = str(dom.get("visible_text") or "")
            semantic_response = page.request.get(
                base_url.rstrip("/") + request.semantic_url,
                headers=_inspection_headers(), timeout=60000,
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
            semantic_projection_node_count = sum(
                1
                for card in starter_cards
                for field in _card_semantic_fields(card)
                if field.get("field") == "pregame_projection"
            )
            canonical_projection_evidence_present = (
                expected_starters > 0
                and semantic_projection_node_count == expected_starters
                and not mismatches
            )
            nodes = dom.get("nodes") or []
            cards = [row for row in nodes if row.get("tag") == "article"]
            result = {
                "visible_text": visible[:20000],
                "cards": [{"text": row.get("text"), "geometry": row.get("geometry")} for row in cards],
                "presentation_contract": {
                    "canonical_projection_evidence_present": canonical_projection_evidence_present,
                    "semantic_projection_node_count": semantic_projection_node_count,
                    "manager_pregame_label_reconciled": not mismatches,
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

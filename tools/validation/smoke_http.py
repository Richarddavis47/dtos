"""Run DTOS HTTP smoke tests against an explicitly started local server."""
from __future__ import annotations

import argparse
import json
import re
from time import perf_counter
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

GENERIC_TEAM_LABEL = re.compile(r"\b(?:Team|Roster)\s+(?:[1-9]|10)\b|\bTeam Detail\b", re.IGNORECASE)
GENERIC_PAGE_TITLE = re.compile(r"<title>\s*(?:Team|Player|Matchup)\s*(?:Detail)?\s*</title>", re.IGNORECASE)
INTERNAL_LABEL = re.compile(r"\b(?:Roster ID|Player ID|Transaction ID|Sleeper ID|Franchise ID|Provider Key)\b", re.IGNORECASE)


def validate_team_identity(body: bytes, path: str) -> None:
    """Reject rendered fallback labels when canonical team identity is available."""
    match = GENERIC_TEAM_LABEL.search(body.decode("utf-8", errors="replace"))
    if match:
        raise AssertionError(f"{path}: rendered generic team label {match.group(0)!r}")


def validate_product_contract(body: bytes, path: str, *, recommendation: bool = False) -> None:
    """Validate the public design-system contract on a rendered page."""
    html = body.decode("utf-8", errors="replace")
    if 'data-dtos-component="page-header"' not in html:
        raise AssertionError(f"{path}: shared page header is missing")
    if 'class="ds-action primary"' not in html and ">Sync League</button>" not in html:
        raise AssertionError(f"{path}: primary page action is missing")
    if GENERIC_PAGE_TITLE.search(html):
        raise AssertionError(f"{path}: page title is generic")
    match = INTERNAL_LABEL.search(html)
    if match:
        raise AssertionError(f"{path}: exposes internal identifier label {match.group(0)!r}")
    if recommendation and 'data-dtos-component="recommendation"' not in html:
        raise AssertionError(f"{path}: shared recommendation contract is missing")


def get(base_url: str, path: str, expected: int = 200) -> bytes:
    started = perf_counter()
    print(f"HTTP smoke requesting: {path}", flush=True)
    try:
        with urlopen(base_url.rstrip("/") + path, timeout=60) as response:
            status = response.status
            body = response.read()
    except HTTPError as exc:
        status = exc.code
        body = exc.read()
    except TimeoutError as exc:
        elapsed = perf_counter() - started
        raise AssertionError(
            f"HTTP smoke timed out: {path} after {elapsed:.3f}s",
        ) from exc
    elapsed = perf_counter() - started
    print(
        f"HTTP smoke completed: {path} status={status} elapsed={elapsed:.3f}s",
        flush=True,
    )
    if status != expected:
        raise AssertionError(f"{path}: expected HTTP {expected}, received {status}; body={body[:300]!r}")
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8767")
    args = parser.parse_args()

    major = (
        "/", "/teams", "/matchups", "/transactions", "/picks", "/settings",
        "/health/live", "/health/ready", "/api/status", "/api/crawl",
        "/api/crawl/history", "/history",
        "/api/platform/health", "/api/intelligence", "/api/league",
        "/api/players", "/front-offices", "/api/front-offices", "/trades",
        "/api/trades", "/openapi.json",
        "/api/inspect", "/api/inspect/pages", "/api/inspect/site-map",
        "/api/inspect/schema", "/api/inspect/health",
        "/api/inspect/visual/pages", "/api/inspect/releases/current",
    )
    product_pages = {"/", "/teams", "/matchups", "/transactions", "/picks", "/settings", "/history", "/front-offices", "/trades"}
    recommendation_pages = {"/", "/front-offices", "/trades"}
    for path in major:
        body = get(args.base_url, path)
        if path in product_pages:
            validate_product_contract(body, path, recommendation=path in recommendation_pages)

    league = json.loads(get(args.base_url, "/api/league"))
    teams = league.get("teams") or []
    if not teams:
        raise AssertionError("Cached league contract contains no teams.")
    roster_ids = [int(team["roster_id"]) for team in teams]
    for roster_id in roster_ids:
        team_path = f"/teams/{roster_id}"
        team_body = get(args.base_url, team_path)
        validate_team_identity(team_body, team_path)
        validate_product_contract(team_body, team_path, recommendation=True)
        front_office_path = f"/front-offices?front_office={roster_id}"
        front_office_body = get(args.base_url, front_office_path)
        validate_team_identity(front_office_body, front_office_path)
        validate_product_contract(front_office_body, front_office_path, recommendation=True)
        organization = json.loads(get(args.base_url, f"/api/front-offices?front_office={roster_id}"))
        if organization.get("active_front_office") != roster_id:
            raise AssertionError(f"Front Office context {roster_id} did not persist through the API.")
        get(args.base_url, f"/trades?front_office={roster_id}")
        get(args.base_url, f"/api/trades?front_office={roster_id}")

    player_index = json.loads(get(args.base_url, "/api/players"))
    players = player_index.get("players") or []
    if not players or not players[0].get("player_id"):
        raise AssertionError("Canonical cached player index contains no discoverable player ID.")
    player_id = quote(str(players[0]["player_id"]), safe="")
    for roster_id in roster_ids:
        player_path = f"/players/{player_id}?front_office={roster_id}"
        validate_product_contract(get(args.base_url, player_path), player_path, recommendation=True)

    get(args.base_url, "/players/", expected=404)
    get(args.base_url, "/players/dtos-validation-missing-player", expected=404)
    print(
        f"HTTP smoke passed: {len(major)} major endpoints, {len(roster_ids)} Team HQ pages, "
        f"{len(roster_ids)} Front Office dossiers/APIs/trade contexts, and one player dossier across all contexts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

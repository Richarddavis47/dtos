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
MARKET_DATASET = re.compile(r"Dataset\s*<code>([^<]+)</code>", re.IGNORECASE)


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


def validate_asset_market_contract(body: bytes, path: str) -> str:
    """Validate a directory surface and return its canonical dataset identity."""
    validate_product_contract(body, path)
    html = body.decode("utf-8", errors="replace")
    for required in (
        "Asset Market &amp; Dynasty Exchange",
        'aria-label="Asset Market filters"',
        "Canonical dynasty asset rankings",
        "Values remain separate; unavailable evidence is never substituted.",
    ):
        if required not in html:
            raise AssertionError(f"{path}: Asset Market contract is missing {required!r}")
    match = MARKET_DATASET.search(html)
    if match is None:
        raise AssertionError(f"{path}: canonical market dataset identity is missing")
    return match.group(1)


def validate_market_asset_contract(payload: dict, path: str) -> None:
    """Require canonical Brain metadata on an expanded market asset response."""
    recommendation = payload.get("recommendation") or {}
    required = (
        "confidence", "brain_snapshot_id", "decision_provenance",
        "primary_reason", "supporting_evidence",
    )
    missing = [name for name in required if recommendation.get(name) is None]
    if missing:
        raise AssertionError(
            f"{path}: canonical Brain recommendation metadata is missing: "
            + ", ".join(missing)
        )
    if payload.get("brain_snapshot_id") != recommendation.get("brain_snapshot_id"):
        raise AssertionError(f"{path}: market detail and recommendation use different Brain snapshots")


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
        "/", "/market", "/commissioner", "/teams", "/matchups", "/transactions", "/picks", "/settings",
        "/health/live", "/health/ready", "/api/status", "/api/crawl",
        "/api/crawl/history", "/history",
        "/api/platform/health", "/api/intelligence", "/api/league",
        "/api/players", "/front-offices", "/api/front-offices", "/trades",
        "/api/trades", "/openapi.json",
        "/api/inspect", "/api/inspect/pages", "/api/inspect/site-map",
        "/api/inspect/schema", "/api/inspect/health",
        "/api/inspect/visual/pages", "/api/inspect/releases/current",
        "/api/valuation", "/api/valuation/status", "/api/valuation/providers",
        "/api/valuation/assets?limit=1", "/api/inspect/valuation",
        "/api/market", "/api/market/health", "/api/market/assets?limit=1",
        "/api/market/search?q=QB", "/api/market/trending", "/api/inspect/market",
    )
    product_pages = {"/", "/market", "/commissioner", "/teams", "/matchups", "/transactions", "/picks", "/settings", "/history", "/front-offices", "/trades"}
    recommendation_pages = {"/commissioner", "/front-offices", "/trades"}
    market_pages: dict[str, str] = {}
    for path in major:
        body = get(args.base_url, path)
        if path in {"/", "/market"}:
            market_pages[path] = validate_asset_market_contract(body, path)
        elif path in product_pages:
            validate_product_contract(body, path, recommendation=path in recommendation_pages)
    if market_pages["/"] != market_pages["/market"]:
        raise AssertionError("/ and /market expose different canonical market datasets")

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
    valuation = json.loads(get(args.base_url, "/api/valuation/status"))
    if int((valuation.get("counts") or {}).get("players") or 0) < len(players):
        raise AssertionError("Valuation universe omits cached Sleeper players.")
    if int(valuation.get("duplicate_identities") or 0):
        raise AssertionError("Valuation universe contains duplicate canonical identities.")
    valuation_asset = json.loads(get(args.base_url, f"/api/valuation/assets/player:{player_id}"))
    if str((valuation_asset.get("identity") or {}).get("sleeper_id")) != player_id:
        raise AssertionError("Valuation lookup did not preserve the canonical Sleeper identity.")
    market = json.loads(get(args.base_url, "/api/market/health"))
    if int((market.get("counts") or {}).get("total") or 0) < len(players):
        raise AssertionError("Asset Market omits canonical cached players.")
    if int(market.get("duplicate_asset_ids") or 0):
        raise AssertionError("Asset Market contains duplicate canonical identities.")
    market_asset = json.loads(get(args.base_url, f"/api/market/assets/player:{player_id}"))
    validate_market_asset_contract(
        market_asset, f"/api/market/assets/player:{player_id}",
    )
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

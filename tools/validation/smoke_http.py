"""Run DTOS HTTP smoke tests against an explicitly started local server."""
from __future__ import annotations

import argparse
import json
import os
import re
from time import perf_counter, sleep
from typing import Callable
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.platform.lifecycle import MARKET_BUILD_BLOCKERS

GENERIC_TEAM_LABEL = re.compile(r"\b(?:Team|Roster)\s+(?:[1-9]|10)\b|\bTeam Detail\b", re.IGNORECASE)
GENERIC_PAGE_TITLE = re.compile(r"<title>\s*(?:Team|Player|Matchup)\s*(?:Detail)?\s*</title>", re.IGNORECASE)
INTERNAL_LABEL = re.compile(r"\b(?:Roster ID|Player ID|Transaction ID|Sleeper ID|Franchise ID|Provider Key)\b", re.IGNORECASE)
MARKET_DATASET = re.compile(r"Dataset\s*<code>([^<]+)</code>", re.IGNORECASE)
MARKET_WARMING_DETAIL = (
    "Asset Market generation is building safely in the background; retry shortly."
)
MARKET_WARMING_PATHS = frozenset(("/market",))
MARKET_WARMING_DEADLINE_SECONDS = 60.0
MARKET_WARMING_RESPONSE_LIMIT_SECONDS = 0.5
MARKET_WARMING_INTERVAL_SECONDS = 0.5


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


def _request(base_url: str, path: str) -> tuple[int, bytes, dict[str, str], float]:
    started = perf_counter()
    print(f"HTTP smoke requesting: {path}", flush=True)
    try:
        headers = {}
        inspection_token = os.getenv("DTOS_INSPECTION_AUTH_TOKEN", "")
        if inspection_token:
            headers["X-DTOS-Inspection-Auth"] = inspection_token
        with urlopen(Request(base_url.rstrip("/") + path, headers=headers), timeout=60) as response:
            status = response.status
            body = response.read()
            headers = dict(response.headers.items())
    except HTTPError as exc:
        status = exc.code
        body = exc.read()
        headers = dict(exc.headers.items())
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
    return status, body, headers, elapsed


def get(base_url: str, path: str, expected: int = 200) -> bytes:
    status, body, _headers, _elapsed = _request(base_url, path)
    if status != expected:
        raise AssertionError(f"{path}: expected HTTP {expected}, received {status}; body={body[:300]!r}")
    return body


def get_market_page(
    base_url: str,
    path: str,
    *,
    request: Callable[[str, str], tuple[int, bytes, dict[str, str], float]] = _request,
    sleeper: Callable[[float], None] = sleep,
    clock: Callable[[], float] = perf_counter,
) -> bytes:
    """Allow only the exact bounded cold-market warming lifecycle."""
    if path not in MARKET_WARMING_PATHS:
        raise AssertionError(f"{path}: is not an Asset Market warming surface")
    started = clock()
    attempts = 0
    observed_generation: str | None = None
    blocker_seen = False
    eligible_seen = False
    initial_build_count: int | None = None
    while True:
        attempts += 1
        status, body, headers, elapsed = request(base_url, path)
        if status == 200:
            if blocker_seen:
                health_status, health_body, _headers, _elapsed = request(
                    base_url, "/api/market/health",
                )
                if health_status != 200:
                    raise AssertionError(
                        f"{path}: Market health failed after lifecycle warming"
                    )
                health = json.loads(health_body)
                cache = health.get("cache") or {}
                final_count = int(cache.get("build_count") or 0)
                if not eligible_seen or initial_build_count is None:
                    raise AssertionError(
                        f"{path}: lifecycle blocker never transitioned to eligibility"
                    )
                if final_count != initial_build_count + 1:
                    raise AssertionError(
                        f"{path}: expected exactly one post-blocker market build; "
                        f"build_count={final_count}, initial={initial_build_count}"
                    )
            duration = clock() - started
            print(
                "Asset Market warming completed: "
                f"path={path} duration={duration:.3f}s attempts={attempts} "
                f"final_status=200 generation={observed_generation or 'published-page-contract'}",
                flush=True,
            )
            return body
        if status != 503:
            raise AssertionError(
                f"{path}: expected HTTP 200 or exact Asset Market warming 503, "
                f"received {status}; body={body[:300]!r}"
            )
        if elapsed > MARKET_WARMING_RESPONSE_LIMIT_SECONDS:
            raise AssertionError(
                f"{path}: Asset Market warming response exceeded 500ms ({elapsed:.3f}s)"
            )
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AssertionError(f"{path}: malformed Asset Market warming response") from exc
        if payload != {"detail": MARKET_WARMING_DETAIL}:
            raise AssertionError(
                f"{path}: unrelated or malformed HTTP 503; body={body[:300]!r}"
            )
        retry_after = next(
            (value for name, value in headers.items() if name.casefold() == "retry-after"),
            None,
        )
        if retry_after != "5":
            raise AssertionError(f"{path}: warming response omitted canonical Retry-After: 5")

        health_status, health_body, _health_headers, _health_elapsed = request(
            base_url, "/api/market/health",
        )
        if health_status != 200:
            raise AssertionError(
                f"{path}: Market health failed during warming: HTTP {health_status}"
            )
        try:
            health = json.loads(health_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AssertionError(f"{path}: malformed Market health during warming") from exc
        cache = health.get("cache") or {}
        if cache.get("last_error"):
            raise AssertionError(
                f"{path}: Asset Market build failed during warming: {cache['last_error']}"
            )
        lifecycle = cache.get("lifecycle") or {}
        startup_fence = lifecycle.get("startup_fence") or {}
        startup_state = startup_fence.get("state")
        startup_reason = startup_fence.get("reason")
        startup_blocked = (
            startup_state == "running"
            and isinstance(startup_reason, str)
            and bool(startup_reason.strip())
        )
        if startup_state == "failed":
            raise AssertionError(
                f"{path}: Asset Market startup fence failed: {startup_reason!r}"
            )
        build_active = bool(cache.get("build_active"))
        build_allowed = lifecycle.get("market_build_allowed")
        phase = str(lifecycle.get("phase") or "idle")
        ready_after_response = (
            health.get("status") == "ready"
            and not build_active
            and bool(cache.get("last_valid_model"))
            and build_allowed is True
            and phase == "idle"
        )
        if health.get("status") not in {"warming", "ready"}:
            raise AssertionError(
                f"{path}: inconsistent Asset Market warming generation: {health!r}"
            )
        if ready_after_response:
            if blocker_seen:
                eligible_seen = True
        elif build_active:
            if build_allowed is False:
                raise AssertionError(
                    f"{path}: market construction overlaps lifecycle blocker {phase!r}"
                )
            if blocker_seen:
                eligible_seen = True
        else:
            registered_blocker = phase in MARKET_BUILD_BLOCKERS or startup_blocked
            if build_allowed is not False or not registered_blocker:
                raise AssertionError(
                    f"{path}: stale Asset Market warming without active build or "
                    f"registered lifecycle blocker: {health!r}"
                )
            blocker_seen = True
            count = int(cache.get("build_count") or 0)
            if initial_build_count is None:
                initial_build_count = count
            elif count != initial_build_count:
                raise AssertionError(
                    f"{path}: market build count changed while lifecycle remained blocked"
                )
        generation = cache.get("market_generation")
        if generation is not None:
            if observed_generation is not None and generation != observed_generation:
                raise AssertionError(f"{path}: Asset Market generation changed during warming")
            observed_generation = str(generation)
        duration = clock() - started
        if duration >= MARKET_WARMING_DEADLINE_SECONDS:
            raise AssertionError(
                f"{path}: Asset Market warming exceeded 60s after {attempts} attempts"
            )
        if not ready_after_response:
            sleeper(min(
                MARKET_WARMING_INTERVAL_SECONDS,
                MARKET_WARMING_DEADLINE_SECONDS - duration,
            ))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8767")
    args = parser.parse_args()

    major = (
        "/", "/market", "/league", "/commissioner", "/teams", "/matchups", "/transactions", "/picks", "/settings",
        "/health/live", "/health/ready", "/api/status", "/api/crawl",
        "/api/crawl/history", "/history",
        "/api/platform/health", "/api/intelligence", "/api/league",
        "/api/players", "/front-offices", "/api/front-offices", "/trades",
        "/api/trades", "/openapi.json",
        "/api/inspect", "/api/inspect/pages", "/api/inspect/site-map",
        "/api/inspect/schema", "/api/inspect/health",
        "/api/inspect/live", "/api/inspect/live/health",
        "/api/inspect/live/visual", "/api/inspect/live/visual/health",
        "/api/inspect/visual/pages", "/api/inspect/releases/current",
        "/current-visual", "/current-visual/manifest.json",
        "/api/valuation", "/api/valuation/status", "/api/valuation/providers",
        "/api/valuation/assets?limit=1", "/api/inspect/valuation",
        "/api/market", "/api/market/health", "/api/market/assets?limit=1",
        "/api/market/search?q=QB", "/api/market/trending", "/api/inspect/market",
    )
    product_pages = {"/", "/market", "/league", "/commissioner", "/teams", "/matchups", "/transactions", "/picks", "/settings", "/history", "/front-offices", "/trades"}
    recommendation_pages = {"/commissioner", "/front-offices"}
    market_pages: dict[str, str] = {}
    for path in major:
        if path == "/market":
            body = get_market_page(args.base_url, path)
            market_pages[path] = validate_asset_market_contract(body, path)
        else:
            body = get(args.base_url, path)
        if path in product_pages and path != "/market":
            validate_product_contract(body, path, recommendation=path in recommendation_pages)
        if path == "/trades" and b"Choose your franchise" not in body:
            raise AssertionError("/trades: explicit manager-context selection is missing")
        if path == "/api/trades":
            trade_selection = json.loads(body)
            if trade_selection.get("status") != "manager_context_required":
                raise AssertionError("/api/trades: missing explicit manager-context state")
    print(
        "Asset Market page contract ready: "
        f"generation={market_pages['/market']} final_status=200",
        flush=True,
    )

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
        trade_path = f"/trades?front_office={roster_id}"
        trade_body = get(args.base_url, trade_path)
        validate_team_identity(trade_body, trade_path)
        validate_product_contract(trade_body, trade_path, recommendation=True)
        trade_api = json.loads(get(args.base_url, f"/api/trades?front_office={roster_id}"))
        if int(trade_api.get("active_front_office") or 0) != roster_id:
            raise AssertionError(f"Trade Center context {roster_id} did not persist through the API.")

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

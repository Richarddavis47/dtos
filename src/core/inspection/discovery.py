"""Automatic, deterministic discovery of public DTOS HTML pages."""
from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from typing import Any
from urllib.parse import quote

from fastapi.routing import APIRoute

from src.core.inspection.models import DiscoveredPage

_PRIVATE_PREFIXES = ("/api/", "/health", "/openapi", "/docs", "/redoc")
_EXCLUDED = {
    "/robots.txt": "Crawler control document, not an HTML user interface.",
    "/sitemap.xml": "Machine-readable site map, not an HTML user interface.",
}


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return result or "home"


def _name(route: APIRoute) -> str:
    return (route.name or route.path).replace("_", " ").title()


def _http_routes(routes: Iterable[Any], prefix: str = "") -> Iterator[tuple[APIRoute, str]]:
    """Flatten FastAPI router containers through their public capabilities."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route, prefix + route.path
            continue
        original = getattr(route, "original_router", None)
        nested = getattr(original, "routes", None)
        if nested is None:
            continue
        context = getattr(route, "include_context", None)
        child_prefix = prefix + str(getattr(context, "prefix", "") or "")
        yield from _http_routes(nested, child_prefix)


def _players(data: dict[str, Any], limit: int = 6) -> tuple[str, ...]:
    players = data.get("players") or {}
    if not isinstance(players, dict):
        return ()
    rows = sorted(
        (
            (player_id, player)
            for player_id, player in players.items()
            if isinstance(player, dict)
            and player.get("position") in {"QB", "RB", "WR", "TE", "K", "DEF"}
            and (player.get("full_name") or player.get("first_name"))
        ),
        key=lambda item: (
            str((item[1] or {}).get("position") or "ZZ"),
            str((item[1] or {}).get("full_name") or item[0]),
        ),
    )
    # Stable cross-position sample; all player pages remain semantically discoverable.
    selected: list[str] = []
    positions: set[str] = set()
    for player_id, player in rows:
        position = str((player or {}).get("position") or "Unknown")
        if position not in positions or len(selected) < 2:
            selected.append(str(player_id))
            positions.add(position)
        if len(selected) >= limit:
            break
    return tuple(selected)


def _representatives(path: str, data: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    teams = tuple(str(row.get("roster_id")) for row in data.get("teams") or () if row.get("roster_id"))
    if "{roster_id}" in path:
        return tuple({"roster_id": item} for item in teams)
    if "{franchise_id:path}" in path:
        league_id = str((data.get("league") or {}).get("league_id") or "")
        identities = tuple(
            quote(f"{league_id}:franchise:{row.get('roster_id')}", safe="")
            for row in data.get("teams") or ()
            if league_id and row.get("roster_id")
        )
        return tuple({"franchise_id:path": item} for item in identities)
    if "{player_id}" in path:
        return tuple({"player_id": item} for item in _players(data))
    if "{matchup_id}" in path:
        matchups = data.get("matchups") or ()
        if isinstance(matchups, dict):
            identifiers = sorted(str(key) for key in matchups)
        else:
            identifiers = sorted({str(row.get("matchup_id")) for row in matchups if isinstance(row, dict) and row.get("matchup_id") is not None})
        return tuple({"matchup_id": item} for item in identifiers[:3])
    if "{" in path:
        return ()
    return ({},)


def discover_pages(routes: Iterable[Any], state: dict[str, Any]) -> tuple[DiscoveredPage, ...]:
    """Return every public GET HTML route with canonical representative parameters."""
    data = state.get("data") or {}
    discovered: list[DiscoveredPage] = []
    seen: set[str] = set()
    for route, canonical_path in _http_routes(routes):
        if "GET" not in (route.methods or set()):
            continue
        path = canonical_path
        if path.startswith(_PRIVATE_PREFIXES):
            continue
        response_name = getattr(route.response_class, "media_type", None)
        if response_name not in (None, "text/html") and path not in _EXCLUDED:
            continue
        if path in _EXCLUDED:
            discovered.append(DiscoveredPage(
                _slug(path), _name(route), path, path, "excluded", "unsupported",
                "unsupported", excluded=True, exclusion_reason=_EXCLUDED[path],
            ))
            continue
        if path == "/history/player/{player_id}":
            discovered.append(DiscoveredPage(
                "history-player", _name(route), path, path, "dynamic", "unsupported",
                "unsupported", excluded=True,
                exclusion_reason="The synchronized league cache does not identify which players have Historical Memory observations; use the inspected League History page and historical crawl index.",
            ))
            continue
        fixtures = _representatives(path, data)
        if not fixtures:
            discovered.append(DiscoveredPage(
                _slug(path), _name(route), path, path, "dynamic", "unsupported",
                "unsupported", excluded=True,
                exclusion_reason="No deterministic representative parameters are available.",
            ))
            continue
        for fixture in fixtures:
            resolved = path
            for key, value in fixture.items():
                resolved = resolved.replace("{" + key + "}", value)
            if resolved in seen:
                continue
            seen.add(resolved)
            page_id = _slug(resolved)
            discovered.append(DiscoveredPage(
                page_id, _name(route), resolved, path,
                "dynamic" if fixture else "static", "live_cached", "deterministic",
            ))
    return tuple(sorted(discovered, key=lambda page: (page.excluded, page.route, page.page_id)))


def uncovered_public_routes(routes: Iterable[Any], state: dict[str, Any]) -> tuple[str, ...]:
    pages = discover_pages(routes, state)
    return tuple(page.route for page in pages if page.excluded and page.exclusion_reason and "representative" in page.exclusion_reason)


def unsupported_dynamic_patterns(routes: Iterable[Any]) -> tuple[str, ...]:
    """Flag public HTML parameters for which DINS has no fixture strategy."""
    supported = {"roster_id", "player_id", "matchup_id", "franchise_id"}
    failures = []
    for route, canonical_path in _http_routes(routes):
        if "GET" not in (route.methods or set()):
            continue
        path = canonical_path
        if path.startswith(_PRIVATE_PREFIXES):
            continue
        response_name = getattr(route.response_class, "media_type", None)
        if response_name not in (None, "text/html"):
            continue
        parameters = set(re.findall(r"{([^}:]+)(?::[^}]+)?}", path))
        if parameters - supported:
            failures.append(path)
    return tuple(sorted(failures))

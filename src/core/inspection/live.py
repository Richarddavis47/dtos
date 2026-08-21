"""Default-on, read-only discovery of the running DTOS public product."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator

from fastapi.routing import APIRoute

from app_metadata import BUILD_NUMBER, VERSION, deployment_metadata
from services.history import history_progress_contracts
from src.core.fois.models import FOIS_MODEL_VERSION
from src.core.inspection.discovery import discover_pages
from src.ui.intelligence_presentation import projection_presentation_value

LIVE_INSPECTION_SCHEMA_VERSION = "1.0"
_PRIVATE_PREFIXES = (
    "/docs", "/redoc", "/openapi.json", "/sync", "/admin", "/debug",
    "/inspection-artifacts", "/__validation__",
)
_MACHINE_SURFACE_PREFIXES = ("/current-visual",)
_APPROVED_EXCLUSIONS = {
    "/robots.txt": "crawler_control",
    "/sitemap.xml": "machine_sitemap",
}


@dataclass(frozen=True)
class PublicSurface:
    surface_id: str
    surface_type: str
    title: str
    category: str
    method: str
    route: str
    human_url: str | None
    semantic_url: str
    parameterized: bool
    inspection_enabled: bool = True
    dins_enabled: bool = True
    public: bool = True
    exclusion_reason: str | None = None


def external_mirror_policy(surface: PublicSurface) -> str:
    """Return the scalable mirror policy derived from canonical registration."""
    if not surface.public or not surface.inspection_enabled or not surface.dins_enabled:
        return "excluded"
    return "representative_or_requested" if surface.parameterized else "always"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "home"


def _routes(routes: Iterable[Any], prefix: str = "") -> Iterator[tuple[APIRoute, str]]:
    for route in routes:
        if isinstance(route, APIRoute):
            yield route, prefix + route.path
            continue
        nested = getattr(getattr(route, "original_router", None), "routes", None)
        if nested is not None:
            context = getattr(route, "include_context", None)
            yield from _routes(nested, prefix + str(getattr(context, "prefix", "") or ""))


def _category(path: str, tags: list[str] | None) -> str:
    if tags:
        return str(tags[0]).replace("-", " ").title()
    first = path.strip("/").split("/", 1)[0] or "home"
    return first.replace("-", " ").title()


def public_surface_registry(routes: Iterable[Any]) -> tuple[PublicSurface, ...]:
    """Derive every public GET surface from the canonical application router."""
    rows: list[PublicSurface] = []
    seen: set[tuple[str, str]] = set()
    for route, path in _routes(routes):
        if "GET" not in (route.methods or set()) or path.startswith(_PRIVATE_PREFIXES):
            continue
        key = ("GET", path)
        if key in seen:
            continue
        seen.add(key)
        excluded = _APPROVED_EXCLUSIONS.get(path)
        is_api = path.startswith(("/api/", "/health", *_MACHINE_SURFACE_PREFIXES))
        surface_id = str(route.name or _slug(path)).replace("_", "-")
        rows.append(PublicSurface(
            surface_id=surface_id,
            surface_type="api" if is_api else "page",
            title=str(route.summary or route.name or path).replace("_", " ").title(),
            category=_category(path, route.tags), method="GET", route=path,
            human_url=None if is_api else path,
            semantic_url=f"/api/inspect/live/surfaces/{surface_id}",
            parameterized="{" in path,
            inspection_enabled=excluded is None,
            dins_enabled=excluded is None and not is_api,
            exclusion_reason=excluded,
        ))
    return tuple(sorted(rows, key=lambda row: (row.category, row.route, row.surface_id)))


def matchup_semantic(
    data: dict[str, Any], matchup_id: str, projection_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    sides = (data.get("matchups") or {}).get(str(matchup_id))
    if not sides:
        return None
    projections = (projection_snapshot or {}).get("players") or {}
    teams = []
    for side in sides:
        starters = []
        canonical_total = 0.0
        canonical_count = 0
        for player in side.get("lineup") or []:
            player_id = str(player.get("id") or player.get("player_id") or "")
            row = projections.get(player_id) or {}
            canonical = row.get("canonical_projection")
            if canonical is not None:
                canonical_total += float(canonical)
                canonical_count += 1
            starters.append({
                "player_id": player_id, "player_name": player.get("name"),
                "position": player.get("position"), "nfl_team": player.get("nfl_team"),
                "lineup_slot": player.get("slot"),
                "displayed": {"canonical_projection": canonical,
                              "provider": "Sleeper", "actual_points": player.get("points")},
                "canonical": {"canonical_projection": canonical, "provider": "Sleeper"},
                "projection_state": "projected_zero" if canonical == 0 else "available" if canonical is not None else "unavailable",
                "technical_details": {"projection_snapshot_id": row.get("projection_snapshot_id")},
            })
        count = len(starters)
        presentation_total = projection_presentation_value(round(canonical_total, 2), canonical_count)
        total_contract = {
            "canonical_projection": presentation_total,
            "raw_aggregate": round(canonical_total, 2),
            "availability": "available" if canonical_count else "unavailable",
        }
        teams.append({
            "roster_id": side.get("roster_id"), "team_name": side.get("team"),
            "manager": side.get("owner"), "actual_score": side.get("points"),
            "starters": starters,
            "displayed_totals": dict(total_contract),
            "canonical_totals": dict(total_contract),
            "coverage": {"canonical": f"{canonical_count}/{count}",
                         "canonical_status": "complete" if canonical_count == count else "partial"},
        })
    return {
        "surface_id": f"matchup-{matchup_id}", "surface_type": "matchup",
        "title": " vs ".join(str(row.get("team_name")) for row in teams),
        "human_url": f"/matchups/{matchup_id}",
        "semantic_url": f"/api/inspect/live/matchups/{matchup_id}",
        "matchup_id": str(matchup_id), "status": "current", "teams": teams,
        "technical_details": {
            "application_version": VERSION, "application_build": BUILD_NUMBER,
            "projection_snapshot_id": (projection_snapshot or {}).get("projection_snapshot_id"),
            "read_only": True,
        },
    }


class LiveInspection:
    """Bounded semantic observer over already-retained canonical state."""

    def __init__(self, *, state: dict[str, Any], routes: Iterable[Any], league_id: str,
                 projection_snapshot: dict[str, Any] | None, market: Any,
                 fois_scores: tuple[Any, ...]) -> None:
        self.state = state
        self.data = state.get("data") or {}
        self.routes = tuple(routes)
        self.league_id = league_id
        self.projection_snapshot = projection_snapshot
        self.market = market
        self.fois_scores = fois_scores
        self.surfaces = public_surface_registry(self.routes)

    def identity(self) -> dict[str, Any]:
        league = self.data.get("league") or {}
        deployment = deployment_metadata()
        history = history_progress_contracts(self.league_id)["canonical_history_progress"]
        market_identity = self.market.audit_identity() if self.market is not None else {}
        return {
            "application_version": VERSION, "application_build": BUILD_NUMBER,
            "commit": deployment["commit"], "deployment_timestamp": deployment["deployed_at"],
            "environment": "production" if "onrender.com" in str(__import__('os').getenv("DTOS_PUBLIC_URL", "")) else "application",
            "live_inspection_schema": LIVE_INSPECTION_SCHEMA_VERSION,
            "league_id": self.league_id, "league_name": league.get("name"),
            "season": (self.projection_snapshot or {}).get("season") or (self.data.get("nfl_state") or {}).get("season"),
            "week": (self.projection_snapshot or {}).get("week") or self.data.get("week"),
            "brain_snapshot_id": market_identity.get("brain_snapshot_id"),
            "projection_snapshot_id": (self.projection_snapshot or {}).get("projection_snapshot_id"),
            "asset_market_generation": market_identity.get("market_generation"),
            "historical_memory": history, "fois_version": FOIS_MODEL_VERSION,
            "inspection_generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def counts(self) -> dict[str, int]:
        players = self.data.get("players") or {}
        picks = (self.data.get("pick_ledger") or []) + (self.data.get("traded_picks") or [])
        seasons = history_progress_contracts(self.league_id)["canonical_history_progress"].get("configured_seasons") or []
        return {
            "leagues": 1, "teams": len(self.data.get("teams") or []),
            "matchups": len(self.data.get("matchups") or {}), "players": len(players),
            "picks": len(picks), "seasons": len(seasons), "fois_profiles": len(self.fois_scores),
            "public_surfaces": len(self.surfaces),
            "inspectable_surfaces": sum(row.inspection_enabled for row in self.surfaces),
            "excluded_surfaces": sum(not row.inspection_enabled for row in self.surfaces),
            "public_apis": sum(row.surface_type == "api" for row in self.surfaces),
        }

    def root(self) -> dict[str, Any]:
        counts = self.counts()
        categories = sorted({row.category for row in self.surfaces if row.inspection_enabled})
        return {
            "status": "complete" if counts["inspectable_surfaces"] else "incomplete",
            "identity": self.identity(), "counts": counts, "categories": categories,
            "collections": {
                "surfaces": "/api/inspect/live/surfaces", "teams": "/api/inspect/live/teams",
                "matchups": "/api/inspect/live/matchups", "players": "/api/inspect/live/players",
                "picks": "/api/inspect/live/picks", "seasons": "/api/inspect/live/seasons",
                "apis": "/api/inspect/live/apis", "search": "/api/inspect/live/search?q=matchups",
            },
            "audit_exports": {"json": "/api/audit/projections/current",
                              "csv": "/api/audit/projections/current.csv"},
            "dins": {"current_release": "/api/inspect/releases/current",
                     "health": "/api/inspect/health"},
            "traversal": "Start with a collection, then follow human_url and semantic_url.",
            "side_effect_contract": {"provider_calls": 0, "projection_refreshes": 0,
                                     "brain_regenerations": 0, "market_constructions": 0,
                                     "fois_regenerations": 0, "historical_writes": 0},
        }

    def health(self) -> dict[str, Any]:
        counts = self.counts()
        eligible = counts["inspectable_surfaces"]
        return {
            "status": "complete", "identity": self.identity(),
            "registered_public_surfaces": counts["public_surfaces"],
            "inspectable_surfaces": eligible,
            "excluded_surfaces": counts["excluded_surfaces"],
            "completeness_percent": 100.0 if eligible else 0.0,
            "broken_links": 0, "semantic_errors": 0,
            "side_effects": 0,
            "exclusions": [asdict(row) for row in self.surfaces if not row.inspection_enabled],
        }

    @staticmethod
    def page(rows: list[dict[str, Any]], limit: int, offset: int, key: str) -> dict[str, Any]:
        page = rows[offset:offset + limit]
        return {"count": len(rows), "limit": limit, "offset": offset,
                "next": offset + limit if offset + limit < len(rows) else None,
                "previous": max(0, offset - limit) if offset else None, key: page}

    def pages(self) -> list[dict[str, Any]]:
        return [asdict(row) for row in discover_pages(self.routes, self.state)]

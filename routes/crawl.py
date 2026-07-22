"""Public, read-only crawl and discovery routes."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from services.crawl import (
    CRAWL_ENDPOINTS,
    PUBLIC_PAGES,
    SCHEMA_VERSION,
    build_snapshot,
    cached_response,
    public_front_offices,
    public_matchups,
    public_picks,
    public_teams,
    public_trades,
    public_transactions,
    standings,
    supported_leagues,
    sync_metadata,
    validate_league,
)

GetData = Callable[[], dict[str, Any]]


def create_crawl_router(*, get_data: GetData, state: dict[str, Any], league_id: str) -> APIRouter:
    router = APIRouter(tags=["public-crawl"])

    def selected(requested: str | None) -> tuple[dict[str, Any], str]:
        data = get_data()
        try:
            return data, validate_league(data, requested, league_id)
        except KeyError as exc:
            raise CrawlLeagueError(str(exc)) from exc

    def respond(key: str, requested: str | None, factory: Callable[[dict[str, Any]], Any]) -> JSONResponse:
        try:
            data, selected_league = selected(requested)
        except CrawlLeagueError as exc:
            return JSONResponse({"ok": False, "schema_version": SCHEMA_VERSION, "error": "invalid_league", "detail": str(exc)}, status_code=404)
        payload = cached_response(f"{selected_league}:{key}", lambda: factory(data), sync_marker=state.get("last_sync"))
        payload["league_id"] = selected_league
        return JSONResponse(payload, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=60"})

    @router.get("/api/crawl")
    async def crawl_index(league: str | None = None) -> JSONResponse:
        try:
            data, selected_league = selected(league)
        except CrawlLeagueError as exc:
            return JSONResponse({"ok": False, "schema_version": SCHEMA_VERSION, "error": "invalid_league", "detail": str(exc)}, status_code=404)
        payload = cached_response(
            f"{selected_league}:index",
            lambda: {
                "default_league_id": league_id,
                "selected_league_id": selected_league,
                "leagues": supported_leagues(data, league_id),
                "sync": sync_metadata(state),
                "pages": PUBLIC_PAGES,
                "endpoints": CRAWL_ENDPOINTS,
            },
            sync_marker=state.get("last_sync"),
        )
        payload.update(payload.pop("data"))
        return JSONResponse(payload, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=60"})

    @router.get("/api/crawl/snapshot")
    async def crawl_snapshot(league: str | None = None) -> JSONResponse:
        return respond("snapshot", league, lambda data: build_snapshot(data, state, league or league_id))

    @router.get("/api/crawl/teams")
    async def crawl_teams(league: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), team: int | None = None) -> JSONResponse:
        def section(data: dict[str, Any]) -> dict[str, Any]:
            rows = public_teams(data)
            if team is not None:
                rows = [row for row in rows if row["roster_id"] == team]
            return {"count": len(rows), "teams": rows[offset : offset + limit]}
        return respond(f"teams:{limit}:{offset}:{team}", league, section)

    @router.get("/api/crawl/front-offices")
    async def crawl_front_offices(league: str | None = None) -> JSONResponse:
        return respond("front-offices", league, public_front_offices)

    @router.get("/api/crawl/trades")
    async def crawl_trades(league: str | None = None) -> JSONResponse:
        return respond("trades", league, public_trades)

    @router.get("/api/crawl/transactions")
    async def crawl_transactions(league: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), since: datetime | None = None, team: int | None = None) -> JSONResponse:
        def section(data: dict[str, Any]) -> dict[str, Any]:
            rows = public_transactions(data)
            if since is not None:
                rows = [row for row in rows if row.get("timestamp") and datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00")) >= since]
            if team is not None:
                rows = [row for row in rows if str(team) in row.get("roster_ids", [])]
            return {"count": len(rows), "transactions": rows[offset : offset + limit]}
        return respond(f"transactions:{limit}:{offset}:{since}:{team}", league, section)

    @router.get("/api/crawl/matchups")
    async def crawl_matchups(league: str | None = None) -> JSONResponse:
        return respond("matchups", league, public_matchups)

    @router.get("/api/crawl/picks")
    async def crawl_picks(league: str | None = None, season: int | None = None, team: int | None = None) -> JSONResponse:
        def section(data: dict[str, Any]) -> dict[str, Any]:
            result = public_picks(data)
            for key in ("pick_ledger", "traded_picks"):
                rows = result[key]
                if season is not None:
                    rows = [row for row in rows if int(row.get("season") or 0) == season]
                if team is not None:
                    rows = [row for row in rows if team in {row.get("current_owner_id"), row.get("owner_id"), row.get("roster_id")}]
                result[key] = rows
            return result
        return respond(f"picks:{season}:{team}", league, section)

    @router.get("/api/crawl/standings")
    async def crawl_standings(league: str | None = None) -> JSONResponse:
        return respond("standings", league, lambda data: {"standings": standings(data)})

    @router.get("/robots.txt", include_in_schema=False)
    async def robots() -> PlainTextResponse:
        content = "User-agent: *\nAllow: /\nAllow: /api/crawl\nDisallow: /sync\nDisallow: /api/data/refresh\nDisallow: /admin\nDisallow: /debug\nSitemap: https://dtos.onrender.com/sitemap.xml\n"
        return PlainTextResponse(content)

    @router.get("/sitemap.xml", include_in_schema=False)
    async def sitemap() -> Response:
        urls = "".join(f"<url><loc>https://dtos.onrender.com{path}</loc></url>" for path in PUBLIC_PAGES)
        return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>', media_type="application/xml")

    return router


class CrawlLeagueError(ValueError):
    """Internal control-flow exception converted to a stable JSON 404."""

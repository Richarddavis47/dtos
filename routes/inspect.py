"""Authenticated semantic diagnostics over the active league cached state."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder

from app_metadata import BUILD_NUMBER, VERSION, deployment_metadata
from services.history import history_progress_contracts
from src.core.brain import brain_service
from src.core.inspection import (
    INSPECTION_SCHEMA_VERSION,
    InspectionEngine,
    discover_pages,
    excluded_current_trade_pages,
)
from src.core.history_context import canonical_history_store
from src.core.asset_market import asset_market
from src.core.valuation.universe import LAYER_NAMES, ValuationUniverse
from src.core.valuation_intelligence import valuation_intelligence_report
from services.fois import fois_service
from src.core.fois.models import FOIS_MODEL_VERSION
from src.core.inspection.live import LiveInspection, matchup_semantic

historical_store = canonical_history_store


def create_inspection_router(
    *,
    state: dict[str, Any],
    route_provider: Callable[[], Iterable[Any]] = tuple,
    league_id: str | None = None,
    projection_service: Any | None = None,
    market_cache: Any | None = None,
    context_resolver: Callable[[], Any | None] | None = None,
    resource_health: Callable[[], dict[str, Any]] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/inspect", tags=["inspection"])
    def engine() -> InspectionEngine:
        return InspectionEngine(state)

    def dependencies() -> tuple[str, Any | None, Any | None]:
        context = context_resolver() if context_resolver else None
        data = state.get("data") or {}
        selected = (
            context.league_id if context is not None else
            league_id or str((data.get("league") or {}).get("league_id") or "")
        )
        return (
            selected,
            context.projection if context is not None else projection_service,
            context.market if context is not None else market_cache,
        )

    def live() -> LiveInspection:
        selected, projections, selected_market = dependencies()
        scores = fois_service.repository.league(selected, FOIS_MODEL_VERSION) if selected else ()
        return LiveInspection(
            state=state, routes=route_provider(), league_id=selected,
            projection_snapshot=projections.snapshot() if projections else None,
            market=selected_market.current() if selected_market else None,
            fois_scores=tuple(scores),
        )

    def progress_contracts() -> dict[str, Any]:
        selected, _projections, _market = dependencies()
        return history_progress_contracts(selected)

    def historical_progress() -> dict[str, Any]:
        return progress_contracts()["canonical_history_progress"]

    @router.get("")
    async def inspection_index() -> Any:
        return jsonable_encoder(engine().index())

    @router.get("/pages")
    async def inspect_pages() -> Any:
        return jsonable_encoder(engine().pages())

    @router.get("/live")
    async def live_root(refresh: bool = False) -> Any:
        """Canonical current-production inspection entry point."""
        # Refresh is inspection-read-model-only; route discovery is derived anew and
        # never refreshes canonical application state.
        return jsonable_encoder(live().root())

    @router.get("/live/health")
    async def live_health() -> Any:
        return jsonable_encoder(live().health())

    @router.get("/live/surfaces")
    async def live_surfaces(
        limit: int = Query(100, ge=1, le=250), offset: int = Query(0, ge=0),
    ) -> Any:
        inspector = live()
        rows = [jsonable_encoder(row) for row in inspector.surfaces]
        return inspector.page(rows, limit, offset, "surfaces")

    @router.get("/live/surfaces/{surface_id}")
    async def live_surface(surface_id: str) -> Any:
        inspector = live()
        row = next((item for item in inspector.surfaces if item.surface_id == surface_id), None)
        if row is None:
            raise HTTPException(404, "Public surface is not registered.")
        return {"identity": inspector.identity(), "surface": jsonable_encoder(row),
                "technical_details": {"source": "canonical_fastapi_router", "read_only": True}}

    @router.get("/live/teams")
    async def live_teams() -> Any:
        inspector = live()
        rows = [{
            "roster_id": row.get("roster_id"), "team_name": row.get("team_name"),
            "manager": row.get("owner"), "human_url": f"/teams/{row.get('roster_id')}",
            "semantic_url": f"/api/inspect/team/{row.get('roster_id')}",
            "front_office_url": f"/front-offices?front_office={row.get('roster_id')}",
            "fois_url": f"/fois/gms/{row.get('owner_id')}" if row.get("owner_id") else "/fois",
        } for row in inspector.data.get("teams") or []]
        return {"identity": inspector.identity(), "count": len(rows), "teams": rows}

    @router.get("/live/matchups")
    async def live_matchups() -> Any:
        inspector = live()
        rows = []
        for matchup_id, sides in sorted((inspector.data.get("matchups") or {}).items()):
            rows.append({"matchup_id": str(matchup_id),
                         "teams": [side.get("team") for side in sides],
                         "human_url": f"/matchups/{matchup_id}",
                         "semantic_url": f"/api/inspect/live/matchups/{matchup_id}",
                         "status": "current"})
        return {"identity": inspector.identity(), "count": len(rows), "matchups": rows}

    @router.get("/live/matchups/{matchup_id}")
    async def live_matchup(matchup_id: str) -> Any:
        inspector = live()
        result = matchup_semantic(inspector.data, matchup_id, inspector.projection_snapshot)
        if result is None:
            raise HTTPException(404, "Current matchup is unavailable.")
        return {"identity": inspector.identity(), **result, "projection_audit": "/api/audit/projections/current"}

    @router.get("/live/players")
    async def live_players(
        limit: int = Query(100, ge=1, le=250), offset: int = Query(0, ge=0),
    ) -> Any:
        inspector = live()
        owned = {str(player.get("id") or player.get("player_id"))
                 for team in inspector.data.get("teams") or []
                 for player in team.get("players") or []}
        projections = (inspector.projection_snapshot or {}).get("players") or {}
        relevant = owned | set(projections)
        rows = []
        for player_id in sorted(relevant):
            player = (inspector.data.get("players") or {}).get(player_id) or {}
            rows.append({"player_id": player_id,
                         "display_name": player.get("full_name") or player.get("first_name") or player_id,
                         "position": player.get("position"), "nfl_team": player.get("team"),
                         "ownership_state": "rostered" if player_id in owned else "free_agent",
                         "human_url": f"/players/{player_id}",
                         "semantic_url": f"/api/inspect/player/{player_id}"})
        return {"identity": inspector.identity(), **inspector.page(rows, limit, offset, "players")}

    @router.get("/live/picks")
    async def live_picks(
        limit: int = Query(100, ge=1, le=250), offset: int = Query(0, ge=0),
    ) -> Any:
        inspector = live()
        source = (inspector.data.get("pick_ledger") or []) + (inspector.data.get("traded_picks") or [])
        rows = []
        seen = set()
        for pick in source:
            pick_id = str(pick.get("canonical_pick_id") or pick.get("pick_id") or
                          f"PICK-{pick.get('season')}-R{pick.get('round')}-ORIG{pick.get('roster_id')}")
            if pick_id in seen:
                continue
            seen.add(pick_id)
            rows.append({"canonical_pick_id": pick_id, "season": pick.get("season"),
                         "round": pick.get("round"), "original_owner": pick.get("roster_id"),
                         "current_owner": pick.get("current_owner_id") or pick.get("owner_id"),
                         "human_url": f"/picks/{pick_id}",
                         "semantic_url": f"/api/inspect/live/picks?query={pick_id}"})
        return {"identity": inspector.identity(), **inspector.page(rows, limit, offset, "picks")}

    @router.get("/live/seasons")
    async def live_seasons() -> Any:
        inspector = live()
        progress = history_progress_contracts(inspector.league_id)["canonical_history_progress"]
        rows = [{"season": season, "status": "completed" if season in progress.get("completed_seasons", []) else "pending",
                 "human_url": f"/history/{season}",
                 "semantic_url": f"/api/crawl/history/seasons?season={season}"}
                for season in progress.get("configured_seasons") or []]
        return {"identity": inspector.identity(), "count": len(rows), "seasons": rows}

    @router.get("/live/apis")
    async def live_apis(
        limit: int = Query(100, ge=1, le=250), offset: int = Query(0, ge=0),
    ) -> Any:
        inspector = live()
        rows = [jsonable_encoder(row) for row in inspector.surfaces
                if row.surface_type == "api" and row.inspection_enabled]
        return {"identity": inspector.identity(), **inspector.page(rows, limit, offset, "apis")}

    @router.get("/live/search")
    async def live_search(q: str = Query(..., min_length=1), limit: int = Query(25, ge=1, le=100)) -> Any:
        inspector = live()
        needle = q.casefold()
        rows = [jsonable_encoder(row) for row in inspector.surfaces
                if needle in f"{row.title} {row.category} {row.route}".casefold()][:limit]
        for matchup_id, sides in sorted((inspector.data.get("matchups") or {}).items()):
            title = f"Matchup {matchup_id}: " + " vs ".join(str(side.get("team")) for side in sides)
            if needle not in title.casefold():
                continue
            rows.insert(0, {
                "surface_id": f"matchups-{matchup_id}", "title": title,
                "human_url": f"/matchups/{matchup_id}",
                "semantic_url": f"/api/inspect/live/matchups/{matchup_id}",
            })
        rows = rows[:limit]
        return {"identity": inspector.identity(), "query": q, "count": len(rows), "results": rows}

    def canonical_trade_discovery() -> dict[str, Any]:
        selected, _projections, _market = dependencies()
        records = (
            historical_store.discoverable_trade_records(selected)
            if selected else []
        )
        return {
            "dataset_version": (
                historical_store.dataset_version(selected) if selected else None
            ),
            "transaction_ids": tuple(
                str(row["source_record_id"]) for row in records
            ),
            "status_rule": "complete_or_completed",
            "source": "durable_historical_memory",
        }

    def page_catalog() -> tuple[Any, ...]:
        trades = canonical_trade_discovery()
        return discover_pages(
            route_provider(), state,
            historical_trades=trades["transaction_ids"],
        )

    @router.get("/pages/{page_id}")
    async def inspect_page(page_id: str) -> Any:
        page = next((row for row in page_catalog() if row.page_id == page_id), None)
        if page is None:
            raise HTTPException(404, "Inspection page ID is not registered.")
        progress = progress_contracts()
        return {
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "page": jsonable_encoder(page),
            "historical_progress": progress["canonical_history_progress"],
            "history_progress_contracts": progress,
        }

    @router.get("/team/{roster_id}")
    async def inspect_team(roster_id: int) -> Any:
        result = engine().team(roster_id)
        if result is None:
            raise HTTPException(404, "Team not found in cached state.")
        return jsonable_encoder(result)

    @router.get("/player/{player_id}")
    async def inspect_player(player_id: str) -> Any:
        result = engine().player(player_id)
        if result is None:
            raise HTTPException(404, "Player not found in cached state.")
        return jsonable_encoder(result)

    @router.get("/front-office/{roster_id}")
    async def inspect_front_office(roster_id: int) -> Any:
        result = engine().front_office(roster_id)
        if result is None:
            raise HTTPException(404, "Front Office not found in cached state.")
        return jsonable_encoder(result)

    @router.get("/trades")
    async def inspect_trades() -> Any:
        return jsonable_encoder(engine().trades())

    @router.get("/fois")
    async def inspect_fois() -> Any:
        """Inspect persisted FOIS summaries without generation or provider access."""
        selected, _projections, _market = dependencies()
        scores = fois_service.repository.league(selected, FOIS_MODEL_VERSION) if selected else ()
        scores = tuple(sorted(scores, key=lambda row: (
            -(row.overall_score if row.overall_score is not None else -1),
            -row.confidence, row.gm_id or "",
        )))
        health = (
            fois_service.repository.canonical_health(selected, FOIS_MODEL_VERSION)
            if selected else {
                "current_gm_count": 0, "current_canonical_count": 0,
                "duplicate_current_count": 0, "historical_snapshot_count": 0,
            }
        )
        return jsonable_encoder({
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "page_name": "FOIS League Overview",
            "route": "/fois",
            "sections": ["Current GM Leaderboard", "GM Quality vs Team Quality", "Evidence Confidence", "GM History"],
            **health,
            "cards": [{"rank": rank, "gm_id": row.gm_id, "gm_name": row.gm_name,
                       "franchise_name": row.franchise_name,
                       "evaluation_kind": row.evaluation_kind,
                       "executive_score": row.overall_score,
                       "grade": row.overall_letter_grade,
                       "current_team_score": row.current_team_score,
                       "confidence": row.confidence, "completeness": row.completeness,
                       "supported_weight": row.supported_weight,
                       "evidence_state": row.evidence_state}
                      for rank, row in enumerate(scores, 1)],
            "tables": ["GM Rankings"], "charts": ["Executive Score by Category"],
            "buttons": ["Executive Profile", "Compare GMs"],
            "navigation": ["Commissioner Desk", "Team Headquarters", "Front Office"],
            "links": [{"label": "FOIS", "route": "/fois"}],
            "empty_states": [] if scores else ["FOIS generation has not completed."],
            "placeholder_actions": [],
            "warnings": [warning for row in scores for warning in row.warnings],
            "page_metrics": {"card_count": len(scores), "button_count": 2,
                             "table_count": 1, "chart_count": 1},
            "last_updated": max((row.generated_at for row in scores), default=None),
            "fois_model_version": FOIS_MODEL_VERSION,
        })

    @router.get("/valuation")
    async def inspect_valuation() -> Any:
        """Inspect the live valuation contract without provider calls or state changes."""
        data = state.get("data") or {}
        universe = ValuationUniverse(data, state)
        calibration = data.get("calibration_report") or {}
        provider_network = data.get("provider_network") or {}
        valuation_intelligence = valuation_intelligence_report(data)
        samples = [universe.assets[0], next((row for row in universe.assets if row["asset_type"] == "pick"), None)] if universe.assets else []
        return jsonable_encoder({
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "page_name": "Valuation API",
            "route": "/api/valuation",
            "status": universe.status(),
            "valuation_layers": LAYER_NAMES,
            "sample_assets": [row for row in samples if row is not None],
            "market_calibration": {
                "schema_version": calibration.get("schema_version"),
                "summary": calibration.get("summary") or {},
                "recommendation_count": len(calibration.get("recommendations") or []),
                "last_calibration_timestamp": calibration.get("generated_at"),
            },
            "provider_network": {
                "provider_registry_version": provider_network.get("provider_registry_version"),
                "evidence_contract_version": provider_network.get("evidence_contract_version"),
                "provider_count": len(provider_network.get("providers") or []),
                "evidence_summary": provider_network.get("evidence_summary") or {},
                "consensus": provider_network.get("consensus") or {},
                "observed_market": provider_network.get("observed_market") or {},
                "safety": provider_network.get("safety") or {},
            },
            "valuation_intelligence": {
                "schema_version": valuation_intelligence.get("schema_version"),
                "availability": valuation_intelligence.get("availability"),
                "asset_count": valuation_intelligence.get("asset_count", 0),
                "summary": valuation_intelligence.get("summary") or {},
                "diagnostics": {key: len(value) for key, value in (valuation_intelligence.get("diagnostics") or {}).items()},
                "safety": valuation_intelligence.get("safety") or {},
                "sample_assets": list((valuation_intelligence.get("assets") or {}).values())[:2],
            },
            "warnings": universe.freshness["reasons"],
        })

    @router.get("/market")
    async def inspect_market() -> Any:
        """Inspect the cached Asset Market without synchronization or mutation."""
        selected, _projections, selected_cache = dependencies()
        context = context_resolver() if context_resolver else None
        market = (
            selected_cache.get(
                state.get("data") or {}, state, historical_store, selected,
                background=True,
            ) if context is not None else
            asset_market(state.get("data") or {}, state, historical_store, selected)
        )
        directory = market.directory(limit=5)
        trending = market.trending(limit=3)
        progress = progress_contracts()
        return jsonable_encoder({
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "page_name": "Asset Market & Dynasty Exchange",
            "route": "/market",
            "market_identity": market.identity(),
            "market_health": market.health(),
            "sample_rankings": directory["assets"],
            "trending": trending,
            "historical_progress": progress["canonical_history_progress"],
            "history_progress_contracts": progress,
            "warnings": (
                [trending["unavailable_reason"]]
                if trending["availability"] == "unavailable" else []
            ),
        })

    @router.get("/brain")
    async def inspect_brain() -> Any:
        """Inspect the canonical cached Brain and migration contract."""
        brain = brain_service(state.get("data") or {})
        return jsonable_encoder({
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "page_name": "DTOS Brain",
            "route": "/brain",
            "health": brain.health(),
            "migration": brain.migration(),
            "warnings": [] if brain.report.get("availability") == "available" else ["The synchronized Brain snapshot is pending."],
        })

    @router.get("/site-map")
    async def inspection_site_map() -> Any:
        pages = page_catalog()
        trade_discovery = canonical_trade_discovery()
        exclusions = excluded_current_trade_pages(
            state, trade_discovery["transaction_ids"],
        )
        return {
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "pages": jsonable_encoder(pages),
            "dynamic_discovery": {
                "historical_trades": trade_discovery,
                "exclusions": jsonable_encoder(exclusions),
            },
            "metrics": {"total": len(pages), "inspectable": sum(not page.excluded for page in pages), "excluded": sum(page.excluded for page in pages)},
        }

    @router.get("/schema")
    async def inspection_schema() -> Any:
        return {"application_version": VERSION, "application_build": BUILD_NUMBER,
                "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
                "contracts": ["semantic", "numeric", "active_league", "read_only"]}

    @router.get("/health")
    async def inspection_health() -> Any:
        progress = progress_contracts()
        deployment = deployment_metadata()
        return {
            "application_version": VERSION, "application_build": BUILD_NUMBER,
            "current_production_commit": deployment["commit"],
            "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
            "status": "available", "mode": "semantic_read_only",
            "historical_progress": progress["canonical_history_progress"],
            "history_progress_contracts": progress,
            "resource_health": resource_health() if resource_health else None,
        }

    return router

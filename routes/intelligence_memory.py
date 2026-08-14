"""Public-safe diagnostics for Sleeper-backed cache and DTOS intelligence memory."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.core.intelligence_memory import (
    DATA_OWNERSHIP, intelligence_checkpoint_store, sleeper_season_cache,
)
from src.core.intelligence_memory.sleeper_source import SleeperHistoricalSource


def create_intelligence_memory_router(
    *, default_league_id: str, secondary_import_enabled: bool = False,
    source: SleeperHistoricalSource | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/intelligence-memory", tags=["intelligence-memory"])
    source = source or SleeperHistoricalSource()

    @router.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "checkpoint_store": intelligence_checkpoint_store.health(),
            "provider_cache": sleeper_season_cache.health(),
            "storage_estimates": intelligence_checkpoint_store.storage_estimates(),
            "data_ownership": DATA_OWNERSHIP,
            "legacy_historical_memory": "preserved_no_destructive_migration",
            "automatic_backfill": False,
        }

    @router.post("/leagues/{league_id}/discover")
    async def discover(league_id: str) -> JSONResponse:
        if str(league_id) != str(default_league_id) and not secondary_import_enabled:
            return JSONResponse({
                "status": "feature_gated",
                "reason": "Secondary-league historical discovery is disabled.",
            }, status_code=403)
        chain = await source.discover(str(league_id))
        return JSONResponse({
            "status": "complete" if chain.terminated else "partial",
            "source_of_truth": "sleeper",
            "historical_memory_fallback": False,
            "fixed_start_year": None,
            "chain": chain.public(),
        })

    @router.post("/leagues/{league_id}/seasons/{season}/cache")
    async def cache_season(league_id: str, season: int) -> JSONResponse:
        if str(league_id) != str(default_league_id) and not secondary_import_enabled:
            return JSONResponse({"status": "feature_gated"}, status_code=403)
        result = await sleeper_season_cache.get_or_rebuild(
            str(league_id), int(season), source.completed_season_facts,
        )
        return JSONResponse({
            "status": result.status, "season": result.season,
            "source_of_truth": "sleeper", "cache_role": "disposable",
            "checksum": result.checksum, "completeness": result.completeness,
            "historical_memory_fallback": False,
        })

    return router

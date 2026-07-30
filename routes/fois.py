"""Feature-flagged API surface for Front Office Intelligence System scores."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder

from src.core.fois.configuration import DEFAULT_FOIS_CONFIGURATION
from src.core.fois.models import FOIS_MODEL_VERSION
from src.core.fois.registry import DEFAULT_METRIC_REGISTRY
from src.core.fois.service import FOISService, fois_enabled


def create_fois_router(
    *,
    service: FOISService,
    require_data: Callable[[], dict[str, Any]],
) -> APIRouter:
    router = APIRouter(prefix="/api/fois", tags=["fois"])

    def require_enabled() -> None:
        if not fois_enabled():
            raise HTTPException(404, "FOIS is disabled.")

    @router.get("/status")
    async def status() -> dict[str, Any]:
        return service.status()

    @router.get("/model")
    async def model() -> dict[str, Any]:
        require_enabled()
        return jsonable_encoder({
            "configuration": asdict(DEFAULT_FOIS_CONFIGURATION),
            "metrics": [asdict(metric) for metric in DEFAULT_METRIC_REGISTRY],
        })

    @router.post("/leagues/{league_id}/calculate")
    async def calculate(league_id: str) -> dict[str, Any]:
        require_enabled()
        data = require_data()
        actual_id = str((data.get("league") or {}).get("league_id") or league_id)
        if actual_id != league_id:
            raise HTTPException(404, "The requested league is not loaded.")
        scores = await service.generate(data)
        return jsonable_encoder({"league_id": league_id, "scores": scores})

    @router.get("/leagues/{league_id}")
    async def league(league_id: str) -> dict[str, Any]:
        require_enabled()
        scores = service.repository.league(league_id, FOIS_MODEL_VERSION)
        return jsonable_encoder({"league_id": league_id, "scores": scores})

    @router.get("/leagues/{league_id}/franchises/{franchise_id}")
    async def franchise(league_id: str, franchise_id: str) -> Any:
        require_enabled()
        score = service.repository.get(league_id, franchise_id, FOIS_MODEL_VERSION)
        if score is None:
            raise HTTPException(404, "No FOIS score exists for this franchise.")
        return jsonable_encoder(score)

    @router.get("/leagues/{league_id}/franchises/{franchise_id}/categories")
    async def categories(league_id: str, franchise_id: str) -> Any:
        score = await franchise(league_id, franchise_id)
        return {"categories": score["category_scores"]}

    @router.get("/leagues/{league_id}/franchises/{franchise_id}/metrics")
    async def metrics(league_id: str, franchise_id: str) -> Any:
        score = await franchise(league_id, franchise_id)
        return {
            "metrics": [
                metric
                for category in score["category_scores"]
                for metric in category["metric_scores"]
            ]
        }

    @router.get("/leagues/{league_id}/franchises/{franchise_id}/results")
    async def results(league_id: str, franchise_id: str) -> Any:
        score = await franchise(league_id, franchise_id)
        category = next(
            (
                row
                for row in score["category_scores"]
                if row["category_key"] == "results"
            ),
            None,
        )
        if category is None:
            raise HTTPException(404, "No Results score exists for this franchise.")
        return category

    @router.get("/leagues/{league_id}/completeness")
    async def completeness(league_id: str) -> dict[str, Any]:
        require_enabled()
        scores = service.repository.league(league_id, FOIS_MODEL_VERSION)
        return {
            "league_id": league_id,
            "franchises": [
                {
                    "franchise_id": score.franchise_id,
                    "completeness": score.completeness,
                    "confidence": score.confidence,
                    "provisional": score.provisional,
                }
                for score in scores
            ],
        }

    return router

"""Read-only projection and intelligence audit exports."""
from __future__ import annotations

import csv
import io
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from services.projection_audit import build_projection_audit
from src.core.fois.models import FOIS_MODEL_VERSION


def create_audit_router(
    *, require_data: Callable[[], dict[str, Any]], projection_service: Any,
    market_cache: Any, fois_service: Any,
) -> APIRouter:
    router = APIRouter(prefix="/api/audit", tags=["Audit"])

    def current() -> dict[str, Any]:
        data = require_data()
        projection = projection_service.snapshot()
        market = market_cache.current()
        if projection is None:
            raise HTTPException(503, "Projection Intelligence snapshot is unavailable.")
        if market is None:
            raise HTTPException(503, "A retained Asset Market generation is unavailable.")
        league_id = str((data.get("league") or {}).get("league_id") or market.league_id)
        scores = tuple(fois_service.repository.league(league_id, FOIS_MODEL_VERSION))
        return build_projection_audit(
            data=data, projection_snapshot=projection,
            projection_health=projection_service.health(include_accuracy=False), market=market,
            fois_scores=scores,
        )

    @router.get("/projections/current")
    async def projections_current() -> dict[str, Any]:
        return current()

    @router.get("/projections/current.csv")
    async def projections_current_csv() -> Response:
        audit = current()
        columns = (
            "matchup_id", "team", "player_id", "player_name", "position",
            "sleeper_projection", "dtos_projection", "canonical_projection",
            "dtos_minus_sleeper", "actual_points", "market_value",
            "intrinsic_dtos_value", "contender_value", "rebuilder_value",
            "overall_rank", "contender_rank", "rebuilder_rank",
            "projection_confidence", "projection_agreement",
        )
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for player in audit["players"]:
            values = player.get("values") or {}
            writer.writerow({key: values.get(key) if key in values else player.get(key) for key in columns})
        return Response(stream.getvalue(), media_type="text/csv", headers={
            "Content-Disposition": "attachment; filename=dtos-projection-audit.csv",
        })

    return router

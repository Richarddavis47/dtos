"""Application boundary for historical evidence capture and queries."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from config import LEAGUE_ID, REQUEST_TIMEOUT
from src.core.historical_memory import (
    HISTORICAL_SCHEMA_VERSION,
    PLAYER_HISTORY_SCHEMA_VERSION,
    PREDICTION_MODEL_VERSION,
    aggregate_production,
    historical_store,
)
from src.core.historical_memory.importer import HistoricalImporter
from src.core.intelligence import intelligence_orchestrator
from src.core.valuation import VALUATION_SCHEMA_VERSION, normalize_value

_BACKFILL_LOCK = asyncio.Lock()
_BACKFILL_TASK: asyncio.Task[dict[str, Any]] | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def capture_current_state(data: dict[str, Any], observed_at: str) -> dict[str, int]:
    """Append current evidence without replacing any earlier observation."""
    league = data.get("league") or {}
    league_id = str(league.get("league_id") or LEAGUE_ID)
    season = int(league.get("season") or datetime.now().year)
    week = int(data.get("week") or 1)
    counts = {"written": 0, "unchanged": 0}

    def append(entity: str, source_id: str, payload: dict[str, Any], **dimensions: Any) -> None:
        identity_variant = dimensions.pop("identity_variant", "")
        key = (
            f"{league_id}:{entity}:{season}:{week}:{observed_at}:"
            f"{source_id}:{identity_variant}"
        )
        inserted = historical_store.append(
            record_key=key, entity_type=entity, league_id=league_id,
            season=season, week=dimensions.pop("week", week),
            source_record_id=source_id, observed_at=observed_at,
            retrieved_at=observed_at, provider=dimensions.pop("provider", "DTOS"),
            availability=dimensions.pop("availability", "observed"),
            confidence=dimensions.pop("confidence", 90),
            calculation_method=dimensions.pop("calculation_method", "current_sync_snapshot"),
            schema_version=dimensions.pop("schema_version", HISTORICAL_SCHEMA_VERSION),
            payload=payload, **dimensions,
        )
        counts["written" if inserted else "unchanged"] += 1

    append("league_season_snapshot", league_id, {
        "league": league, "scoring_settings": data.get("scoring_settings") or {},
        "roster_positions": data.get("roster_positions") or [],
        "league_settings": data.get("league_settings") or {},
    })
    normalized_players = data.get("normalized_players") or {}
    for player_id, player in normalized_players.items():
        historical_store.upsert_identity(
            str(player_id), "Sleeper", str(player_id),
            str(player.get("name") or player_id), 100, observed_at,
            {"provider_ids": player.get("provider_ids") or {}, "aliases": player.get("aliases") or []},
        )
    for team in data.get("teams") or []:
        roster_id = int(team.get("roster_id") or 0)
        franchise_id = f"{league_id}:franchise:{roster_id}"
        append("weekly_roster_snapshot", str(roster_id), {
            "players": [player.get("id") for player in team.get("players") or []],
            "starters": [player.get("id") for player in team.get("players") or [] if player.get("roster_slot") == "Starter"],
            "bench": [player.get("id") for player in team.get("players") or [] if player.get("roster_slot") == "Bench"],
            "taxi": [player.get("id") for player in team.get("players") or [] if player.get("roster_slot") == "Taxi"],
            "ir": [player.get("id") for player in team.get("players") or [] if player.get("roster_slot") == "IR"],
        }, franchise_id=franchise_id)
    if data.get("teams"):
        intelligence = intelligence_orchestrator.analyze(
            data, int(data["teams"][0].get("roster_id") or 0),
        )
        cards = intelligence.roster.team_intelligence
        for roster_id, card in cards.items():
            franchise_id = f"{league_id}:franchise:{roster_id}"
            payload = asdict(card)
            payload["snapshot_type"] = "current_team_intelligence"
            payload["model_version"] = PREDICTION_MODEL_VERSION
            append(
                "team_intelligence_snapshot", str(roster_id), payload,
                franchise_id=franchise_id, derived=True,
                availability="calculated", confidence=card.confidence,
                calculation_method="Team Intelligence v1.0",
                identity_variant=(
                    f"current_team_intelligence:{PREDICTION_MODEL_VERSION}"
                ),
            )
            append("prediction", f"team:{roster_id}", {
                "snapshot_type": "team_preseason_prediction",
                "prediction_type": "team_preseason",
                "projected_finish": card.projected_finish,
                "playoff_odds": card.playoff_odds,
                "championship_odds": card.championship_odds,
                "projected_wins": card.projected_wins,
                "team_tier": card.current_window.value,
                "model_version": PREDICTION_MODEL_VERSION,
                "inputs_version": HISTORICAL_SCHEMA_VERSION,
                "actual_result": None,
                "evaluation_date": None,
            }, franchise_id=franchise_id, derived=True, availability="calculated",
               identity_variant=(
                   f"team_preseason_prediction:{PREDICTION_MODEL_VERSION}"
               ))
        for player_id, card in intelligence.roster.players.items():
            append("valuation_snapshot", f"DTOS:{player_id}", {
                "provider": "DTOS", "raw_provider_value": None,
                "normalized_provider_value": card.market_value,
                "market_value": card.market_value,
                "dtos_intrinsic_value": card.dynasty_value,
                "win_now_value": card.contender_value,
                "rebuild_value": card.rebuilder_value,
                "future_value": card.dynasty_value,
                "trade_value": card.dynasty_value,
                "risk_score": card.risk,
                "liquidity_score": card.trade_liquidity,
                "confidence_score": None,
                "valuation_model_version": VALUATION_SCHEMA_VERSION,
                "calibration_status": "calculated",
            }, player_id=str(player_id), provider="DTOS",
               availability="calculated", calculation_method="Valuation Calibration v1.0")
    for provider, rows in ((data.get("market_data") or {}).get("providers") or {}).items():
        distribution = tuple(
            float(row.get("value"))
            for row in (rows or {}).values()
            if isinstance(row, dict) and row.get("value") is not None
        )
        for player_id, row in (rows or {}).items():
            if not isinstance(row, dict):
                continue
            normalized = (
                normalize_value(
                    provider, float(row["value"]), distribution=distribution,
                    updated_at=row.get("updated_at"), source_season=row.get("season"),
                    provider_confidence=int(row.get("confidence") or 70),
                )
                if row.get("value") is not None else None
            )
            append("valuation_snapshot", f"{provider}:{player_id}", {
                "provider": provider, "raw_provider_value": row.get("value"),
                "normalized_provider_value": normalized.normalized_value if normalized else None,
                "market_value": normalized.normalized_value if normalized else None,
                "confidence_score": normalized.confidence_score if normalized else 0,
                "valuation_model_version": VALUATION_SCHEMA_VERSION,
                "calibration_status": "calibrated" if normalized else "insufficient_data",
                "normalization_method": normalized.method if normalized else None,
                "freshness": normalized.freshness if normalized else None,
            }, player_id=str(player_id), provider=provider,
               availability="observed" if row.get("value") is not None else "unavailable")
    return counts


async def backfill_history(
    fetch: Any, *, league_id: str = LEAGUE_ID, seasons: set[int] | None = None,
) -> dict[str, Any]:
    async with _BACKFILL_LOCK:
        workbook = Path("/mnt/data/Day_Traders_Front_Office_Database_v13_8_Master(1).xlsx")
        return await HistoricalImporter(historical_store, fetch).backfill(
            league_id, earliest=2021, workbook=workbook, seasons=seasons,
        )


async def ensure_history_backfill(fetch: Any, *, league_id: str = LEAGUE_ID) -> dict[str, Any]:
    existing = historical_store.import_status(league_id)
    if existing and existing[0]["status"] == "complete":
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(existing[0]["completed_at"])
        except (TypeError, ValueError):
            age = None
        if age is not None and age.total_seconds() < 86400:
            return {
                "status": "current", "run_id": existing[0]["run_id"],
                "reason": "A complete backfill finished within the last 24 hours.",
            }
    return await backfill_history(fetch, league_id=league_id)


def start_background_backfill(fetch: Any) -> asyncio.Task[dict[str, Any]]:
    global _BACKFILL_TASK
    if _BACKFILL_TASK is None or _BACKFILL_TASK.done():
        _BACKFILL_TASK = asyncio.create_task(ensure_history_backfill(fetch))
    return _BACKFILL_TASK


async def direct_fetch(path: str) -> Any:
    from services.sleeper import request_headers, sleeper_get

    async with httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT), headers=request_headers()) as client:
        return await sleeper_get(client, path)


def history_records(
    league_id: str, entity_type: str | None, *, season: int | None = None,
    week: int | None = None, franchise_id: str | None = None,
    player_id: str | None = None, limit: int = 100, offset: int = 0,
) -> dict[str, Any]:
    count, rows = historical_store.records(
        league_id, entity_type, season=season, week=week,
        franchise_id=franchise_id, player_id=player_id, limit=limit, offset=offset,
    )
    return {
        "schema_version": HISTORICAL_SCHEMA_VERSION,
        "player_history_schema_version": PLAYER_HISTORY_SCHEMA_VERSION,
        "count": count, "limit": limit, "offset": offset, "records": rows,
    }


def player_career(league_id: str, player_id: str) -> dict[str, Any]:
    count, rows = historical_store.records(league_id, "player_week", player_id=player_id, limit=1000)
    by_season: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_season.setdefault(int(row["season"]), []).append(row["payload"])
    return {
        "schema_version": PLAYER_HISTORY_SCHEMA_VERSION, "player_id": player_id,
        "weekly_record_count": count,
        "seasons": {
            str(season): aggregate_production(payloads)
            for season, payloads in sorted(by_season.items())
        },
        "usage": {
            "availability": "provider_not_supported",
            "reason": "Sleeper historical league endpoints do not supply advanced snap, route, target, or carry usage.",
        },
    }


def player_history_evidence(league_id: str, player_id: str) -> dict[str, Any]:
    count, rows = historical_store.records(
        league_id, "player_week", player_id=player_id, limit=1000,
    )
    summary = aggregate_production([row["payload"] for row in rows])
    return {
        **summary, "weekly_record_count": count,
        "source": "Historical League Memory", "schema_version": PLAYER_HISTORY_SCHEMA_VERSION,
    }


def import_status(league_id: str) -> dict[str, Any]:
    runs = historical_store.import_status(league_id)
    return {
        "schema_version": HISTORICAL_SCHEMA_VERSION,
        "runs": runs,
        "latest": runs[0] if runs else {
            "status": "waiting", "reason": "Historical backfill has not started."
        },
    }


def data_quality(league_id: str) -> dict[str, Any]:
    issues = historical_store.quality(league_id)
    return {
        "schema_version": HISTORICAL_SCHEMA_VERSION,
        "issues": issues,
        "blocking_count": sum(item["severity"] == "blocking" and not item["resolved"] for item in issues),
        "warning_count": sum(item["severity"] == "warning" and not item["resolved"] for item in issues),
        "informational_count": sum(item["severity"] == "informational" and not item["resolved"] for item in issues),
    }

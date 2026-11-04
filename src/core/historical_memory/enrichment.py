"""Player-week enrichment through approved provider adapters."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from src.core.historical_memory.models import (
    HISTORICAL_SCHEMA_VERSION,
    IMPORTER_VERSION,
)
from src.core.historical_memory.scoring import calculate_fantasy_points
from src.core.historical_memory.store import HistoricalStore


@dataclass(frozen=True)
class IdentityContext:
    gsis_to_dtos: dict[str, str]
    canonical_count: int
    gsis_count: int
    latest_identity_at: str | None
    build_ms: float


def build_identity_context(store: HistoricalStore) -> IdentityContext:
    started = perf_counter()
    resolved: dict[str, str] = {}
    canonical_count = 0
    for identity in store.iter_current_identity_mappings():
        canonical_count += 1
        candidate = identity.get("gsis_id")
        if candidate and int(identity["confidence"]) >= 70:
            resolved[str(candidate)] = str(identity["dtos_player_id"])
    return IdentityContext(
        gsis_to_dtos=resolved,
        canonical_count=canonical_count,
        gsis_count=len(resolved),
        latest_identity_at=None,
        build_ms=round((perf_counter() - started) * 1000, 3),
    )


def prepare_enrichment_records(
    league_id: str, rows: list[dict[str, Any]],
    scoring_settings: dict[str, Any], identity_context: IdentityContext,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Prepare one bounded raw/derived batch without opening a transaction."""
    mapped = identity_context.gsis_to_dtos
    raw_records: list[dict[str, Any]] = []
    derived_records: list[dict[str, Any]] = []
    unresolved = 0
    retrieved = datetime.now(timezone.utc).isoformat()
    for row in rows:
        provider_player_id = str(row.get("provider_player_id") or "")
        player_id = mapped.get(provider_player_id)
        if not player_id:
            unresolved += 1
            continue
        season = int(row["season"])
        week = int(row["week"])
        provider_record_id = str(row["provider_record_id"])
        raw_records.append({
            "record_key": (
                f"{league_id}:player_raw_week:{season}:{week}:"
                f"{row['provider']}:{provider_record_id}:{IMPORTER_VERSION}"
            ),
            "entity_type": "player_raw_week", "league_id": league_id,
            "season": season, "week": week, "player_id": player_id,
            "source_record_id": provider_record_id, "observed_at": retrieved,
            "retrieved_at": retrieved, "provider": str(row["provider"]),
            "availability": "observed", "confidence": int(row["confidence"]),
            "calculation_method": "provider_record",
            "schema_version": HISTORICAL_SCHEMA_VERSION, "payload": row,
        })
        scoring = calculate_fantasy_points(row["raw_stats"], scoring_settings)
        derived_records.append({
            "record_key": (
                f"{league_id}:player_fantasy_week:{season}:{week}:"
                f"{player_id}:{IMPORTER_VERSION}"
            ),
            "entity_type": "player_fantasy_week", "league_id": league_id,
            "season": season, "week": week, "player_id": player_id,
            "source_record_id": provider_record_id, "observed_at": retrieved,
            "retrieved_at": retrieved, "provider": "DTOS",
            "availability": scoring["availability"],
            "confidence": int(scoring["confidence"]),
            "calculation_method": "league_scoring_engine:1.1", "derived": True,
            "schema_version": HISTORICAL_SCHEMA_VERSION,
            "payload": {
                **scoring, "scoring_settings": scoring_settings,
                "raw_stats_provider": row["provider"],
                "raw_stats_version": IMPORTER_VERSION,
            },
        })
    return raw_records, derived_records, unresolved


def enrich_rows(
    store: HistoricalStore, league_id: str, rows: list[dict[str, Any]],
    scoring_settings: dict[str, Any],
    identity_context: IdentityContext | None = None,
) -> dict[str, int]:
    """Persist one bounded batch through the shared transaction boundary."""
    context = identity_context or build_identity_context(store)
    raw_records, derived_records, unresolved = prepare_enrichment_records(
        league_id, rows, scoring_settings, context,
    )
    written, unchanged = store.append_many([*raw_records, *derived_records])
    return {"written": written, "unchanged": unchanged, "unresolved": unresolved}

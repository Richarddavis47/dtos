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
    identities = store.identities()
    latest: str | None = None
    for identity in identities:
        valid_from = str(identity.get("valid_from") or "")
        latest = max(latest, valid_from) if latest else valid_from or None
        provider_ids = identity["metadata"].get("provider_ids") or {}
        candidate = provider_ids.get("GSIS") or provider_ids.get("gsis_id")
        if candidate and identity["confidence"] >= 70:
            resolved[str(candidate)] = str(identity["dtos_player_id"])
    return IdentityContext(
        gsis_to_dtos=resolved,
        canonical_count=len(identities),
        gsis_count=len(resolved),
        latest_identity_at=latest,
        build_ms=round((perf_counter() - started) * 1000, 3),
    )


def enrich_rows(
    store: HistoricalStore, league_id: str, rows: list[dict[str, Any]],
    scoring_settings: dict[str, Any],
    identity_context: IdentityContext | None = None,
) -> dict[str, int]:
    """Persist versioned raw stats and reproducible league fantasy scoring."""
    mapped = (
        identity_context.gsis_to_dtos
        if identity_context is not None
        else build_identity_context(store).gsis_to_dtos
    )
    counts = {"written": 0, "unchanged": 0, "unresolved": 0}
    retrieved = datetime.now(timezone.utc).isoformat()
    for row in rows:
        provider_player_id = str(row.get("provider_player_id") or "")
        player_id = mapped.get(provider_player_id)
        if not player_id:
            counts["unresolved"] += 1
            continue
        season = int(row["season"])
        week = int(row["week"])
        provider_record_id = str(row["provider_record_id"])
        raw_inserted = store.append(
            record_key=(
                f"{league_id}:player_raw_week:{season}:{week}:"
                f"{row['provider']}:{provider_record_id}:{IMPORTER_VERSION}"
            ),
            entity_type="player_raw_week", league_id=league_id,
            season=season, week=week, player_id=player_id,
            source_record_id=provider_record_id, observed_at=retrieved,
            retrieved_at=retrieved, provider=str(row["provider"]),
            availability="observed", confidence=int(row["confidence"]),
            calculation_method="provider_record",
            schema_version=HISTORICAL_SCHEMA_VERSION, payload=row,
        )
        counts["written" if raw_inserted else "unchanged"] += 1
        scoring = calculate_fantasy_points(row["raw_stats"], scoring_settings)
        fantasy_inserted = store.append(
            record_key=(
                f"{league_id}:player_fantasy_week:{season}:{week}:"
                f"{player_id}:{IMPORTER_VERSION}"
            ),
            entity_type="player_fantasy_week", league_id=league_id,
            season=season, week=week, player_id=player_id,
            source_record_id=provider_record_id, observed_at=retrieved,
            retrieved_at=retrieved, provider="DTOS",
            availability=scoring["availability"],
            confidence=int(scoring["confidence"]),
            calculation_method="league_scoring_engine:1.1",
            derived=True, schema_version=HISTORICAL_SCHEMA_VERSION,
            payload={
                **scoring, "scoring_settings": scoring_settings,
                "raw_stats_provider": row["provider"],
                "raw_stats_version": IMPORTER_VERSION,
            },
        )
        counts["written" if fantasy_inserted else "unchanged"] += 1
    return counts

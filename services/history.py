"""Application boundary for historical evidence capture and queries."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from config import ENRICHMENT_BATCH_SIZE, LEAGUE_ID, REQUEST_TIMEOUT
from src.core.historical_memory import (
    HISTORICAL_SCHEMA_VERSION,
    PLAYER_HISTORY_SCHEMA_VERSION,
    PREDICTION_MODEL_VERSION,
    aggregate_production,
    historical_store,
)
from src.core.historical_memory.importer import HistoricalImporter
from src.core.historical_memory.enrichment import (
    build_identity_context,
    prepare_enrichment_records,
)
from src.core.historical_memory.jobs import (
    ImportJob,
    completeness_report,
    recover_stalled_jobs,
    utcnow,
)
from src.core.historical_memory.models import IMPORTER_VERSION
from src.core.historical_memory.providers import (
    NflverseProvider,
    classify_nflverse_404,
)
from src.core.historical_memory.season_state import classify_season
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


async def wait_for_historical_lease(
    league_id: str, *, poll_seconds: float = 30.0,
) -> int:
    """Wait for a live lease or atomically recover it after its heartbeat expires."""
    while True:
        locks = [
            row for row in historical_store.locks()
            if str(row.get("lock_key") or "").startswith(f"{league_id}:")
        ]
        if not locks:
            return recover_stalled_jobs(historical_store, league_id)
        expirations = [
            datetime.fromisoformat(str(row["expires_at"]))
            for row in locks if row.get("expires_at")
        ]
        if not expirations:
            return 0
        remaining = (min(expirations) - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            return recover_stalled_jobs(historical_store, league_id)
        await asyncio.sleep(min(remaining + 0.1, poll_seconds))


async def ensure_history_backfill(fetch: Any, *, league_id: str = LEAGUE_ID) -> dict[str, Any]:
    recover_stalled_jobs(historical_store, league_id)
    foundation = historical_store.latest_completed_foundation(league_id)
    if foundation is not None:
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(
                foundation["completed_at"],
            )
        except (TypeError, ValueError):
            age = None
        if age is not None and age.total_seconds() < 86400:
            enrichment = await enrich_player_history(
                league_id, skip_current=True,
            )
            return {
                "status": "current", "run_id": foundation["run_id"],
                "reason": "A complete backfill finished within the last 24 hours.",
                "enrichment": enrichment,
            }
    result = await backfill_history(fetch, league_id=league_id)
    if result.get("status") == "blocked" and "Overlapping import lease" in (
        result.get("errors") or []
    ):
        # A replacement worker can start before the terminated worker's lease
        # expires. Wait for the persisted heartbeat to expire, then recover from
        # checkpoints instead of leaving the deployment blocked indefinitely.
        await wait_for_historical_lease(league_id)
        result = await backfill_history(fetch, league_id=league_id)
    if result.get("status") == "complete":
        result["enrichment"] = await enrich_player_history(
            league_id, seasons=set(result.get("seasons") or []),
            skip_current=True,
        )
    return result


async def enrich_player_history(
    league_id: str, *, seasons: set[int] | None = None,
    today: date | None = None, skip_current: bool = False,
) -> dict[str, Any]:
    """Fetch approved weekly stats in the background and persist mapped records."""
    current_date = today or datetime.now(timezone.utc).date()
    selected = sorted(seasons or range(2021, current_date.year + 1))
    totals = {"written": 0, "unchanged": 0, "unresolved": 0}
    errors: list[str] = []
    segments: list[dict[str, Any]] = []
    identity_context_reuses = 0
    identity_context = await asyncio.to_thread(
        build_identity_context, historical_store,
    )
    current_checkpoints = {
        (row["season"], row["data_type"], row["provider"]): row
        for row in historical_store.checkpoints(league_id)
    }
    job = ImportJob(
        historical_store, league_id, tuple(selected), ("player_week",),
        requested_by="player_enrichment", provider="nflverse",
    )
    job.create()
    if not job.acquire():
        historical_store.update_job(
            job.job_id, status="blocked",
            last_error_message="Overlapping enrichment lease is active.",
        )
        return {"provider": "nflverse", "status": "blocked", "errors": []}
    historical_store.synchronize_enrichment_job_progress(job.job_id)
    completed_batches = {
        (int(row["season"]), int(row["batch_sequence"]))
        for row in historical_store.enrichment_batches(league_id)
        if row["provider"] == "nflverse" and row["status"] == "completed"
    }
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(max(REQUEST_TIMEOUT, 60)),
        follow_redirects=True,
        headers={"User-Agent": "DTOS/1.5.1 historical-enrichment"},
    ) as client:
        provider = NflverseProvider(client)
        for season in selected:
            classification = classify_season(season, today=current_date)
            checkpoint_key = (
                f"{league_id}:{season}:player_week:nflverse:{IMPORTER_VERSION}"
            )
            historical_store.update_job(
                job.job_id, current_season=season, current_data_type="player_week",
                last_progress_at=utcnow().isoformat(),
            )
            existing_checkpoint = current_checkpoints.get(
                (season, "player_week", "nflverse"),
            )
            checkpoint_current = (
                skip_current
                and existing_checkpoint is not None
                and existing_checkpoint["status"] == "completed"
                and existing_checkpoint["importer_version"] == IMPORTER_VERSION
                and (
                    identity_context.latest_identity_at is None
                    or str(existing_checkpoint.get("completed_at") or "")
                    >= identity_context.latest_identity_at
                )
            )
            if checkpoint_current:
                segments.append({
                    "season": season, "status": "current",
                    "provider": "nflverse",
                    "reason": "Completed checkpoint and identity context are current.",
                    "checked_at": utcnow().isoformat(),
                })
                continue
            if classification.state.value in {
                "pre_regular", "future", "unsupported",
            }:
                availability = classify_nflverse_404(classification)
                checked_at = utcnow().isoformat()
                historical_store.checkpoint(
                    checkpoint_key=checkpoint_key, job_id=job.job_id,
                    league_id=league_id, season=season, week=None,
                    data_type="player_week", provider="nflverse",
                    importer_version=IMPORTER_VERSION,
                    status=availability.status, completed_at=checked_at,
                    error=availability.reason,
                )
                segments.append({
                    "season": season, "status": availability.status,
                    "provider": "nflverse", "reason": availability.reason,
                    "checked_at": checked_at,
                    "next_eligible_at": availability.next_eligible_at,
                })
                continue
            try:
                _, season_rows = historical_store.records(
                    league_id, "league_season", season=season, limit=1,
                )
                settings = (
                    season_rows[0]["payload"].get("scoring_settings") or {}
                    if season_rows else {}
                )
                result = {"written": 0, "unchanged": 0, "unresolved": 0}
                batch_sequence = 0
                async for rows in provider.weekly_batches(
                    season, ENRICHMENT_BATCH_SIZE,
                ):
                    batch_sequence += 1
                    identity_context_reuses += 1
                    if (season, batch_sequence) in completed_batches:
                        rows.clear()
                        continue
                    raw_records, derived_records, unresolved = (
                        prepare_enrichment_records(
                            league_id, rows, settings, identity_context,
                        )
                    )
                    started_at = utcnow()
                    completed_at = utcnow()
                    last_identity = next(
                        (
                            record["record_key"]
                            for record in reversed(derived_records or raw_records)
                        ),
                        None,
                    )
                    batch = await asyncio.to_thread(
                        historical_store.commit_enrichment_batch,
                        raw_records=raw_records,
                        derived_records=derived_records,
                        progress={
                            "batch_key": (
                                f"{league_id}:{season}:nflverse:"
                                f"{batch_sequence}:{IMPORTER_VERSION}"
                            ),
                            "job_id": job.job_id,
                            "lease_owner": job.worker_identity,
                            "league_id": league_id, "season": season,
                            "week": max(
                                (int(row["week"]) for row in rows if row.get("week")),
                                default=None,
                            ),
                            "provider": "nflverse",
                            "batch_sequence": batch_sequence,
                            "raw_records_received": len(rows),
                            "batch_started_at": started_at.isoformat(),
                            "batch_completed_at": completed_at.isoformat(),
                            "last_durable_event_identity": last_identity,
                        },
                        lease_expires_at=(
                            completed_at + timedelta(minutes=15)
                        ).isoformat(),
                    )
                    result["written"] += (
                        batch["raw_inserted"] + batch["derived_inserted"]
                    )
                    result["unchanged"] += batch["duplicates"]
                    result["unresolved"] += unresolved
                    rows.clear()
                    raw_records.clear()
                    derived_records.clear()
                    await asyncio.sleep(0)
                for key in totals:
                    totals[key] += result[key]
                checked_at = utcnow().isoformat()
                historical_store.checkpoint(
                    checkpoint_key=checkpoint_key, job_id=job.job_id,
                    league_id=league_id, season=season, week=None,
                    data_type="player_week", provider="nflverse",
                    importer_version=IMPORTER_VERSION, status="completed",
                    completed_at=checked_at, records_written=result["written"],
                    records_unchanged=result["unchanged"],
                )
                segments.append({
                    "season": season, "status": "imported",
                    "provider": "nflverse", "checked_at": checked_at, **result,
                })
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    errors.append(f"{season}:{type(exc).__name__}:{exc}")
                    historical_store.checkpoint(
                        checkpoint_key=checkpoint_key, job_id=job.job_id,
                        league_id=league_id, season=season, week=None,
                        data_type="player_week", provider="nflverse",
                        importer_version=IMPORTER_VERSION, status="failed",
                        completed_at=utcnow().isoformat(), error=str(exc),
                    )
                    continue
                count, _ = historical_store.records(
                    league_id, "player_raw_week", season=season, limit=1,
                )
                availability = classify_nflverse_404(
                    classification, prior_week_count=count,
                )
                checked_at = utcnow().isoformat()
                historical_store.checkpoint(
                    checkpoint_key=checkpoint_key, job_id=job.job_id,
                    league_id=league_id, season=season, week=None,
                    data_type="player_week", provider="nflverse",
                    importer_version=IMPORTER_VERSION,
                    status=availability.status, completed_at=checked_at,
                    error=availability.reason,
                )
                segments.append({
                    "season": season, "status": availability.status,
                    "provider": "nflverse", "reason": availability.reason,
                    "checked_at": checked_at,
                    "next_eligible_at": availability.next_eligible_at,
                })
                if availability.status == "failed":
                    errors.append(f"{season}:HTTP404:{availability.reason}")
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"{season}:{type(exc).__name__}:{exc}")
                historical_store.checkpoint(
                    checkpoint_key=checkpoint_key, job_id=job.job_id,
                    league_id=league_id, season=season, week=None,
                    data_type="player_week", provider="nflverse",
                    importer_version=IMPORTER_VERSION, status="failed",
                    completed_at=utcnow().isoformat(), error=str(exc),
                )
    pending = [
        segment for segment in segments
        if segment["status"] in {"pending", "not_yet_available", "unsupported"}
    ]
    status = (
        "failed" if errors
        else "completed_with_pending" if pending
        else "complete"
    )
    historical_store.update_job(
        job.job_id,
        status="completed" if status == "complete" else status,
        completed_at=utcnow().isoformat(),
        inserted_records=totals["written"],
        unchanged_records=totals["unchanged"],
        skipped_records=totals["unresolved"],
        failed_records=len(errors), last_error_message="; ".join(errors) or None,
        next_retry_at=next(
            (
                segment["next_eligible_at"] for segment in pending
                if segment.get("next_eligible_at")
            ),
            None,
        ),
    )
    job.release()
    return {
        "provider": "nflverse", "seasons": selected, **totals,
        "segments": segments, "pending": pending, "errors": errors,
        "status": status,
        "identity_context": {
            "canonical_count": identity_context.canonical_count,
            "gsis_count": identity_context.gsis_count,
            "latest_identity_at": identity_context.latest_identity_at,
            "build_ms": identity_context.build_ms,
            "batch_reuse_count": identity_context_reuses,
        },
    }


def start_background_backfill(fetch: Any) -> asyncio.Task[dict[str, Any]]:
    global _BACKFILL_TASK
    if _BACKFILL_TASK is None or _BACKFILL_TASK.done():
        _BACKFILL_TASK = asyncio.create_task(
            ensure_history_backfill(fetch), name="dtos-history-worker",
        )
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
    foundation = historical_store.latest_completed_foundation(league_id)
    jobs = historical_store.jobs(league_id)
    for job in jobs:
        progress = historical_store.enrichment_job_progress(job["job_id"])
        if progress is not None:
            job["progress"] = progress
    return {
        "schema_version": HISTORICAL_SCHEMA_VERSION,
        "runs": runs,
        "jobs": jobs,
        "checkpoints": historical_store.checkpoints(league_id),
        "progress_repairs": historical_store.progress_repairs(),
        "latest_attempt": runs[0] if runs else None,
        "latest_completed_foundation": foundation,
        "latest": runs[0] if runs else {
            "status": "waiting", "reason": "Historical backfill has not started."
        },
    }


def import_completeness(league_id: str) -> dict[str, Any]:
    seasons = tuple(range(2021, datetime.now().year + 1))
    return {
        "schema_version": HISTORICAL_SCHEMA_VERSION,
        **completeness_report(historical_store, league_id, seasons),
    }


def provider_coverage() -> dict[str, Any]:
    provider = NflverseProvider
    return {
        "schema_version": HISTORICAL_SCHEMA_VERSION,
        "providers": [{
            "name": provider.name,
            "status": "configured",
            "license": provider.license,
            "cost": provider.cost,
            "update_frequency": provider.update_frequency,
            "capabilities": asdict(provider.capabilities),
            "limitations": (
                "Weekly player statistics do not include snaps, routes, "
                "availability designations, or complete red-zone participation."
            ),
        }, {
            "name": "Sleeper",
            "status": "configured",
            "license": "Public API; provider terms apply",
            "cost": "$0",
            "capabilities": {
                "league_history": True, "league_scored_points": True,
                "advanced_usage": False,
            },
        }],
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

"""Application boundary for historical evidence capture and queries."""
from __future__ import annotations

import asyncio
import copy
from collections import OrderedDict
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any

import httpx

from config import (
    ENRICHMENT_BATCH_SIZE,
    HISTORICAL_START_SEASON,
    LEAGUE_ID,
    REQUEST_TIMEOUT,
    SLEEPER_SEASON_CACHE_ROOT,
)
from src.core.historical_memory.aggregation import aggregate_production
from src.core.historical_memory.importer import HistoricalImporter
from src.core.historical_memory.enrichment import (
    build_identity_context, prepare_enrichment_records,
)
from src.core.historical_memory.jobs import (
    ImportJob, recover_stalled_jobs, utcnow,
)
from src.core.historical_memory.models import (
    HISTORICAL_SCHEMA_VERSION, IMPORTER_VERSION, PLAYER_HISTORY_SCHEMA_VERSION,
)
from src.core.history_context import canonical_history_store, minimal_metadata_store
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.historical_memory.providers import (
    NflverseProvider,
    classify_nflverse_404,
)
from src.core.historical_memory.season_state import classify_season
from src.platform.lifecycle import lifecycle_coordinator

historical_store = canonical_history_store
sleeper_season_cache = SleeperSeasonCache(SLEEPER_SEASON_CACHE_ROOT)

_PROGRESS_CACHE_LOCK = RLock()
_RETAINED_PROGRESS: dict[str, dict[str, Any]] = {}
_BACKFILL_LOCK = asyncio.Lock()
_BACKFILL_TASK: asyncio.Task[dict[str, Any]] | None = None
_ACTIVE_ENRICHMENT_STATUSES = frozenset({
    "queued", "running", "partially_complete", "retry_wait", "recoverable", "stale",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def capture_current_state(data: dict[str, Any], observed_at: str) -> dict[str, int]:
    """Update bounded operational state without legacy historical persistence."""
    league = data.get("league") or {}
    league_id = str(league.get("league_id") or LEAGUE_ID)
    historical_store.update_current(league_id, data)
    return {"written": 0, "unchanged": 0, "legacy_write_attempts": 0}


async def backfill_history(
    fetch: Any, *, league_id: str = LEAGUE_ID, seasons: set[int] | None = None,
) -> dict[str, Any]:
    if historical_store is canonical_history_store:
        raise RuntimeError(
            "Legacy bulk HistoricalStore backfill is retired; use SleeperSeasonCache."
        )
    async with _BACKFILL_LOCK:
        workbook = Path("/mnt/data/Day_Traders_Front_Office_Database_v13_8_Master(1).xlsx")
        return await HistoricalImporter(historical_store, fetch).backfill(
            league_id, earliest=2021, workbook=workbook, seasons=seasons,
        )


async def wait_for_historical_lease(
    league_id: str, *, poll_seconds: float = 30.0,
) -> int:
    """Legacy bulk-import leases no longer participate in canonical runtime."""
    if historical_store is canonical_history_store:
        return 0

    # Isolated legacy stores remain supported for compatibility validation only.
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
    if historical_store is canonical_history_store:
        raise RuntimeError(
            "Legacy HistoricalStore startup backfill is retired; use the historical cache worker."
        )
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
    if historical_store is canonical_history_store:
        raise RuntimeError(
            "Permanent provider-history enrichment is retired; provider evidence is cache-only."
        )
    current_date = today or datetime.now(timezone.utc).date()
    selected = sorted(seasons or range(2021, current_date.year + 1))
    totals = {"written": 0, "unchanged": 0, "unresolved": 0}
    errors: list[str] = []
    segments: list[dict[str, Any]] = []
    identity_context_reuses = 0
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
    generations = historical_store.identity_generations()
    mapping_generation = generations["mapping"]
    current_checkpoints = {
        (row["season"], row["data_type"], row["provider"]): row
        for row in historical_store.checkpoints(league_id)
    }
    eligible: list[int] = []
    skipped: list[int] = []
    pending_seasons: list[int] = []
    for season in selected:
        classification = classify_season(season, today=current_date)
        checkpoint_key = (
            f"{league_id}:{season}:player_week:nflverse:{IMPORTER_VERSION}"
        )
        existing_checkpoint = current_checkpoints.get(
            (season, "player_week", "nflverse"),
        )
        checkpoint_current = (
            skip_current
            and existing_checkpoint is not None
            and existing_checkpoint["status"] == "completed"
            and existing_checkpoint["importer_version"] == IMPORTER_VERSION
            and int(existing_checkpoint.get("identity_generation") or 0)
            == mapping_generation
        )
        if checkpoint_current:
            skipped.append(season)
            segments.append({
                "season": season, "status": "current", "provider": "nflverse",
                "reason": "Completed checkpoint and identity mapping generation are current.",
                "checked_at": utcnow().isoformat(),
                "identity_generation": mapping_generation,
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
                identity_generation=mapping_generation,
            )
            pending_seasons.append(season)
            segments.append({
                "season": season, "status": availability.status,
                "provider": "nflverse", "reason": availability.reason,
                "checked_at": checked_at,
                "next_eligible_at": availability.next_eligible_at,
                "identity_generation": mapping_generation,
            })
            continue
        eligible.append(season)
    projected_identity_count = historical_store.current_identity_count() if eligible else 0
    historical_store.update_job(
        job.job_id, eligible_seasons=eligible, skipped_seasons=skipped,
        pending_seasons=pending_seasons, identity_generation=mapping_generation,
        context_build_state="pending" if eligible else "not_required",
        projected_identity_count=projected_identity_count,
        last_progress_at=utcnow().isoformat(),
    )
    historical_store.synchronize_enrichment_job_progress(job.job_id)
    if not eligible:
        pending = [
            segment for segment in segments
            if segment["status"] in {
                "pending", "not_yet_available", "unsupported",
            }
        ]
        status = "completed_with_pending" if pending else "complete"
        historical_store.update_job(
            job.job_id,
            status="completed" if status == "complete" else status,
            completed_at=utcnow().isoformat(), last_progress_at=utcnow().isoformat(),
            context_build_state="not_required",
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
            "segments": segments, "pending": pending, "errors": [],
            "status": status,
            "identity_context": {
                "canonical_count": 0, "gsis_count": 0,
                "latest_identity_at": None, "build_ms": 0.0,
                "batch_reuse_count": 0, "state": "not_required",
                "identity_generation": mapping_generation,
            },
        }
    historical_store.update_job(
        job.job_id, context_build_state="building",
        last_progress_at=utcnow().isoformat(),
    )
    try:
        identity_context = await asyncio.to_thread(
            build_identity_context, historical_store,
        )
    except Exception as exc:
        historical_store.update_job(
            job.job_id, status="failed", failed_at=utcnow().isoformat(),
            context_build_state="failed", last_error_type=type(exc).__name__,
            last_error_message=str(exc), last_error_context="identity_context",
            last_progress_at=utcnow().isoformat(),
        )
        job.release()
        raise
    historical_store.update_job(
        job.job_id, context_build_state="complete",
        context_build_duration_ms=identity_context.build_ms,
        projected_identity_count=identity_context.canonical_count,
        last_progress_at=utcnow().isoformat(),
    )
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
        for season in eligible:
            classification = classify_season(season, today=current_date)
            checkpoint_key = (
                f"{league_id}:{season}:player_week:nflverse:{IMPORTER_VERSION}"
            )
            historical_store.update_job(
                job.job_id, current_season=season, current_data_type="player_week",
                last_progress_at=utcnow().isoformat(),
            )
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
                    with lifecycle_coordinator.phase("historical_import") as phase:
                        phase.update({
                            "historical_job_state": "batch_persistence",
                            "season": season,
                            "batch_sequence": batch_sequence,
                            "raw_records_received": len(rows),
                        })
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
                        phase.update({
                            "written": (
                                batch["raw_inserted"] + batch["derived_inserted"]
                            ),
                            "unchanged": batch["duplicates"],
                        })
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
                    identity_generation=mapping_generation,
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
                        identity_generation=mapping_generation,
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
                    identity_generation=mapping_generation,
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
                    identity_generation=mapping_generation,
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
    """Discover and cache provider-owned seasons without legacy persistence."""
    global _BACKFILL_TASK
    if _BACKFILL_TASK is None or _BACKFILL_TASK.done():
        async def coordinated_backfill() -> dict[str, Any]:
            with lifecycle_coordinator.phase("historical_cache") as phase:
                from src.core.intelligence_memory.sleeper_source import SleeperHistoricalSource

                source = SleeperHistoricalSource()
                chain = await source.discover(LEAGUE_ID)
                current = datetime.now(timezone.utc).year
                manifest = {
                    "root_league_id": str(LEAGUE_ID),
                    "year_one": chain.year_one,
                    "terminated": bool(chain.terminated),
                    "termination_reason": chain.termination_reason,
                    "updated_at": _now(),
                    "seasons": [
                        {
                            "season": reference.season,
                            "league_id": reference.league_id,
                            "previous_league_id": reference.previous_league_id,
                            "provider_availability": reference.availability,
                            "cache_status": (
                                "pending_current" if reference.season == current
                                else "available_not_cached"
                            ),
                            "checksum": None,
                            "error": reference.reason,
                        }
                        for reference in chain.seasons if reference.season is not None
                    ],
                }
                # Discovery is durable before hydration. A later provider or disk
                # failure therefore cannot make the dynasty appear to start late.
                minimal_metadata_store.record_season_chain(LEAGUE_ID, manifest)
                available = []
                unavailable = []
                for reference in chain.seasons:
                    if reference.season is None or reference.season >= current:
                        continue
                    row = next(item for item in manifest["seasons"]
                               if item["season"] == reference.season)
                    try:
                        season = await sleeper_season_cache.get_or_rebuild(
                            reference.league_id, reference.season,
                            source.completed_season_facts,
                        )
                        if not season.facts:
                            raise RuntimeError("provider_season_unavailable")
                        # Alias under the current league so consumers use one chain.
                        normalized = sleeper_season_cache.normalize(
                            LEAGUE_ID, reference.season, season.facts,
                        )
                        sleeper_season_cache.write(normalized)
                        minimal_metadata_store.record_season_cache_checkpoint(
                            LEAGUE_ID, reference.season, normalized.checksum,
                            normalized.status,
                        )
                    except Exception as exc:
                        row.update({
                            "cache_status": "unavailable",
                            "error": f"cache_hydration_failed:{type(exc).__name__}",
                        })
                        unavailable.append(reference.season)
                    else:
                        row.update({
                            "cache_status": "cached",
                            "checksum": normalized.checksum,
                            "error": None,
                        })
                        available.append(reference.season)
                    manifest["updated_at"] = _now()
                    minimal_metadata_store.record_season_chain(LEAGUE_ID, manifest)
                result = {
                    "status": "complete" if not unavailable else "partial",
                    "seasons": available, "unavailable_seasons": unavailable,
                    "year_one": chain.year_one, "source": "sleeper_season_cache",
                    "errors": [
                        {"season": row["season"], "error": row.get("error")}
                        for row in manifest["seasons"] if row.get("error")
                    ],
                }
                phase.update({
                    "historical_job_state": result.get("status"),
                    "season_count": len(result.get("seasons") or []),
                })
                return result

        _BACKFILL_TASK = asyncio.create_task(
            coordinated_backfill(), name="dtos-history-worker",
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


def season_archive(league_id: str, season: int) -> dict[str, Any]:
    """Compose cached section read models without provider access."""
    sections = {
        name: season_archive_section(league_id, season, name)
        for name in (
            "identity", "standings", "playoffs", "weeks", "transactions",
            "draft", "leaders",
        )
    }
    identity = sections["identity"]
    standings = sections["standings"]
    playoffs = sections["playoffs"]
    weeks = sections["weeks"]
    transactions = sections["transactions"]
    draft = sections["draft"]
    leaders = sections["leaders"]
    expected = {
        "standings": bool(standings["standings"]),
        "playoffs": bool(playoffs["result"].get("champion_roster_id")),
        "weekly_results": bool(weeks["weeks"]),
        "transactions": bool(transactions["count"]),
        "draft": bool(draft["drafts"] or draft["picks"]),
        "player_production": bool(leaders["player_week_count"]),
    }
    current = season == date.today().year
    complete = all(expected.values()) and not current
    return {
        "schema_version": HISTORICAL_SCHEMA_VERSION,
        "season": season,
        "state": "current" if current else "complete" if complete else "partial",
        "display_status": "Current Season" if current else "Complete" if complete else "Partial",
        "league_name": identity["league_name"],
        "champion": playoffs["champion"],
        "runner_up": playoffs["runner_up"],
        "standings": standings["standings"],
        "playoffs": {"result": playoffs["result"], "brackets": playoffs["brackets"]},
        "weeks": weeks["weeks"],
        "transactions": transactions["records"],
        "draft": {"drafts": draft["drafts"], "picks": draft["picks"]},
        "leaders": leaders["leaders"],
        "availability": expected,
        "counts": {
            "standings": len(standings["standings"]),
            "matchups": weeks["count"],
            "transactions": transactions["count"],
            "draft_picks": draft["pick_count"],
            "player_weeks": leaders["player_week_count"],
        },
        "provider_requests": 0,
    }


_SEASON_SECTION_CACHE: OrderedDict[tuple[int, str, str, int, str], dict[str, Any]] = OrderedDict()
_SEASON_SECTION_CACHE_LOCK = RLock()
_SEASON_SECTION_CACHE_LIMIT = 96


def _season_names(league_id: str, season: int) -> dict[int, dict[str, str]]:
    identities = history_records(
        league_id, "franchise_identity", season=season, limit=100,
    )
    names: dict[int, dict[str, str]] = {}
    for row in identities["records"]:
        payload = row["payload"]
        roster_id = int(payload.get("sleeper_roster_id") or 0)
        if roster_id:
            names[roster_id] = {
                "team_name": str(payload.get("dtos_display_name") or "Unassigned Franchise"),
                "gm_name": str(payload.get("sleeper_username") or "Unassigned GM"),
                "franchise_id": str(payload.get("franchise_id") or ""),
            }
    return names


def season_archive_section(league_id: str, season: int, section: str) -> dict[str, Any]:
    """Return one bounded season section, cached by the durable dataset identity."""
    version = historical_store.dataset_version(league_id)
    key = (id(historical_store), version, league_id, season, section)
    with _SEASON_SECTION_CACHE_LOCK:
        cached = _SEASON_SECTION_CACHE.get(key)
        if cached is not None:
            _SEASON_SECTION_CACHE.move_to_end(key)
            return copy.deepcopy(cached)
    value = _build_season_archive_section(league_id, season, section)
    with _SEASON_SECTION_CACHE_LOCK:
        _SEASON_SECTION_CACHE[key] = copy.deepcopy(value)
        _SEASON_SECTION_CACHE.move_to_end(key)
        while len(_SEASON_SECTION_CACHE) > _SEASON_SECTION_CACHE_LIMIT:
            _SEASON_SECTION_CACHE.popitem(last=False)
    return value


def _build_season_archive_section(
    league_id: str, season: int, section: str,
) -> dict[str, Any]:
    names = _season_names(league_id, season) if section in {"identity", "standings", "playoffs", "weeks"} else {}
    if section == "identity":
        league = history_records(league_id, "league_season", season=season, limit=1)
        payload = league["records"][0]["payload"] if league["records"] else {}
        return {"league_name": payload.get("league_name") or "Sleeper League", "names": names}
    if section == "playoffs":
        playoffs = history_records(league_id, "playoff_result", season=season, limit=10)
        brackets = history_records(league_id, "playoff_bracket", season=season, limit=10)
        placement = next((row["payload"] for row in playoffs["records"] if row["payload"].get("champion_roster_id") is not None), {})
        return {
            "result": placement, "brackets": brackets["records"],
            "champion": names.get(int(placement.get("champion_roster_id") or 0)),
            "runner_up": names.get(int(placement.get("runner_up_roster_id") or 0)),
        }
    if section == "standings":
        standings = history_records(league_id, "season_standing", season=season, limit=100)
        playoff = season_archive_section(league_id, season, "playoffs")["result"]
        places = {int(roster_id): int(place) for place, roster_id in (playoff.get("placements") or {}).items()}
        rows = []
        for record in sorted(standings["records"], key=lambda item: int(item["payload"].get("rank") or 999)):
            payload = record["payload"]
            roster_id = int(payload.get("roster_id") or 0)
            rows.append({
                "rank": payload.get("rank"), "roster_id": roster_id,
                **names.get(roster_id, {"team_name": "Unassigned Franchise", "gm_name": "Unassigned GM", "franchise_id": record.get("franchise_id") or ""}),
                "wins": payload.get("wins"), "losses": payload.get("losses"),
                "ties": payload.get("ties"), "points_for": payload.get("points_for"),
                "points_against": payload.get("points_against"),
                "postseason_finish": places.get(roster_id),
            })
        return {"standings": rows}
    if section == "weeks":
        matchups = history_records(league_id, "matchup", season=season, limit=500)
        weekly: dict[int, list[dict[str, Any]]] = {}
        for record in matchups["records"]:
            payload = record["payload"]
            sides = [int(value) for value in payload.get("franchises") or []]
            weekly.setdefault(int(record.get("week") or 0), []).append({
                "matchup_id": payload.get("matchup_id"),
                "teams": [{"roster_id": roster_id, **names.get(roster_id, {"team_name": "Unassigned Franchise", "gm_name": "Unassigned GM", "franchise_id": ""}), "score": (payload.get("team_points") or {}).get(str(roster_id))} for roster_id in sides],
                "winner_roster_id": payload.get("winner"), "tie": bool(payload.get("tie")),
                "postseason": bool(payload.get("postseason_context")),
            })
        return {"weeks": [{"week": week, "matchups": rows} for week, rows in sorted(weekly.items()) if week], "count": matchups["count"]}
    if section == "transactions":
        transactions = history_records(league_id, "transaction", season=season, limit=1000)
        trades = history_records(league_id, "trade", season=season, limit=1000)
        return {"records": [*trades["records"], *transactions["records"]], "count": trades["count"] + transactions["count"]}
    if section == "draft":
        drafts = history_records(league_id, "draft", season=season, limit=20)
        picks = history_records(league_id, "draft_pick", season=season, limit=500)
        return {"drafts": drafts["records"], "picks": picks["records"], "pick_count": picks["count"]}
    if section == "leaders":
        count, rows = historical_store.season_player_leaders(league_id, season, limit=40)
        return {"player_week_count": count, "leaders": [{"player_id": str(row["player_id"]), "player_name": row.get("display_name") or f"Player {row['player_id']}", "position": row.get("position"), "fantasy_points": round(float(row["points"]), 2)} for row in rows]}
    raise ValueError(f"Unsupported season archive section: {section}")


def season_index(league_id: str) -> dict[str, Any]:
    rows = history_records(league_id, "league_season", limit=100)["records"]
    seasons = sorted({int(row["season"]) for row in rows}, reverse=True)
    return {
        "schema_version": HISTORICAL_SCHEMA_VERSION,
        "seasons": [
            {
                "season": season,
                "route": f"/history/{season}",
                "api_route": f"/api/history/seasons/{season}",
                "state": "current" if season == date.today().year else "historical",
            }
            for season in seasons
        ],
        "provider_requests": 0,
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
    if historical_store is not canonical_history_store:
        runs = historical_store.import_status(league_id)
        foundation = historical_store.latest_completed_foundation(league_id)
        jobs = historical_store.jobs(league_id)
        for job in jobs:
            progress = historical_store.enrichment_job_progress(job["job_id"])
            if progress is not None:
                job["progress"] = progress
        progress_contracts = history_progress_contracts(
            league_id, jobs=jobs, foundation=foundation,
        )
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
            "canonical_progress": progress_contracts["canonical_history_progress"],
            **progress_contracts,
        }
    progress_contracts = history_progress_contracts(league_id)
    return {
        "schema_version": HISTORICAL_SCHEMA_VERSION,
        "runs": [], "jobs": [], "checkpoints": [], "progress_repairs": [],
        "latest_attempt": None,
        "latest_completed_foundation": {
            "status": "complete", "run_id": "sleeper-season-cache",
            "completed_at": None,
        },
        "latest": {"status": progress_contracts["canonical_history_progress"]["status"],
                   "reason": "Canonical history is derived from Sleeper cache availability."},
        "canonical_progress": progress_contracts["canonical_history_progress"],
        **progress_contracts,
    }


def history_progress_contracts(
    league_id: str, *, jobs: list[dict[str, Any]] | None = None,
    foundation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return canonical and scoped progress through one shared serializer."""
    if historical_store is not canonical_history_store:
        candidates = jobs if jobs is not None else historical_store.jobs(league_id)
        latest_enrichment = next(
            (row for row in candidates if row.get("requested_data_types") == ["player_week"]),
            None,
        )
        active_enrichment = next(
            (
                row for row in candidates
                if row.get("requested_data_types") == ["player_week"]
                and row.get("status") in _ACTIVE_ENRICHMENT_STATUSES
            ),
            None,
        )
        latest_job_progress = _job_progress_contract(latest_enrichment)
        active_job_progress = _job_progress_contract(active_enrichment)
        foundation_run = foundation or historical_store.latest_completed_foundation(league_id)
        foundation_progress = {
            "status": str((foundation_run or {}).get("status") or "waiting"),
            "run_id": (foundation_run or {}).get("run_id"),
            "completed_at": (foundation_run or {}).get("completed_at"),
        }
    else:
        latest_job_progress = None
        active_job_progress = None
        foundation_progress = {
            "status": "complete", "run_id": "sleeper-season-cache",
            "completed_at": None,
        }
    result = {
        "canonical_history_progress": canonical_history_progress(league_id),
        "latest_job_progress": latest_job_progress,
        "active_job_progress": active_job_progress,
        "foundation_progress": foundation_progress,
    }
    with _PROGRESS_CACHE_LOCK:
        _RETAINED_PROGRESS[league_id] = copy.deepcopy(result)
    return result


def retained_history_progress_contracts(league_id: str) -> dict[str, Any]:
    """Return the last canonical progress snapshot without durable-store access."""
    with _PROGRESS_CACHE_LOCK:
        progress = _RETAINED_PROGRESS.get(league_id)
        if progress is not None:
            return copy.deepcopy(progress)
    return {
        "canonical_history_progress": {
            "status": "waiting",
            "display_status": "Historical progress not yet retained",
            "completed_steps": 0,
            "total_steps": 0,
            "completed_seasons": [],
            "pending_seasons": [],
            "consistent": True,
            "terminal": False,
            "reason": "Canonical historical progress has not been loaded yet.",
        },
        "latest_job_progress": None,
        "active_job_progress": None,
        "foundation_progress": {
            "status": "waiting", "run_id": None, "completed_at": None,
        },
    }


def _job_progress_contract(job: dict[str, Any] | None) -> dict[str, Any] | None:
    """Serialize one job's own scope without promoting it to league progress."""
    if job is None:
        return None
    progress = job.get("progress") or historical_store.enrichment_job_progress(
        str(job["job_id"]),
    ) or {}
    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "requested_seasons": list(job.get("requested_seasons") or []),
        "requested_data_types": list(job.get("requested_data_types") or []),
        "completed_steps": int(progress.get("completed_steps") or 0),
        "total_steps": int(progress.get("total_steps") or 0),
        "completed_seasons": list(progress.get("completed_seasons") or []),
        "pending_seasons": list(progress.get("pending_seasons") or []),
        "failed_seasons": list(progress.get("failed_seasons") or []),
        "current_season": job.get("current_season"),
        "current_data_type": job.get("current_data_type") or "player_week",
        "consistent": bool(progress.get("consistent", True)),
        "last_progress_at": job.get("last_progress_at"),
    }


def canonical_history_progress(
    league_id: str, *, jobs: list[dict[str, Any]] | None = None,
    current_year: int | None = None,
) -> dict[str, Any]:
    """Return league progress from the configured durable checkpoint universe."""
    selected_year = current_year or datetime.now().year
    if historical_store is canonical_history_store:
        cached = sorted(historical_store._cache_index(league_id))
        manifest = historical_store.season_chain(league_id) or {}
        discovered = sorted({
            int(row["season"]) for row in manifest.get("seasons", [])
            if row.get("season") is not None
        })
        seasons = tuple(discovered or cached or [selected_year])
        completed_seasons = [
            season for season in seasons if season in cached and season < selected_year
        ]
        pending = [season for season in seasons if season == selected_year]
        failed: list[int] = []
        invalidated: list[int] = []
        missing = [
            season for season in seasons
            if season not in completed_seasons and season not in pending
        ]
        identity_generation = historical_store.identity_generations()["mapping"]
        semantic_generations = historical_store.semantic_generations(league_id)
    else:
        seasons = tuple(range(HISTORICAL_START_SEASON, selected_year + 1))
        state = historical_store.canonical_enrichment_progress(
            league_id, seasons, provider="nflverse", importer_version=IMPORTER_VERSION,
        )
        completed_seasons = list(state["completed_seasons"])
        pending = list(state["pending_seasons"])
        failed = list(state["failed_seasons"])
        invalidated = list(state["invalidated_seasons"])
        missing = list(state["missing_seasons"])
        identity_generation = state["identity_generation"]
        semantic_generations = state["semantic_generations"]
    completed = len(completed_seasons)
    total = len(seasons)
    candidates = jobs if jobs is not None else (
        [] if historical_store is canonical_history_store else historical_store.jobs(league_id)
    )
    active = next(
        (
            row for row in candidates
            if row.get("requested_data_types") == ["player_week"]
            and row.get("status") in _ACTIVE_ENRICHMENT_STATUSES
        ),
        None,
    )
    if failed:
        status = "failed"
    elif completed == total:
        status = "completed"
    elif pending and completed + len(pending) == total:
        status = "completed_with_pending"
    elif active is not None:
        status = "running"
    elif completed or invalidated or missing:
        status = "incomplete"
    else:
        status = "waiting"
    consistent = 0 <= completed <= total and not set(completed_seasons).intersection(
        {*pending, *failed, *invalidated, *missing},
    )
    labels = {
        "completed": "Completed",
        "completed_with_pending": "Completed with pending season",
        "running": "Running",
        "failed": "Failed",
        "inconsistent": "Inconsistent progress",
        "incomplete": "Incomplete",
        "waiting": "Waiting",
    }
    active_pending = selected_year in pending
    pending_reason = None
    if pending:
        pending_reason = (
            "Active/current-season player-week evidence is not yet complete or available."
            if active_pending else
            "Player-week evidence is not yet complete or available."
        )
    return {
        "status": status,
        "display_status": labels.get(status, status.replace("_", " ").title()),
        "completed_steps": completed,
        "total_steps": total,
        "percentage": round(100 * completed / total) if total else None,
        "completed_seasons": completed_seasons,
        "pending_seasons": pending,
        "failed_seasons": failed,
        "invalidated_seasons": invalidated,
        "missing_seasons": missing,
        "current_season": selected_year if selected_year in pending else None,
        "current_data_type": "player_week",
        "consistent": consistent,
        "terminal": status in {"completed", "completed_with_pending", "failed"},
        "pending_reason": pending_reason,
        "configured_seasons": list(seasons),
        "identity_generation": identity_generation,
        "semantic_generations": semantic_generations,
    }


def import_completeness(league_id: str) -> dict[str, Any]:
    progress = canonical_history_progress(league_id)
    return {"schema_version": HISTORICAL_SCHEMA_VERSION,
            "status": "complete" if progress["consistent"] else "incomplete",
            "source": "sleeper_season_cache", "progress": progress}


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
    issues: list[dict[str, Any]] = []
    return {
        "schema_version": HISTORICAL_SCHEMA_VERSION,
        "issues": issues,
        "blocking_count": sum(item["severity"] == "blocking" and not item["resolved"] for item in issues),
        "warning_count": sum(item["severity"] == "warning" and not item["resolved"] for item in issues),
        "informational_count": sum(item["severity"] == "informational" and not item["resolved"] for item in issues),
    }

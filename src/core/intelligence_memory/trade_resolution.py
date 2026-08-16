"""Background event-driven historical trade resolution over Sleeper cache facts."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from time import perf_counter, sleep
from typing import Any

from .historical_resolver import (
    HistoricalMarketResolver, PersistenceContext,
)
from .market_memory import market_context_id
from .models import (
    CheckpointTrigger, EvidenceCompleteness, IntelligenceCheckpoint, ProvenanceType,
)


@dataclass(frozen=True)
class TradeResolutionSummary:
    completed_trades: int
    fully_valued: int
    partially_valued: int
    unavailable: int
    process_gradable: int
    process_not_gradable: int
    unclassified_process_trades: int
    assets_total: int
    assets_valued: int
    counters: dict[str, int]


class HistoricalTradeResolutionService:
    """Resolve only actual cached trade assets; never persist Sleeper facts."""

    def __init__(self, resolver: HistoricalMarketResolver):
        self.resolver = resolver
        self._lock = RLock()
        self._state: dict[str, Any] = {"status": "waiting", "last_error": None}

    @staticmethod
    def _assets(payload: dict[str, Any]) -> tuple[tuple[str, str, str | None], ...]:
        values: set[tuple[str, str, str | None]] = set()
        for mapping in (payload.get("adds") or {}, payload.get("drops") or {}):
            if isinstance(mapping, dict):
                values.update((f"player:{asset}", "player", str(roster)) for asset, roster in mapping.items())
        for pick in payload.get("draft_picks") or ():
            season, round_number = pick.get("season"), pick.get("round")
            roster = pick.get("roster_id") or pick.get("original_roster_id")
            owner = pick.get("owner_id") or roster
            if season not in {None, ""} and round_number not in {None, ""} and roster not in {None, ""}:
                values.add((f"pick:{season}:{round_number}:{roster}", "future_pick", str(owner)))
        return tuple(sorted(values))

    def run(self, history_store: Any, league_id: str) -> TradeResolutionSummary:
        started = perf_counter()
        phase_started_at = datetime.now(timezone.utc).isoformat()
        resolver_before = Counter(self.resolver.health().get("counts") or {})
        total, trades = history_store.records(league_id, "trade", limit=1_000_000)
        trades = sorted(trades, key=lambda row: (str(row.get("occurred_at") or ""), str(row.get("source_record_id") or "")))
        counts: Counter[str] = Counter()
        requests: list[tuple[IntelligenceCheckpoint, str, PersistenceContext]] = []
        trade_work: list[tuple[dict[str, Any], tuple[tuple[str, str, str | None], ...], tuple[int, ...]]] = []
        for trade_index, row in enumerate(trades, 1):
            occurred_at = row.get("occurred_at")
            payload = row.get("payload") or {}
            assets = self._assets(payload)
            if not occurred_at or not assets:
                counts["unavailable_trades"] += 1
                counts["process_not_gradable"] += 1
                if not occurred_at:
                    counts["reason_missing_occurred_at"] += 1
                else:
                    counts["reason_no_supported_market_assets"] += 1
                    if payload.get("waiver_budget"):
                        counts["faab_only_trades"] += 1
                trade_work.append((row, (), ()))
                continue
            request_indexes = []
            for asset_id, asset_type, roster_id in assets:
                checkpoint = IntelligenceCheckpoint(
                    checkpoint_id="", asset_id=asset_id, asset_type=asset_type,
                    timestamp=str(occurred_at), season=int(row.get("season") or 0),
                    trigger_type=CheckpointTrigger.TRADE_EXECUTION,
                    provenance_type=ProvenanceType.UNAVAILABLE, league_id=str(league_id),
                    roster_id=roster_id, market_value=None, confidence=0,
                    evidence_completeness=EvidenceCompleteness.UNAVAILABLE,
                    model_version="1.10.31", related_event_id=str(row["source_record_id"]),
                    knowledge_state="generic_future_pick" if asset_type == "future_pick" else "player_at_execution",
                )
                request_indexes.append(len(requests))
                requests.append((
                    checkpoint,
                    market_context_id(asset_type=asset_type, scoring_profile_id=None),
                    PersistenceContext("trade_execution"),
                ))
            trade_work.append((row, assets, tuple(request_indexes)))
            if trade_index % 32 == 0:
                sleep(0)

        resolved, bulk_metrics = self.resolver.resolve_checkpoints_bulk(requests)

        for trade_index, (_row, assets, request_indexes) in enumerate(trade_work, 1):
            if not assets:
                continue
            available = 0
            for request_index in request_indexes:
                if request_index >= len(resolved):
                    continue
                resolved_item = resolved[request_index]
                if resolved_item is None:
                    counts["historical_provider_rate_limited"] += 1
                    counts["historical_resolution_assets_retry_pending"] += 1
                    continue
                result, _stored, observation_created, reference_created = resolved_item
                available += int(result.available)
                counts[f"persistence_{result.persistence.value}"] += 1
                counts["historical_resolution_assets_new"] += int(
                    observation_created or reference_created
                )
                counts["historical_resolution_assets_reused"] += int(
                    result.source in {"durable_resolution_reference", "durable_final_unavailable"}
                )
            counts["assets_total"] += len(assets)
            counts["assets_valued"] += available
            if available == len(assets):
                counts["fully_valued"] += 1
                counts["process_gradable"] += 1
            elif available:
                counts["partially_valued"] += 1
                counts["process_not_gradable"] += 1
            else:
                counts["unavailable_trades"] += 1
                counts["process_not_gradable"] += 1
            if trade_index % 32 == 0:
                sleep(0)
        unclassified = total - (
            counts["process_gradable"] + counts["process_not_gradable"]
        )
        execution_unclassified = total - (
            counts["fully_valued"]
            + counts["partially_valued"]
            + counts["unavailable_trades"]
        )
        if unclassified or execution_unclassified:
            raise RuntimeError(
                "Historical trade accounting invariant failed: "
                f"process_unclassified={unclassified}, "
                f"execution_unclassified={execution_unclassified}."
            )
        summary = TradeResolutionSummary(
            total, counts["fully_valued"], counts["partially_valued"],
            counts["unavailable_trades"], counts["process_gradable"],
            counts["process_not_gradable"], unclassified, counts["assets_total"],
            counts["assets_valued"], dict(counts),
        )
        resolver_counts = Counter(self.resolver.health().get("counts") or {})
        resolver_run = resolver_counts - resolver_before
        summary.counters.update({
            "historical_resolution_assets_total": counts["assets_total"],
            "historical_resolution_assets_unavailable": (
                counts["assets_total"] - counts["assets_valued"]
            ),
            "historical_provider_requests": int(resolver_run.get("provider_queries", 0)),
            "historical_provider_rate_limited": int(
                resolver_run.get("provider_rate_limited", 0)
            ),
            "historical_resolution_replay_skipped": int(resolver_run.get("replay_skipped", 0)),
            "historical_resolution_assets_bulk_reused": int(
                bulk_metrics.get("assets_bulk_reused", 0)
            ),
            "historical_resolution_assets_provider_resolved": int(
                bulk_metrics.get("assets_provider_resolved", 0)
            ),
            "historical_resolution_sqlite_connections": int(
                bulk_metrics.get("sqlite_connections", 0)
            ),
            "historical_resolution_sqlite_queries": int(
                bulk_metrics.get("sqlite_queries", 0)
            ),
            "historical_resolution_rows_loaded": int(
                bulk_metrics.get("rows_loaded", 0)
            ),
            "historical_resolution_objects_decoded": int(
                bulk_metrics.get("objects_decoded", 0)
            ),
            "historical_resolution_batches": int(bulk_metrics.get("batches", 0)),
            "historical_resolution_elapsed_ms": int(
                round((perf_counter() - started) * 1000)
            ),
        })
        for key, value in resolver_run.items():
            if key.startswith("provider_") and key.endswith("_queries"):
                summary.counters[f"historical_{key}"] = int(value)
        status = (
            "degraded_provider_retry_pending"
            if counts["historical_resolution_assets_retry_pending"]
            else "complete_with_unavailable"
            if counts["unavailable_trades"]
            else "complete_with_new_resolutions"
            if counts["historical_resolution_assets_new"]
            else "complete_reused"
        )
        with self._lock:
            exposed = {
                key: value for key, value in summary.counters.items()
                if key.startswith("historical_")
            }
            self._state = {
                "status": status, "historical_resolution_status": status,
                "last_error": None, "phase_started_at": phase_started_at,
                **summary.__dict__, **exposed,
            }
        return summary

    def run_safe(self, history_store: Any, league_id: str) -> TradeResolutionSummary | None:
        with self._lock:
            if self._state.get("status") == "running":
                return None
            self._state = {
                "status": "running", "last_error": None,
                "phase_started_at": datetime.now(timezone.utc).isoformat(),
            }
        try:
            return self.run(history_store, league_id)
        except Exception as exc:
            with self._lock:
                self._state = {
                    "status": "failed", "last_error": f"{type(exc).__name__}: {exc}",
                }
            return None

    def health(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

"""Background event-driven historical trade resolution over Sleeper cache facts."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from threading import RLock
from typing import Any

from .historical_resolver import HistoricalMarketResolver, PersistenceContext
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
        total, trades = history_store.records(league_id, "trade", limit=1_000_000)
        trades = sorted(trades, key=lambda row: (str(row.get("occurred_at") or ""), str(row.get("source_record_id") or "")))
        counts: Counter[str] = Counter()
        for row in trades:
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
                continue
            available = 0
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
                result, _stored, _observation_created, _reference_created = self.resolver.resolve_checkpoint(
                    checkpoint,
                    market_context_id=market_context_id(asset_type=asset_type, scoring_profile_id=None),
                    persistence=PersistenceContext("trade_execution"),
                )
                available += int(result.available)
                counts[f"persistence_{result.persistence.value}"] += 1
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
        with self._lock:
            self._state = {"status": "complete", "last_error": None, **summary.__dict__}
        return summary

    def run_safe(self, history_store: Any, league_id: str) -> TradeResolutionSummary | None:
        with self._lock:
            if self._state.get("status") == "running":
                return None
            self._state = {"status": "running", "last_error": None}
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

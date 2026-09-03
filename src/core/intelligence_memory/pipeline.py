"""Canonical runtime bridge from normalized provider events to checkpoints."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Iterable

from app_metadata import VERSION
from src.core.league_runtime.identity import scoring_profile_id

from .models import CheckpointTrigger, EvidenceCompleteness, ProvenanceType
from .models import PickLineage, SourceObservation
from .relevance import (
    material_related_candidates, milestone_asset_ids, related_player_candidates,
)
from .service import IntelligenceMemoryService


def _timestamp(value: Any, fallback: str) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()
    return str(value or fallback)


def _canonical_timestamp(value: Any) -> str | None:
    """Return only trustworthy temporal evidence; event identity is not time."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.isoformat()


class CheckpointPipeline:
    """Idempotently process canonical events; request-time reads never call this."""

    def __init__(self, service: IntelligenceMemoryService) -> None:
        self.service = service
        self._lock = RLock()
        self._counts: Counter[str] = Counter()
        self._by_trigger: dict[str, Counter[str]] = {}
        self._last_error: str | None = None

    def _record(self, trigger: CheckpointTrigger, result: str) -> None:
        self._counts[result] += 1
        self._by_trigger.setdefault(trigger.value, Counter())[result] += 1

    @staticmethod
    def _values(data: dict[str, Any], asset_id: str) -> dict[str, Any]:
        key = asset_id if ":" in asset_id else f"player:{asset_id}"
        asset = ((data.get("valuation_intelligence") or {}).get("assets") or {}).get(key) or {}
        layers = asset.get("valuation_layers") or asset.get("layers") or {}
        def value(name: str) -> Any:
            return (layers.get(name) or {}).get("value")
        current = value("market_value")
        return {
            "dtos_value": value("league_adjusted_value") or value("intrinsic_dtos_value"),
            "intrinsic_value": value("intrinsic_dtos_value"),
            "contender_value": value("contender_value"),
            "rebuilder_value": value("rebuilder_value"),
            "market_value": current,
            "completeness": EvidenceCompleteness.COMPLETE if current is not None else EvidenceCompleteness.PARTIAL,
            "knowledge_state": "current_market_fresh" if current is not None else "current_market_unavailable",
        }

    @staticmethod
    def _context(data: dict[str, Any], *, provenance: ProvenanceType) -> dict[str, Any]:
        league = data.get("league") or {}
        return {
            "league_id": str(league.get("league_id") or ""),
            "season": int(league.get("season") or datetime.now(timezone.utc).year),
            "week": int(data.get("week") or 1),
            "scoring_profile_id": scoring_profile_id(
                data.get("scoring_settings") or league.get("scoring_settings") or {},
                roster_positions=tuple(data.get("roster_positions") or league.get("roster_positions") or ()),
            ),
            "provenance": provenance,
            "model_version": VERSION,
            "brain_identity": ((data.get("brain") or {}).get("brain_snapshot_id")
                               or (data.get("valuation_intelligence") or {}).get("brain_snapshot_id")),
        }

    @staticmethod
    def _projection_observations(
        data: dict[str, Any], asset_id: str,
    ) -> tuple[SourceObservation, ...]:
        """Attach one compact canonical projection fact to a material event."""
        if not asset_id.startswith("player:"):
            return ()
        projection = ((data.get("projection_intelligence") or {}).get("players") or {}).get(
            asset_id.removeprefix("player:")
        ) or {}
        if not projection:
            return ()
        return (SourceObservation(
            provider="Sleeper",
            raw_value=projection.get("canonical_projection"),
            normalized_value=projection.get("canonical_projection"),
            observed_at=projection.get("source_timestamp") or projection.get("generated_at"),
            source_identity=projection.get("sleeper_evidence_fingerprint"),
            temporal_distance_seconds=None,
            metadata={
                "evidence_type": "canonical_weekly_projection",
                "season": projection.get("season"),
                "week": projection.get("week"),
                "scoring_profile_id": projection.get("scoring_profile_id"),
                "availability": projection.get("availability"),
                "availability_state": projection.get("availability_state"),
                "confidence": projection.get("projection_confidence"),
                "freshness": projection.get("source_freshness"),
            },
        ),)

    @staticmethod
    def _market_observations(
        data: dict[str, Any], asset_id: str,
    ) -> tuple[SourceObservation, ...]:
        """Extract only compact canonical market-provider evidence."""
        asset = ((data.get("valuation_intelligence") or {}).get("assets") or {}).get(
            asset_id
        ) or {}
        rows = []
        for item in asset.get("evidence_sources") or ():
            provider = str(item.get("provider_id") or "").strip()
            value = item.get("normalized_value")
            if not provider or value is None:
                continue
            rows.append(SourceObservation(
                provider=provider,
                raw_value=value,
                normalized_value=value,
                observed_at=None,
                source_identity=(
                    f"{provider}:{item.get('family')}:{value}:"
                    f"{item.get('freshness_tier')}"
                ),
                temporal_distance_seconds=None,
                metadata={
                    "evidence_family": item.get("family"),
                    "category": item.get("category"),
                    "weight": item.get("weight"),
                    "freshness_tier": item.get("freshness_tier"),
                    "reliability": item.get("reliability"),
                },
            ))
        return tuple(sorted(rows, key=lambda row: (row.provider, str(row.source_identity))))

    @staticmethod
    def _historical_safe_values(
        values: dict[str, Any], provenance: ProvenanceType,
    ) -> dict[str, Any]:
        """Never attach current valuation state to an old league event."""
        if provenance is not ProvenanceType.HISTORICAL_SOURCE_BACKFILL:
            return values
        return {
            **values,
            "dtos_value": None, "intrinsic_value": None,
            "contender_value": None, "rebuilder_value": None,
            "market_value": None,
            "completeness": EvidenceCompleteness.UNAVAILABLE,
            "knowledge_state": "historical_market_evidence_requires_resolver",
        }

    def _capture(self, trigger: CheckpointTrigger, **values: Any) -> None:
        self._counts["checkpoints_attempted"] += 1
        event_id = str(values.get("event_id") or "")
        if event_id and self.service.store.event_exists(
            league_id=values.get("league_id"), event_id=event_id,
            asset_id=str(values["asset_id"]), trigger_type=trigger.value,
        ):
            self._record(trigger, "duplicates_skipped")
            self._counts["events_replayed"] += 1
            return
        capture_result = self.service.capture_detailed(trigger=trigger, **values)
        inserted = capture_result.checkpoint_created
        result_name = "checkpoints_written" if inserted else "duplicates_skipped"
        self._record(trigger, result_name)
        if result_name == "checkpoints_written":
            self._counts["references_persisted"] += 1
        if result_name == "duplicates_skipped":
            self._counts["events_replayed"] += 1
        if capture_result.observation_created:
            self._counts["global_observations_persisted"] += 1
        elif capture_result.market_decision == "reused_observation":
            self._counts["global_observations_deduplicated"] += 1
        if values.get("completeness") is EvidenceCompleteness.UNAVAILABLE:
            self._record(trigger, "unavailable_evidence_writes")

    def ingest_transactions(
        self, data: dict[str, Any], transactions: Iterable[dict[str, Any]], *,
        provenance: ProvenanceType = ProvenanceType.LIVE_CAPTURED,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        fallback = observed_at or datetime.now(timezone.utc).isoformat()
        context = self._context(data, provenance=provenance)
        with self._lock:
            for transaction in transactions or ():
                self._counts["canonical_events_observed"] += 1
                event_id = str(transaction.get("transaction_id") or "")
                if not event_id:
                    self._counts["materiality_skips"] += 1
                    continue
                kind = str(transaction.get("type") or "").casefold()
                trigger_assets: list[tuple[CheckpointTrigger, str, str | None]] = []
                if kind == "trade":
                    for mapping in (transaction.get("adds") or {}, transaction.get("drops") or {}):
                        trigger_assets.extend((CheckpointTrigger.TRADE_EXECUTION, str(asset), str(roster)) for asset, roster in mapping.items())
                    trigger_assets.extend((CheckpointTrigger.TRADE_EXECUTION,
                        str((pick or {}).get("season")) + ":" + str((pick or {}).get("round")) + ":" + str((pick or {}).get("roster_id")),
                        str((pick or {}).get("owner_id") or (pick or {}).get("roster_id") or "") or None)
                        for pick in transaction.get("draft_picks") or ())
                else:
                    trigger_assets.extend((CheckpointTrigger.WAIVER_ADD, str(asset), str(roster)) for asset, roster in (transaction.get("adds") or {}).items())
                    trigger_assets.extend((CheckpointTrigger.DROP, str(asset), str(roster)) for asset, roster in (transaction.get("drops") or {}).items())
                if not trigger_assets:
                    self._counts["materiality_skips"] += 1
                    continue
                self._counts["eligible_events"] += 1
                for trigger, raw_asset, roster_id in sorted(set(trigger_assets), key=lambda row: (row[0].value, row[1], row[2] or "")):
                    if not raw_asset or raw_asset.startswith("None"):
                        continue
                    is_pick = trigger is CheckpointTrigger.TRADE_EXECUTION and raw_asset.count(":") == 2
                    asset_id = f"pick:{raw_asset}" if is_pick else f"player:{raw_asset}"
                    values = self._historical_safe_values(
                        self._values(data, asset_id), provenance,
                    )
                    self._capture(
                        trigger, asset_id=asset_id,
                        asset_type="future_pick" if is_pick else "player",
                        timestamp=_timestamp(transaction.get("created"), fallback),
                        event_id=event_id, roster_id=roster_id,
                        confidence=85 if values["market_value"] is not None else 0,
                        observations=(
                            self._projection_observations(data, asset_id)
                            if provenance is not ProvenanceType.HISTORICAL_SOURCE_BACKFILL
                            else ()
                        ),
                        market_observations=(
                            self._market_observations(data, asset_id)
                            if provenance is not ProvenanceType.HISTORICAL_SOURCE_BACKFILL
                            else ()
                        ),
                        **context, **values,
                    )
        return self.health()

    def ingest_drafts(
        self, data: dict[str, Any], picks: Iterable[dict[str, Any]], *,
        provenance: ProvenanceType = ProvenanceType.LIVE_CAPTURED,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        context = self._context(data, provenance=provenance)
        with self._lock:
            for pick in picks or ():
                self._counts["canonical_events_observed"] += 1
                player_id = str(pick.get("player_id") or "")
                draft_id = str(pick.get("draft_id") or "")
                number = pick.get("pick_no") or pick.get("pick_number")
                if not player_id or not draft_id or number is None:
                    self._counts["materiality_skips"] += 1
                    continue
                self._counts["eligible_events"] += 1
                values = self._historical_safe_values(
                    self._values(data, f"player:{player_id}"), provenance,
                )
                selection_time = _canonical_timestamp(
                    pick.get("picked_at") or pick.get("created")
                )
                if selection_time is not None:
                    self._capture(
                        CheckpointTrigger.FANTASY_DRAFT_PICK,
                        asset_id=f"player:{player_id}", asset_type="player",
                        timestamp=selection_time,
                        event_id=f"{draft_id}:{number}",
                        roster_id=str(pick.get("roster_id") or "") or None,
                        confidence=85 if values["market_value"] is not None else 0,
                        observations=(
                            self._projection_observations(data, f"player:{player_id}")
                            if provenance is not ProvenanceType.HISTORICAL_SOURCE_BACKFILL
                            else ()
                        ),
                        market_observations=(
                            self._market_observations(data, f"player:{player_id}")
                            if provenance is not ProvenanceType.HISTORICAL_SOURCE_BACKFILL
                            else ()
                        ),
                        knowledge_state=f"fantasy_draft_selection:{number}",
                        **context,
                        **{key: value for key, value in values.items()
                           if key != "knowledge_state"},
                    )
                else:
                    self._counts["undated_draft_events"] += 1
                round_number = int(pick.get("round") or max(1, int(float(number))))
                roster_id = str(pick.get("roster_id") or "unknown")
                generic = f"pick:{context['season']}:{round_number}:{roster_id}"
                self.service.store.put_lineage(PickLineage(
                    lineage_id=self.service.identifier("lineage", draft_id, number),
                    generic_pick_id=generic, season=context["season"], round=round_number,
                    original_roster_id=roster_id, exact_slot=str(number),
                    selected_player_id=f"player:{player_id}", selected_at=selection_time,
                ))
        return self.health()

    def ingest_scheduled(self, data: dict[str, Any], *, observed_at: str) -> dict[str, Any]:
        context = self._context(data, provenance=ProvenanceType.LIVE_CAPTURED)
        week = int(data.get("week") or 1)
        league = data.get("league") or {}
        playoff_week = int((league.get("settings") or {}).get("playoff_week_start") or 15)
        triggers = []
        if week == 1:
            triggers.append(CheckpointTrigger.SEASON_START)
        if week == max(2, playoff_week // 2):
            triggers.append(CheckpointTrigger.MIDSEASON)
        if week == playoff_week:
            triggers.append(CheckpointTrigger.REGULAR_SEASON_END)
        if str(league.get("status") or "").casefold() == "complete":
            triggers.append(CheckpointTrigger.FANTASY_SEASON_END)
        assets = milestone_asset_ids(data)
        valuation_count = len(
            ((data.get("valuation_intelligence") or {}).get("assets") or {})
        )
        self._counts["milestone_assets_excluded"] += max(
            0, valuation_count - len(assets),
        )
        for trigger in triggers:
            # Benchmarks are global by provider-compatible market context. A
            # second league observes the same global event and is idempotently
            # collapsed rather than multiplying a full-universe snapshot.
            for asset_id in assets:
                self._counts["canonical_events_observed"] += 1
                self._counts["eligible_events"] += 1
                values = self._values(data, asset_id)
                benchmark_context = {
                    **context, "league_id": None, "scoring_profile_id": None,
                }
                self._capture(
                    trigger, asset_id=asset_id,
                    asset_type="future_pick" if asset_id.startswith("pick:") else "player",
                    timestamp=f"{context['season']}-W{week:02d}",
                    event_id=f"global:{context['season']}:{week}:{trigger.value}:{asset_id}",
                    confidence=85 if values["market_value"] is not None else 40,
                    market_observations=self._market_observations(data, asset_id),
                    knowledge_state="scheduled_global_market_benchmark",
                    **benchmark_context,
                    **{key: value for key, value in values.items() if key != "knowledge_state"},
                )
        return self.health()

    def ingest_market_event(
        self, data: dict[str, Any], *, event_id: str,
        trigger: CheckpointTrigger, primary_asset_ids: Iterable[str],
        before_values: dict[str, float | int | None],
        after_values: dict[str, float | int | None], observed_at: str,
        related_limit: int = 12,
    ) -> dict[str, Any]:
        """Evaluate one global event and only its bounded, material neighborhood."""
        if trigger not in {
            CheckpointTrigger.NFL_DRAFT_SELECTION, CheckpointTrigger.NFL_TRADE,
            CheckpointTrigger.FREE_AGENCY, CheckpointTrigger.MAJOR_INJURY,
            CheckpointTrigger.INJURY_RETURN, CheckpointTrigger.SUSPENSION,
            CheckpointTrigger.RETIREMENT,
        }:
            raise ValueError("Market events require a supported global player trigger.")
        primary = tuple(sorted({
            value if str(value).startswith("player:") else f"player:{value}"
            for value in map(str, primary_asset_ids) if value
        }))
        context = self._context(data, provenance=ProvenanceType.LIVE_CAPTURED)
        context.update({"league_id": None, "scoring_profile_id": None})
        candidates = related_player_candidates(data, primary, maximum=related_limit)
        related = material_related_candidates(
            candidates, before=before_values, after=after_values,
        )
        self._counts["events_evaluated"] += 1
        self._counts["primary_players_considered"] += len(primary)
        self._counts["related_players_considered"] += len(candidates)
        self._counts["related_players_rejected_immaterial"] += (
            len(candidates) - len(related)
        )
        relationship_by_asset = {
            candidate.asset_id: candidate.relationship for candidate in related
        }
        for asset_id in (*primary, *(row.asset_id for row in related)):
            market_value = after_values.get(asset_id)
            if market_value is None:
                self._counts["provider_unavailable"] += 1
                continue
            values = self._values(data, asset_id)
            if values["market_value"] != market_value:
                raise ValueError(
                    "Post-event market value must match attached canonical evidence."
                )
            values.update({
                "completeness": EvidenceCompleteness.COMPLETE,
                "knowledge_state": (
                    "primary_asset_event" if asset_id in primary else
                    f"related_player_impact:{relationship_by_asset[asset_id]}"
                ),
            })
            self._capture(
                trigger, asset_id=asset_id, asset_type="player",
                timestamp=observed_at, event_id=event_id,
                confidence=85,
                market_observations=self._market_observations(data, asset_id),
                **context, **values,
            )
        return self.health()

    def ingest_runtime(self, data: dict[str, Any], *, observed_at: str) -> dict[str, Any]:
        try:
            self.ingest_transactions(data, data.get("transactions") or (), observed_at=observed_at)
            self.ingest_drafts(data, data.get("draft_picks") or (), observed_at=observed_at)
            self.ingest_scheduled(data, observed_at=observed_at)
            self._last_error = None
        except Exception as exc:
            self._counts["failures"] += 1
            self._last_error = f"{type(exc).__name__}: {exc}"
            raise
        return self.health()

    def health(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._last_error is None else "degraded",
            **{key: int(self._counts.get(key, 0)) for key in (
                "canonical_events_observed", "eligible_events", "checkpoints_attempted",
                "checkpoints_written", "duplicates_skipped", "materiality_skips",
                "unavailable_evidence_writes", "failures", "events_evaluated",
                "primary_players_considered", "related_players_considered",
                "related_players_rejected_immaterial", "provider_unavailable",
                "global_observations_persisted", "global_observations_deduplicated",
                "references_persisted", "events_replayed", "milestone_assets_excluded",
                "undated_draft_events",
            )},
            "by_trigger": {key: dict(value) for key, value in sorted(self._by_trigger.items())},
            "last_error": self._last_error,
            "request_time_writes": 0,
            "producer_status": {
                "trade_execution": "implemented_and_connected",
                "waiver_add": "implemented_and_connected",
                "player_drop": "implemented_and_connected",
                "fantasy_rookie_draft_selection": "implemented_and_connected",
                "scheduled_benchmarks": "implemented_and_connected",
                "nfl_draft": "implemented_not_connected_no_canonical_source",
                "nfl_status_events": "implemented_not_connected_no_canonical_source",
            },
        }

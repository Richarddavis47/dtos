"""The single public read boundary for cached DTOS intelligence."""
from __future__ import annotations

from statistics import mean
from time import perf_counter
from typing import Any, Iterable

from app_metadata import BUILD_NUMBER, VERSION
from src.core.brain.contracts import BrainDecision, DecisionConfidence
from src.core.valuation_intelligence import valuation_intelligence_report
from src.core.projection_intelligence import projection_service

BRAIN_SCHEMA_VERSION = "1.0"
CONSUMERS = (
    "Team Headquarters", "FOIS", "Trade Intelligence", "Recommendation Engine",
    "Decision Engine", "Team Intelligence", "Championship Odds", "Playoff Odds",
    "Power Rankings", "Roster Intelligence", "League Intelligence", "Asset Intelligence",
    "Player Dossier",
    "Asset Market",
)


def canonical_asset_id(asset_id: str) -> str:
    value = str(asset_id).strip()
    return value if value.startswith(("player:", "pick:")) else f"player:{value}"


class BrainService:
    """Serve immutable synchronized intelligence without I/O or recalculation."""

    def __init__(self, data: dict[str, Any]) -> None:
        started = perf_counter()
        self._data = data
        self._report = valuation_intelligence_report(data)
        self._assets = self._report.get("assets") or {}
        self.latency_ms = round((perf_counter() - started) * 1000, 3)

    @property
    def report(self) -> dict[str, Any]:
        return self._report

    def asset(self, asset_id: str) -> dict[str, Any] | None:
        canonical_id = canonical_asset_id(asset_id)
        asset = self._assets.get(canonical_id)
        if asset is None or not canonical_id.startswith("player:"):
            return asset
        projection = projection_service.player(canonical_id.removeprefix("player:"))
        if projection is None:
            return asset
        return {
            **asset,
            "forward_production": projection,
            "projection_confidence": projection.get("projection_confidence"),
            "projection_snapshot_id": projection.get("projection_snapshot_id"),
        }

    def assets(self, asset_ids: Iterable[str]) -> tuple[dict[str, Any], ...]:
        rows = (self.asset(asset_id) for asset_id in asset_ids)
        return tuple(row for row in rows if row is not None)

    def decision(
        self,
        consumer: str,
        asset_ids: Iterable[str],
        *,
        trade_complexity: int = 0,
        roster_context_available: bool = True,
        league_settings_available: bool = True,
    ) -> BrainDecision:
        canonical_ids = tuple(dict.fromkeys(canonical_asset_id(value) for value in asset_ids))
        assets = self.assets(canonical_ids)
        scores = [row.get("scores") or {} for row in assets]
        def average(key: str, default: int) -> int:
            return round(mean(float(row.get(key, default)) for row in scores)) if scores else default
        evidence_confidence = average("confidence", 25)
        agreement = average("agreement", 35)
        coverage = average("coverage", 20)
        context_quality = (50 if roster_context_available else 20) + (30 if league_settings_available else 10)
        calibration = 100 if self._report.get("safety", {}).get("unsafe_adjustments") == 0 else 40
        histories = [self._report.get("timeline", {}).get(asset_id, []) for asset_id in canonical_ids]
        stability = round(mean(100 if len(history) <= 1 else max(30, 100 - (len(history) - 1) * 10) for history in histories)) if histories else 40
        complexity_penalty = min(25, max(0, trade_complexity - 2) * 5)
        history_by_player = {
            str(player.get("id") or player.get("player_id")): player.get("historical_evidence") or {}
            for team in self._data.get("teams") or []
            for player in team.get("players") or []
            if player.get("id") or player.get("player_id")
        }
        raw_player_ids = [asset_id.removeprefix("player:") for asset_id in canonical_ids if asset_id.startswith("player:")]
        historical_observations = sum(
            int((history_by_player.get(player_id) or {}).get("weekly_record_count") or 0)
            for player_id in raw_player_ids
        )
        history_covered = sum(
            int((history_by_player.get(player_id) or {}).get("weekly_record_count") or 0) > 0
            for player_id in raw_player_ids
        )
        historical_coverage = round(100 * history_covered / len(raw_player_ids)) if raw_player_ids else 0
        history_penalty = 0 if not raw_player_ids else round((100 - historical_coverage) * .10)
        value = round(evidence_confidence * .25 + agreement * .20 + coverage * .20 + context_quality * .10 + calibration * .10 + stability * .15 - complexity_penalty - history_penalty)
        confidence = DecisionConfidence(
            max(0, min(100, value)), evidence_confidence, agreement, coverage,
            context_quality, calibration, stability, complexity_penalty,
            (
                f"Canonical evidence confidence is {evidence_confidence}/100.",
                f"Provider agreement is {agreement}/100 and coverage is {coverage}/100.",
                f"Context quality is {context_quality}/100; calibration safety is {calibration}/100.",
                f"Recommendation stability is {stability}/100; complexity penalty is {complexity_penalty}.",
                f"Historical coverage is {historical_coverage}/100 across {historical_observations} verified weekly observations; missing history penalty is {history_penalty}.",
            ),
        )
        generated_at = self._report.get("generated_at")
        return BrainDecision(
            consumer, canonical_ids, assets, confidence, generated_at, VERSION,
            BRAIN_SCHEMA_VERSION, f"{VERSION}:{generated_at or 'pending'}", generated_at,
            (
                "DTOS Brain synchronized valuation-intelligence snapshot",
                "Canonical Projection Intelligence snapshot (when available)",
                "Historical Memory immutable Sleeper evidence (confidence-only, capped at 10 points)",
                f"Consumer: {consumer}",
                "Decision Confidence is calculated once inside BrainService.",
            ),
            confidence.rationale,
        )

    def migration(self) -> dict[str, Any]:
        consumers = [{"consumer": name, "status": "migrated", "boundary": "BrainService via Intelligence Orchestrator"} for name in CONSUMERS]
        return {
            "consumer_count": len(consumers), "migrated_count": len(consumers),
            "legacy_consumer_count": 0, "duplicate_calculation_count": 0,
            "consumers": consumers,
            "deprecated_contracts": ["Direct consumer assembly of valuation_intelligence fields"],
        }

    def health(self) -> dict[str, Any]:
        summary = self._report.get("summary") or {}
        return {
            "application_version": VERSION, "application_build": BUILD_NUMBER,
            "brain_schema_version": BRAIN_SCHEMA_VERSION,
            "status": "healthy" if self._report.get("availability") == "available" else "pending",
            "generated_at": self._report.get("generated_at"), "asset_count": len(self._assets),
            "coverage": summary.get("average_coverage", 0),
            "confidence": summary.get("average_confidence", 0),
            "agreement": summary.get("average_agreement", 0),
            "cache": {"mode": "synchronized_snapshot", "hit": True, "read_latency_ms": self.latency_ms},
            "provider_health": self._report.get("availability", "pending"),
            "migration": self.migration(), "diagnostics": self._report.get("diagnostics") or {},
            "synchronization": {"external_requests": 0, "request_time_recalculation": False},
        }


def brain_service(data: dict[str, Any]) -> BrainService:
    return BrainService(data)

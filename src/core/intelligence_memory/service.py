"""Bounded checkpoint trigger service; inactive leagues perform no work."""
from __future__ import annotations

import hashlib
from typing import Iterable

from .models import (
    CheckpointTrigger, EvidenceCompleteness, IntelligenceCheckpoint,
    ProvenanceType, SourceObservation,
)
from .store import IntelligenceCheckpointStore
from .market_memory import market_context_id
from .triggers import material_teammate_impacts


class IntelligenceMemoryService:
    def __init__(self, store: IntelligenceCheckpointStore):
        self.store = store

    @staticmethod
    def identifier(*parts: object) -> str:
        return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()

    def capture(
        self,
        *, asset_id: str, asset_type: str, timestamp: str, season: int,
        trigger: CheckpointTrigger, provenance: ProvenanceType,
        league_id: str | None = None, scoring_profile_id: str | None = None,
        roster_id: str | None = None,
        week: int | None = None, dtos_value: float | int | None = None,
        intrinsic_value: float | int | None = None,
        contender_value: float | int | None = None,
        rebuilder_value: float | int | None = None,
        market_value: float | int | None = None, confidence: int = 0,
        completeness: EvidenceCompleteness = EvidenceCompleteness.UNAVAILABLE,
        model_version: str = "unknown", brain_identity: str | None = None,
        event_id: str | None = None,
        observations: Iterable[SourceObservation] = (),
        market_observations: Iterable[SourceObservation] | None = None,
        knowledge_state: str | None = None,
    ) -> tuple[IntelligenceCheckpoint, bool]:
        checkpoint = IntelligenceCheckpoint(
            checkpoint_id=self.identifier(
                asset_id, league_id, timestamp, trigger.value, event_id,
                model_version, brain_identity,
            ),
            asset_id=asset_id, asset_type=asset_type, league_id=league_id,
            roster_id=roster_id,
            scoring_profile_id=scoring_profile_id, timestamp=timestamp,
            season=season, week=week, trigger_type=trigger,
            provenance_type=provenance, dtos_value=dtos_value,
            intrinsic_value=intrinsic_value, contender_value=contender_value,
            rebuilder_value=rebuilder_value, market_value=market_value,
            confidence=max(0, min(100, int(confidence))),
            evidence_completeness=completeness, model_version=model_version,
            brain_identity=brain_identity, related_event_id=event_id,
            observations=tuple(observations), knowledge_state=knowledge_state,
        )
        context_id = market_context_id(
            asset_type=asset_type, scoring_profile_id=scoring_profile_id,
        )
        persisted, inserted, _, _, _ = self.store.put_sparse(
            checkpoint, market_context_id=context_id,
            provider_evidence=(
                tuple(market_observations)
                if market_observations is not None else tuple(observations)
            ),
        )
        return persisted, inserted

    def capture_trade_assets(self, assets: Iterable[dict], **context) -> list[IntelligenceCheckpoint]:
        return [self.capture(
            asset_id=str(asset["asset_id"]), asset_type=str(asset["asset_type"]),
            trigger=CheckpointTrigger.TRADE_EXECUTION,
            knowledge_state=asset.get("knowledge_state"),
            market_value=asset.get("market_value"), dtos_value=asset.get("dtos_value"),
            intrinsic_value=asset.get("intrinsic_value"),
            contender_value=asset.get("contender_value"),
            rebuilder_value=asset.get("rebuilder_value"),
            **context,
        )[0] for asset in assets]

    def capture_waiver_or_drop(self, *, dropped: bool, **context) -> tuple[IntelligenceCheckpoint, bool]:
        return self.capture(
            trigger=CheckpointTrigger.DROP if dropped else CheckpointTrigger.WAIVER_ADD,
            **context,
        )

    def capture_benchmark(self, trigger: CheckpointTrigger, **context) -> tuple[IntelligenceCheckpoint, bool]:
        if trigger not in {
            CheckpointTrigger.SEASON_START, CheckpointTrigger.MIDSEASON,
            CheckpointTrigger.REGULAR_SEASON_END, CheckpointTrigger.FANTASY_SEASON_END,
        }:
            raise ValueError("Scheduled checkpoint trigger is not a benchmark.")
        return self.capture(trigger=trigger, **context)

    def capture_nfl_draft_impacts(
        self, before: dict[str, int | float | None],
        after: dict[str, int | float | None], **context,
    ) -> list[IntelligenceCheckpoint]:
        return [self.capture(
            asset_id=asset_id,
            asset_type="player",
            trigger=CheckpointTrigger.NFL_DRAFT_TEAMMATE_IMPACT,
            dtos_value=after[asset_id],
            knowledge_state="post_nfl_draft_material_teammate_impact",
            **context,
        )[0] for asset_id in material_teammate_impacts(before, after)]

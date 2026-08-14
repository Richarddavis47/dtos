"""Bounded event-to-checkpoint helpers; no background all-league fan-out."""
from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .models import (
    EvidenceCompleteness, HistoricalTradeAssessment, IntelligenceCheckpoint,
    ProvenanceType,
)


MATERIAL_VALUE_DELTA = 250


def material_teammate_impacts(
    before: dict[str, int | float | None],
    after: dict[str, int | float | None],
    *, threshold: int = MATERIAL_VALUE_DELTA,
) -> tuple[str, ...]:
    """Return only teammates whose canonical value changed materially."""
    return tuple(sorted(
        asset_id for asset_id, old in before.items()
        if old is not None and after.get(asset_id) is not None
        and abs(float(after[asset_id]) - float(old)) >= threshold
    ))


def trade_assessment(
    checkpoints_by_side: dict[str, Iterable[IntelligenceCheckpoint]],
) -> HistoricalTradeAssessment:
    valued = unavailable = 0
    totals: dict[str, float | None] = {}
    ids: list[str] = []
    eligible = True
    for side, checkpoints in checkpoints_by_side.items():
        total = 0.0
        side_incomplete = False
        for checkpoint in checkpoints:
            ids.append(checkpoint.checkpoint_id)
            if checkpoint.market_value is None:
                unavailable += 1
                side_incomplete = True
            else:
                valued += 1
                total += float(checkpoint.market_value)
            eligible = eligible and checkpoint.provenance_type.definitive_process_evidence
        totals[side] = None if side_incomplete else total
    status = (
        EvidenceCompleteness.UNAVAILABLE if not valued else
        EvidenceCompleteness.PARTIAL if unavailable else EvidenceCompleteness.COMPLETE
    )
    return HistoricalTradeAssessment(
        status=status, process_grade_eligible=eligible and not unavailable,
        valued_assets=valued, unavailable_assets=unavailable,
        side_totals=totals, evidence_checkpoint_ids=tuple(ids),
    )


def current_market_checkpoint(
    checkpoint: IntelligenceCheckpoint,
    *, current_provider_available: bool,
) -> IntelligenceCheckpoint:
    """Never use historical market memory as a current-value safety net."""
    if current_provider_available:
        return checkpoint
    return replace(
        checkpoint, market_value=None, confidence=min(checkpoint.confidence, 40),
        evidence_completeness=EvidenceCompleteness.PARTIAL,
        knowledge_state="current_market_unavailable",
    )


def historical_backfill_checkpoint(
    checkpoint: IntelligenceCheckpoint,
    *, legitimate_historical_observation: bool,
) -> IntelligenceCheckpoint:
    if legitimate_historical_observation:
        return replace(checkpoint, provenance_type=ProvenanceType.HISTORICAL_SOURCE_BACKFILL)
    return replace(
        checkpoint, provenance_type=ProvenanceType.UNAVAILABLE,
        market_value=None, confidence=0,
        evidence_completeness=EvidenceCompleteness.UNAVAILABLE,
    )

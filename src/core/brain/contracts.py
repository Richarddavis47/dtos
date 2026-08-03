"""Public, implementation-neutral contracts for the DTOS Brain."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DecisionConfidence:
    """Confidence that an action is appropriate, distinct from asset confidence."""

    value: int
    evidence_confidence: int
    agreement: int
    coverage: int
    context_quality: int
    calibration: int
    stability: int
    complexity_penalty: int
    rationale: tuple[str, ...]


@dataclass(frozen=True)
class BrainDecision:
    """Cached canonical evidence supplied to a recommendation consumer."""

    consumer: str
    asset_ids: tuple[str, ...]
    assets: tuple[dict[str, Any], ...]
    confidence: DecisionConfidence
    generated_at: str | None
    brain_version: str
    decision_confidence_version: str
    brain_snapshot_id: str
    recommendation_timestamp: str | None
    decision_provenance: tuple[str, ...]
    recommendation_explanation: tuple[str, ...]

"""Canonical presentation contract for every Brain recommendation endpoint."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any


def recommendation_contract(recommendation: Any, brain_decision: Any) -> dict[str, Any]:
    """Serialize canonical Brain output without recalculating presentation values."""
    if brain_decision is None:
        return {
            "recommendation": asdict(recommendation) if recommendation is not None else None,
            "decision_confidence": None,
            "decision_confidence_version": None,
            "brain_snapshot_id": None,
            "recommendation_timestamp": None,
            "decision_provenance": ("Canonical Brain decision data is unavailable.",),
            "recommendation_explanation": ("No synchronized Brain recommendation was produced.",),
            "availability": "unavailable",
        }
    return {
        "recommendation": asdict(recommendation) if recommendation is not None else None,
        "decision_confidence": asdict(brain_decision.confidence),
        "decision_confidence_version": brain_decision.decision_confidence_version,
        "brain_snapshot_id": brain_decision.brain_snapshot_id,
        "recommendation_timestamp": brain_decision.recommendation_timestamp,
        "decision_provenance": brain_decision.decision_provenance,
        "recommendation_explanation": brain_decision.recommendation_explanation,
        "availability": "available",
    }

"""Presentation-neutral contracts for league-scoped GM behavior evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


GM_BEHAVIOR_SCHEMA_VERSION = "gm-behavioral-intelligence-1"
GM_BEHAVIOR_METHOD_VERSION = "step6-canonical-decision-aggregation-1"


@dataclass(frozen=True)
class BehavioralDimension:
    key: str
    tendency: str
    confidence: str
    sample_count: int
    opportunity_count: int | None
    coverage: float
    supporting_counts: dict[str, int]
    explanation: str
    evidence_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class GMBehavioralProfile:
    league_id: str
    franchise_id: str
    gm_id: str | None
    transaction_count: int
    evaluated_transaction_count: int
    first_observed_at: str | None
    last_observed_at: str | None
    dimensions: tuple[BehavioralDimension, ...]
    process_distribution: dict[str, int]
    outcome_distribution: dict[str, int]
    overall_confidence: str
    evidence_completeness: float
    evidence_references: tuple[str, ...]
    source_evidence_identity: str
    semantic_identity: str
    as_of: str | None
    schema_version: str = GM_BEHAVIOR_SCHEMA_VERSION
    method_version: str = GM_BEHAVIOR_METHOD_VERSION

    def contract(self) -> dict[str, Any]:
        # Normalize tuples exactly as persistence does so in-process and
        # spawned-process FOIS publication remain semantically identical.
        import json

        return json.loads(json.dumps(asdict(self), sort_keys=True))

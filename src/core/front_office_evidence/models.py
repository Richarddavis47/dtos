"""Immutable, presentation-neutral evidence shared by FOIS, Front Office and Brain."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FRONT_OFFICE_EVIDENCE_SCHEMA_VERSION = "front-office-evidence-1"
FRONT_OFFICE_EVIDENCE_METHOD_VERSION = "step5-process-outcome-unification-1"


@dataclass(frozen=True)
class FrontOfficeEvidenceSummary:
    league_id: str
    franchise_id: str
    gm_id: str | None
    transaction_count: int
    evaluated_transaction_count: int
    process_distribution: dict[str, int]
    outcome_distribution: dict[str, int]
    process_confidence: dict[str, int]
    outcome_maturity: dict[str, int]
    partner_counts: dict[str, int]
    process_score: float | None
    outcome_score: float | None
    evidence_completeness: float
    evidence_references: tuple[str, ...]
    source_history_generations: tuple[str, ...]
    source_market_generations: tuple[str, ...]
    semantic_identity: str
    schema_version: str = FRONT_OFFICE_EVIDENCE_SCHEMA_VERSION
    method_version: str = FRONT_OFFICE_EVIDENCE_METHOD_VERSION

    def contract(self) -> dict[str, Any]:
        """Return a bounded JSON-safe contract; never raw history or provider payloads."""
        from dataclasses import asdict
        import json

        return json.loads(json.dumps(asdict(self), sort_keys=True))

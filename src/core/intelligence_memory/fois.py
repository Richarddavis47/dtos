"""FOIS compatibility boundary for permanent historical intelligence."""
from __future__ import annotations

from typing import Iterable

from .models import IntelligenceCheckpoint


def fois_process_evidence(
    checkpoints: Iterable[IntelligenceCheckpoint],
) -> dict[str, object]:
    rows = tuple(checkpoints)
    definitive = tuple(
        row for row in rows
        if row.provenance_type.definitive_process_evidence
        and row.market_value is not None
        and row.confidence > 0
    )
    unavailable = sum(row.market_value is None for row in rows)
    completeness = round(100 * len(definitive) / len(rows), 1) if rows else 0.0
    return {
        "status": "available" if definitive else "insufficient_data",
        "definitive_checkpoint_ids": [row.checkpoint_id for row in definitive],
        "excluded_checkpoint_ids": [
            row.checkpoint_id for row in rows if row not in definitive
        ],
        "confidence_multiplier": completeness / 100,
        "completeness": completeness,
        "unavailable_values": unavailable,
        "reconstructed_is_definitive": False,
    }

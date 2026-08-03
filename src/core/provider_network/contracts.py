"""Immutable, versioned provider-evidence contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceObservation:
    canonical_asset_id: str
    provider_id: str
    evidence_category: str
    raw_value: float | None
    normalized_value: int | None
    position_rank: int | None
    overall_rank: int | None
    tier: str | None
    scoring_format: str
    league_format: str
    league_size: int
    te_premium: bool
    observation_timestamp: str | None
    source_publication_timestamp: str | None
    ingestion_timestamp: str
    freshness_age_hours: float | None
    sample_size: int
    confidence: int
    availability: str
    identity_match_confidence: int
    identity_match_status: str
    source_version: str
    provenance: str
    evidence_family: str
    redistributable: bool

    def public_dict(self) -> dict[str, Any]:
        row = asdict(self)
        if not self.redistributable:
            for key in ("raw_value", "normalized_value", "position_rank", "overall_rank", "tier"):
                row[key] = None
            row["provenance"] = "Restricted provider contribution; raw evidence is not redistributed."
        return row


@dataclass(frozen=True)
class TradeObservation:
    transaction_id: str
    league_id: str
    timestamp: str | None
    side_a_assets: tuple[str, ...]
    side_b_assets: tuple[str, ...]
    league_settings: str
    transaction_quality: int
    outlier_status: str
    inferred_package_premium: float | None
    exclusion_reason: str | None = None

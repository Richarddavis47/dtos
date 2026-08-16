"""Global sparse market-memory semantics shared by every league trigger."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from .models import (
    EvidenceCompleteness, GlobalMarketObservation,
    MARKET_MATERIALITY_POLICY_VERSION, SourceObservation,
)


@dataclass(frozen=True)
class MarketObservationMaterialityPolicy:
    """One versioned rule for deciding whether a market state is new."""

    version: str = MARKET_MATERIALITY_POLICY_VERSION
    canonical_value_delta: float = 250.0
    canonical_relative_delta: float = 0.08
    provider_value_delta: float = 250.0
    provider_relative_delta: float = 0.08
    confidence_delta: int = 10
    market_tier_width: int = 1000

    @staticmethod
    def _providers(rows: Iterable[SourceObservation]) -> tuple[str, ...]:
        return tuple(sorted({row.provider.casefold() for row in rows}))

    def materially_changed(
        self, previous: GlobalMarketObservation, *, market_context_id: str,
        canonical_value: float, confidence: int,
        evidence_completeness: EvidenceCompleteness,
        provider_evidence: tuple[SourceObservation, ...],
    ) -> bool:
        if previous.market_context_id != market_context_id:
            return True
        if previous.evidence_completeness is not evidence_completeness:
            return True
        if self._providers(previous.provider_evidence) != self._providers(provider_evidence):
            return True
        canonical_delta = abs(float(previous.canonical_value) - canonical_value)
        canonical_base = max(abs(float(previous.canonical_value)), 1.0)
        if (
            canonical_delta >= self.canonical_value_delta
            or canonical_delta / canonical_base >= self.canonical_relative_delta
            or int(float(previous.canonical_value) // self.market_tier_width)
               != int(canonical_value // self.market_tier_width)
        ):
            return True
        if abs(int(previous.confidence) - int(confidence)) >= self.confidence_delta:
            return True
        old_values = {
            row.provider.casefold(): row.normalized_value
            for row in previous.provider_evidence if row.normalized_value is not None
        }
        for row in provider_evidence:
            value = row.normalized_value
            old = old_values.get(row.provider.casefold())
            if value is not None and old is not None:
                provider_delta = abs(float(value) - float(old))
                provider_base = max(abs(float(old)), 1.0)
                if (
                    provider_delta >= self.provider_value_delta
                    or provider_delta / provider_base >= self.provider_relative_delta
                ):
                    return True
        return False


def market_context_id(
    *, asset_type: str, scoring_profile_id: str | None,
    format_class: str | None = None,
) -> str:
    """Share provider-compatible contexts without including a league ID."""
    payload = {
        "asset_type": str(asset_type).casefold(),
        "format": str(format_class or "dynasty-default").casefold(),
        # Current canonical dynasty market evidence is scoring-independent.
        # A provider-specific format_class is the explicit compatibility boundary;
        # a league's scoring-profile hash must never create per-league copies.
        "scoring_profile_scope": "provider-global" if format_class is None else "explicit-format",
    }
    return "market-context-v1:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def semantic_fingerprint(
    *, asset_id: str, asset_type: str, market_context_id: str,
    canonical_value: float, intrinsic_value: float | None, confidence: int,
    completeness: EvidenceCompleteness, provider_evidence: Iterable[SourceObservation],
    model_version: str, normalization_version: str,
) -> str:
    """Hash only semantic evidence; timestamps and league/event IDs are excluded."""
    providers = [{
        "provider": row.provider,
        "raw_value": row.raw_value,
        "normalized_value": row.normalized_value,
        "source_identity": row.source_identity,
        "normalization_version": row.normalization_version,
    } for row in provider_evidence]
    payload = {
        "asset_id": asset_id, "asset_type": asset_type,
        "market_context_id": market_context_id,
        "canonical_value": canonical_value, "intrinsic_value": intrinsic_value,
        "confidence": confidence, "completeness": completeness.value,
        "providers": sorted(providers, key=lambda row: (
            str(row["provider"]), str(row["source_identity"]), str(row["normalized_value"]),
        )),
        "model_version": model_version,
        "normalization_version": normalization_version,
        "materiality_policy_version": MARKET_MATERIALITY_POLICY_VERSION,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()

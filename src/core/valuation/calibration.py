"""Shared, explainable calibration for player and cached market values."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from src.core.valuation.consensus import build_canonical_consensus
from src.core.valuation.models import CalibrationStatus, NormalizedValuation
from src.core.valuation.normalization import normalize_value, prepare_distribution


@dataclass(frozen=True)
class AssetCalibration:
    intrinsic_value: int
    market_value: int | None
    calibrated_value: int
    market_weight: float
    confidence: int
    tier: str
    grade: str
    status: CalibrationStatus
    reasoning: tuple[str, ...]


def valuation_tier(value: int, *, market_available: bool) -> str:
    """Classify canonical value without granting elite status to weak evidence."""
    thresholds = (
        ((790, "Elite Franchise Player"), (675, "Cornerstone"), (550, "Core Starter"),
         (425, "Quality Starter"), (300, "Flex Asset"), (200, "Depth"),
         (100, "Developmental"))
        if market_available
        else ((850, "Core Starter"), (700, "Quality Starter"), (550, "Flex Asset"),
              (400, "Depth"), (250, "Developmental"))
    )
    for threshold, label in thresholds:
        if value >= threshold:
            return label
    return "Replacement Level"


def valuation_grade(value: int, *, market_available: bool) -> str:
    """Map the observed canonical distribution to a readable asset grade."""
    thresholds = (
        ((790, "A+"), (725, "A"), (650, "A-"), (575, "B+"), (500, "B"),
         (425, "B-"), (350, "C+"), (275, "C"), (200, "C-"), (125, "D"))
        if market_available
        else ((850, "A"), (775, "A-"), (700, "B+"), (625, "B"),
              (550, "B-"), (475, "C"), (400, "D"))
    )
    for threshold, label in thresholds:
        if value >= threshold:
            return label
    return "F"


def contextualize_valuation_tier(tier: str, age: float | None) -> str:
    """Keep value tiers semantically accurate across player age curves."""
    if age is None or age < 27:
        return tier
    if tier == "Developmental":
        return "Veteran Depth"
    if tier == "Replacement Level":
        return "Veteran Replacement"
    return tier


def calibrate_asset_value(
    intrinsic_value: int,
    market_value: int | None,
    confidence: int,
    *,
    status: CalibrationStatus = CalibrationStatus.INSUFFICIENT_DATA,
) -> AssetCalibration:
    """Blend independent intrinsic and market evidence on the canonical scale."""
    intrinsic = max(0, min(1000, round(intrinsic_value)))
    market = (
        max(0, min(1000, round(market_value)))
        if market_value is not None
        else None
    )
    market_available = (
        market is not None
        and status in {
            CalibrationStatus.CALIBRATED,
            CalibrationStatus.PARTIALLY_CALIBRATED,
            CalibrationStatus.STALE,
        }
    )
    if market_available:
        market_weight = min(0.75, max(0.35, confidence / 100))
        calibrated = round(
            market * market_weight + intrinsic * (1 - market_weight)
        )
        reasoning = (
            f"DTOS intrinsic value contributes {(1 - market_weight) * 100:.0f}%.",
            f"Provider market consensus contributes {market_weight * 100:.0f}%.",
            f"Market confidence is {confidence}/100 with status {status.value}.",
        )
    else:
        market_weight = 0.0
        calibrated = intrinsic
        reasoning = (
            "No sufficiently supported market consensus is available.",
            "The calibrated value therefore remains the disclosed DTOS intrinsic value.",
            "Elite classification is withheld when market evidence is unavailable.",
        )
    return AssetCalibration(
        intrinsic,
        market,
        calibrated,
        market_weight,
        max(0, min(100, confidence)),
        valuation_tier(calibrated, market_available=market_available),
        valuation_grade(calibrated, market_available=market_available),
        status,
        reasoning,
    )


def cached_market_consensus(
    market_data: dict[str, Any],
    player_ids: Iterable[str],
) -> dict[str, tuple[int | None, int, CalibrationStatus]]:
    """Normalize cached public providers once for downstream intelligence."""
    providers = market_data.get("providers") or {}
    supported = tuple(
        provider
        for provider in ("FantasyCalc", "DynastyProcess")
        if providers.get(provider)
    )
    distributions = {
        provider: prepare_distribution(
            provider,
            (
                row.get("value")
                for row in (providers.get(provider) or {}).values()
                if isinstance(row, dict) and row.get("value") is not None
            ),
        )
        for provider in supported
    }
    result: dict[str, tuple[int | None, int, CalibrationStatus]] = {}
    for player_id in player_ids:
        normalized: list[NormalizedValuation] = []
        for provider in supported:
            row = (providers.get(provider) or {}).get(str(player_id))
            if not isinstance(row, dict) or row.get("value") is None:
                continue
            try:
                raw = float(row["value"])
            except (TypeError, ValueError):
                continue
            normalized.append(
                normalize_value(
                    provider,
                    raw,
                    prepared_distribution=distributions[provider],
                    updated_at=row.get("updated_at"),
                    provider_confidence=int(row.get("confidence") or 70),
                )
            )
        consensus = build_canonical_consensus(
            tuple(normalized),
            expected_providers=max(1, len(supported)),
        )
        result[str(player_id)] = (
            consensus.market_consensus,
            consensus.confidence_score,
            consensus.calibration_status,
        )
    return result

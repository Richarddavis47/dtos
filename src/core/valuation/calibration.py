"""Shared, explainable calibration for player and cached market values."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from src.core.valuation.consensus import build_canonical_consensus
from src.core.valuation.models import CalibrationStatus, CanonicalConsensus, NormalizedValuation, PlayerMarketFact
from src.core.valuation.normalization import normalize_cached_value, prepare_distribution


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
    return {key: (value.market_consensus, value.confidence_score, value.calibration_status)
            for key, value in cached_market_results(market_data, player_ids).items()}


def cached_market_results(market_data: dict[str, Any], player_ids: Iterable[str]) -> dict[str, CanonicalConsensus]:
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
    result: dict[str, CanonicalConsensus] = {}
    for player_id in player_ids:
        normalized: list[NormalizedValuation] = []
        for provider in supported:
            row = (providers.get(provider) or {}).get(str(player_id))
            if not isinstance(row, dict) or row.get("value") is None:
                continue
            try:
                float(row["value"])
            except (TypeError, ValueError):
                continue
            normalized.append(
                normalize_cached_value(
                    provider,
                    row,
                    prepared_distribution=distributions[provider],
                    updated_at=row.get("updated_at"),
                    provider_confidence=int(row["confidence"]) if row.get("confidence") is not None else 70,
                )
            )
        consensus = build_canonical_consensus(
            tuple(normalized),
            expected_providers=max(1, len(supported)),
        )
        result[str(player_id)] = consensus
    return result


def cached_market_facts(market_data: dict[str, Any], player_ids: Iterable[str]) -> dict[str, PlayerMarketFact]:
    """One published-snapshot boundary shared by Market, dossiers and Trade.

    Reuse canonical selection/normalization. Do not consult provider namespaces,
    warehouses or manager portfolios to replace absent published evidence.
    Retained provider rows remain eligible under the existing quote policy.
    """
    from hashlib import sha256
    import json
    from src.core.valuation.quote_eligibility import exclusion_reason
    from src.core.valuation.source_time import market_times
    from src.core.valuation.consensus import MARKET_SELECTION_VERSION
    from src.core.valuation.config import NORMALIZATION_VERSION

    results = cached_market_results(market_data, player_ids)
    providers = market_data.get("providers") or {}
    statuses = market_data.get("provider_status") or {}
    facts = {}
    reasons = {
        "AMBIGUOUS_UNRESOLVED_PLAYER_IDENTITY": "Player identity is unresolved in Market evidence.",
        "STALE_BEYOND_USABLE_POLICY": "Market evidence is stale beyond the accepted usable policy.",
        "INCOMPATIBLE_PROVIDER_FORMAT": "No supported Market evidence in a compatible format.",
        "HISTORICAL_ONLY_EVIDENCE": "Only historical Market evidence is available; no supported current quote.",
        "ZERO_CONFIDENCE_INVALID_QUOTE": "No valid supported Market evidence is available.",
    }
    for player_id, result in results.items():
        used = tuple(p.provider for p in result.providers_used)
        rows = {name: table[player_id] for name, table in providers.items()
                if name in {"FantasyCalc", "DynastyProcess"} and isinstance(table, dict)
                and isinstance(table.get(player_id), dict)}
        clocks = tuple({"provider": name, **market_times(rows[name])} for name in used)
        source_time = max((r["source_updated_at"] for r in clocks if r["source_updated_at"]), default=None)
        retrieved = max((r["retrieved_at"] for r in clocks if r["retrieved_at"]), default=None)
        fallback = any(rows[name].get("retrieval_mode") == "cached_fallback"
                       or (statuses.get(name) or {}).get("refresh_result") == "cached_fallback" for name in used)
        freshnesses = {p.freshness for p in result.providers_used}
        freshness = next(iter(freshnesses)) if len(freshnesses) == 1 else "mixed" if freshnesses else "unavailable"
        reason = None
        if result.market_consensus is None:
            excluded = [exclusion_reason(name, row) for name, row in rows.items() if row]
            reason = next((reasons[key] for key in reasons if key in excluded), None)
            if reason is None:
                reason = ("Market generation is warming; no valid published Market evidence is available."
                          if market_data.get("status") == "warming" and not any(rows.values())
                          else result.warning if any(row.get("value") is not None for row in rows.values())
                          else "No supported Market evidence is available for this player.")
        # Per-asset source generation: independent of league/strategy/ownership.
        # Include the selected normalized result and source references so legacy
        # caches and freshness transitions cannot masquerade as one generation.
        identity = [player_id, NORMALIZATION_VERSION, MARKET_SELECTION_VERSION,
                    market_data.get("generation"), market_data.get("generated_at"),
                    rows, result, fallback, freshness, reason]
        generation = sha256(json.dumps(identity, sort_keys=True, default=lambda v: v.__dict__,
                                        separators=(",", ":")).encode()).hexdigest()
        facts[player_id] = PlayerMarketFact(player_id, result.market_consensus, generation,
            market_data.get("generated_at"), source_time, retrieved, freshness,
            "available" if result.market_consensus is not None else "unavailable", reason,
            result.confidence_score, used, result.providers_used, result.calibration_status.value,
            max(0, 100 - round(result.provider_spread / 4)) if result.provider_spread is not None else None,
            result.warning, fallback, clocks)
    return facts

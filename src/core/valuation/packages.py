"""Canonical package adjustments and explainable trade-safety guardrails."""
from __future__ import annotations

from typing import Any

from src.core.valuation.config import DEFAULT_CONFIG, ValuationConfig
from src.core.valuation.models import CalibrationStatus, PackageValue, TradeGuardrailResult


def adjusted_package_value(assets: tuple[Any, ...], config: ValuationConfig = DEFAULT_CONFIG) -> PackageValue:
    values = sorted((int(getattr(asset, "trade_value", 0) or getattr(asset, "dynasty_value", 0)) for asset in assets), reverse=True)
    raw_total = sum(values)
    adjusted = 0.0
    reasons: list[str] = []
    for index, value in enumerate(values):
        marginal = max(0.45, 1 - index * config.consolidation_penalty)
        if value < config.low_value_threshold and index:
            marginal *= 0.65
        adjusted += value * marginal
    if len(values) > 1:
        reasons.append(f"{len(values)}-asset package receives diminishing-return and roster-slot adjustments.")
    if sum(value < config.low_value_threshold for value in values) >= 2:
        reasons.append("Multiple low-value or low-liquidity pieces receive reduced marginal credit.")
    return PackageValue(raw_total, round(adjusted), round(adjusted - raw_total), tuple(reasons))


def evaluate_trade_guardrails(
    offered: tuple[Any, ...],
    requested: tuple[Any, ...],
    *,
    superflex: bool = False,
    confidence: int = 75,
    calibration_status: CalibrationStatus = CalibrationStatus.CALIBRATED,
    config: ValuationConfig = DEFAULT_CONFIG,
) -> TradeGuardrailResult:
    offer = adjusted_package_value(offered, config)
    request = adjusted_package_value(requested, config)
    premium = max((int(getattr(asset, "trade_value", 0) or getattr(asset, "dynasty_value", 0)) for asset in requested), default=0)
    centerpiece = max((int(getattr(asset, "trade_value", 0) or getattr(asset, "dynasty_value", 0)) for asset in offered), default=0)
    requested_qb = any(getattr(asset, "position", None) == "QB" for asset in requested)
    low_pieces = sum(int(getattr(asset, "trade_value", 0) or getattr(asset, "dynasty_value", 0)) < config.low_value_threshold for asset in offered)
    if calibration_status not in {CalibrationStatus.CALIBRATED, CalibrationStatus.PARTIALLY_CALIBRATED}:
        return TradeGuardrailResult("suppressed", "UNCALIBRATED_VALUES", "Precise packages are suppressed until values are calibrated.", offer.adjusted_value, request.adjusted_value, min(confidence, 40))
    if confidence < config.minimum_confidence:
        return TradeGuardrailResult("suppressed", "LOW_CONFIDENCE", "Provider confidence is below the trade-package threshold.", offer.adjusted_value, request.adjusted_value, confidence)
    required = request.adjusted_value * config.market_floor_tolerance * (config.superflex_qb_premium if superflex and requested_qb else 1)
    if premium >= config.elite_asset_threshold and centerpiece < config.premium_asset_threshold:
        code = "SUPERFLEX_QB_SCARCITY" if superflex and requested_qb else "ELITE_ASSET_MISMATCH"
        return TradeGuardrailResult("rejected", code, "A premium asset requires a meaningful centerpiece; low-value aggregation is insufficient.", offer.adjusted_value, request.adjusted_value, confidence)
    if low_pieces >= 2 and premium >= config.premium_asset_threshold:
        return TradeGuardrailResult("rejected", "TOO_MANY_LOW_VALUE_PIECES", "Low-value pieces cannot substitute for a premium centerpiece.", offer.adjusted_value, request.adjusted_value, confidence)
    if offer.adjusted_value < required:
        return TradeGuardrailResult("rejected", "BELOW_MARKET_FLOOR", "Package is below the current calibrated market floor.", offer.adjusted_value, request.adjusted_value, confidence)
    return TradeGuardrailResult("accepted", None, "Package clears canonical DTOS trade-safety guardrails.", offer.adjusted_value, request.adjusted_value, confidence)

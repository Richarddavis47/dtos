"""Robust source-preserving consensus and historical trend calculations."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median, pstdev

from src.core.data_platform.models import ConsensusResult, DataEnvelope, TrendResult


def consensus(key: str, rows: tuple[DataEnvelope, ...], expected: tuple[str, ...]) -> ConsensusResult:
    available = tuple(row for row in rows if isinstance(row.value, (int, float)) and row.quality.status != "blocked")
    missing = tuple(name for name in expected if name not in {row.provider for row in available})
    if not available:
        return ConsensusResult(key, None, 0, None, 0, (), (), missing, rows)
    values = tuple(float(row.value) for row in available)
    center = median(values)
    deviations = tuple(abs(value - center) for value in values)
    scale = median(deviations) or max(abs(center) * 0.1, 1)
    weights = tuple(max(0.05, row.confidence / 100) * max(0.05, row.reliability / 100) * (1 if row.freshness == "fresh" else 0.7) / (1 + abs(float(row.value) - center) / scale) for row in available)
    result = sum(float(row.value) * weight for row, weight in zip(available, weights, strict=True)) / sum(weights)
    variance = round(pstdev(values), 2) if len(values) > 1 else 0.0
    agreement = max(0, min(100, round(100 - variance / max(abs(result), 1) * 180)))
    coverage = len(available) / max(len(expected), 1)
    source_confidence = sum(row.confidence * row.reliability / 100 for row in available) / len(available)
    freshness = sum(100 if row.freshness == "fresh" else 65 for row in available) / len(available)
    confidence = round(source_confidence * 0.35 + agreement * 0.30 + coverage * 100 * 0.20 + freshness * 0.15)
    bullish = tuple(sorted(row.provider for row in available if float(row.value) > result * 1.05))
    bearish = tuple(sorted(row.provider for row in available if float(row.value) < result * 0.95))
    return ConsensusResult(key, round(result, 2), confidence, variance, agreement, bullish, bearish, missing, rows)


def trend(key: str, rows: tuple[DataEnvelope, ...], now: datetime | None = None) -> TrendResult:
    now = now or datetime.now(timezone.utc)
    numeric = tuple(row for row in rows if isinstance(row.value, (int, float)))
    values = tuple(float(row.value) for row in numeric)
    absolute = round(values[-1] - values[0], 2) if len(values) > 1 else None
    percentage = round(absolute / abs(values[0]) * 100, 2) if absolute is not None and values[0] else None
    volatility = round(pstdev(values) / max(abs(sum(values) / len(values)), 1) * 100, 2) if len(values) > 1 else 0.0
    periods: dict[str, float | None] = {}
    for label, days in (("7 days", 7), ("30 days", 30), ("90 days", 90), ("1 year", 365), ("lifetime", None)):
        eligible = numeric if days is None else tuple(row for row in numeric if datetime.fromisoformat(row.timestamp.replace("Z", "+00:00")) >= now - timedelta(days=days))
        periods[label] = round(float(eligible[-1].value) - float(eligible[0].value), 2) if len(eligible) > 1 else None
    momentum = percentage or 0.0
    direction = "Rising" if momentum > 3 else "Falling" if momentum < -3 else "Stable"
    return TrendResult(key, absolute, percentage, momentum, volatility, direction, periods)

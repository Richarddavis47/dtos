"""Explainable historical trend and volatility calculations."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev

from src.core.market_intelligence.history import MarketSnapshot
from src.core.market_intelligence.models import MarketTrend


def _timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _change(rows: tuple[MarketSnapshot, ...], days: int, now: datetime) -> float | None:
    eligible = [row for row in rows if (stamp := _timestamp(row.timestamp)) and now - timedelta(days=days) <= stamp <= now]
    if len(eligible) < 2 or not eligible[0].value:
        return None
    return round((eligible[-1].value - eligible[0].value) / abs(eligible[0].value) * 100, 2)


def calculate_trend(rows: tuple[MarketSnapshot, ...], now: datetime | None = None) -> MarketTrend:
    now = now or datetime.now(timezone.utc)
    unavailable = MarketTrend("Unavailable", None, None, None, {}, ("COMPARABLE_HISTORY_UNAVAILABLE",))
    if not rows or any(not all((row.value_concept, row.value_scale, row.format_key, row.methodology)) for row in rows):
        return unavailable
    boundaries = {(row.asset_id, row.provider, row.value_concept, row.value_scale,
                   row.format_key, row.methodology) for row in rows}
    if len(boundaries) != 1:
        reason = "METHODOLOGY_BOUNDARY" if len({row.methodology for row in rows}) > 1 else "INCOMPATIBLE_OBSERVATION_BOUNDARY"
        return MarketTrend("Unavailable", None, None, None, {}, (reason,))
    valid = [(stamp, row) for row in rows if (stamp := _timestamp(row.timestamp)) is not None and stamp <= now]
    # Conflicting same-time observations do not define an ordered price path.
    by_time = {}
    for stamp, row in valid:
        if stamp in by_time and by_time[stamp] != row:
            return unavailable
        by_time[stamp] = row
    rows = tuple(row for _, row in sorted(by_time.items()))
    if len(rows) < 2 or rows[0].value == 0:
        return unavailable
    # Arrival order is knowledge order, not proof of a newer source state.
    # Keep late older facts, but never present them as forward price movement.
    previous_source = None
    for row in rows:
        source = _timestamp(row.source_updated_at) if row.source_updated_at else None
        if source is not None and previous_source is not None and source < previous_source:
            return MarketTrend("Unavailable", None, None, None, {}, ("SOURCE_TIME_ORDER_UNAVAILABLE",))
        if source is not None:
            previous_source = source
    values = [row.value for row in rows]
    momentum = round((values[-1] - values[0]) / abs(values[0]) * 100, 2) if len(values) >= 2 and values[0] else 0.0
    volatility = round(pstdev(values) / max(abs(mean(values)), 1) * 100, 2) if len(values) >= 2 else 0.0
    drift = round(rows[-1].confidence - rows[0].confidence, 2) if len(rows) >= 2 else 0.0
    direction = "Rising" if momentum > 3 else "Falling" if momentum < -3 else "Stable"
    periods = {"7 day": _change(rows, 7, now), "30 day": _change(rows, 30, now), "Season": _change(rows, 180, now), "Career": momentum if len(rows) >= 2 else None}
    reasons = []
    if rows[-1].value != rows[0].value:
        reasons.append("MARKET_PRICE_CHANGED" if rows[0].value_concept == "external_provider_raw_price" else "NORMALIZED_VALUE_CHANGED")
    if drift:
        reasons.append("EVIDENCE_CONFIDENCE_CHANGED")
    if rows[0].source_rank is not None and rows[-1].source_rank is not None and rows[0].source_rank != rows[-1].source_rank:
        reasons.append("RANK_CHANGED_WITHOUT_PRICE_CHANGE" if rows[-1].value == rows[0].value else "SOURCE_RANK_CHANGED")
    if rows[0].source_tier is not None and rows[-1].source_tier is not None and rows[0].source_tier != rows[-1].source_tier:
        reasons.append("SOURCE_TIER_CHANGED")
    return MarketTrend(direction, momentum, volatility, drift, periods, tuple(reasons) or ("UNCHANGED_EVIDENCE",))

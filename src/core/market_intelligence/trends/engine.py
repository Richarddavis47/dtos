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
    eligible = [row for row in rows if (stamp := _timestamp(row.timestamp)) and stamp >= now - timedelta(days=days)]
    if len(eligible) < 2 or not eligible[0].value:
        return None
    return round((eligible[-1].value - eligible[0].value) / abs(eligible[0].value) * 100, 2)


def calculate_trend(rows: tuple[MarketSnapshot, ...], now: datetime | None = None) -> MarketTrend:
    now = now or datetime.now(timezone.utc)
    values = [row.value for row in rows]
    momentum = round((values[-1] - values[0]) / abs(values[0]) * 100, 2) if len(values) >= 2 and values[0] else 0.0
    volatility = round(pstdev(values) / max(abs(mean(values)), 1) * 100, 2) if len(values) >= 2 else 0.0
    drift = round(rows[-1].confidence - rows[0].confidence, 2) if len(rows) >= 2 else 0.0
    direction = "Rising" if momentum > 3 else "Falling" if momentum < -3 else "Stable"
    periods = {"7 day": _change(rows, 7, now), "30 day": _change(rows, 30, now), "Season": _change(rows, 180, now), "Career": momentum if len(rows) >= 2 else None}
    return MarketTrend(direction, momentum, volatility, drift, periods)

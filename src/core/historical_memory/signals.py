"""Conservative, explainable signals from historical observations."""
from __future__ import annotations

from src.core.historical_memory.models import HistorySignal


def role_trend_signal(
    metric_name: str, values: list[float | None], date_range: str,
) -> HistorySignal:
    observed = [value for value in values if value is not None]
    if len(observed) < 4:
        return HistorySignal(metric_name, "insufficient_data", 0, ("At least four observed weeks are required.",), 20, date_range)
    midpoint = len(observed) // 2
    early = sum(observed[:midpoint]) / midpoint
    late = sum(observed[midpoint:]) / (len(observed) - midpoint)
    change = late - early
    status = "role_growth" if change >= .08 else "role_erosion" if change <= -.08 else "stable"
    return HistorySignal(metric_name, status, min(100, round(abs(change) * 300)), (f"Late-period {metric_name}: {late:.1%}.", f"Early-period {metric_name}: {early:.1%}.",), min(90, 50 + len(observed) * 4), date_range)

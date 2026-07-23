"""Reproducible production aggregates that preserve missing-data semantics."""
from __future__ import annotations

from statistics import mean, median, pstdev
from typing import Any


def aggregate_production(rows: list[dict[str, Any]]) -> dict[str, Any]:
    observed = [float(row["fantasy_points"]) for row in rows if row.get("fantasy_points") is not None]
    if not observed:
        return {
            "availability": "unavailable", "games_played": 0, "season_total": None,
            "points_per_game": None, "median": None, "floor": None, "ceiling": None,
            "standard_deviation": None, "coefficient_of_variation": None,
            "consistency_score": None,
        }
    deviation = pstdev(observed) if len(observed) > 1 else 0.0
    average = mean(observed)
    return {
        "availability": "calculated",
        "games_played": len(observed),
        "season_total": round(sum(observed), 2),
        "points_per_game": round(average, 2),
        "median": round(median(observed), 2),
        "floor": round(min(observed), 2),
        "ceiling": round(max(observed), 2),
        "standard_deviation": round(deviation, 2),
        "coefficient_of_variation": round(deviation / average, 3) if average else None,
        "consistency_score": round(max(0, 100 - (deviation / average * 100)), 1) if average else None,
        "rolling_3": rolling_average(observed, 3),
        "rolling_5": rolling_average(observed, 5),
        "rolling_8": rolling_average(observed, 8),
    }


def rolling_average(values: list[float], window: int) -> float | None:
    return round(mean(values[-window:]), 2) if values else None

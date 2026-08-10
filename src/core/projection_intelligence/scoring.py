"""League-specific conversion of projected football statistics."""
from __future__ import annotations

from typing import Any


STAT_KEYS = {
    "pass_yd": "pass_yd", "pass_td": "pass_td", "pass_int": "pass_int",
    "pass_2pt": "pass_2pt", "rush_yd": "rush_yd", "rush_td": "rush_td",
    "rush_2pt": "rush_2pt", "rec": "rec", "rec_yd": "rec_yd",
    "rec_td": "rec_td", "rec_2pt": "rec_2pt", "fum_lost": "fum_lost",
    "fgm": "fgm", "fgmiss": "fgmiss", "xpm": "xpm", "xpmiss": "xpmiss",
}


def fantasy_points(stats: dict[str, Any], scoring: dict[str, Any], position: str = "") -> float:
    """Score raw projected stats with the league's actual supported rules."""
    total = 0.0
    for stat, scoring_key in STAT_KEYS.items():
        total += float(stats.get(stat) or 0) * float(scoring.get(scoring_key) or 0)
    if position.upper() == "TE":
        total += float(stats.get("rec") or 0) * float(
            scoring.get("bonus_rec_te") or scoring.get("rec_te") or 0
        )
    for threshold, key in ((300, "bonus_pass_yd_300"), (400, "bonus_pass_yd_400")):
        if float(stats.get("pass_yd") or 0) >= threshold:
            total += float(scoring.get(key) or 0)
    for stat, threshold, key in (
        ("rush_yd", 100, "bonus_rush_yd_100"),
        ("rec_yd", 100, "bonus_rec_yd_100"),
    ):
        if float(stats.get(stat) or 0) >= threshold:
            total += float(scoring.get(key) or 0)
    return round(total, 2)

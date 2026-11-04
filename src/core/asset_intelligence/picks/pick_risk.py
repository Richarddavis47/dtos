"""Draft-pick uncertainty evaluation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.core.asset_intelligence.models import Evidence, RiskReport


def evaluate_pick_risk(pick: dict[str, Any]) -> RiskReport:
    season = int(pick.get("season") or datetime.now(timezone.utc).year + 1)
    round_number = int(pick.get("round") or 4)
    years_away = max(0, season - datetime.now(timezone.utc).year)
    score = min(90, 25 + round_number * 7 + years_away * 5)
    evidence = (
        Evidence("Round uncertainty", f"Round {round_number}", round_number * 7, "Later rounds contain a wider range of player outcomes.", "Sleeper pick round"),
        Evidence("Time uncertainty", f"{years_away} year(s) away", years_away * 5, "Longer horizons add roster, class, and draft-position uncertainty.", "Pick season and current UTC year"),
        Evidence("Projected slot", "Unknown", 10, "Unknown draft position adds explicit uncertainty rather than an assumed midpoint.", "Not available", False),
    )
    level = "High" if score >= 65 else "Moderate" if score >= 40 else "Low"
    return RiskReport(score, level, evidence, ("Future class strength and franchise finish are not modeled.",))

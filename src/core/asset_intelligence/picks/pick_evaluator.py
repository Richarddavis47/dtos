"""Contextual draft-pick report builder."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.core.asset_intelligence.evidence import evidence_engine
from src.core.asset_intelligence.models import AssetContext, AssetRecommendation, PickReport
from src.core.asset_intelligence.picks.pick_risk import evaluate_pick_risk
from src.core.asset_intelligence.picks.pick_value import dynasty_pick_value, market_pick_value


def evaluate_pick(pick: dict[str, Any], context: AssetContext) -> PickReport:
    season = int(pick.get("season") or datetime.now(timezone.utc).year + 1)
    round_number = int(pick.get("round") or 4)
    dynasty = dynasty_pick_value(pick)
    market = market_pick_value()
    risk = evaluate_pick_risk(pick)
    window = context.team_window.casefold()
    if "rebuild" in window or "ascension" in window:
        action, priority = "Hold", "High"
        rationale = "The Front Office window favors preserving future optionality."
    elif "championship" in window and season > datetime.now(timezone.utc).year + 1:
        action, priority = "Trade", "Medium"
        rationale = "A distant pick may be reviewed against current-window needs, but no trade is assumed."
    else:
        action, priority = "Hold", "Medium"
        rationale = "No contextual threshold supports moving the pick without a specific return."
    evidence = dynasty.evidence + (risk.evidence[0],)
    recommendation = AssetRecommendation(action, f"{rationale} The GM makes the final decision.", priority, evidence_engine.confidence(evidence), evidence)
    return PickReport(
        season,
        round_number,
        str(pick.get("original_team") or pick.get("original_owner") or "Unknown"),
        int(pick.get("current_owner_id") or pick.get("owner_id")) if (pick.get("current_owner_id") or pick.get("owner_id")) is not None else None,
        dynasty,
        market,
        risk,
        f"Round {round_number}; exact slot unknown",
        "Next draft" if season <= datetime.now(timezone.utc).year + 1 else f"{season - datetime.now(timezone.utc).year} years",
        recommendation,
        tuple(dict.fromkeys((*dynasty.limitations, *market.limitations, *risk.limitations))),
    )

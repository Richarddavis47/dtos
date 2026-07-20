"""Traceable draft-pick value calculations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.core.asset_intelligence.evidence import evidence_engine
from src.core.asset_intelligence.models import AssetEvaluation, Evidence

ROUND_BASE = {1: 82, 2: 64, 3: 48, 4: 36}


def dynasty_pick_value(pick: dict[str, Any]) -> AssetEvaluation:
    round_number = int(pick.get("round") or 4)
    season = int(pick.get("season") or datetime.now(timezone.utc).year + 1)
    years_away = max(0, season - datetime.now(timezone.utc).year)
    round_score = ROUND_BASE.get(round_number, max(20, 44 - round_number * 6))
    time_adjustment = -min(15, max(0, years_away - 1) * 5)
    evidence = (
        Evidence("Draft round", f"Round {round_number}", round_score - 50, "Earlier rounds receive higher option-value baselines using the published DTOS v1 table.", "Sleeper pick ledger and DTOS ROUND_BASE"),
        Evidence("Time to draft", f"{season}; {years_away} year(s) away", time_adjustment, "Picks beyond the next draft receive a small, explicit liquidity discount.", "Pick season and current UTC year"),
        Evidence("Projected slot", "Unknown", 0, "No early, middle, or late slot is assumed.", "Not available", False),
    )
    score = round_score + time_adjustment
    return AssetEvaluation("Dynasty Value", score, evidence_engine.confidence(evidence), "Round and time-horizon option value without guessing a future draft slot.", evidence, ("Draft class quality and projected finish are unavailable.",))


def market_pick_value() -> AssetEvaluation:
    evidence = (Evidence("Market consensus", "Provider unavailable", 0, "A neutral baseline is retained until a traceable market feed is connected.", "Not available", False),)
    return AssetEvaluation("Market Value", 50, evidence_engine.confidence(evidence, 30), "Neutral market placeholder; it is not inferred from DTOS dynasty value.", evidence, ("Historical pick trades and external market consensus are unavailable.",))

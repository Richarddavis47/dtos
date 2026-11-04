"""Traceable draft-pick value calculations."""
from __future__ import annotations

from typing import Any

from src.core.asset_intelligence.models import AssetEvaluation, Evidence

def dynasty_pick_value(pick: dict[str, Any]) -> AssetEvaluation:
    return AssetEvaluation("Pick utility", None, 0,
        "No supported independent long-term pick utility scalar.",
        (Evidence("Draft identity", f"{pick.get('year', pick.get('season', 'Unavailable'))} Round {pick.get('round', 'Unavailable')}",
                  0, "Identity and timing, not a dynasty utility score.", "Sleeper pick ledger"),),
        ("Use canonical identity, external Market quote, range/confidence and portfolio evidence separately.",))


def market_pick_value() -> AssetEvaluation:
    evidence = (Evidence("Market consensus", "Provider unavailable", 0, "No validated external pick quote is connected.", "Not available", False),)
    return AssetEvaluation("Market Value", None, 0, "Pick Market price unavailable; internal option scores are not acquisition prices.", evidence, ("Current external pick Market evidence is unavailable.",))

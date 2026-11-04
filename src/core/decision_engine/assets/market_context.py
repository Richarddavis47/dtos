"""Market-context interface for future valuation providers."""
from __future__ import annotations

from typing import Any


def build_market_context(data: dict[str, Any]) -> dict[str, Any]:
    """Return observable league supply signals without inventing market values."""
    positions = {position: 0 for position in ("QB", "RB", "WR", "TE")}
    for team in data.get("teams") or []:
        for player in team.get("players") or []:
            position = str(player.get("position") or "")
            if position in positions:
                positions[position] += 1
    return {
        "rostered_position_supply": positions,
        "team_count": len(data.get("teams") or []),
        "valuation_provider": None,
        "trend_provider": None,
    }

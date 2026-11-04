"""League-relative positional-scarcity signals."""
from __future__ import annotations

from typing import Any


def positional_scarcity(market_context: dict[str, Any], position: str) -> tuple[int, str]:
    supply = int((market_context.get("rostered_position_supply") or {}).get(position, 0))
    teams = max(1, int(market_context.get("team_count") or 1))
    per_team = supply / teams
    targets = {"QB": 3, "RB": 7, "WR": 9, "TE": 4}
    target = targets.get(position, 1)
    scarcity = max(0, min(100, round((1 - min(per_team / target, 1)) * 100)))
    return scarcity, f"{supply} rostered {position}s across {teams} teams ({per_team:.1f} per team)."

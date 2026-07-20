"""Normalize cached player data into a stable profile."""
from __future__ import annotations

from typing import Any

from src.core.asset_intelligence.models import PlayerProfile


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _age(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_player_profile(player: dict[str, Any]) -> PlayerProfile:
    name = player.get("full_name") or player.get("name") or " ".join(
        str(value) for value in (player.get("first_name"), player.get("last_name")) if value
    )
    return PlayerProfile(
        player_id=str(player.get("player_id") or player.get("id") or "unknown"),
        name=str(name or "Unknown player"),
        position=str(player.get("position") or "Unknown"),
        nfl_team=str(player.get("team") or "Free Agent"),
        age=_age(player.get("age")),
        experience=_integer(player.get("years_exp")),
        contract_status=str(player.get("contract_status") or "Unavailable"),
        injury_status=str(player.get("injury_status") or "No reported designation"),
        bye_week=str(player.get("bye_week") or "Unavailable"),
    )

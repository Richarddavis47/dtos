"""Application-facing matchup projections through the Intelligence Orchestrator."""
from __future__ import annotations

from statistics import mean
from typing import Any

from src.core.intelligence import intelligence_orchestrator


def matchup_player_values(
    data: dict[str, Any],
    matchup_groups: dict[str, list[dict[str, Any]]],
) -> dict[int, dict[str, Any]]:
    roster_ids = tuple(
        int(side.get("roster_id") or 0)
        for sides in matchup_groups.values()
        for side in sides[:2]
        if int(side.get("roster_id") or 0)
    )
    return intelligence_orchestrator.matchup_player_values(data, roster_ids)


def matchup_projection(
    data: dict[str, Any],
    sides: list[dict[str, Any]],
    player_values: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    summaries = []
    player_edges = []
    missing = 0
    values_by_roster = player_values
    for side in sides[:2]:
        roster_id = int(side.get("roster_id") or 0)
        if values_by_roster is None:
            values_by_roster = intelligence_orchestrator.matchup_player_values(
                data,
                tuple(
                    int(item.get("roster_id") or 0)
                    for item in sides[:2]
                ),
            )
        lineup = side.get("lineup") or []
        roster_values = values_by_roster.get(roster_id) or {}
        values = [roster_values.get(str(player.get("id"))) for player in lineup]
        projections = [item.projection for item in values if item is not None]
        missing += len(lineup) - len(projections)
        total = sum(item.projected_points or 0 for item in projections)
        floor = sum(item.floor or 0 for item in projections)
        ceiling = sum(item.ceiling or 0 for item in projections)
        confidence = round(mean(item.confidence for item in projections)) if projections else 0
        position_totals: dict[str, float] = {}
        for player, value in zip(lineup, values):
            if value is None:
                continue
            position = str(player.get("position") or "Other")
            position_totals[position] = position_totals.get(position, 0) + (value.projection.projected_points or 0)
            player_edges.append(((value.projection.ceiling or 0) - (value.projection.floor or 0), value.name, side.get("team")))
        summaries.append({"roster_id": roster_id, "team": side.get("team"), "projected": round(total, 2), "floor": round(floor, 2), "ceiling": round(ceiling, 2), "confidence": confidence, "positions": position_totals})
    advantages = []
    if len(summaries) == 2:
        for position in sorted(set(summaries[0]["positions"]) | set(summaries[1]["positions"])):
            delta = summaries[0]["positions"].get(position, 0) - summaries[1]["positions"].get(position, 0)
            if delta:
                winner = summaries[0]["team"] if delta > 0 else summaries[1]["team"]
                advantages.append((abs(delta), f"{winner} {position} +{abs(delta):.1f}"))
    largest = max(advantages, default=(0, "No projected positional edge"))[1]
    volatile = max(player_edges, default=(0, "Unavailable", ""))
    confidence = round(mean(item["confidence"] for item in summaries)) if summaries else 0
    return {"sides": summaries, "largest_advantage": largest, "highest_volatility": f"{volatile[1]} ({volatile[2]})" if volatile[1] != "Unavailable" else "Unavailable", "confidence": "High" if confidence >= 75 else "Medium" if confidence >= 50 else "Low", "missing": missing, "status": "fallback" if summaries else "unavailable"}

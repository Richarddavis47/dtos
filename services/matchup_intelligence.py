"""Application-facing matchup projections through the Intelligence Orchestrator."""
from __future__ import annotations

from statistics import mean
from typing import Any

from src.core.intelligence import intelligence_orchestrator
from src.core.projection_intelligence import projection_service


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
        player_rows = []
        sleeper_total = 0.0
        sleeper_available = 0
        dtos_total = 0.0
        dtos_available = 0
        for player, value in zip(lineup, values):
            player_id = str(player.get("id") or "")
            canonical = projection_service.player(player_id) or {}
            sleeper_value = canonical.get("sleeper_projection")
            dtos_value = canonical.get("dtos_projection")
            if sleeper_value is not None:
                sleeper_total += float(sleeper_value)
                sleeper_available += 1
            if dtos_value is not None:
                dtos_total += float(dtos_value)
                dtos_available += 1
            player_rows.append({
                "player_id": player_id, "name": player.get("name"),
                "position": player.get("position"), "nfl_team": player.get("nfl_team"),
                "sleeper_projection": sleeper_value, "dtos_projection": dtos_value,
                "canonical_projection": canonical.get("canonical_projection"),
                "actual_points": player.get("points"),
                "projection_status": canonical.get("status") or "unavailable",
                "agreement": canonical.get("projection_agreement"),
            })
            if value is None:
                continue
            position = str(player.get("position") or "Other")
            position_totals[position] = position_totals.get(position, 0) + (value.projection.projected_points or 0)
            player_edges.append(((value.projection.ceiling or 0) - (value.projection.floor or 0), value.name, side.get("team")))
        summaries.append({
            "roster_id": roster_id, "team": side.get("team"),
            "projected": round(total, 2), "canonical_total": round(total, 2),
            "sleeper_total": round(sleeper_total, 2), "dtos_total": round(dtos_total, 2),
            "sleeper_coverage": f"{sleeper_available}/{len(lineup)}",
            "dtos_coverage": f"{dtos_available}/{len(lineup)}",
            "sleeper_status": "Complete" if sleeper_available == len(lineup) else "Partial",
            "dtos_status": "Complete" if dtos_available == len(lineup) else "Partial",
            "floor": round(floor, 2), "ceiling": round(ceiling, 2),
            "confidence": confidence, "positions": position_totals, "players": player_rows,
        })
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
    snapshot_ids = sorted({
        item.projection.projection_snapshot_id
        for roster_values in (values_by_roster or {}).values()
        for item in roster_values.values()
        if item.projection.projection_snapshot_id
    })
    projected_margin = round(abs(summaries[0]["projected"] - summaries[1]["projected"]), 2) if len(summaries) == 2 else None
    return {"sides": summaries, "largest_advantage": largest, "highest_volatility": f"{volatile[1]} ({volatile[2]})" if volatile[1] != "Unavailable" else "Unavailable", "confidence": "High" if confidence >= 75 else "Medium" if confidence >= 50 else "Low", "missing": missing, "status": "canonical" if len(snapshot_ids) == 1 else "fallback" if summaries else "unavailable", "projection_snapshot_id": snapshot_ids[0] if len(snapshot_ids) == 1 else None, "snapshot_consistent": len(snapshot_ids) <= 1, "projected_margin": projected_margin, "win_probability": None}

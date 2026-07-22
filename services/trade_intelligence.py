"""Application-facing Trade Intelligence view assembly."""
from __future__ import annotations

from typing import Any

from src.core.intelligence import intelligence_orchestrator


def build_trade_center(data: dict[str, Any], active_roster_id: int | None = None) -> dict[str, Any]:
    teams = list(data.get("teams") or [])
    if not teams:
        raise ValueError("No Front Office is available for Trade Intelligence.")
    valid_ids = {int(team.get("roster_id") or 0) for team in teams}
    roster_id = active_roster_id if active_roster_id in valid_ids else int(teams[0].get("roster_id") or 0)
    active_team = next(team for team in teams if int(team.get("roster_id") or 0) == roster_id)
    intelligence = intelligence_orchestrator.analyze(data, roster_id)
    dossiers: tuple[Any, ...] = intelligence.trades
    impacts = {}
    for dossier in dossiers:
        def totals(assets: tuple[Any, ...], attribute: str) -> float:
            return sum(float(getattr(intelligence.player_values.get(asset.asset_id), attribute).value or 0) for asset in assets if intelligence.player_values.get(asset.asset_id))

        def projections(assets: tuple[Any, ...]) -> float:
            return sum(float(intelligence.player_values[asset.asset_id].projection.projected_points or 0) for asset in assets if asset.asset_id in intelligence.player_values)

        received, sent = dossier.proposal.assets_received, dossier.proposal.assets_sent
        impacts[dossier.partner.roster_id] = {
            "dtos_dynasty": round(totals(received, "dtos_dynasty") - totals(sent, "dtos_dynasty"), 1),
            "market": round(totals(received, "market_consensus") - totals(sent, "market_consensus"), 1),
            "contender": round(totals(received, "contender") - totals(sent, "contender"), 1),
            "rebuild": round(totals(received, "rebuilder") - totals(sent, "rebuilder"), 1),
            "weekly": round(projections(received) - projections(sent), 2),
        }
    return {"active_team": active_team, "teams": teams, "dossiers": dossiers, "value_impacts": impacts, "unified_recommendation": intelligence.recommendation}

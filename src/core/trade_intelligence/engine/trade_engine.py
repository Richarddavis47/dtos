"""Trade Intelligence orchestration over Decision and Asset Intelligence."""
from __future__ import annotations

from typing import Any

from src.core.asset_intelligence import AssetContext
from src.core.decision_engine import DecisionContext, TeamDecision, evaluate_team
from src.core.trade_intelligence.engine.recommendation_engine import prioritize
from src.core.trade_intelligence.engine.trade_evaluator import evaluate_proposal
from src.core.trade_intelligence.engine.trade_generator import generate_proposals
from src.core.trade_intelligence.gm import evaluate_partners
from src.core.trade_intelligence.market import build_asset_pool
from src.core.trade_intelligence.models import TradeDossier


def _asset_context(decision: TeamDecision) -> AssetContext:
    needs = tuple(position for position, evaluation in decision.position_evaluations.items() if evaluation.score < 55)
    depths = {position: room.total_players for position, room in decision.profile.position_rooms.items()}
    return AssetContext(
        decision.profile.league_id,
        decision.profile.roster_id,
        decision.profile.league_settings,
        decision.window.value,
        decision.profile.strategy,
        needs,
        depths,
        decision.profile.market_context.get("position_counts") or {},
    )


class TradeIntelligence:
    def opportunities(self, data: dict[str, Any], active_roster_id: int, limit: int = 12) -> tuple[TradeDossier, ...]:
        teams = data.get("teams") or []
        if not any(int(team.get("roster_id") or 0) == active_roster_id for team in teams):
            raise ValueError(f"Front Office {active_roster_id} is not available.")
        league = data.get("league") or {}
        league_id = str(league.get("league_id") or "configured-league")
        settings = {**(data.get("league_settings") or {}), "roster_positions": league.get("roster_positions") or []}
        decisions = {
            int(team.get("roster_id") or 0): evaluate_team(
                data,
                int(team.get("roster_id") or 0),
                DecisionContext(int(team.get("roster_id") or 0), league_id, settings),
            )
            for team in teams
        }
        active = decisions[active_roster_id]
        reports = evaluate_partners(data, active, decisions)
        team_by_id = {int(team.get("roster_id") or 0): team for team in teams}
        dossiers = []
        for partner in reports:
            partner_decision = decisions[partner.roster_id]
            outgoing = build_asset_pool(data, team_by_id[active_roster_id], _asset_context(partner_decision))
            incoming = build_asset_pool(data, team_by_id[partner.roster_id], _asset_context(active))
            proposals = generate_proposals(active_roster_id, partner.roster_id, outgoing, incoming)
            alternative_labels = tuple(asset.label for asset in sorted(incoming, key=lambda item: (-item.team_fit_value, item.label))[:3])
            dossiers.extend(evaluate_proposal(proposal, active, partner, alternative_labels) for proposal in proposals)
        return prioritize(tuple(dossiers), limit)


trade_intelligence = TradeIntelligence()

"""Trade Intelligence orchestration over Decision and Asset Intelligence."""
from __future__ import annotations

from typing import Any

from src.core.asset_intelligence import AssetContext
from src.core.decision_engine import TeamDecision
from src.core.trade_intelligence.engine.recommendation_engine import prioritize
from src.core.trade_intelligence.engine.trade_evaluator import evaluate_proposal
from src.core.trade_intelligence.engine.trade_generator import generate_proposals
from src.core.trade_intelligence.gm import evaluate_partners
from src.core.trade_intelligence.market import build_asset_pool
from src.core.trade_intelligence.models import TradeDossier
from src.core.front_office_intelligence import LeagueFrontOfficeModel
from src.core.valuation import cached_market_consensus
from src.core.trade_intelligence.evidence_context import build_trade_evidence_context


def _asset_context(decision: TeamDecision) -> AssetContext:
    needs = tuple(position for position, evaluation in decision.position_evaluations.items() if evaluation.score < 55)
    depths = {position: room.total_players for position, room in decision.profile.position_rooms.items()}
    return AssetContext(
        decision.profile.league_id,
        decision.profile.roster_id,
        decision.profile.league_settings,
        decision.competitive_window.classification.value,
        decision.profile.strategy,
        needs,
        depths,
        decision.profile.market_context.get("position_counts") or {},
    )


class TradeIntelligence:
    def opportunities(
        self,
        data: dict[str, Any],
        active_roster_id: int,
        limit: int = 12,
        *,
        decisions: dict[int, TeamDecision] | None = None,
        front_office_model: LeagueFrontOfficeModel | None = None,
    ) -> tuple[TradeDossier, ...]:
        teams = data.get("teams") or []
        if not any(int(team.get("roster_id") or 0) == active_roster_id for team in teams):
            raise ValueError(f"Front Office {active_roster_id} is not available.")
        if decisions is None:
            from src.core.front_office_intelligence import build_league_model

            front_office_model = build_league_model(data)
            decisions = {
                roster_id: report.decision
                for roster_id, report in front_office_model.reports.items()
            }
        active = decisions[active_roster_id]
        reports = evaluate_partners(data, active, decisions, front_office_model)
        team_by_id = {int(team.get("roster_id") or 0): team for team in teams}
        player_ids = {
            str(player.get("id") or player.get("player_id"))
            for team in teams
            for player in (team.get("players") or ())
            if player.get("id") or player.get("player_id")
        }
        market_values = cached_market_consensus(data.get("market_data") or {}, player_ids)
        all_assets = []
        partner_pools = []
        for partner in reports:
            partner_decision = decisions[partner.roster_id]
            outgoing = build_asset_pool(data, team_by_id[active_roster_id], _asset_context(partner_decision), market_values)
            incoming = build_asset_pool(data, team_by_id[partner.roster_id], _asset_context(active), market_values)
            partner_pools.append((partner, outgoing, incoming))
            all_assets.extend((*outgoing, *incoming))
        evidence_context = build_trade_evidence_context(data, all_assets)
        dossiers = []
        for partner, outgoing, incoming in partner_pools:
            proposals = generate_proposals(active_roster_id, partner.roster_id, outgoing, incoming)
            alternative_labels = tuple(asset.label for asset in sorted(incoming, key=lambda item: (-item.team_fit_value, item.label))[:3])
            dossiers.extend(evaluate_proposal(proposal, active, partner, alternative_labels, evidence_context) for proposal in proposals)
        return prioritize(tuple(dossiers), limit)


trade_intelligence = TradeIntelligence()

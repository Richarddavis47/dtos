"""Trade adapter for shared Front Office Intelligence partner profiles."""
from __future__ import annotations

from typing import Any

from src.core.decision_engine import TeamDecision
from src.core.front_office_intelligence import build_league_model
from src.core.front_office_intelligence import LeagueFrontOfficeModel
from src.core.trade_intelligence.models import PartnerReport


def evaluate_partners(
    data: dict[str, Any],
    active: TeamDecision,
    decisions: dict[int, TeamDecision],
    front_office_model: LeagueFrontOfficeModel | None = None,
) -> tuple[PartnerReport, ...]:
    model = front_office_model or build_league_model(data, decisions)
    reports = []
    for roster_id, decision in decisions.items():
        if roster_id == active.profile.roster_id:
            continue
        compatibility = model.compatibility(active.profile.roster_id, roster_id)
        office = model.reports[roster_id]
        complexity = "Low" if compatibility.score >= 75 else "Moderate" if compatibility.score >= 55 else "High"
        reports.append(PartnerReport(roster_id, decision.profile.team_name, decision.profile.owner_name, compatibility.score, compatibility.difficulty, complexity, compatibility.shared_interests, compatibility.bilateral_trades, compatibility.evidence, office.negotiation_style, compatibility.forecast.acceptance_probability, compatibility.forecast.expected_counter, compatibility.forecast.notes))
    return tuple(sorted(reports, key=lambda item: (-item.compatibility_score, item.team_name)))

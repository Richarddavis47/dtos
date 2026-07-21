"""Deterministic partner compatibility without invented manager tendencies."""
from __future__ import annotations

from typing import Any

from src.core.asset_intelligence import Evidence
from src.core.decision_engine import TeamDecision
from src.core.trade_intelligence.models import PartnerReport


def _trade_count(data: dict[str, Any], first: int, second: int) -> int:
    return sum(
        str(item.get("type") or "").lower() == "trade"
        and {first, second}.issubset({int(value) for value in item.get("roster_ids") or []})
        for item in data.get("transactions") or []
    )


def _needs(decision: TeamDecision) -> set[str]:
    return {position for position, evaluation in decision.position_evaluations.items() if evaluation.score < 55}


def _surpluses(decision: TeamDecision) -> set[str]:
    targets = {"QB": 2, "RB": 4, "WR": 5, "TE": 2}
    return {
        position for position, room in decision.profile.position_rooms.items()
        if room.total_players > targets[position]
    }


def evaluate_partners(
    data: dict[str, Any],
    active: TeamDecision,
    decisions: dict[int, TeamDecision],
) -> tuple[PartnerReport, ...]:
    active_needs = _needs(active)
    active_surplus = _surpluses(active)
    reports = []
    for roster_id, decision in decisions.items():
        if roster_id == active.profile.roster_id:
            continue
        partner_needs = _needs(decision)
        partner_surplus = _surpluses(decision)
        inbound_matches = active_needs & partner_surplus
        outbound_matches = partner_needs & active_surplus
        historical = _trade_count(data, active.profile.roster_id, roster_id)
        compatibility = min(100, 40 + len(inbound_matches) * 15 + len(outbound_matches) * 15 + min(historical, 3) * 5)
        complexity = "Low" if compatibility >= 75 else "Moderate" if compatibility >= 55 else "High"
        difficulty = "Favorable" if compatibility >= 75 else "Workable" if compatibility >= 55 else "Difficult"
        evidence = (
            Evidence("Active needs matched", ", ".join(sorted(inbound_matches)) or "None", len(inbound_matches) * 15, "Partner surplus is compared with the Active Front Office's Decision Engine needs.", "Decision Engine position evaluations"),
            Evidence("Partner needs matched", ", ".join(sorted(outbound_matches)) or "None", len(outbound_matches) * 15, "Active surplus is compared with the partner's Decision Engine needs.", "Decision Engine position evaluations"),
            Evidence("Previous bilateral trades", str(historical), min(historical, 3) * 5, "Cached completed trade history provides a small familiarity signal, not a behavior prediction.", "Sleeper cached transactions"),
        )
        reports.append(PartnerReport(roster_id, decision.profile.team_name, decision.profile.owner_name, compatibility, difficulty, complexity, tuple(sorted(inbound_matches | outbound_matches)), historical, evidence))
    return tuple(sorted(reports, key=lambda item: (-item.compatibility_score, item.team_name)))

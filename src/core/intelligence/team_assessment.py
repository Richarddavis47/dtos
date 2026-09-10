"""Generation-bound team assessment; valuation strength is not weekly points."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.team_intelligence.models import TeamIntelligenceCard
from src.core.intelligence.roster_evidence import RosterEvidence, build_roster_evidence


@dataclass(frozen=True)
class TeamAssessment:
    league_id: str
    roster_id: int
    generation: str
    projection_snapshot_id: str | None
    projection_as_of: str | None
    projection_week: int | None
    team: TeamIntelligenceCard
    projected_points: float | None
    weekly_floor: float | None
    weekly_ceiling: float | None
    starter_count: int
    projected_starter_count: int
    limitations: tuple[str, ...]
    roster_evidence: RosterEvidence | None = None

    @property
    def current_outlook(self) -> str:
        grade = self.team.current_contending
        if grade.score is None:
            return "Unavailable: complete optimal projected lineup evidence is required."
        return f"{grade.grade} ({grade.score}/100 league-relative): " + " ".join(grade.reasons)

    @property
    def future_outlook(self) -> str:
        grade = self.team.future_outlook
        if grade.score is None:
            return "Unavailable: a validated long-term team utility aggregate is not available; Market price and age are separate dimensions."
        return f"{grade.grade} ({grade.score}/100 league-relative): " + " ".join(grade.reasons)


def build_team_assessment(context: Any, team: TeamIntelligenceCard) -> TeamAssessment:
    if context.active_roster_id != team.roster_id:
        raise ValueError("Team assessment franchise mismatch")
    if team.league_id != context.league_id or team.generation != context.evidence_generation:
        raise ValueError("Team assessment league/generation mismatch")
    snapshot = context.projection_snapshot or {}
    roster_evidence = build_roster_evidence(context)
    if snapshot and str(snapshot.get("league_id") or "") != context.league_id:
        raise ValueError("Team assessment projection league mismatch")
    ids = tuple(dict.fromkeys(str(row.get("id") or row.get("player_id")) for row in context.roster.get("players") or () if row.get("roster_slot") == "Starter"))
    rows = snapshot.get("players") or {}
    week = snapshot.get("week")
    selected = [rows.get(key) or {} for key in ids]

    def total(field: str) -> float | None:
        # Partial evidence is not a complete lineup projection. Genuine zeros
        # remain zeros; absent and wrong-week evidence remain unavailable.
        values = [row.get(field) for row in selected if row.get("week") == week]
        if week is None or not ids or len(values) != len(ids) or any(value is None for value in values):
            return None
        return round(sum(float(value) for value in values), 2)

    covered = sum(week is not None and row.get("weekly_projected_points") is not None and row.get("week") == week for row in selected)
    floor, ceiling = total("weekly_floor"), total("weekly_ceiling")
    limitations = ["Lineup, Market, production and longevity are separate evidence dimensions; no overall dynasty grade is inferred from any one dimension."]
    if covered != len(ids) or not ids:
        limitations.append("Complete starter projection evidence is unavailable; no missing player is scored as zero.")
    if floor is None or ceiling is None:
        limitations.append("Canonical weekly uncertainty bounds are unavailable; no floor/ceiling is inferred from a strength index.")
    return TeamAssessment(
        context.league_id, team.roster_id, context.evidence_generation,
        snapshot.get("projection_snapshot_id"), snapshot.get("generated_at"), week,
        team, total("weekly_projected_points"), floor, ceiling, len(ids), covered,
        tuple(dict.fromkeys((*limitations, *roster_evidence.limitations))), roster_evidence,
    )

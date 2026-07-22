"""Application-facing Front Office Intelligence views."""
from __future__ import annotations

from typing import Any
from dataclasses import replace

from src.core.intelligence import intelligence_orchestrator


def build_front_office_center(data: dict[str, Any], roster_id: int | None = None) -> dict[str, Any]:
    teams = data.get("teams") or []
    if not teams:
        raise ValueError("No Front Office is available.")
    valid_ids = {int(team.get("roster_id") or 0) for team in teams}
    selected = roster_id if roster_id in valid_ids else min(valid_ids)
    intelligence = intelligence_orchestrator.analyze(data, selected)
    model = intelligence.front_office_model
    reports = {
        key: replace(report, competitive_window=intelligence.roster.team_intelligence[key].current_window.value)
        for key, report in model.reports.items()
    }
    return {
        "active": reports[selected],
        "reports": tuple(reports[key] for key in sorted(reports)),
        "compatibilities": tuple(model.compatibility(selected, key) for key in sorted(model.reports) if key != selected),
        "relationships": model.relationships,
        "unified_recommendation": intelligence.recommendation,
    }

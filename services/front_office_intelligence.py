"""Application-facing Front Office Intelligence views."""
from __future__ import annotations

from typing import Any

from config import LEAGUE_ID
from src.core.intelligence import intelligence_orchestrator
from src.core.historical_memory.read_model import historical_graph
from src.core.history_context import canonical_history_store
from services.fois import fois_service
from src.core.fois.models import FOIS_MODEL_VERSION


def build_front_office_center(data: dict[str, Any], roster_id: int | None = None) -> dict[str, Any]:
    teams = data.get("teams") or []
    if not teams:
        raise ValueError("No Front Office is available.")
    valid_ids = {int(team.get("roster_id") or 0) for team in teams}
    selected = roster_id if roster_id in valid_ids else min(valid_ids)
    intelligence = intelligence_orchestrator.analyze(data, selected)
    model = intelligence.front_office_model
    reports = model.reports
    league_id = str((data.get("league") or {}).get("league_id") or LEAGUE_ID)
    graph = historical_graph(canonical_history_store, league_id, data)
    histories = {str(selected): graph.franchise_history(str(selected))}
    selected_team = next((row for row in teams if int(row.get("roster_id") or 0) == selected), {})
    owner_id = selected_team.get("owner_id") or selected_team.get("user_id")
    gm_id = f"{league_id}:gm:{owner_id}" if owner_id is not None else None
    fois_score = (
        fois_service.repository.score_for_gm(league_id, gm_id, FOIS_MODEL_VERSION)
        if gm_id else None
    )
    return {
        "active": reports[selected],
        "reports": tuple(reports[key] for key in sorted(reports)),
        "compatibilities": tuple(model.compatibility(selected, key) for key in sorted(model.reports) if key != selected),
        "relationships": model.relationships,
        "unified_recommendation": intelligence.recommendation,
        "brain": intelligence.brain,
        "brain_recommendation": intelligence.brain_decision,
        "decision_confidence": intelligence.brain_decision.confidence,
        "historical_contract_version": histories[next(iter(histories))]["schema_version"] if histories else None,
        "franchise_histories": histories,
        "fois": ({
            "gm_id": fois_score.gm_id,
            "gm_name": fois_score.gm_name,
            "executive_score": fois_score.overall_score,
            "grade": fois_score.overall_letter_grade,
            "confidence": fois_score.confidence,
            "strongest_category": fois_score.strongest_category,
            "weakest_category": fois_score.weakest_category,
            "management_momentum": fois_score.management_momentum,
            "snapshot_id": fois_score.score_key,
            "model_version": fois_score.model_version,
        } if fois_score else {
            "evidence_state": "unavailable",
            "reason": "No persisted FOIS executive snapshot is available.",
        }),
    }

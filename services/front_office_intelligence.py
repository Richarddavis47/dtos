"""Application-facing Front Office Intelligence views."""
from __future__ import annotations

from typing import Any

from config import LEAGUE_ID
from src.core.intelligence import intelligence_orchestrator
from src.core.historical_memory import HistoricalAssetGraph, historical_store


def build_front_office_center(data: dict[str, Any], roster_id: int | None = None) -> dict[str, Any]:
    teams = data.get("teams") or []
    if not teams:
        raise ValueError("No Front Office is available.")
    valid_ids = {int(team.get("roster_id") or 0) for team in teams}
    selected = roster_id if roster_id in valid_ids else min(valid_ids)
    intelligence = intelligence_orchestrator.analyze(data, selected)
    model = intelligence.front_office_model
    reports = model.reports
    graph = HistoricalAssetGraph(historical_store, LEAGUE_ID, data)
    histories = {str(selected): graph.franchise_history(str(selected))}
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
    }

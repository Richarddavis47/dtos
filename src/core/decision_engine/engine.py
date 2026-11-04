"""High-level Decision Engine entry point."""
from __future__ import annotations

from typing import Any

from src.core.decision_engine.models.decision import DecisionContext, TeamDecision
from src.core.decision_engine.team.team_evaluator import evaluate_team


class DecisionEngine:
    """Stateless reusable facade for current and future DTOS consumers."""

    def evaluate_team(self, data: dict[str, Any], roster_id: int, context: DecisionContext) -> TeamDecision:
        return evaluate_team(data, roster_id, context)


decision_engine = DecisionEngine()

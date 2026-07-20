"""Draft-pick asset evaluation."""
from __future__ import annotations

from src.core.decision_engine.models.evaluation import EvaluationFactor
from src.core.decision_engine.models.team_profile import TeamProfile


def evaluate_pick_assets(profile: TeamProfile) -> tuple[float, tuple[EvaluationFactor, ...], tuple[str, ...]]:
    total_score = min(profile.draft_pick_count / 12, 1) * 60
    first_score = min(profile.first_round_pick_count / 3, 1) * 40
    return (
        total_score + first_score,
        (
            EvaluationFactor(
                "Future pick inventory",
                f"{profile.draft_pick_count} picks",
                total_score,
                "Total inventory is measured against a three-year, four-round foundation benchmark.",
                "Sleeper future-pick ledger",
            ),
            EvaluationFactor(
                "First-round inventory",
                f"{profile.first_round_pick_count} first-round picks",
                first_score,
                "First-round picks receive additional weight as flexible future assets.",
                "Sleeper future-pick ledger",
            ),
        ),
        ("Pick quality within a round and projected draft position are not yet modeled.",),
    )

"""Player-asset signals available before the full Player Intelligence engine."""
from __future__ import annotations

from src.core.decision_engine.models.evaluation import EvaluationFactor
from src.core.decision_engine.models.team_profile import TeamProfile


def evaluate_player_assets(profile: TeamProfile) -> tuple[float, tuple[EvaluationFactor, ...], tuple[str, ...]]:
    """Evaluate only observable age distribution; market value remains a future input."""
    if not profile.known_ages:
        return (
            50.0,
            (
                EvaluationFactor(
                    "Age availability",
                    "No known ages",
                    50.0,
                    "A neutral placeholder is used because objective age data is unavailable.",
                    "Sleeper player records",
                ),
            ),
            ("Player market value and rookie-pipeline data are not available.",),
        )
    young_share = profile.young_player_count / len(profile.known_ages)
    veteran_share = profile.veteran_player_count / len(profile.known_ages)
    score = 50 + young_share * 50 - veteran_share * 25
    return (
        score,
        (
            EvaluationFactor(
                "Young core",
                f"{profile.young_player_count} of {len(profile.known_ages)} known ages are 24 or younger",
                young_share * 50,
                "A larger young-player share improves future flexibility.",
                "Sleeper roster and player ages",
            ),
            EvaluationFactor(
                "Veteran concentration",
                f"{profile.veteran_player_count} of {len(profile.known_ages)} known ages are 28 or older",
                -(veteran_share * 25),
                "Veteran concentration reduces the age-based future signal without judging player quality.",
                "Sleeper roster and player ages",
            ),
        ),
        ("Dynasty market value, rookie pipeline quality, and player trajectories are future inputs.",),
    )

"""Versioned FOIS scoring configuration and validation."""
from __future__ import annotations

from dataclasses import replace

from src.core.fois.models import FOIS_MODEL_VERSION, FrontOfficeScoringConfiguration

DEFAULT_GRADE_THRESHOLDS = (
    (97, "A+"), (93, "A"), (90, "A-"), (87, "B+"), (83, "B"),
    (80, "B-"), (77, "C+"), (73, "C"), (70, "C-"), (67, "D+"),
    (63, "D"), (60, "D-"), (0, "F"),
)

DEFAULT_FOIS_CONFIGURATION = FrontOfficeScoringConfiguration(
    model_version=FOIS_MODEL_VERSION,
    category_weights={
        "results": 35.0,
        "trading_asset_management": 25.0,
        "roster_construction": 20.0,
        "drafting_talent_evaluation": 20.0,
    },
    metric_definitions={},
    normalization_rules={"default": "league_relative_percentile"},
    minimum_sample_sizes={"results": 3, "trades": 3, "drafts": 2},
    confidence_rules={"season_target": 10.0, "minimum": 20.0},
    historical_weighting={
        "full_history": 1.0,
        "trailing_five": 1.0,
        "trailing_three": 1.0,
        "current_cycle": 1.0,
    },
    championship_probability_ceiling=50.0,
    rebuild_duration_thresholds=(2, 3),
    grade_thresholds=DEFAULT_GRADE_THRESHOLDS,
    feature_flags={"advanced_trade_outcomes": True, "draft_slot_model": True},
    created_at="2026-08-09T00:00:00+00:00",
    active=True,
)


def validate_configuration(
    configuration: FrontOfficeScoringConfiguration,
) -> FrontOfficeScoringConfiguration:
    if not configuration.model_version:
        raise ValueError("FOIS model_version is required.")
    if not configuration.category_weights:
        raise ValueError("FOIS requires category weights.")
    if any(weight < 0 for weight in configuration.category_weights.values()):
        raise ValueError("FOIS category weights cannot be negative.")
    if abs(sum(configuration.category_weights.values()) - 100.0) > .001:
        raise ValueError("FOIS category weights must total 100%.")
    if not 0 < configuration.championship_probability_ceiling <= 100:
        raise ValueError("Championship probability ceiling must be within 0-100.")
    if tuple(sorted(configuration.grade_thresholds, reverse=True)) != configuration.grade_thresholds:
        raise ValueError("Grade thresholds must be ordered from highest to lowest.")
    return configuration


def with_metric_definitions(
    configuration: FrontOfficeScoringConfiguration,
    definitions: dict[str, tuple[str, ...]],
) -> FrontOfficeScoringConfiguration:
    return validate_configuration(replace(configuration, metric_definitions=definitions))

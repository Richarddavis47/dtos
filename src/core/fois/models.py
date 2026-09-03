"""Versioned, presentation-neutral FOIS data contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

FOIS_MODEL_VERSION = "5.0"
FOIS_CATEGORY_DEFINITION_VERSION = "5.0"
FOIS_METRIC_DEFINITION_VERSION = "5.0"
FOIS_CONFIGURATION_VERSION = "5.0"
FOIS_EVIDENCE_VERSION = "2.0"
FOIS_CONFIDENCE_VERSION = "1.0"


class EvaluationKind(str, Enum):
    CURRENT_CANONICAL = "current_canonical"
    HISTORICAL_SNAPSHOT = "historical_snapshot"
    HISTORICAL_TENURE = "historical_tenure"
    DUPLICATE_DERIVATION = "duplicate_derivation"
    INCOMPLETE_OBSOLETE_DERIVATION = "incomplete_obsolete_derivation"


class MetricStatus(str, Enum):
    ACTIVE = "active"
    PROVISIONAL = "provisional"
    INSUFFICIENT_DATA = "insufficient_data"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class Directionality(str, Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    TARGET_RANGE = "target_range"
    CONTEXTUAL = "contextual"


@dataclass(frozen=True)
class FrontOfficeEvidence:
    evidence_type: str
    source_system: str
    source_identifier: str
    description: str
    observed_value: Any
    observed_at: str
    season: int | None = None
    week: int | None = None
    transaction_id: str | None = None
    matchup_id: str | None = None
    draft_id: str | None = None
    player_id: str | None = None


@dataclass(frozen=True)
class FrontOfficeMetricScore:
    metric_key: str
    metric_name: str
    description: str
    raw_value: float | int | None
    normalized_score: float | None
    metric_weight: float
    weighted_contribution: float | None
    directionality: Directionality
    sample_size: int
    confidence: float
    completeness: float
    explanation: str
    evidence_references: tuple[str, ...]
    warnings: tuple[str, ...]
    status: MetricStatus
    metric_definition_version: str = FOIS_METRIC_DEFINITION_VERSION


@dataclass(frozen=True)
class FrontOfficeCategoryScore:
    category_key: str
    category_name: str
    raw_score: float | None
    normalized_score: float | None
    weight: float
    weighted_contribution: float | None
    letter_grade: str | None
    metric_scores: tuple[FrontOfficeMetricScore, ...]
    explanation: str
    confidence: float
    completeness: float
    evidence_references: tuple[str, ...]
    warnings: tuple[str, ...]
    strengths: tuple[str, ...] = ()
    weaknesses: tuple[str, ...] = ()
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class FrontOfficeIntelligenceScore:
    application_version: str
    league_id: str
    franchise_id: str
    owner_id: str | None
    evaluation_start_season: int
    evaluation_end_season: int
    seasons_evaluated: int
    overall_score: float | None
    overall_letter_grade: str | None
    category_scores: tuple[FrontOfficeCategoryScore, ...]
    strongest_category: str | None
    weakest_category: str | None
    executive_summary: str
    confidence: float
    completeness: float
    model_version: str
    generated_at: str
    evidence_references: tuple[str, ...]
    warnings: tuple[str, ...]
    provisional: bool
    score_key: str
    gm_id: str | None = None
    gm_name: str | None = None
    tenure_id: str | None = None
    tenure_started_at: str | None = None
    evidence_state: str = "provisional"
    brain_snapshot_id: str | None = None
    brain_version: str | None = None
    category_definition_version: str = FOIS_CATEGORY_DEFINITION_VERSION
    configuration_version: str = FOIS_CONFIGURATION_VERSION
    evidence_version: str = FOIS_EVIDENCE_VERSION
    current_team_score: float | None = None
    management_momentum: str = "Unavailable"
    strengths: tuple[str, ...] = ()
    weaknesses: tuple[str, ...] = ()
    franchise_name: str | None = None
    evaluation_kind: str = EvaluationKind.CURRENT_CANONICAL.value
    supported_weight: float = 0.0
    confidence_model_version: str = FOIS_CONFIDENCE_VERSION
    tendencies: tuple[str, ...] = ()
    unavailable_tendencies: tuple[str, ...] = ()
    trade_partner_count: int = 0
    front_office_evidence: dict[str, Any] | None = None


@dataclass(frozen=True)
class GMTenure:
    tenure_id: str
    league_id: str
    franchise_id: str
    gm_id: str
    gm_name: str
    started_at: str
    ended_at: str | None = None
    active: bool = True


@dataclass(frozen=True)
class TakeoverSnapshot:
    takeover_id: str
    tenure_id: str
    captured_at: str
    brain_snapshot_id: str | None
    competitive_window: str | None
    roster_asset_ids: tuple[str, ...]
    draft_pick_ids: tuple[str, ...]
    inherited_obligations: tuple[str, ...]
    context: dict[str, Any]


@dataclass(frozen=True)
class DecisionAssessment:
    decision_id: str
    decision_type: str
    process_score: float | None
    outcome_score: float | None
    context_score: float | None
    recovery_score: float | None
    overall_score: float | None
    impact_weight: float
    evidence_references: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class ExecutiveProfile:
    score: FrontOfficeIntelligenceScore
    tenure: GMTenure
    takeover: TakeoverSnapshot | None
    current_team_score: float | None
    category_ranks: dict[str, int | None]
    management_style: dict[str, str]
    resume: dict[str, Any]
    decision_assessments: tuple[DecisionAssessment, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class FrontOfficeScoringConfiguration:
    model_version: str
    category_weights: dict[str, float]
    metric_definitions: dict[str, tuple[str, ...]]
    normalization_rules: dict[str, str]
    minimum_sample_sizes: dict[str, int]
    confidence_rules: dict[str, float]
    historical_weighting: dict[str, float]
    championship_probability_ceiling: float
    rebuild_duration_thresholds: tuple[int, int]
    grade_thresholds: tuple[tuple[float, str], ...]
    feature_flags: dict[str, bool]
    created_at: str
    active: bool
    renormalize_available_categories: bool = True


@dataclass(frozen=True)
class CrossCategoryTrait:
    key: str
    name: str
    contributing_metrics: tuple[str, ...]
    score: float | None
    explanation: str
    evidence_references: tuple[str, ...]
    status: MetricStatus


@dataclass(frozen=True)
class SeasonTimeline:
    season: int
    state: str
    wins: int | None
    losses: int | None
    finish: int | None
    league_size: int | None
    playoff: bool
    final_four: bool
    championship_game: bool
    championship: bool
    explanation: str
    confidence: float


@dataclass(frozen=True)
class CompetitiveCycle:
    cycle_id: str
    cycle_type: str
    start_season: int
    end_season: int
    duration: int
    peak_finish: int | None
    peak_years: tuple[int, ...]
    championships: int
    playoff_appearances: int
    rebuild_length: int
    reload_time: int | None
    explanation: str


@dataclass(frozen=True)
class HistoricalWindow:
    key: str
    start_season: int
    end_season: int
    seasons: tuple[int, ...]
    sufficient: bool
    confidence: float


@dataclass(frozen=True)
class ResultsAnalysis:
    timeline: tuple[SeasonTimeline, ...]
    competitive_cycles: tuple[CompetitiveCycle, ...]
    historical_windows: tuple[HistoricalWindow, ...]
    rebuild_summary: dict[str, float | int | None]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    explanation: str

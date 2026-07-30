"""Deterministic FOIS normalization, grading, and weighted aggregation."""
from __future__ import annotations

from statistics import mean

from src.core.fois.models import (
    FrontOfficeCategoryScore,
    FrontOfficeMetricScore,
    FrontOfficeScoringConfiguration,
    MetricStatus,
)


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def letter_grade(
    score: float | None,
    configuration: FrontOfficeScoringConfiguration,
) -> str | None:
    if score is None:
        return None
    for threshold, grade in configuration.grade_thresholds:
        if score >= threshold:
            return grade
    return "F"


def aggregate_metrics(
    category_key: str,
    category_name: str,
    category_weight: float,
    metrics: tuple[FrontOfficeMetricScore, ...],
    configuration: FrontOfficeScoringConfiguration,
) -> FrontOfficeCategoryScore:
    included = tuple(
        metric for metric in metrics
        if metric.status in {MetricStatus.ACTIVE, MetricStatus.PROVISIONAL}
        and metric.normalized_score is not None
    )
    if not included:
        return FrontOfficeCategoryScore(
            category_key, category_name, None, None, category_weight, None, None,
            metrics, "No supported metric has sufficient evidence for this category.",
            0.0, 0.0, (), ("Missing data is excluded rather than scored as zero.",),
        )
    total_metric_weight = sum(metric.metric_weight for metric in included)
    normalized = sum(
        metric.normalized_score * metric.metric_weight for metric in included
    ) / total_metric_weight
    evidence = tuple(dict.fromkeys(
        reference for metric in included for reference in metric.evidence_references
    ))
    warnings = tuple(dict.fromkeys(
        warning for metric in metrics for warning in metric.warnings
    ))
    return FrontOfficeCategoryScore(
        category_key,
        category_name,
        round(mean(metric.raw_value for metric in included if metric.raw_value is not None), 2),
        round(normalized, 2),
        category_weight,
        round(normalized * category_weight / 100, 2),
        letter_grade(normalized, configuration),
        metrics,
        f"{len(included)} of {len(metrics)} registered metrics currently contribute; unavailable metrics do not become zero.",
        round(mean(metric.confidence for metric in included), 2),
        round(sum(metric.completeness for metric in included) / len(metrics), 2),
        evidence,
        warnings,
    )


def aggregate_categories(
    categories: tuple[FrontOfficeCategoryScore, ...],
    configuration: FrontOfficeScoringConfiguration,
) -> float | None:
    included = tuple(
        category for category in categories if category.normalized_score is not None
    )
    if not included:
        return None
    active_weight = sum(category.weight for category in included)
    if active_weight < 100 and not configuration.renormalize_available_categories:
        return None
    return round(
        sum(category.normalized_score * category.weight for category in included)
        / active_weight,
        2,
    )

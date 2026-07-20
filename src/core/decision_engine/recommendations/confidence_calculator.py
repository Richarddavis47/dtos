"""Consistent recommendation-confidence calculation."""
from __future__ import annotations

from statistics import mean

from src.core.decision_engine.models.evaluation import Evaluation
from src.core.decision_engine.models.recommendation import ConfidenceScore


def calculate_confidence(*evaluations: Evaluation, adjustment: int = 0) -> ConfidenceScore:
    if not evaluations:
        return ConfidenceScore(0)
    base = mean(evaluation.confidence for evaluation in evaluations)
    limitation_penalty = min(15, sum(len(evaluation.limitations) for evaluation in evaluations) * 2)
    return ConfidenceScore(round(base - limitation_penalty + adjustment))

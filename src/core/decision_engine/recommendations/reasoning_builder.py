"""Reusable human-readable reasoning construction."""
from __future__ import annotations

from src.core.decision_engine.models.evaluation import Evaluation


def supporting_metrics(*evaluations: Evaluation, limit: int = 6) -> tuple[str, ...]:
    metrics = []
    for evaluation in evaluations:
        metrics.append(f"{evaluation.horizon.value}: {evaluation.score}/100 ({evaluation.grade})")
        metrics.extend(f"{factor.name}: {factor.value}" for factor in evaluation.factors[:2])
    return tuple(metrics[:limit])


def build_reasoning(subject: str, *evaluations: Evaluation) -> str:
    horizons = ", ".join(f"{evaluation.horizon.value} {evaluation.score}/100" for evaluation in evaluations)
    limitations = tuple(dict.fromkeys(item for evaluation in evaluations for item in evaluation.limitations))
    disclosure = f" Known limits: {' '.join(limitations[:2])}" if limitations else ""
    return f"{subject} is based on {horizons}.{disclosure} DTOS advises; the GM makes the final decision."

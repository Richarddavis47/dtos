"""Shared deterministic scoring helpers."""
from __future__ import annotations


def clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def grade(score: float) -> str:
    value = clamp(score)
    if value >= 90:
        return "A"
    if value >= 80:
        return "B"
    if value >= 70:
        return "C"
    if value >= 60:
        return "D"
    return "F"


def relative_score(value: float, population: tuple[float, ...]) -> float:
    """Return a stable 0-100 percentile-like score, neutral when data is flat."""
    if not population or max(population) == min(population):
        return 50.0
    below = sum(item < value for item in population)
    equal = sum(item == value for item in population)
    return ((below + equal * 0.5) / len(population)) * 100

"""Traceable evidence primitives."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    factor: str
    observed_value: str
    impact: float
    explanation: str
    source: str
    available: bool = True

"""Canonical competitive-window contract and deterministic classifier."""
from src.core.competitive_window.engine import build_competitive_window
from src.core.competitive_window.models import (
    COMPETITIVE_WINDOW_CONTRACT_VERSION,
    CompetitiveWindowClassification,
    CompetitiveWindowContract,
)

__all__ = [
    "COMPETITIVE_WINDOW_CONTRACT_VERSION",
    "CompetitiveWindowClassification",
    "CompetitiveWindowContract",
    "build_competitive_window",
]

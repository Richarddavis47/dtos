"""Canonical normalized models accepted by the DTOS Data Platform."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedPlayer:
    dtos_id: str
    name: str
    position: str
    nfl_team: str
    age: float | None
    experience: int | None
    status: str
    provider_ids: dict[str, str]
    aliases: tuple[str, ...]
    metadata: dict[str, str]


@dataclass(frozen=True)
class NormalizedValue:
    dtos_id: str
    provider: str
    value: float | None
    rank: int | None
    position_rank: int | None
    tier: str | None
    adp: float | None
    timestamp: str
    confidence: int
    source_field: str
    warnings: tuple[str, ...]

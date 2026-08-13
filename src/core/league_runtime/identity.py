"""Deterministic league and scoring identities used by process-wide caches."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    return value


def scoring_profile_id(
    scoring_settings: Mapping[str, Any] | None,
    *,
    roster_positions: list[str] | tuple[str, ...] = (),
) -> str:
    """Return a stable identity for settings that affect fantasy scoring."""
    payload = {
        "roster_positions": list(roster_positions),
        "scoring_settings": _canonical(scoring_settings or {}),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"scoring-v1:{sha256(encoded.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True, slots=True)
class StructuredCacheKey:
    """Collision-safe cache identity for shared multi-league services."""

    league_id: str
    season: int
    subsystem: str
    model_version: str
    source_generation: str
    week: int | None = None
    scoring_profile: str | None = None

    def __post_init__(self) -> None:
        required = {
            "league_id": self.league_id,
            "subsystem": self.subsystem,
            "model_version": self.model_version,
            "source_generation": self.source_generation,
        }
        for name, value in required.items():
            if not str(value).strip():
                raise ValueError(f"{name} is required for a structured cache key.")
        if self.season < 2000:
            raise ValueError("season must identify a supported fantasy season.")
        if self.week is not None and self.week < 0:
            raise ValueError("week cannot be negative.")

    @property
    def namespace(self) -> str:
        return f"league:{self.league_id}:{self.subsystem}"

    def public(self) -> dict[str, Any]:
        return {
            "league_id": self.league_id,
            "season": self.season,
            "week": self.week,
            "subsystem": self.subsystem,
            "model_version": self.model_version,
            "source_generation": self.source_generation,
            "scoring_profile_id": self.scoring_profile,
        }

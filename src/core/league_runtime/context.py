"""Canonical league-scoped consumer context.

This module is the only adapter between a hydrated ``LeagueRuntime`` and
league-dependent DTOS product consumers.  It deliberately retains shared NFL
identity data by reference while keeping every mutable/derived consumer scoped
to one Sleeper league.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.core.asset_market import AssetMarketCache
from src.core.brain import BrainService
from src.core.projection_intelligence.service import ProjectionService

if TYPE_CHECKING:
    from src.core.history_context.store import CanonicalHistoryStore

from .manager import LeagueRuntime


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def source_generations(data: dict[str, Any], scoring_profile: str) -> dict[str, str]:
    """Return bounded semantic generations for league-consumer compatibility."""
    league = data.get("league") or {}
    return {
        "sleeper_canonical": _digest({
            "league": league,
            "season": data.get("season"),
            "week": data.get("week"),
        }),
        "settings_scoring": scoring_profile,
        "rosters": _digest(data.get("teams") or ()),
        "matchups": _digest(data.get("matchups") or {}),
        "picks": _digest(data.get("pick_ledger") or data.get("traded_picks") or ()),
        "transactions": _digest(data.get("transactions") or ()),
        "projections": _digest(data.get("projection_intelligence") or {}),
    }


@dataclass(slots=True)
class CanonicalLeagueContext:
    """Presentation-ready, league-scoped canonical product dependencies."""

    runtime: LeagueRuntime
    historical_store: "CanonicalHistoryStore"
    projection: ProjectionService
    brain: BrainService
    market: AssetMarketCache
    fois_state: str = "pending"
    history_state: str = "available"

    @property
    def league_id(self) -> str:
        return self.runtime.league_id

    @property
    def data(self) -> dict[str, Any]:
        return self.runtime.state.get("data") or {}

    @property
    def state(self) -> dict[str, Any]:
        return self.runtime.state

    def refresh_generations(self) -> dict[str, str]:
        generations = source_generations(
            self.data, str(self.runtime.scoring_profile or "scoring:pending"),
        )
        brain_health = self.brain.health()
        generations["brain"] = str(
            brain_health.get("semantic_digest") or "brain:pending"
        )
        snapshot = self.projection.snapshot() or {}
        generations["projections"] = str(
            snapshot.get("projection_snapshot_id") or generations["projections"]
        )
        self.runtime.source_generations = generations
        return generations

    def close(self) -> None:
        """Drop secondary operational references after background tasks finish."""
        if self.runtime.owns_state:
            self.historical_store.release_current(self.league_id, self.data)

    def health(self) -> dict[str, Any]:
        projection = self.projection.health()
        market = self.market.health()
        return {
            "league_id": self.league_id,
            "status": "ready" if self.data else "runtime_warming",
            "runtime_state": self.runtime.status.value,
            "canonical_context_state": "ready" if self.data else "warming",
            "projection_state": projection.get("status", "pending"),
            "brain_state": self.brain.health().get("status", "pending"),
            "market_state": market.get("status", "warming"),
            "fois_state": self.fois_state,
            "history_state": self.history_state,
            "scoring_profile_id": self.runtime.scoring_profile,
            "source_generations": dict(self.runtime.source_generations),
        }

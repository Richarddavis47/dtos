"""Registry-based projection and production providers with explicit fallback states."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.core.player_value_projection.models import DataStatus, ProductionContext, Projection
from src.core.projection_intelligence import projection_service


class WeeklyProjectionProvider(ABC):
    name = "weekly_projection"
    version = "1"

    @abstractmethod
    def project(self, player: dict[str, Any], redraft_score: int, scoring: dict[str, Any], week: int | None) -> Projection:
        raise NotImplementedError


class ProductionProvider(ABC):
    name = "production"
    version = "1"

    @abstractmethod
    def production(self, player: dict[str, Any]) -> ProductionContext:
        raise NotImplementedError


def scoring_multiplier(position: str, scoring: dict[str, Any]) -> float:
    reception = float(scoring.get("rec") or 0)
    te_bonus = float(scoring.get("bonus_rec_te") or scoring.get("rec_te") or 0) if position == "TE" else 0
    pass_td = float(scoring.get("pass_td") or 4)
    turnover = abs(float(scoring.get("pass_int") or -1))
    if position == "QB":
        return max(.75, min(1.35, 1 + (pass_td - 4) * .055 - (turnover - 1) * .025))
    return max(.75, min(1.35, 1 + (reception - .5) * .12 + te_bonus * .08))


class SleeperCanonicalProjectionProvider(WeeklyProjectionProvider):
    """Consume the active league's cached canonical Sleeper projection."""

    name = "sleeper_canonical_weekly"
    version = "1"

    def project(self, player: dict[str, Any], redraft_score: int, scoring: dict[str, Any], week: int | None) -> Projection:
        player_id = str(player.get("id") or player.get("player_id") or "")
        try:
            from src.platform.league_context import current_league_context
            context = current_league_context()
        except (ImportError, RuntimeError):
            context = None
        service = context.projection if context is not None else projection_service
        canonical = service.player(player_id)
        return self.from_canonical(canonical, week)

    def from_canonical(self, canonical: dict[str, Any] | None, week: int | None) -> Projection:
        """Convert a pinned published row without another service read."""
        if week is not None and canonical is not None and canonical.get("week") == week:
            status = DataStatus.UNAVAILABLE if canonical.get("weekly_projected_points") is None else DataStatus.CACHED
            return Projection(
                canonical.get("weekly_projected_points"), canonical.get("weekly_floor"),
                canonical.get("weekly_median"), canonical.get("weekly_ceiling"),
                int(canonical.get("projection_confidence") or 0), 0.0, 0.0,
                0.0, "Sleeper canonical weekly projection" if status is DataStatus.CACHED else "Unavailable", None,
                "Sleeper", status, canonical.get("generated_at"),
                week, tuple(canonical.get("limitations") or ()),
                canonical.get("projection_snapshot_id"), canonical.get("rest_of_season_points"),
                canonical.get("rest_of_season_games"), canonical.get("season_projected_points"),
                canonical.get("projection_agreement"), str(canonical.get("source_freshness") or "unavailable").lower(),
            )
        return Projection(
            None, None, None, None, 0, 0.0, 0.0, 0.0,
            "Sleeper projection unavailable", None, "Sleeper", DataStatus.UNAVAILABLE,
            None, week, ("Sleeper projection evidence is unavailable; DTOS does not fabricate a positional fallback.",),
        )


# Compatibility import name for extensions; the implementation is no longer an
# internal forecast and remains canonical Sleeper-only.
InternalProjectionProvider = SleeperCanonicalProjectionProvider


class CachedProductionProvider(ProductionProvider):
    name = "sleeper_explicit_actuals_only"
    version = "2"

    def production(self, player: dict[str, Any]) -> ProductionContext:
        # Unscoped extension fields have no league/week/source identity. Even
        # a plausible number cannot be relabeled as an authoritative result.
        return ProductionContext((), None, None, "Unavailable", "Sleeper league matchup results",
            DataStatus.UNAVAILABLE, None,
            ("League-scoped prepared Sleeper actual results are required; unscoped cached statistics are not a fallback.",))


class PlayerDataRegistry:
    def __init__(self) -> None:
        self._projection: WeeklyProjectionProvider = SleeperCanonicalProjectionProvider()
        self._production: ProductionProvider = CachedProductionProvider()

    def projection(self) -> WeeklyProjectionProvider:
        return self._projection

    def production(self) -> ProductionProvider:
        return self._production

    def register_projection(self, provider: WeeklyProjectionProvider) -> None:
        self._projection = provider

    def register_production(self, provider: ProductionProvider) -> None:
        self._production = provider

    def health(self) -> dict[str, dict[str, str]]:
        return {"projection": {"provider": self._projection.name, "version": self._projection.version}, "production": {"provider": self._production.name, "version": self._production.version}}


player_data_registry = PlayerDataRegistry()

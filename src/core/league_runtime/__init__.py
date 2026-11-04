"""League-scoped runtime management and cache identity contracts."""

from .manager import (
    LeagueRuntime,
    LeagueRuntimeError,
    LeagueRuntimeDeferred,
    LeagueRuntimeManager,
    LeagueRuntimeNotFound,
    RuntimeState,
)
from .context import CanonicalLeagueContext, source_generations
from .identity import StructuredCacheKey, scoring_profile_id

__all__ = [
    "LeagueRuntime",
    "LeagueRuntimeError",
    "LeagueRuntimeDeferred",
    "LeagueRuntimeManager",
    "CanonicalLeagueContext",
    "LeagueRuntimeNotFound",
    "RuntimeState",
    "StructuredCacheKey",
    "scoring_profile_id",
    "source_generations",
]

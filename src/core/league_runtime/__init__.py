"""League-scoped runtime management and cache identity contracts."""

from .manager import (
    LeagueRuntime,
    LeagueRuntimeError,
    LeagueRuntimeManager,
    LeagueRuntimeNotFound,
    RuntimeState,
)
from .identity import StructuredCacheKey, scoring_profile_id

__all__ = [
    "LeagueRuntime",
    "LeagueRuntimeError",
    "LeagueRuntimeManager",
    "LeagueRuntimeNotFound",
    "RuntimeState",
    "StructuredCacheKey",
    "scoring_profile_id",
]

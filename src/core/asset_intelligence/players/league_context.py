"""League-specific player value signals."""
from __future__ import annotations

from src.core.asset_intelligence.models import AssetContext, Evidence, PlayerProfile


def league_adjustment(profile: PlayerProfile, context: AssetContext) -> tuple[int, Evidence]:
    positions = tuple(str(item).upper() for item in context.league_settings.get("roster_positions") or ())
    superflex = "SUPER_FLEX" in positions or "SF" in positions
    if profile.position == "QB" and superflex:
        return 8, Evidence("Superflex format", "Superflex enabled", 8, "A published +8 QB adjustment reflects additional lineup demand.", "Sleeper roster settings")
    if positions:
        return 0, Evidence("League lineup format", ", ".join(positions), 0, "No v1 format adjustment applies to this position.", "Sleeper roster settings")
    return 0, Evidence("League lineup format", "Unavailable", 0, "League format cannot contribute, so no adjustment is made.", "Not available", False)

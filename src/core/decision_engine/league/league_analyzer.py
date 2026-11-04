"""League-context assembly for all Decision Engine consumers."""
from __future__ import annotations

from typing import Any

from src.core.decision_engine.assets.market_context import build_market_context
from src.core.decision_engine.league.trend_detector import detect_trends


def analyze_league(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "settings": data.get("league_settings") or {},
        "market": build_market_context(data),
        "trends": detect_trends(data),
        "team_count": len(data.get("teams") or []),
    }

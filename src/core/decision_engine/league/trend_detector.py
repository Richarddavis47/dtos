"""Historical trend-detection extension point."""
from __future__ import annotations

from typing import Any


def detect_trends(_: dict[str, Any]) -> dict[str, str]:
    return {
        "team_trend": "Unavailable without historical team snapshots",
        "market_trend": "Unavailable without historical valuation snapshots",
    }

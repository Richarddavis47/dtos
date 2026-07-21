"""Application-facing Front Office Intelligence views."""
from __future__ import annotations

from typing import Any

from src.core.front_office_intelligence import front_office_intelligence


def build_front_office_center(data: dict[str, Any], roster_id: int | None = None) -> dict[str, Any]:
    model = front_office_intelligence.league(data)
    if not model.reports:
        raise ValueError("No Front Office is available.")
    selected = roster_id if roster_id in model.reports else sorted(model.reports)[0]
    return {
        "active": model.reports[selected],
        "reports": tuple(model.reports[key] for key in sorted(model.reports)),
        "compatibilities": tuple(model.compatibility(selected, key) for key in sorted(model.reports) if key != selected),
        "relationships": model.relationships,
    }

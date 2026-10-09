"""Admission of complete, comparable decision-time Market evidence."""
from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Iterable


def comparison_reason(assets: Iterable[object], *, boundary: str | None = None) -> str | None:
    rows = tuple(assets)
    if not rows:
        return "historical_market_package_empty"
    identities = set()
    for row in rows:
        value = getattr(row, "market_value", None)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value) or value < 0:
            return "historical_market_package_incomplete"
        identity = tuple(getattr(row, name, None) for name in (
            "market_provider", "market_context_id", "market_normalization_version", "market_value_concept",
            "market_comparison_identity",
        ))
        if not all(identity) or any(not isinstance(value, str) or not value.strip() or value.casefold() in {"unknown", "unavailable"} for value in identity[:4]):
            return "historical_market_comparison_identity_unavailable"
        if identity[3] != "canonical_market":
            return "historical_market_value_concept_not_market"
        identities.add(identity)
        try:
            observed = datetime.fromisoformat(str(row.market_observed_at).replace("Z", "+00:00"))
            decision = datetime.fromisoformat(boundary.replace("Z", "+00:00")) if boundary else None
            if observed.tzinfo is None or (decision and (decision.tzinfo is None or observed > decision)):
                return "historical_market_quote_not_decision_eligible"
        except (ValueError, TypeError, AttributeError):
            return "historical_market_observation_time_unavailable"
    if len(identities) != 1:
        return "historical_market_source_context_normalization_or_concept_incompatible"
    return None


def value_ratio(received: float, sent: float) -> float:
    """Complete supported zero is valid; unavailable values never reach here."""
    return received / sent if sent else 1.0 if not received else float("inf")


def retained_comparison_identity(semantics: dict | None, providers: Iterable[str]) -> tuple[str, ...] | None:
    """Preserve units/format, without mistaking exact asset identity for units.

    The canonical producer records pick year/range and player identity concepts
    in its format key. Those describe which asset was quoted, not another price
    scale. Only that known producer contract admits this projection.
    """
    import json
    from src.core.market_trends.compatibility import comparison_identity
    from src.core.valuation.consensus import MARKET_SELECTION_VERSION
    from src.core.valuation.observation_identity import OBSERVATION_IDENTITY_VERSION

    identity = comparison_identity({"comparison_semantics": semantics, "providers": tuple(providers)})
    if not identity:
        return None
    if identity[3] != MARKET_SELECTION_VERSION + ":" + OBSERVATION_IDENTITY_VERSION:
        return identity
    try:
        formats = json.loads(identity[2])
        if not isinstance(formats, list) or not formats:
            return None
        keys = ("provider", "format", "details", "source_scale", "normalization")
        if any(not isinstance(row, dict) or not all(row.get(key) for key in ("provider", "format", "normalization")) for row in formats):
            return None
        projected = json.dumps([{key: row.get(key) for key in keys} for row in formats],
            sort_keys=True, separators=(",", ":"))
    except (ValueError, TypeError):
        return None
    return (*identity[:2], projected, *identity[3:])

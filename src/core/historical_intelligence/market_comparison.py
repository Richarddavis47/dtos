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


def observation_clocks(observation, boundary: str | None = None):
    """Read provider clocks, never certify an event attachment as quote time.

    A provider's observation clock is its publication/knowledge boundary unless
    it explicitly supplies a separate knowledge clock. Application retrieval is
    not a substitute. Legacy outer dates remain stored unchanged.
    """
    from src.core.history_context.timestamps import canonical_utc_timestamp
    boundary = canonical_utc_timestamp(boundary) if boundary else None
    rows = tuple(getattr(observation, "provider_evidence", ()))
    if not rows:
        return None
    quotes, known = [], []
    for row in rows:
        quote = canonical_utc_timestamp(row.observed_at)
        metadata = row.metadata or {}
        knowledge = canonical_utc_timestamp(metadata.get('source_knowledge_at') or metadata.get('known_at') or row.observed_at)
        if not quote or not knowledge or not row.source_identity:
            return None
        if boundary and (quote > boundary or knowledge > boundary):
            return None
        quotes.append(quote)
        known.append(knowledge)
    return {'quote_observed_at': max(quotes), 'oldest_quote_at': min(quotes),
            'source_knowledge_at': max(known), 'retained_attachment_at':
            getattr(observation, 'retained_attachment_at', None) or observation.observed_at}

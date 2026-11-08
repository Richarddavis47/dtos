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
            reasons = tuple(reason for reason in getattr(row, 'market_reason_codes', ())
                            if reason != 'historical_market_older_than_seven_days')
            if reasons and reasons[0] != 'historical_market_unavailable':
                return reasons[0]
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
    from src.core.intelligence_memory.timestamps import observation_time
    cutoff = observation_time(boundary) if boundary is not None else None
    if boundary is not None and cutoff is None:
        return None
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
        if cutoff and (observation_time(quote) > cutoff or observation_time(knowledge) > cutoff):
            return None
        quotes.append(quote)
        known.append(knowledge)
    return {'quote_observed_at': max(quotes, key=observation_time), 'oldest_quote_at': min(quotes, key=observation_time),
            'source_knowledge_at': max(known, key=observation_time), 'retained_attachment_at':
            getattr(observation, 'retained_attachment_at', None) or observation.observed_at}


def trade_observation_admission(observation, *, asset_id, league_ids, boundary):
    """Existing trade quote admission, applied before latest-state selection.

    This proves a retained quote's identity/units, not historical league-format
    parity or whole-package freshness. No price conversion or acquisition.
    """
    from src.core.intelligence_memory.market import supported_quote_identity
    from src.core.valuation.config import CANONICAL_MIN, CANONICAL_MAX
    from src.core.intelligence_memory.timestamps import observation_time
    if observation_time(boundary) is None:
        return None, 'Trade timestamp unavailable; prior quote ordering cannot be established.'
    if observation.asset_id != asset_id:
        return None, 'Retained observation has a different exact asset identity.'
    rows = tuple(observation.provider_evidence)
    from collections.abc import Mapping
    for row in rows:
        metadata = row.metadata or {}
        if not isinstance(metadata, Mapping):
            return None, 'Retained observation has unavailable source metadata.'
        if metadata.get('league_id') not in (None, '', *league_ids):
            return None, 'Retained observation belongs to a different league context.'
        if metadata.get('asset_id') not in (None, asset_id):
            return None, 'Retained observation has a different exact asset identity.'
        if not supported_quote_identity(row):
            return None, 'Retained observation lacks compatible exact asset evidence; no range-average substitute is admitted.'
    clocks = observation_clocks(observation, boundary)
    if not clocks:
        return None, 'Retained observation is not decision-time eligible: quote/knowledge clocks are after the trade or unavailable.'
    for row in rows:
        metadata = row.metadata or {}
        # Explicit unknown/invalid knowledge is not replaced by an earlier
        # quote. A source publication/update later than the trade is not prior
        # evidence. Optional absent publication fields make no extra claim.
        for field in ('source_knowledge_at', 'known_at', 'published_at', 'source_updated_at'):
            if field not in metadata or (field in ('published_at', 'source_updated_at') and metadata[field] is None):
                continue
            stamp = observation_time(metadata[field])
            if stamp is None or stamp > observation_time(boundary):
                return None, 'Retained observation is not decision-time eligible: a stated knowledge/publication/update clock is unavailable or after the trade.'
    semantics = [(row.metadata or {}).get('comparison_semantics') for row in rows]
    providers = tuple(sorted({row.provider for row in rows}))
    identity = retained_comparison_identity(
        semantics[0] if semantics and all(s == semantics[0] for s in semantics) else None, providers)
    value = observation.canonical_value
    if (not identity or identity[:2] != ('external_market_normalized_index', '0-1000')
            or not isinstance(value, (int, float)) or isinstance(value, bool)
            or not isfinite(value) or not CANONICAL_MIN <= value <= CANONICAL_MAX):
        return None, 'Retained observation lacks compatible provider, units, format or normalization evidence.'
    return identity, None

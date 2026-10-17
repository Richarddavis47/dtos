"""Read-only admission of historical canonical Market units; never conversion."""
from datetime import datetime
import json
from math import isfinite
from collections.abc import Mapping

from src.core.valuation.config import CANONICAL_MAX, CANONICAL_MIN, NORMALIZATION_VERSION, DEFAULT_CONFIG
from src.core.valuation.consensus import MARKET_SELECTION_VERSION
from src.core.valuation.observation_identity import OBSERVATION_IDENTITY_VERSION


def instant(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed if parsed.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def quote_time(row):
    """Qualification ages from source observations, not later knowledge/retrieval."""
    if any(not isinstance(provider, Mapping) for provider in row.provider_observations):
        return None
    clocks = [instant(provider.get('observed_at')) for provider in row.provider_observations]
    return min(clocks) if clocks and all(clocks) else instant(row.occurred_at)


def checkpoint_reason(row, boundary):
    """Opaque legacy method/context hashes do not prove comparable currency."""
    identity = row.comparison_identity
    def known(value):
        return isinstance(value, str) and value.strip() and value.casefold() not in {'unknown', 'unavailable'}
    if (not all(known(value) for value in (row.source_reference, row.market_context_id, row.normalization_version))
            or len(identity) < 5 or any(not isinstance(x, str) or not x.strip() for x in identity)):
        return 'historical_market_comparison_identity_unavailable'
    if row.value_concept != 'canonical_market':
        return 'historical_market_value_concept_not_market'
    if (identity[:2] != ('external_market_normalized_index', '0-1000')
            or identity[3] != MARKET_SELECTION_VERSION + ':' + OBSERVATION_IDENTITY_VERSION
            or row.normalization_version != NORMALIZATION_VERSION):
        return 'historical_market_units_or_method_incompatible'
    providers = tuple(sorted(set(identity[4:])))
    if (not set(providers) <= set(DEFAULT_CONFIG.provider_scales)
            or row.provider != (providers[0] if len(providers) == 1 else 'dtos_consensus')):
        return 'historical_market_provider_incompatible'
    try:
        formats = json.loads(identity[2])
        if (not isinstance(formats, list) or not formats
                or {f['provider'] for f in formats} != set(providers)
                or any(not f.get('format') or f['format'].casefold() in {'unknown', 'unavailable'}
                       or f.get('normalization') != row.normalization_version for f in formats)):
            return 'historical_market_format_or_normalization_incompatible'
    except (ValueError, TypeError, KeyError, AttributeError):
        return 'historical_market_format_or_normalization_incompatible'
    value = row.normalized_value
    if (not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value)
            or not CANONICAL_MIN <= value <= CANONICAL_MAX):
        return 'historical_market_canonical_value_incompatible'
    observed, decision = instant(row.occurred_at), instant(boundary)
    if not observed or not decision or observed > decision:
        return 'historical_market_quote_not_decision_eligible'
    for provider in row.provider_observations:
        if not isinstance(provider, Mapping) or not isinstance(provider.get('metadata') or {}, Mapping):
            return 'historical_market_provider_clock_not_decision_eligible'
        metadata = provider.get('metadata') or {}
        component = provider.get('normalized_value')
        if (provider.get('provider') not in providers
                or provider.get('normalization_version') != row.normalization_version
                or not isinstance(component, (int, float)) or isinstance(component, bool)
                or not isfinite(component) or not CANONICAL_MIN <= component <= CANONICAL_MAX
                or metadata.get('matching') == 'generic_pick_round_average'):
            return 'historical_market_provider_units_or_identity_incompatible'
        quote = instant(provider.get('observed_at'))
        knowledge = instant(metadata.get('source_knowledge_at') or metadata.get('known_at') or provider.get('observed_at'))
        if (not known(provider.get('source_identity')) or not quote or not knowledge
                or max(quote, knowledge) > min(decision, observed)):
            return 'historical_market_provider_clock_not_decision_eligible'
        for name in ('source_updated_at', 'published_at'):
            if metadata.get(name) is not None:
                published = instant(metadata[name])
                if not published or published > min(decision, observed):
                    return 'historical_market_provider_clock_not_decision_eligible'
    return None

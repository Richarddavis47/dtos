"""Compact provenance captured with the selected price, never inferred on reads."""
import json

from .config import NORMALIZATION_VERSION
from .consensus import MARKET_SELECTION_VERSION
from .source_time import market_times

OBSERVATION_IDENTITY_VERSION = 'observation-identity-1'


def observation_evidence(selected, *, canonical_value):
    """Selected (provider, raw quote, normalized price) only; no price selection."""
    if canonical_value is None or not selected:
        return None
    identities, observations = [], []
    for provider, quote, normalized in selected:
        ref = quote.get('normalization_reference') or {}
        # A legacy/fallback normalization cannot acquire guessed provenance.
        if (ref.get('provider') != provider or ref.get('raw_value') != quote.get('value')
                or ref.get('normalized_value') != normalized or not ref.get('generation')
                or ref.get('version') != NORMALIZATION_VERSION
                or ref.get('method') not in {'provider_range_linear', 'provider_range_70_percentile_30'}):
            return None
        fmt = quote.get('market_format') or quote.get('format')
        if not isinstance(fmt, str) or not fmt.strip() or fmt.casefold() in {'unknown', 'unavailable'}:
            return None
        concept = {'type': quote.get('pick_type', 'player'),
                   **{k: quote[k] for k in ('year', 'round', 'range', 'exact_slot') if quote.get(k) is not None}}
        identities.append({'provider': provider, 'format': fmt,
                           'details': quote.get('format_details'), 'concept': concept,
                           'source_scale': quote.get('value_scale'),
                           'normalization': ref['version'], 'method': ref['method']})
        clocks = market_times(quote)
        observations.append({'provider': provider, 'raw_value': quote['value'],
                             'normalized_value': normalized,
                             'normalization_version': ref['version'],
                             'observed_at': clocks['retrieved_at'],
                             'source_identity': ref['generation'],
                             'temporal_distance_seconds': None,
                             'metadata': {'source_updated_at': clocks['source_updated_at'],
                                          'retrieved_at': clocks['retrieved_at'],
                                          'published_at': clocks['published_at']}})
    # The normalized index is comparable under this same definition, not a raw
    # provider currency. Changing population may move the index, not prove cause.
    semantics = {'value_concept': 'external_market_normalized_index',
                 'value_scale': '0-1000',
                 'format_key': json.dumps(sorted(identities, key=lambda r: r['provider']),
                                          sort_keys=True, separators=(',', ':')),
                 'methodology': MARKET_SELECTION_VERSION + ':' + OBSERVATION_IDENTITY_VERSION}
    for observation in observations:
        observation['metadata']['comparison_semantics'] = semantics
    return {'canonical_value': canonical_value, 'observations': observations}

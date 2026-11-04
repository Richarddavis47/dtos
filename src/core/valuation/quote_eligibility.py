"""Current quote admission; never turn historical/missing evidence into price."""
from math import isfinite


def exclusion_reason(provider, row):
    if not isinstance(row, dict) or row.get('value') is None:
        return 'NO_CURRENT_PROVIDER_QUOTE'
    if row.get('identity_status') in {'ambiguous', 'unresolved', 'conflicting'}:
        return 'AMBIGUOUS_UNRESOLVED_PLAYER_IDENTITY'
    if row.get('retrieval_mode') == 'historical_snapshot' or row.get('availability') == 'historical':
        return 'HISTORICAL_ONLY_EVIDENCE'
    if row.get('availability') in {'expired', 'stale_beyond_usable'}:
        return 'STALE_BEYOND_USABLE_POLICY'
    if row.get('availability') in {'blocked', 'unavailable', 'invalid'}:
        return 'ZERO_CONFIDENCE_INVALID_QUOTE'
    try:
        if not isfinite(float(row['value'])) or float(row['value']) < 0 or float(row.get('confidence', 70)) <= 0:
            return 'ZERO_CONFIDENCE_INVALID_QUOTE'
    except (ValueError, TypeError):
        return 'ZERO_CONFIDENCE_INVALID_QUOTE'
    # Do not transform an explicitly different feed into the configured reference.
    if provider in {'FantasyCalc', 'DynastyProcess'} and row.get('format') not in {None, 'dynasty_2qb'}:
        return 'INCOMPATIBLE_PROVIDER_FORMAT'
    details = row.get('format_details') or {}
    if provider == 'FantasyCalc' and any(details.get(k, v) != v for k, v in (('num_teams', 12), ('ppr', 1), ('num_qbs', 2))):
        return 'INCOMPATIBLE_PROVIDER_FORMAT'
    return None

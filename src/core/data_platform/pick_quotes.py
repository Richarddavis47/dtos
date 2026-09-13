"""Parse provider pick concepts without turning ranges into exact slots."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from math import isfinite
from typing import Any


def pick_concept(provider: str, label: str, source_id: str | None = None) -> dict[str, Any] | None:
    if provider == 'FantasyCalc':
        match = re.fullmatch(r'(\d{4}) ([1-9]\d*)(?:st|nd|rd|th)(?: \((Early|Mid|Late)\))?', label)
        if not match:
            return None
        year, round_number, band = match.groups()
        expected = f'FP_{year}_{band.lower()}_{int(round_number)-1}' if band else f'FP_{year}_{round_number}'
        if source_id != expected:
            return None
        return {'year': int(year), 'round': int(round_number),
                'pick_type': 'projected_range' if band else 'generic_round',
                'range': band.upper() if band else None, 'exact_slot': None}
    if provider == 'DynastyProcess':
        exact = re.fullmatch(r'(\d{4}) Pick ([1-9]\d*)\.([0-9]{2})', label)
        if exact:
            year, round_number, slot = exact.groups()
            if int(slot) == 0:
                return None
            return {'year': int(year), 'round': int(round_number), 'pick_type': 'exact_slot',
                    'range': None, 'exact_slot': f'{round_number}.{slot}'}
        match = re.fullmatch(r'(\d{4}) (?:(Early|Mid|Late) )?([1-9]\d*)(?:st|nd|rd|th)', label)
        if match:
            year, band, round_number = match.groups()
            return {'year': int(year), 'round': int(round_number),
                    'pick_type': 'projected_range' if band else 'generic_round',
                    'range': band.upper() if band else None, 'exact_slot': None}
    return None


def select_pick_quote(pick: dict[str, Any], quotes: list[dict[str, Any]], *,
                      market_format: str, now: datetime,
                      max_age: timedelta = timedelta(hours=48)) -> dict[str, Any]:
    """Select one compatible raw quote, never synthesize consensus or a price.

    The caller supplies the requested provider-format identity, not a team-fit
    multiplier. Raw units are retained; downstream package normalization must
    prove compatibility separately.
    """
    exact = pick.get('exact_slot') if pick.get('exact_slot_established') is True else None
    band = pick.get('projected_range') if pick.get('range_supported') is True and not exact else None
    priorities = [('exact_slot', exact)] if exact else [('projected_range', band)] if band in {'EARLY', 'MID', 'LATE'} else []
    priorities.append(('generic_round', None))
    eligible = []
    exclusions = []
    for quote in quotes:
        reason = None
        if quote.get('provider') not in {'FantasyCalc', 'DynastyProcess'}:
            reason = 'NOT_EXTERNAL_PROVIDER'
        elif quote.get('market_format') != market_format:
            reason = 'FORMAT_INCOMPATIBLE'
        elif quote.get('availability') != 'current':
            reason = 'NOT_CURRENT_EVIDENCE'
        try:
            if isinstance(quote.get('value'), bool) or not isfinite(float(quote['value'])) or float(quote['value']) < 0 or float(quote.get('confidence', 0)) <= 0:
                reason = reason or 'INVALID_VALUE_OR_CONFIDENCE'
            # Source freshness and knowledge time are independently checked.
            retrieved = datetime.fromisoformat(quote['retrieved_at'].replace('Z', '+00:00'))
            source = quote.get('source_updated_at')
            effective = datetime.fromisoformat(source.replace('Z', '+00:00')) if source else retrieved
            if not retrieved.tzinfo or not effective.tzinfo:
                raise ValueError('timezone required')
            if retrieved > now or effective > now or now - effective > max_age or now - retrieved > max_age:
                reason = reason or 'STALE_OR_FUTURE_EVIDENCE'
        except (KeyError, TypeError, ValueError, AttributeError):
            reason = reason or 'INVALID_EVIDENCE'
        if reason:
            exclusions.append({'provider': quote.get('provider'), 'reason': reason})
        else:
            eligible.append(quote)
    for kind, detail in priorities:
        candidates = [q for q in eligible
                      if q.get('year') == pick.get('year', pick.get('season'))
                      and q.get('round') == pick.get('round') and q.get('pick_type') == kind
                      and (kind == 'generic_round' or q.get('exact_slot' if kind == 'exact_slot' else 'range') == detail)]
        # Conflicting same-source snapshots are not resolved by input order.
        for provider in ('FantasyCalc', 'DynastyProcess'):
            rows = [q for q in candidates if q['provider'] == provider]
            if rows and len({(q['value'], q.get('value_scale'), q.get('source_updated_at'), q['retrieved_at']) for q in rows}) == 1:
                return {'availability': 'available', 'evidence_state': 'SINGLE-PROVIDER MARKET',
                        'quote': dict(rows[0]), 'exclusions': exclusions,
                        'freshness_basis': 'provider_update' if rows[0].get('source_updated_at') else 'retrieval_only_source_time_unknown'}
    return {'availability': 'unavailable', 'evidence_state': 'MARKET UNAVAILABLE',
            'quote': None, 'exclusions': exclusions}


def canonical_pick_market(pick: dict[str, Any], market_data: dict[str, Any], *,
                          now: datetime | None = None,
                          market_format: str = 'fc:12:2qb:ppr') -> dict[str, Any]:
    """Read prepared evidence only; no provider work or normalization on requests."""
    from datetime import timezone
    from src.core.valuation.config import NORMALIZATION_VERSION

    result = select_pick_quote(pick, [q for rows in (market_data.get('pick_quotes') or {}).values()
                                     for q in rows], market_format=market_format,
                               now=now or datetime.now(timezone.utc))
    quote = result['quote']
    ref = (quote or {}).get('normalization_reference') or {}
    value = ref.get('normalized_value')
    if quote is not None and (
        ref.get('provider') == quote['provider']
        and ref.get('raw_value') == float(quote['value'])
        and ref.get('version') == NORMALIZATION_VERSION and ref.get('generation')
        and ref.get('method') in {'provider_range_linear', 'provider_range_70_percentile_30'}
        and isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 1000
    ):
        return {**result, 'normalized_market_price': value,
                'normalization_generation': ref['generation']}
    return {**result, 'availability': 'unavailable', 'evidence_state': 'MARKET UNAVAILABLE',
            'normalized_market_price': None, 'reason': 'NO_VALID_PREPARED_PICK_PRICE'}

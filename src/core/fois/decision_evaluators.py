"""Bounded historical decision assessments, not blended manager scores.

Inputs are preparation-flight evidence; only reference IDs and derived
conclusions leave this boundary. Process never reads outcome evidence.
"""
from datetime import datetime
from math import isfinite

METHOD = 'fois-decision-dimensions-v1'


def _time(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result if result.tzinfo is not None else None
    except ValueError:
        return None


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def evaluate_decision(row, category, *, market=(), alternatives=(), roster_assessment=None,
                      outcome=None):
    """Assess supported dimensions independently, with no invented overall grade.

    Market inputs must carry an exact asset, time, reference and comparison
    context. Alternative membership must be established at the decision time,
    not inferred from later draft selections. Missing dimensions remain missing.
    """
    boundary = _time(row.get('occurred_at'))
    reasons, dimensions = [], []
    identity = (bool(row.get('draft_id') and row.get('player_id'))
                and _number(row.get('pick_number')) and row['pick_number'] > 0
                if category == 'drafting' else
                bool(row.get('transaction_id') and (row.get('adds') or row.get('drops'))))
    if not identity:
        reasons.append('INCOMPLETE_TRANSACTION_IDENTITY')
    if not boundary:
        reasons.append('DECISION_TIME_UNAVAILABLE' if row.get('occurred_at') in (None, '')
                       else 'INVALID_TIME_BOUNDARY')
    if not row.get('owner_id'):
        reasons.append('NO_GM_ATTRIBUTION')
    prices = {}
    if boundary:
        for evidence in market:
            stamp = _time(evidence.get('observed_at'))
            if (stamp and stamp <= boundary and evidence.get('reference')
                    and evidence.get('context') and _number(evidence.get('value'))
                    and evidence['value'] >= 0):
                prices[str(evidence['asset_id'])] = evidence
    if not prices:
        reasons.append('NO_CONTEMPORANEOUS_MARKET' if boundary
                       else 'MARKET_LOOKUP_UNAVAILABLE_TIME_BOUNDARY')
    if identity and boundary and row.get('owner_id'):
        if category == 'drafting':
            selected = prices.get(str(row.get('player_id')))
            eligible = [prices[str(item['asset_id'])] for item in alternatives
                        if item.get('available_at_decision') is True
                        and item.get('reference') and _time(item.get('known_at'))
                        and _time(item['known_at']) <= boundary
                        and str(item.get('asset_id')) in prices]
            comparable = [item for item in eligible if selected and item['context'] == selected['context']]
            if selected and comparable:
                best = max(item['value'] for item in comparable)
                dimensions.append({'dimension': 'market_relative_selection',
                    'assessment': 'at_or_above_observed_alternatives' if selected['value'] >= best
                                  else 'below_observed_alternative',
                    'difference': selected['value'] - best,
                    'references': sorted({selected['reference'], *(item['reference'] for item in comparable)}),
                    'scope': 'observed_alternatives_only_not_overall_draft_quality'})
            else:
                reasons.append('NO_COMPARABLE_AVAILABLE_ALTERNATIVES')
        elif category == 'waivers':
            adds, drops = tuple(row.get('adds') or ()), tuple(row.get('drops') or ())
            package = [prices.get(str(asset)) for asset in (*adds, *drops)]
            if adds and drops and all(package) and len({item['context'] for item in package}) == 1:
                delta = sum(prices[str(asset)]['value'] for asset in adds) - sum(prices[str(asset)]['value'] for asset in drops)
                dimensions.append({'dimension': 'contemporaneous_asset_exchange',
                    'assessment': 'higher_observed_market' if delta > 0 else 'lower_observed_market' if delta < 0 else 'equal_observed_market',
                    'difference': delta, 'references': sorted({item['reference'] for item in package}),
                    'scope': 'market_exchange_only_not_faab_efficiency_or_overall_quality'})
            else:
                reasons.append('NO_COMPLETE_COMPARABLE_ADD_DROP_MARKET')
            if row.get('faab_bid') is None:
                reasons.append('FAAB_UNAVAILABLE_OR_NOT_APPLICABLE')
        # Independently supplied historical roster conclusions can support a
        # bounded assessment even when Market is missing. Never accept a current
        # roster or an unscoped assessment as a historical substitute.
        context = roster_assessment or {}
        at = _time(context.get('as_of'))
        if (context.get('reference') and at and at <= boundary
                and context.get('owner_id') == row.get('owner_id')
                and context.get('league_id') == row.get('league_id')
                and context.get('assessment') in {'supported_need_addressed', 'supported_need_unaddressed'}):
            dimensions.append({'dimension': 'historical_roster_alignment',
                'assessment': context['assessment'], 'references': [context['reference']],
                'scope': 'historical_roster_alignment_only'})
        else:
            reasons.append('NO_SUPPORTED_ROSTER_FIT_CONCLUSION' if context.get('reference') else 'NO_HISTORICAL_ROSTER_CONTEXT')
    process = {'evaluability': 'partially_evaluable' if dimensions else 'insufficient',
               'assessment': dimensions, 'quality': None,
               'confidence': 'limited_scope' if dimensions else 'unavailable',
               'reasons': reasons}
    # Later outcomes are reported only with their own explicit observation
    # boundary, identity, scope and source reference. They never alter process.
    later = outcome or {}
    later_at = _time(later.get('as_of'))
    outcome_supported = (boundary and later_at and later_at > boundary and later.get('reference')
                         and later.get('decision_id') == (row.get('transaction_id') or row.get('draft_id'))
                         and later.get('league_id') == row.get('league_id')
                         and later.get('assessment') is not None)
    result = {'evaluability': 'partially_evaluable' if outcome_supported else 'insufficient',
              'assessment': later.get('assessment') if outcome_supported else None,
              'confidence': 'limited_scope' if outcome_supported else 'unavailable',
              'references': [later['reference']] if outcome_supported else [],
              'reasons': [] if outcome_supported else ['NO_OUTCOME_EVIDENCE']}
    return {'method': METHOD, 'process': process, 'outcome': result,
            'historical_roster_context': roster_assessment}

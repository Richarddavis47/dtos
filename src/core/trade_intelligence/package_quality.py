"""Observable package utility, deliberately separate from acquisition price."""
from decimal import Decimal
from math import isfinite

from src.core.projection_intelligence.sleeper_provider import freshness_state

from .market_balance import package_market


def reserve_quality(weekly):
    """Compare already-solved disjoint replacements, never sum removal scenarios.

    A known subtotal is useful even when a roster cannot field a second full
    lineup. Missing candidate projections do not establish a zero or a bound
    on their potential replacement contribution.
    """
    comparisons = {}
    for week, row in weekly.items():
        before = (row.get('pre') or {}).get('reserve_capacity') or {}
        after = (row.get('post') or {}).get('reserve_capacity') or {}
        limitations = []
        states, freshness = [], set()

        def points(capacity):
            qualification = capacity.get('qualification') or {}
            limitations.extend(qualification.get('limitations') or [])
            clocks = qualification.get('source_timestamps')
            if isinstance(clocks, dict):
                clocks = list(clocks.values())
            source_states = ({freshness_state(clock) for clock in clocks}
                             if isinstance(clocks, (list, tuple)) else set())
            freshness.update(source_states or qualification.get('projection_freshness') or [])
            state = qualification.get('conclusion_state')
            if source_states and source_states != {'Fresh'}:
                limitations.append('Original projection observations are not confirmed Fresh; replacement production remains conditional.')
                state = 'provisional' if state != 'unavailable' else state
            states.append(state)
            missing = capacity.get('missing_player_ids') or []
            if missing or qualification.get('calculation_supported') is False:
                limitations.append('Some eligible reserve projections are unavailable; replacement production is not established.')
                return None
            value = capacity.get('known_subtotal')
            if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value):
                return value
            # Empty supported pools have no replacement production. Legacy or
            # missing evidence has no candidate identity and remains unknown.
            if capacity.get('candidate_count') == 0 and qualification.get('calculation_supported') is True:
                return 0.0
            limitations.append('Supported replacement-production evidence is unavailable.')
            return None

        pre, post = points(before), points(after)
        supported = pre is not None and post is not None
        delta = float(Decimal(str(post)) - Decimal(str(pre))) if supported else None
        weekly_threshold = max(1.0, (pre or 0) * .03)
        state = ('unavailable' if not supported else 'current' if states == ['current', 'current'] else 'provisional')
        if supported and None in states:
            limitations.append('Reserve source and eligibility qualifications are unavailable; the numerical comparison is provisional.')
        comparisons[week] = {
            'pre_points': pre, 'post_points': post,
            'delta': delta,
            'material_weekly_threshold': weekly_threshold,
            'material_gain': delta is not None and delta >= weekly_threshold,
            'material_loss': delta is not None and delta <= -weekly_threshold,
            'availability': 'supported' if supported else 'unavailable',
            'conclusion_state': state,
            'projection_freshness': sorted(freshness),
            'pre_slots': before.get('supported_slots'), 'post_slots': after.get('supported_slots'),
            'limitations': sorted(set(limitations)),
        }
    admitted = {week: row for week, row in comparisons.items() if row['delta'] is not None}
    mean = (float(sum((Decimal(str(row['delta'])) for row in admitted.values()), Decimal(0)) / len(admitted))
            if admitted else None)
    baseline = (float(sum((Decimal(str(row['pre_points'])) for row in admitted.values()), Decimal(0)) / len(admitted))
                if admitted else None)
    # Match the established production materiality convention; do not price
    # reserves or invent injury probabilities or future games played.
    threshold = max(1.0, (baseline or 0) * .03)
    complete = bool(comparisons) and len(admitted) == len(comparisons)
    loss_weeks = [week for week, row in admitted.items() if row['material_loss']]
    aggregate = {
        'mean_weekly_delta': mean, 'pre_mean_weekly_points': baseline,
        'material_weekly_threshold': threshold,
        'material_gain': complete and not loss_weeks and mean is not None and mean >= threshold,
        'material_loss': bool(loss_weeks),
        'gain_weeks': [week for week, row in admitted.items() if row['material_gain']],
        'loss_weeks': loss_weeks,
        'complete': complete, 'supported_weeks': list(admitted), 'weeks_counted_once': list(admitted),
        'conclusion_state': ('unavailable' if not admitted else 'current'
                             if complete and all(row['conclusion_state'] == 'current' for row in admitted.values())
                             else 'provisional'),
        'projection_freshness': sorted({state for row in comparisons.values()
                                       for state in row['projection_freshness']}),
        'availability': 'supported' if complete else 'partial' if admitted else 'unavailable',
        'meaning': 'unique supported weeks of disjoint legal reserve production; not an injury forecast or a second starting lineup',
    }
    return comparisons, aggregate


def package_profile(incoming, outgoing, impact):
    incoming_ids = {a.asset_id.removeprefix('player:') for a in incoming if a.kind == 'player'}
    outgoing_ids = {a.asset_id.removeprefix('player:') for a in outgoing if a.kind == 'player'}
    weekly = (impact or {}).get('weekly') or {}
    supported = {week: row for week, row in weekly.items() if row.get('delta') is not None}
    contributors = {entry['asset_id'] for row in supported.values()
                    for entry in row['post']['optimal']['entries'] if entry['asset_id'] in incoming_ids}
    gains = [week for week, row in supported.items() if row['delta'] > 0]
    losses = [week for week, row in supported.items() if row['delta'] < 0]
    capacity = (impact or {}).get('roster_capacity')
    depth_changes = {week: row['post']['reserve_capacity']['supported_slots'] - row['pre']['reserve_capacity']['supported_slots']
                     for week, row in supported.items()}
    quality_by_week, quality = reserve_quality(weekly)
    market = package_market(incoming)
    prices = [a.trade_value for a in incoming if a.trade_value is not None]
    concentration = max(prices) / market['total'] if market['total'] and prices else None
    reasons = []
    assessment = 'UNAVAILABLE'
    explanation = 'Supported legal-lineup contribution is unavailable; price alone does not establish package utility.'
    if supported:
        assessment = 'MIXED' if gains and losses else 'BOUNDED CONTRIBUTION'
        explanation = 'Supported weekly contribution is reported separately from Market price and unknown cut cost.'
        if len(contributors) >= 2 and gains and not losses:
            assessment = 'USEFUL DEPTH'
            explanation = 'Multiple incoming players enter supported optimal lineups with gains and no observed supported-week loss.'
            reasons.append('MULTIPLE_LINEUP_CONTRIBUTORS')
        elif (len(incoming_ids) >= 3 and not contributors and losses
              and (quality['material_loss'] or quality['complete'] and not quality['material_gain']
                   or not any(d > 0 for d in depth_changes.values()))):
            assessment = 'POOR'
            explanation = 'None of the incoming players enters the supported optimal lineups, while lineup strength falls without a supported useful replacement-production gain.'
            reasons.append('PACKAGE_STUFFING')
        elif len(incoming_ids) >= 3 and not contributors and losses:
            assessment = 'MIXED'
            explanation = 'Starting strength falls but supported reserve coverage improves; this is a depth tradeoff, not established stuffing.'
            reasons.append('RESERVE_COVERAGE_GAIN_WITH_STARTER_LOSS')
        if gains and losses:
            reasons.append('MIXED_WEEKLY_LINEUP_EFFECTS')
        elif gains:
            reasons.append('SUPPORTED_LINEUP_GAIN')
        elif losses:
            reasons.append('SUPPORTED_LINEUP_LOSS')
        if len(incoming_ids) == 1 and len(outgoing_ids) > 1 and contributors and gains and not losses:
            reasons.append('CONSOLIDATION_LINEUP_GAIN')
            assessment = 'SUPPORTED CONSOLIDATION'
            explanation = 'A concentrated incoming player improves supported optimal lineups; Market premium and reserve losses remain separate.'
    if capacity and capacity['additional_spots_to_resolve']:
        reasons.append('ROSTER_SPOT_COST')
    if quality['material_loss']:
        reasons.append('RESERVE_PRODUCTION_LOSS')
    if quality['material_gain']:
        reasons.append('RESERVE_PRODUCTION_GAIN')
    if quality['gain_weeks'] and quality['loss_weeks']:
        reasons.append('MIXED_WEEKLY_RESERVE_PRODUCTION')
    return {'label': 'Package Quality', 'assessment': assessment, 'explanation': explanation,
            'reason_codes': reasons, 'supported_weeks': list(supported),
            'incoming_lineup_contributors': sorted(contributors),
            'gain_weeks': gains, 'loss_weeks': losses, 'reserve_slot_changes': depth_changes,
            'reserve_quality_by_week': quality_by_week, 'reserve_quality': quality,
            'net_player_roster_spots': len(incoming_ids) - len(outgoing_ids),
            'market_concentration': concentration, 'tier_cliff': None,
            'centerpiece_evidence': {
                'lineup_contributor_ids': sorted(contributors),
                'market_concentration': concentration,
                'production_quality': None, 'liquidity': None, 'elite_tier': None,
                'meaning': 'observed contribution and price concentration, not an elite-asset classification'},
            'roster_capacity': capacity, 'cut_cost': None,
            'capacity_availability': 'configured_slots_only' if capacity else 'unavailable',
            'liquidity_availability': 'unavailable', 'universal_package_discount': False}

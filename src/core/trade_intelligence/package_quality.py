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


def package_adjustment(incoming, outgoing, impact, package, strategy, league, *,
                       incoming_total, outgoing_total):
    """Qualify top-player tradeoffs without pricing NFL points or useful depth."""
    from src.core.valuation.config import DEFAULT_CONFIG

    slots = tuple(str(slot).upper() for slot in (league.get('roster_positions') or ()))
    extra_qb_slot = slots.count('QB') > 1 or 'SUPER_FLEX' in slots
    best_ball = (league.get('settings') or {}).get('best_ball') == 1
    required_spots = (package.get('roster_capacity') or {}).get('additional_spots_to_resolve', 0)
    extra_players = max(0, package['net_player_roster_spots'])
    result = {
        'assessment': 'UNVERIFIED', 'blocks_recommendation': False,
        'explanation': 'Complete prices are needed to compare the top assets in these packages.',
        'best_ball': best_ball, 'extra_qb_slot': extra_qb_slot,
        'extra_active_players': extra_players, 'spots_to_resolve': required_spots,
    }
    if required_spots:
        result.update(assessment='LIMITED', blocks_recommendation=True,
                      explanation=f'The incoming package exceeds the active roster limit by {required_spots}. No drop or exception is assumed.')
        return result

    if incoming_total is None or outgoing_total is None:
        return result
    top = max((asset for asset in outgoing if asset.kind == 'player'),
              key=lambda asset: (asset.trade_value, asset.asset_id), default=None)
    scarce_qb = bool(top and top.position == 'QB' and extra_qb_slot)
    tier_floor = DEFAULT_CONFIG.premium_asset_threshold if scarce_qb else DEFAULT_CONFIG.elite_asset_threshold
    best_incoming = max((a.trade_value for a in incoming if a.kind == 'player'
                         and (not scarce_qb or a.position == 'QB')), default=0)
    gap = bool(top and top.trade_value >= tier_floor and best_incoming < top.trade_value * .85)
    production = strategy['production_evidence']
    quality = package['reserve_quality']
    incoming_ids = {a.asset_id.removeprefix('player:') for a in incoming if a.kind == 'player'}
    distinct_roles = 0
    for week, row in ((impact or {}).get('weekly') or {}).items():
        if row.get('delta') is None:
            continue
        post = row['post']
        assigned = list(post['optimal']['entries'])
        reserve = package['reserve_quality_by_week'].get(week) or {}
        if best_ball and reserve.get('conclusion_state') == 'current' and reserve.get('material_gain'):
            # These are disjoint assignments, not separate one-player removal scenarios.
            assigned += post['reserve_capacity'].get('entries') or []
        distinct_roles = max(distinct_roles, len(incoming_ids.intersection(entry['asset_id'] for entry in assigned)))
    complete = strategy['projection_coverage_complete']
    loss = production['material_loss'] or any(
        row.get('delta') is not None
        and row['delta'] <= -max(1.0, (row.get('pre_total') or 0) * .03)
        for row in strategy['horizons'].values())
    depth = (distinct_roles >= 2 and quality['material_gain'] and not loss
             and quality['conclusion_state'] == 'current')
    production_compensation = complete and not loss and (production['material_gain'] or depth)
    capital = strategy['future_capital'].get('assessment') or {}
    premium = incoming_total - outgoing_total >= outgoing_total * .05
    premium_compensation = complete and premium and capital.get('meaningful_gain')
    capacity_note = (
        f' Adds {extra_players} to the active roster. No drop value is assumed.'
        if extra_players else '')
    result.update(distinct_incoming_roles=distinct_roles, major_top_player_gap=gap)
    capital_only_with_loss = (
        complete and loss and capital.get('meaningful_gain') and not premium_compensation
        and strategy['manager_strategy']['strategy'] is None
    )
    if not gap and capital_only_with_loss:
        result.update(assessment='LIMITED', blocks_recommendation=True, explanation=(
            'The draft capital adds flexibility, but the team gives up projected lineup points. '
            'The return does not establish enough compensation, and this team’s direction is unconfirmed.'
            + capacity_note))
    elif not gap:
        result.update(assessment='COMPARABLE', explanation=(
            'No major drop from the top player was identified.' + capacity_note))
    else:
        role = 'quarterback for this league’s QB-eligible slots' if scarce_qb else 'top player'
        lead = f'Gives up {top.label} without receiving a comparable {role}. '
        if production_compensation:
            support = ('The incoming players fill distinct useful roles and improve supported backup coverage.'
                       if depth else 'The return improves supported optimal-lineup production.')
        elif premium_compensation:
            support = 'Receives a separate Market premium and meaningful priced draft capital. Any projected lineup loss still matters.'
        else:
            fit = ('They lose projected lineup points. ' if loss else
                   'A complete lineup benefit is unconfirmed. ' if not complete else '')
            support = fit + ('The pick adds flexibility, but the return does not establish enough compensation.'
                             if capital.get('meaningful_gain') else 'The return does not establish enough lineup, depth or priced-capital compensation.')
        accepted = bool(production_compensation or premium_compensation)
        result.update(assessment='COMPENSATED' if accepted else 'LIMITED',
                      blocks_recommendation=not accepted, explanation=lead + support + capacity_note)
    return result


def package_blocks_recommendation(evaluation):
    return any(row.get('blocks_recommendation') is True
               for row in (evaluation.get('package_adjustment') or {}).values())

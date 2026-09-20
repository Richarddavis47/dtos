"""Observable package utility, deliberately separate from acquisition price."""
from .market_balance import package_market


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
        elif len(incoming_ids) >= 3 and not contributors and losses and not any(d > 0 for d in depth_changes.values()):
            assessment = 'POOR'
            explanation = 'None of the incoming players enters the supported optimal lineups, while lineup strength falls.'
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
    return {'label': 'Package Quality', 'assessment': assessment, 'explanation': explanation,
            'reason_codes': reasons, 'supported_weeks': list(supported),
            'incoming_lineup_contributors': sorted(contributors),
            'gain_weeks': gains, 'loss_weeks': losses, 'reserve_slot_changes': depth_changes,
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

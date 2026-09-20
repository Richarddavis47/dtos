"""Evidence coverage by dimension; no probability or recommendation strength."""


def evidence_confidence(market, strategies, historical, proposal, impact):
    projections = {}
    for side, strategy in strategies.items():
        projections[side] = {
            name: {'availability': row.get('availability', 'unavailable'),
                   'weeks_requested': row.get('weeks_requested', []),
                   'pre_supported_weeks': row.get('pre_supported_weeks', []),
                   'post_supported_weeks': row.get('post_supported_weeks', []),
                   'complete_delta_available': row.get('delta') is not None and row.get('availability') == 'complete'}
            for name, row in strategy['horizons'].items()
        }
    picks = [{'asset_id': a.asset_id,
              'market_availability': 'available' if a.trade_value is not None else 'unavailable',
              'projected_range': a.projected_range or 'UNKNOWN',
              'range_confidence': a.projected_range_confidence or 'UNAVAILABLE',
              'exact_slot': a.exact_slot}
             for a in (*proposal.assets_sent, *proposal.assets_received) if a.kind == 'pick']
    complete = all(s['projection_coverage_complete'] for s in strategies.values())
    return {
        'assessment': 'MEDIUM' if market['availability'] == 'full' and complete else 'LIMITED',
        'explanation': 'Support for bounded Market/lineup conclusions; not acceptance probability or outcome certainty.',
        'dimensions': {
            'market': {'availability': market['availability'],
                       'priced_assets': market['sent']['priced_assets'] + market['received']['priced_assets'],
                       'asset_count': market['sent']['asset_count'] + market['received']['asset_count']},
            'projection_and_lineup': projections,
            'picks': {'availability': 'applicable' if picks else 'not_applicable', 'assets': picks},
            'fois': {'availability': 'supported_context' if historical and historical.get('evidence_references') else 'unavailable',
                     'confidence': (historical or {}).get('confidence'),
                     'role': 'soft context, not a plausibility veto'},
            'team_context': {side: {'window': 'available' if s['competitive_window'] else 'unavailable',
                                    'capacity': 'configured_slots_only' if s['roster_capacity'] else 'unavailable'}
                             for side, s in strategies.items()},
            'methodology': {'projection_methodology': impact.get('methodology'),
                            'projection_generation': impact.get('projection_generation'),
                            'team_strength_generation': impact.get('team_strength_generation')},
        },
        'scope': 'bounded supported dimensions; unavailable longevity, liquidity and cut cost do not receive invented certainty',
    }

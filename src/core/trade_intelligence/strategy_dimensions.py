"""Bilateral observable strategic effects; no blended utility score."""


def strategic_profile(incoming, outgoing, impact, package):
    horizons = (impact or {}).get('horizons') or {}
    reasons = []
    prefix = {'current_week': 'CURRENT_LINEUP', 'next_n': 'NEXT_N',
              'rest_of_regular_season': 'ROS', 'playoff_window': 'PLAYOFF_WINDOW'}
    for name, row in horizons.items():
        delta = row.get('delta')
        if delta is not None and delta != 0:
            reasons.append(prefix[name] + ('_UPGRADE' if delta > 0 else '_DOWNGRADE'))
    depth = package['reserve_slot_changes']
    if any(value > 0 for value in depth.values()) and any(value < 0 for value in depth.values()):
        reasons.append('MIXED_WEEKLY_DEPTH_EFFECTS')
    elif any(value > 0 for value in depth.values()):
        reasons.append('DEPTH_GAIN')
    elif any(value < 0 for value in depth.values()):
        reasons.append('DEPTH_LOSS')
    def picks(assets, owner):
        return [{'asset_id': a.asset_id, 'year': a.season, 'round': a.round,
                 'original_franchise': a.original_roster_id, 'canonical_owner': a.current_owner_id,
                 'hypothetical_owner': owner, 'market_price': a.trade_value,
                 'market_evidence': a.pick_market_evidence, 'projected_range': a.projected_range,
                 'range_confidence': a.projected_range_confidence, 'exact_slot': a.exact_slot}
                for a in assets if a.kind == 'pick']
    roster = (impact or {}).get('roster_id')
    gained, lost = picks(incoming, roster), picks(outgoing, None)
    # Describe capital movement, not class quality or projected utility.
    if gained:
        reasons.append('FUTURE_CAPITAL_RECEIVED')
    if lost:
        reasons.append('FUTURE_CAPITAL_SENT')
    if (package.get('roster_capacity') or {}).get('additional_spots_to_resolve'):
        reasons.append('ROSTER_SPOT_COST')
    complete = bool(horizons) and all(row.get('availability') == 'complete' for row in horizons.values())
    if not complete:
        reasons.append('PARTIAL_PROJECTION_EVIDENCE')
    return {'horizons': horizons, 'reserve_slot_changes': depth,
            'future_capital': {'received': gained, 'sent': lost, 'utility_delta': None},
            'competitive_window': None, 'longevity': None, 'liquidity': None,
            'roster_capacity': package.get('roster_capacity'),
            'projection_coverage_complete': complete, 'reason_codes': reasons,
            'unavailable_dimensions': ['competitive_window', 'asset_longevity', 'liquidity', 'cut_cost'],
            'meaning': 'supported team-specific effects, not Market fairness or a strategy score'}


def plausibility(strategy, package, market_return, historical):
    deltas = [row['delta'] for row in strategy['horizons'].values() if row.get('delta') is not None]
    gains, losses = any(d > 0 for d in deltas), any(d < 0 for d in deltas)
    reasons = []
    if package['assessment'] == 'POOR':
        state, reasons = 'LOW', ['POOR_COUNTERPARTY_PACKAGE']
    elif not deltas:
        state, reasons = 'INSUFFICIENT EVIDENCE', ['COUNTERPARTY_PROJECTION_UNAVAILABLE']
    elif losses and not gains and market_return is not None and market_return <= 0 and not strategy['future_capital']['received']:
        state, reasons = 'LOW', ['COUNTERPARTY_LINEUP_LOSS_WITHOUT_SUPPORTED_COMPENSATION']
    elif gains and not losses and market_return is not None and market_return >= 0 and strategy['projection_coverage_complete'] and not any(d < 0 for d in strategy['reserve_slot_changes'].values()):
        state, reasons = 'STRONG', ['COUNTERPARTY_LINEUP_AND_MARKET_GAIN']
    elif gains or (market_return is not None and market_return > 0 and not losses):
        state, reasons = 'PLAUSIBLE', ['SUPPORTED_COUNTERPARTY_BENEFIT']
    else:
        state, reasons = 'INSUFFICIENT EVIDENCE', ['COUNTERPARTY_TRADEOFF_UNRESOLVED']
    if (strategy.get('roster_capacity') or {}).get('additional_spots_to_resolve'):
        state = 'INSUFFICIENT EVIDENCE'
        reasons.append('COUNTERPARTY_CAPACITY_UNRESOLVED')
    return {'label': 'Counterparty Plausibility', 'assessment': state,
            'reason_codes': reasons, 'historical_context': historical,
            'history_role': 'supporting context only; never a deterministic veto',
            'acceptance_probability': None,
            'explanation': 'Supported counterparty effects; not a prediction of manager behavior.'}


def reconcile_result(result, proposal, impact, historical=None, *, team_windows=None):
    """Migrate the existing canonical result, including partial-Market results."""
    from .package_quality import package_profile
    sides = impact.get('sides') or {}
    packages, strategies = {}, {}
    for side, incoming, outgoing in (('active', proposal.assets_received, proposal.assets_sent),
                                      ('partner', proposal.assets_sent, proposal.assets_received)):
        packages[side] = package_profile(incoming, outgoing, sides.get(side))
        strategies[side] = strategic_profile(incoming, outgoing, sides.get(side), packages[side])
        roster_id = proposal.active_roster_id if side == 'active' else proposal.partner_roster_id
        window = (team_windows or {}).get(str(roster_id))
        if (window and window.get('generation') and window['generation'] == impact.get('team_strength_generation')
                and window.get('classification') != 'Unavailable'):
            strategies[side]['competitive_window'] = window
            strategies[side]['unavailable_dimensions'].remove('competitive_window')
        other = proposal.partner_roster_id if side == 'active' else proposal.active_roster_id
        for pick in strategies[side]['future_capital']['sent']:
            pick['hypothetical_owner'] = str(other)
    market = result['market_evidence']
    difference = market['difference']
    plausible = plausibility(strategies['partner'], packages['partner'],
                              -difference if difference is not None else None, historical)
    active = strategies['active']
    values = [row['delta'] for row in active['horizons'].values() if row.get('delta') is not None]
    gains, losses = any(d > 0 for d in values), any(d < 0 for d in values)
    depth_loss = any(d < 0 for d in active['reserve_slot_changes'].values())
    capacity = (active.get('roster_capacity') or {}).get('additional_spots_to_resolve', 0)
    depth_gain = any(d > 0 for d in active['reserve_slot_changes'].values())
    capital_changed = bool(active['future_capital']['received'] or active['future_capital']['sent'])
    complete = active['projection_coverage_complete']
    trace = []
    recommendation = None
    if not result['legal']:
        recommendation = 'REJECT'
        trace.append('OWNERSHIP_OR_IDENTITY_INVALID')
    elif not values:
        trace.append('SUPPORTED_TEAM_IMPACT_UNAVAILABLE')
    elif capacity:
        trace.append('CUT_COST_UNRESOLVED')
    elif capital_changed:
        # Capital transfer is not a quantified substitute for player utility.
        trace.append('FUTURE_CAPITAL_TRADEOFF_UNRESOLVED')
    elif packages['active']['assessment'] == 'POOR' and losses and not gains and not depth_gain:
        recommendation = 'NOT WORTH IT'
        trace.append('LINEUP_AND_PACKAGE_COST_WITHOUT_DEPTH_BENEFIT')
    elif losses and not gains and not depth_gain and difference is not None and difference <= 0:
        recommendation = 'REJECT' if difference < 0 and complete else 'NOT WORTH IT'
        trace.append('SUPPORTED_LINEUP_COST_WITHOUT_MARKET_OR_DEPTH_COMPENSATION')
    elif gains and not losses and not depth_loss and complete:
        recommendation = 'SMASH ACCEPT' if difference is not None and difference >= 0 else 'WORTH PURSUING'
        trace.append('SUPPORTED_HORIZON_BENEFIT_WITHOUT_DEPTH_OR_CAPACITY_LOSS')
        if difference is None:
            trace.append('PURSUIT_ONLY_MARKET_TERMS_UNRESOLVED')
        elif difference < 0:
            trace.append('MARKET_PREMIUM_FOR_SUPPORTED_LINEUP_BENEFIT')
    elif (complete and not gains and not losses and not depth_gain and not depth_loss
          and difference == 0 and packages['active']['assessment'] != 'POOR'):
        recommendation = 'FAIR / OPTIONAL'
        trace.append('SUPPORTED_MARKET_LINEUP_AND_DEPTH_PARITY')
    else:
        trace.append('MATERIAL_TRADEOFF_UNRESOLVED')
    codes = list(active['reason_codes']) + list(packages['active']['reason_codes'])
    if difference is not None and difference != 0:
        codes.append('MARKET_VALUE_EDGE' if difference > 0 else 'MARKET_OVERPAY')
    if market['availability'] != 'full':
        codes.append('PARTIAL_MARKET_EVIDENCE' if market['availability'] == 'partial' else 'MARKET_EVIDENCE_UNAVAILABLE')
    if plausible['assessment'] == 'LOW':
        codes.append('LOW_COUNTERPARTY_PLAUSIBILITY')
    if recommendation is None and active['future_capital']['received'] and losses and not gains:
        codes.append('LONG_TERM_COMPENSATION_UNESTABLISHED')
    limitations = sorted(set(active['unavailable_dimensions'] + strategies['partner']['unavailable_dimensions']))
    if not historical or not historical.get('evidence_references'):
        limitations.append('insufficient_fois_history')
    if any(a.kind == 'pick' and str(a.projected_range_confidence or 'LOW').upper() == 'LOW'
           for a in (*proposal.assets_sent, *proposal.assets_received)):
        limitations.append('low_confidence_pick_range')
    from .confidence import evidence_confidence
    confidence_profile = evidence_confidence(market, strategies, historical, proposal, impact)
    confidence = confidence_profile['assessment']
    confidence_profile['limitations'] = limitations
    result['recommendation_trace'] = {
        'rule_reasons': trace,
        'scope': 'supported Market/lineup/package decision; unavailable dynasty dimensions are not inferred',
        'market_availability': market['availability'], 'market_difference': difference,
        'horizons': {name: {'delta': h.get('delta'), 'availability': h.get('availability')}
                     for name, h in active['horizons'].items()},
        'depth_by_week': active['reserve_slot_changes'],
        'package': packages['active']['assessment'], 'capacity_spots_to_resolve': capacity,
        'future_capital_changed': capital_changed,
        'unavailable_dimensions': active['unavailable_dimensions'],
        'confidence': confidence_profile['assessment'],
        'counterparty_plausibility_role': 'separate, not a user-side recommendation gate',
    }
    codes.extend(trace)
    result.update(recommendation=recommendation,
                  recommendation_availability='bounded' if recommendation else 'unavailable',
                  dominant_reason='User-side conclusion from supported Market, optimal-lineup and package evidence; counterparty plausibility is separate.',
                  reason_codes=sorted(set(codes)), major_limitations=limitations,
                  generated_trade_eligible=bool(result['legal'] and plausible['assessment'] in ('STRONG', 'PLAUSIBLE')
                                                and recommendation in ('SMASH ACCEPT', 'WORTH PURSUING') and confidence != 'LIMITED'))
    unresolved_capacity = any((s.get('roster_capacity') or {}).get('additional_spots_to_resolve') for s in strategies.values())
    result['legality'] = {'ownership_and_identity_valid': result['legal'],
                         'execution_status': 'NOT EXECUTABLE' if not result['legal'] else
                         'REQUIRES ROSTER RESOLUTION' if unresolved_capacity else 'NO IDENTIFIED OWNERSHIP OR CAPACITY BLOCKER',
                         'capacity_exception_policy': 'not inferred',
                         'reason_codes': ['ROSTER_SPOT_COST'] if unresolved_capacity else result.get('legality_reasons', [])}
    result['major_risks'] = sorted(set(code for code in codes if any(word in code for word in ('LOSS', 'DOWNGRADE', 'PARTIAL', 'UNAVAILABLE', 'UNESTABLISHED', 'COST', 'LOW_COUNTERPARTY'))))
    if unresolved_capacity:
        result['generated_trade_eligible'] = False
    best_for = {}
    for side, strategy in strategies.items():
        window = (strategy['competitive_window'] or {}).get('classification')
        deltas = [h['delta'] for h in strategy['horizons'].values() if h.get('delta') is not None]
        supported_gain = any(d > 0 for d in deltas) and not any(d < 0 for d in deltas)
        best_for[side] = ('CONTENDING' if window in ('Elite Contender', 'Contender', 'Playoff Team') and supported_gain
                          else 'RETOOLING' if window == 'Re-tooling' and supported_gain
                          else 'NO CLEAR FIT')
    best_for['reason'] = 'Canonical generation-matched window plus supported impact; capital counts alone do not establish long-term improvement.'
    result['dimensions'].update(
        strategic_fit={'label': 'Strategic Fit', 'active': active, 'partner': strategies['partner']},
        package_quality=packages, counterparty_plausibility=plausible,
        best_for=best_for,
        confidence=confidence_profile)
    result['why_you_would_do_it'] = 'Review supported user-side effects and explicit limitations.'
    result['why_they_would_do_it'] = plausible['explanation']
    result['perspectives'] = {'for_your_team': recommendation or 'UNAVAILABLE', 'bilateral_reality': plausible['assessment']}
    result.setdefault('provenance', {})['strategy_methodology'] = 'scoped-trade-effects-v2'
    return result

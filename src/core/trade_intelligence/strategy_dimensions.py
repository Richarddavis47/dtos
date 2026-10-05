"""Bilateral observable strategic effects; no blended utility score."""
from .capital_assessment import assess_capital, production_evidence, resolve_strategy


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
    complete = bool(horizons) and all(row.get('availability') == 'complete' and row.get('delta') is not None for row in horizons.values())
    if not complete:
        reasons.append('PARTIAL_PROJECTION_EVIDENCE')
    return {'horizons': horizons, 'reserve_slot_changes': depth,
            'production_evidence': production_evidence(impact),
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
    capital_fit = strategy.get('capital_strategy_fit')
    material_gain = strategy['production_evidence']['material_gain']
    material_loss = strategy['production_evidence']['material_loss']
    ratio = strategy.get('market_return_ratio')
    if ratio is not None and ratio < .50:
        state, reasons = 'LOW', ['COUNTERPARTY_SEVERE_MARKET_LOSS']
    elif capital_fit:
        recommendation = capital_fit['recommendation']
        state = ('PLAUSIBLE' if recommendation in ('SMASH ACCEPT', 'WORTH PURSUING', 'FAIR / OPTIONAL')
                 else 'LOW' if recommendation else 'INSUFFICIENT EVIDENCE')
        reasons = [capital_fit['reason_code']]
        if recommendation == 'FAIR / OPTIONAL' and capital_fit['reason_code'] == 'CAPITAL_AND_LINEUP_PARITY':
            state, reasons = 'INSUFFICIENT EVIDENCE', ['COUNTERPARTY_TRADEOFF_UNRESOLVED']
        # A manager's unobserved intent is not required to establish a concrete
        # production benefit at bounded Market cost. Do not invent that intent.
        capital = strategy['future_capital'].get('assessment') or {}
        if (recommendation is None and capital.get('availability') == 'supported' and strategy['projection_coverage_complete']
                and strategy['manager_strategy']['strategy'] is None and material_gain
                and package['assessment'] != 'POOR' and not material_loss and not losses and ratio is not None and ratio >= .80):
            state, reasons = 'PLAUSIBLE', ['COUNTERPARTY_SUPPORTED_PRODUCTION_TRADEOFF',
                                          'COUNTERPARTY_STRATEGY_UNCONFIRMED']
        elif (recommendation is None and capital.get('availability') == 'supported'
                and strategy['projection_coverage_complete'] and strategy['manager_strategy']['strategy'] is None
                and package['assessment'] != 'POOR' and capital.get('meaningful_gain')
                and ratio is not None and ratio >= .85):
            state, reasons = 'PLAUSIBLE', ['COUNTERPARTY_SUPPORTED_CAPITAL_TRADEOFF',
                                          'COUNTERPARTY_STRATEGY_UNCONFIRMED']
    elif material_loss and gains:
        state, reasons = 'LOW', ['COUNTERPARTY_MATERIAL_PRODUCTION_LOSS']
    elif package['assessment'] == 'POOR':
        state, reasons = 'LOW', ['POOR_COUNTERPARTY_PACKAGE']
    elif not deltas:
        state, reasons = 'INSUFFICIENT EVIDENCE', ['COUNTERPARTY_PROJECTION_UNAVAILABLE']
    elif losses and not gains and market_return is not None and market_return <= 0 and not strategy['future_capital']['received']:
        state, reasons = 'LOW', ['COUNTERPARTY_LINEUP_LOSS_WITHOUT_SUPPORTED_COMPENSATION']
    elif material_gain and not losses and market_return is not None and market_return >= 0 and strategy['projection_coverage_complete'] and not any(d < 0 for d in strategy['reserve_slot_changes'].values()):
        state, reasons = 'STRONG', ['COUNTERPARTY_LINEUP_AND_MARKET_GAIN']
    elif (strategy['projection_coverage_complete'] and not losses and market_return is not None and market_return >= 0
          and any(d >= 1 for d in strategy['reserve_slot_changes'].values())):
        state, reasons = 'PLAUSIBLE', ['COUNTERPARTY_SUPPORTED_DEPTH_GAIN']
    elif (material_gain and not material_loss) or (market_return is not None and market_return > 0 and not losses):
        state, reasons = 'PLAUSIBLE', ['SUPPORTED_COUNTERPARTY_BENEFIT']
    else:
        state, reasons = 'INSUFFICIENT EVIDENCE', ['COUNTERPARTY_TRADEOFF_UNRESOLVED']
    if (strategy.get('roster_capacity') or {}).get('additional_spots_to_resolve'):
        state = 'INSUFFICIENT EVIDENCE'
        reasons.append('COUNTERPARTY_CAPACITY_UNRESOLVED')
    explanation = capital_fit['explanation'] if capital_fit else 'Supported counterparty effects; not a prediction of manager behavior.'
    if 'COUNTERPARTY_SUPPORTED_PRODUCTION_TRADEOFF' in reasons:
        explanation = 'Material legal-lineup production is gained at bounded Market cost; capital spent remains a cost and manager strategy is unconfirmed.'
    elif 'COUNTERPARTY_SUPPORTED_CAPITAL_TRADEOFF' in reasons:
        explanation = 'Meaningful priced future capital is gained at broadly balanced Market terms; current production and reserve costs remain disclosed, and manager strategy is unconfirmed.'
    elif 'COUNTERPARTY_SUPPORTED_DEPTH_GAIN' in reasons:
        explanation = 'Supported roster coverage improves without a current-production loss; Market and capacity costs remain separate. This is not an acceptance prediction.'
    return {'label': 'Counterparty Plausibility', 'assessment': state,
            'reason_codes': reasons, 'historical_context': historical,
            'history_role': 'supporting context only; never a deterministic veto',
            'acceptance_probability': None, 'explanation': explanation,
            'policy': {'severe_market_loss_ratio': .50, 'unknown_direction_production_min_return_ratio': .80,
                       'unknown_direction_capital_min_return_ratio': .85, 'requires_complete_projection_and_capital': True},
            'manager_history': {'availability': 'supported' if historical and historical.get('evidence_references') else 'limited',
                                'disclosure': None if historical and historical.get('evidence_references') else 'Limited manager-history evidence'},
            'manager_strategy': strategy.get('manager_strategy')}


def disclosed_costs(strategy, market_return):
    costs = []
    production = strategy['production_evidence']
    mean = production['mean_weekly_delta']
    if mean is not None and mean < 0:
        costs.append(f'Optimal legal-lineup production falls {abs(mean):.2f} points per supported week')
    net = (strategy['future_capital'].get('assessment') or {}).get('net_market_value')
    if net is not None and net < 0:
        costs.append(f'Spends {abs(net):.0f} Market units of future capital')
    if market_return is not None and market_return < 0:
        costs.append(f'Market overpay of {abs(market_return):.0f} units')
    if any(d < 0 for d in strategy['reserve_slot_changes'].values()):
        costs.append('Reserve coverage declines in supported weeks')
    if (strategy.get('roster_capacity') or {}).get('additional_spots_to_resolve'):
        costs.append('Roster capacity requires resolution')
    return costs


def reconcile_result(result, proposal, impact, historical=None, *, team_windows=None, manager_strategies=None):
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
        strategies[side]['manager_strategy'] = resolve_strategy(
            (manager_strategies or {}).get(str(roster_id)), strategies[side]['competitive_window'])
        other = proposal.partner_roster_id if side == 'active' else proposal.active_roster_id
        for pick in strategies[side]['future_capital']['sent']:
            pick['hypothetical_owner'] = str(other)
    market = result['market_evidence']
    difference = market['difference']
    for side in ('active', 'partner'):
        strategy = strategies[side]
        outgoing = market['sent' if side == 'active' else 'received']['total']
        incoming = market['received' if side == 'active' else 'sent']['total']
        strategy['market_return_ratio'] = incoming / outgoing if outgoing and incoming is not None else None
        if strategy['future_capital']['received'] or strategy['future_capital']['sent']:
            strategy['capital_strategy_fit'] = assess_capital(strategy, packages[side], market,
                                                            outgoing_total=outgoing, incoming_total=incoming)
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
        fit = active['capital_strategy_fit']
        recommendation = fit['recommendation']
        trace.append(fit['reason_code'])
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
    elif (complete and not losses and market['availability'] == 'full' and packages['active']['assessment'] != 'POOR'
          and active['production_evidence']['material_gain']
          and active.get('market_return_ratio') is not None
          and active['market_return_ratio'] >= (.65 if active['manager_strategy']['strategy'] == 'WIN NOW' else .85)):
        recommendation = 'WORTH PURSUING'
        trace.append('MATERIAL_PRODUCTION_GAIN_WITH_DISCLOSED_ROSTER_COST')
    elif (complete and not losses and depth_gain and market['availability'] == 'full'
          and packages['active']['assessment'] != 'POOR' and active.get('market_return_ratio') is not None
          and active['market_return_ratio'] >= .85):
        recommendation = 'FAIR / OPTIONAL'
        trace.append('SUPPORTED_DEPTH_GAIN_WITH_DISCLOSED_MARKET_COST')
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
        'scope': 'separate supported Market, legal-lineup, package, priced-capital and manager-strategy evidence; unavailable dynasty dimensions are not inferred',
        'market_availability': market['availability'], 'market_difference': difference,
        'horizons': {name: {'delta': h.get('delta'), 'availability': h.get('availability')}
                     for name, h in active['horizons'].items()},
        'depth_by_week': active['reserve_slot_changes'],
        'package': packages['active']['assessment'], 'capacity_spots_to_resolve': capacity,
        'future_capital_changed': capital_changed,
        'manager_strategy': active['manager_strategy'],
        'capital_assessment': active['future_capital'].get('assessment'),
        'capital_strategy_fit': active.get('capital_strategy_fit'),
        'production_evidence': active['production_evidence'],
        'unavailable_dimensions': active['unavailable_dimensions'],
        'confidence': confidence_profile['assessment'],
        'counterparty_plausibility_role': 'separate, not a user-side recommendation gate',
    }
    codes.extend(trace)
    result.update(recommendation=recommendation,
                  recommendation_availability='bounded' if recommendation else 'unavailable',
                  dominant_reason='User-side conclusion from separate Market, optimal-lineup, package, capital and strategy evidence; counterparty plausibility is separate.',
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
        if strategy.get('capital_strategy_fit', {}).get('recommendation') in ('SMASH ACCEPT', 'WORTH PURSUING', 'FAIR / OPTIONAL'):
            best_for[side] = strategy['manager_strategy']['strategy'] or 'BALANCED EXCHANGE'
    best_for['reason'] = 'Canonical generation-matched window plus supported impact; capital counts alone do not establish long-term improvement.'
    result['dimensions'].update(
        strategic_fit={'label': 'Strategic Fit', 'active': active, 'partner': strategies['partner']},
        package_quality=packages, counterparty_plausibility=plausible,
        best_for=best_for,
        confidence=confidence_profile)
    mean = active['production_evidence']['mean_weekly_delta']
    help_text = (f'Optimal legal-lineup production improves {mean:.2f} points per supported week.' if mean is not None and mean > 0
                 else 'Supported reserve coverage improves while current production is preserved.' if depth_gain and not losses
                 else 'Review the separate supported Market, lineup and roster effects.')
    result['why_you_would_do_it'] = (active.get('capital_strategy_fit') or {}).get('explanation', help_text)
    result['major_drawback'] = '; '.join(disclosed_costs(active, difference)) or 'No material downside identified in supported evidence; projections remain conditional.'
    partner_costs = disclosed_costs(strategies['partner'], -difference if difference is not None else None)
    result['why_they_would_do_it'] = plausible['explanation']
    result['counterparty_summary'] = plausible['explanation'] + (' Costs: ' + '; '.join(partner_costs) + '.' if partner_costs else '')
    if plausible['manager_history']['disclosure']:
        result['counterparty_summary'] += ' ' + plausible['manager_history']['disclosure'] + '.'
    result['perspectives'] = {'for_your_team': recommendation or 'UNAVAILABLE', 'bilateral_reality': plausible['assessment']}
    result.setdefault('provenance', {})['strategy_methodology'] = 'scoped-trade-effects-v4-discovery'
    return result

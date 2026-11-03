"""Describe recorded evidence gaps, without changing discovery classification."""
from services.trade_lineup_evidence import completed_lineup_admissions


def evidence_limitations(result, *, admissions=None):
    admissions = admissions or completed_lineup_admissions(result)
    impact = result.get('multi_horizon_impact') or {}
    dimensions = result.get('dimensions') or {}
    fit = dimensions.get('strategic_fit') or {}
    inputs = (result.get('provenance') or {}).get('inputs') or {}
    current = (inputs.get('projection_evidence') or {}).get('week')
    blocking, qualifications = [], []
    market = result.get('market_evidence') or {}
    if market.get('availability') != 'full':
        blocking.append({'cause': 'exchanged_asset_market_price',
                         'message': 'A compatible current Market price is missing for an exchanged asset.'})
    for side in ('active', 'partner'):
        view = admissions[side]
        profile = fit.get(side) or {}
        if view['identity_state'] != 'compatible':
            blocking.append({'cause': 'projection_context', 'side': side,
                'message': 'The recorded league, season, scoring or projection generation cannot be verified.'})
        expected = sorted({w for h in (profile.get('horizons') or {}).values() for w in h.get('weeks_requested') or []})
        observed = ((impact.get('sides') or {}).get(side) or {}).get('weekly') or {}
        for week in expected:
            admitted = view['weekly'].get(week) or {}
            row = observed.get(week) or observed.get(str(week)) or {}
            if admitted.get('delta') is None:
                missing, slots = set(), set()
                for phase in ('pre', 'post'):
                    phase_row = row.get(phase) or {}
                    missing.update((phase_row.get('coverage') or {}).get('missing_player_ids') or [])
                    slots.update((phase_row.get('optimal') or {}).get('unsupported_slots') or [])
                blocking.append({'cause': 'current_week_lineup' if week == current else 'future_week_lineup',
                    'side': side, 'week': week, 'missing_player_ids': sorted(missing),
                    'unsupported_slots': sorted(slots),
                    'message': 'Compatible before/after legal-lineup evidence is incomplete for this week.',
                    'upstream_absence': 'not established by this completed evaluation'})
            for phase in ('pre', 'post'):
                reserve = (row.get(phase) or {}).get('reserve_capacity') or {}
                q = reserve.get('qualification') or {}
                if q.get('calculation_supported') is not True:
                    qualifications.append({'cause': 'reserve_depth', 'side': side, 'week': week, 'phase': phase,
                        'missing_player_ids': reserve.get('missing_player_ids') or [],
                        'message': 'Complete compatible reserve projections or eligibility are not established; missing replacement effects are not zero.'})
                for limitation in q.get('limitations') or []:
                    qualifications.append({'cause': 'availability_or_freshness', 'side': side, 'week': week,
                                           'phase': phase, 'message': limitation})
        if profile.get('projection_coverage_complete') is False and not expected:
            blocking.append({'cause': 'projection_horizon', 'side': side,
                             'message': 'The requested projection horizon has no compatible recorded coverage.'})
        capital = profile.get('future_capital') or {}
        if (capital.get('sent') or capital.get('received')) and (
                capital.get('assessment') or {}).get('availability') != 'supported':
            blocking.append({'cause': 'future_capital_qualification', 'side': side,
                             'message': 'Exact future-capital qualification is incomplete; a pick cannot supply missing projections.'})
        strategy = profile.get('manager_strategy') or {}
        if not strategy.get('strategy'):
            qualifications.append({'cause': 'manager_direction', 'side': side,
                'message': 'Manager direction is unconfirmed; this alone does not invalidate compatible production evidence.'})
    reasons = (result.get('recommendation_trace') or {}).get('rule_reasons') or []
    if 'FUTURE_CAPITAL_TRADEOFF_UNRESOLVED' in reasons:
        blocking.append({'cause': 'future_capital_tradeoff',
            'message': 'The recorded future-capital strategy trade-off remains unresolved; this is not proof of a missing source price.'})
    history = dimensions.get('historical_counterparty_evidence') or {}
    if not history.get('evidence_references'):
        qualifications.append({'cause': 'manager_history',
            'message': 'Historical manager evidence is limited; it is context, not a promise of acceptance.'})
    return {'blocking_requirements': blocking, 'contextual_qualifications': qualifications,
            'meaning': 'Recorded assessment limitations; categories may overlap. A missing downstream value does not establish upstream absence.'}

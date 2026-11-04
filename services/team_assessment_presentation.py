"""Present one prepared diagnostic publication; never solve or prepare on reads."""
MODEL_NOTE = ('DTOS shows lineup strength, depth, Market value and future outlook separately. '
              'It does not yet calculate a validated overall team grade.')


def prepared_comparison(data, snapshot=None):
    from src.core.intelligence.roster_diagnostics import prepared_diagnostics
    # The existing reader keys by current eligibility, scoring and publication,
    # and reapplies clock/failed-refresh qualification without solving a lineup.
    diagnostic = prepared_diagnostics(data, snapshot)
    if diagnostic is None:
        return None
    from src.core.intelligence.roster_diagnostics import BENCH_SLOTS
    slots = data.get('roster_positions') or (data.get('league') or {}).get('roster_positions') or []
    return {**diagnostic, 'required_slot_count': sum(str(slot).upper() not in BENCH_SLOTS for slot in slots)}


def weekly_comparison(card, week, *, compact=False, diagnostics=None):
    gap = (f'Week {week} projected lineup comparison needs compatible current availability, '
           'league, week and scoring evidence. A matching prepared comparison is not available.')
    short_gap = f'Week {week} · Comparison pending: current availability and source evidence need matching preparation.'
    if (not diagnostics or diagnostics.get('league_id') != getattr(card, 'league_id', None)
            or diagnostics.get('week') != week or not diagnostics.get('projection_generation')):
        return short_gap if compact else gap
    teams = diagnostics.get('teams') or {}
    row = teams.get(str(getattr(card, 'roster_id', ''))) or {}
    qualification = row.get('evidence') or {}
    # All displayed numbers, including the population and rank, belong to this
    # one diagnostic publication, never to a saved horizon or a different card.
    points = row.get('optimal_points')
    if points is None or not qualification.get('calculation_supported'):
        reasons = qualification.get('limitations') or row.get('lineup_limitations') or []
        return short_gap if compact else gap + (' ' + ' '.join(reasons) if reasons else '')
    supported = [r['optimal_points'] for r in teams.values()
                 if r.get('optimal_points') is not None and (r.get('evidence') or {}).get('calculation_supported')]
    rank = 1 + sum(value > points for value in supported)
    covered = len(row.get('optimal_ids') or [])
    # Required slots are supplied from the same admitted request configuration.
    expected = diagnostics['required_slot_count']
    provisional = qualification.get('conclusion_state') != 'current'
    qualifier = 'Provisional · ' if provisional else ''
    reason = ' '.join(qualification.get('limitations') or []) if provisional else ''
    if provisional and not reason:
        reason = 'Availability or source support remains qualified; this is not a freshly verified team verdict.'
    if compact:
        return (f'{qualifier}Week {week} optimal lineup · {points:.2f} projected points · {covered}/{expected} slots · '
                f'#{rank} of {len(supported)} comparable teams ({len(teams)} total).')
    return (f'{qualifier}Week {week} projected optimal lineup: {points:.2f} points; '
            f'{covered}/{expected} slots covered; #{rank} among {len(supported)} comparable teams; '
            f'{len(supported)} of {len(teams)} league teams comparable. '
            'This compares analytical lineups, not submitted Sleeper starters or overall franchise quality.'
            + (' ' + reason if reason else ''))

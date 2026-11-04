"""Presentation of already-admitted dimensions; no grading or preparation."""
MODEL_NOTE = ('DTOS shows lineup strength, depth, Market value and future outlook separately. '
              'It does not yet calculate a validated overall team grade.')


def weekly_comparison(card, week, *, compact=False):
    profile = getattr(getattr(card, 'competitive_window', None), 'production_profile', None) or {}
    league_id = getattr(card, 'league_id', None)
    comparison = profile.get('current_week_comparison') or {}
    if (not league_id or comparison.get('league_id') != league_id or comparison.get('week') != week
            or comparison.get('projection_generation') != profile.get('projection_generation')):
        return f'Week {week} projected lineup comparison needs compatible league, week and scoring evidence.'
    weekly = profile.get('weekly') or {}
    row = weekly.get(week) or weekly.get(str(week)) or {}
    coverage = row.get('coverage') or {}
    expected = len(comparison.get('required_slots') or [])
    covered = coverage.get('supported_slots', 0)
    population = f"{comparison['supported_count']} of {comparison['league_size']} league teams comparable"
    optimal = row.get('optimal') or {}
    points = optimal.get('projected_points')
    if row.get('available') is True and getattr(getattr(card, 'starting_lineup', None), 'score', None) is None:
        return f'Week {week} projected lineup comparison needs compatible league, week and scoring evidence.'
    if row.get('available') is not True or points is None:
        slots = ', '.join(map(str, coverage.get('unsupported_slots') or []))
        reason = (f'No supported eligible projections for required slots: {slots}.' if slots else
                  'Compatible projections cannot establish a complete legal starting lineup.')
        if compact:
            return f'Week {week} · {covered}/{expected} slots covered; {population}. {reason}'
        return f'Week {week} projected lineup comparison: {covered}/{expected} slots covered; {population}. {reason} Missing points are not zero.'
    qualification = ((row.get('reserve_capacity') or {}).get('qualification') or {})
    qualifier = 'Provisional · ' if qualification.get('conclusion_state') != 'current' else ''
    rank = card.starting_lineup.rank
    ranking = f'#{rank} among {comparison["supported_count"]} comparable teams' if rank is not None else 'Comparison rank not available'
    if compact:
        ranking = f'#{rank} of ' if rank is not None else ''
        return (f'{qualifier}Week {week} optimal lineup · {points:.2f} projected points · {covered}/{expected} slots · '
                f'{ranking}{comparison["supported_count"]} comparable teams ({comparison["league_size"]} total).')
    return (f'{qualifier}Week {week} projected optimal lineup: {points:.2f} points; '
            f'{covered}/{expected} slots covered; {ranking}; {population}. '
            'This compares analytical lineups, not submitted Sleeper starters or overall franchise quality.')

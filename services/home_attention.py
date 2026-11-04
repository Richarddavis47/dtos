"""Bounded read-only Attention selection; no scoring, optimization or storage."""
from src.core.intelligence.team_strength import compatible_profile


METHOD = 'home-attention-v1'


def attention_state(data, roster_id, projection, *, change_rows=(), change_coverage='unconnected'):
    """Read admitted current conditions. Change-family adapters remain explicit gaps."""
    league = str((data.get('league') or {}).get('league_id') or '')
    result = {'league_id': league, 'roster_id': roster_id, 'methodology': METHOD,
              'candidates': [], 'items': [], 'deduplicated': 0,
              'coverage': {'player_changes': 'unconnected', 'pick_changes': 'unconnected',
                           'trade_opportunities': 'unconnected', 'playoff_changes': 'unconnected',
                           'matchup_changes': 'unconnected', 'team_current_state': 'unavailable'}}
    if not any(str(t.get('roster_id')) == str(roster_id) for t in data.get('teams') or []):
        return result
    result['coverage']['pick_changes'] = change_coverage
    seen = set()
    for event in sorted(change_rows, key=lambda e: (e.get('reason') != 'EXACT_SLOT_ESTABLISHED', e['identity'])):
        if event.get('league_id') != league or str(event.get('current_owner')) != str(roster_id):
            continue
        if event['identity'] in seen:
            result['deduplicated'] += 1
            continue
        seen.add(event['identity'])
        result['candidates'].append(event)
        if event['qualifies']:
            result['items'].append(event)
    profile = compatible_profile(data, projection)
    if profile is None:
        result['items'] = result['items'][:4]
        return result
    team = (profile.get('teams') or {}).get(str(roster_id)) or (profile.get('teams') or {}).get(roster_id)
    if not team:
        result['items'] = result['items'][:4]
        return result
    result['coverage']['team_current_state'] = 'available'
    # Next-N already defines the accepted current/near-term window. Never scan
    # an invented horizon or extrapolate a future playoff opponent.
    weeks = ((team.get('horizons') or {}).get('next_n') or {}).get('weeks_requested') or [profile['current_week']]
    for week in weeks:
        row = (team.get('weekly') or {}).get(str(week)) or (team.get('weekly') or {}).get(week) or {}
        optimal = row.get('optimal') or {}
        missing = optimal.get('unsupported_slots') or []
        current = int(week) == int(profile['current_week'])
        byes = row.get('previous_optimal_players_on_known_bye') or []
        qualifies = optimal.get('available') is False and bool(missing) and (current or bool(byes))
        reason = ('CURRENT_REQUIRED_SLOT_EVIDENCE_GAP' if current else 'UPCOMING_BYE_AND_SLOT_EVIDENCE_GAP') if qualifies else (
            'SUPPORTED_LINEUP_NOT_AUTOMATIC_EDGE' if optimal.get('available') is True else 'MATERIALITY_NOT_ESTABLISHED')
        candidate = {'identity': f'{league}:{roster_id}:{profile["season"]}:{week}:lineup-coverage',
                     'family': 'team_lineup', 'kind': 'current_state', 'week': week,
                     'generation': profile['semantic_generation'], 'source_methodology': profile['methodology_version'],
                     'reason': reason, 'qualifies': qualifies,
                     'priority_reasons': ['DIRECT_ROSTER_RELEVANCE', 'CURRENT_WEEK' if current else 'PREPARED_NEXT_N', 'REVIEW_EVIDENCE'],
                     'unsupported_slots': list(missing), 'reference': f'team_strength/teams/{roster_id}/weekly/{week}',
                     'href': f'/teams/{roster_id}', 'confidence': 'Evidence coverage, not a forecast of performance.'}
        result['candidates'].append(candidate)
        if qualifies:
            candidate['title'] = f'Week {week}: lineup projection incomplete'
            candidate['why'] = 'Required slots lack supported projections. Review the lineup evidence; this is not a prediction of poor performance.'
            result['items'].append(candidate)
    # A single condition may affect multiple upcoming weeks: compose rather
    # than filling Home with one coverage warning for every week.
    changes = [item for item in result['items'] if item['kind'] == 'change_event']
    states = [item for item in result['items'] if item['kind'] == 'current_state']
    if len(states) > 1:
        primary = dict(states[0])
        primary['related_weeks'] = [item['week'] for item in states[1:]]
        result['deduplicated'] += len(states) - 1
        states = [primary]
    result['items'] = (states + changes)[:4]
    return result

"""Pregame Desk evidence adapter. Reuses prepared Matchups, never predicts odds."""
from decimal import Decimal
from services.matchup_season import season_week_view
from services.matchup_season import number

METHOD = 'matchup-desk-pregame-v2'


def _lineup_opportunity(side):
    optimal = side.get('optimal') or {}
    target = number(optimal.get('projected_points'))
    submitted = side['projection']
    if submitted is None or target is None or not optimal.get('available') or optimal.get('unsupported_slots'):
        return {'availability': 'unavailable', 'gain': None}
    gain = Decimal(str(target)) - Decimal(str(submitted))
    if gain < Decimal('-.005'):
        return {'availability': 'unavailable', 'gain': None, 'reason': 'INCONSISTENT_PREPARED_LINEUP_TOTALS'}
    # A sub-display precision difference is not a meaningful visible edge.
    visible = gain.quantize(Decimal('.01')) > 0
    return {'availability': 'available', 'gain': float(gain), 'opportunity': visible,
            'meaning': 'optimal among supported projections; Sleeper lineup unchanged'}


def _slot_edges(sides):
    """Compare configured submitted lineup slots, not asset value/roster size."""
    buckets = []
    for side in sides:
        grouped = {}
        for row in side['lineup']:
            grouped.setdefault(row['slot'], []).append(number(row['projection']))
        buckets.append(grouped)
    result = []
    for slot in sorted(set(buckets[0]) | set(buckets[1])):
        a, b = buckets[0].get(slot, []), buckets[1].get(slot, [])
        if not a or len(a) != len(b) or any(value is None for value in a + b):
            result.append({'slot': slot, 'availability': 'unavailable', 'edge_roster_id': None})
            continue
        totals = [sum((Decimal(str(v)) for v in values), Decimal(0)) for values in (a, b)]
        difference = totals[0] - totals[1]
        result.append({'slot': slot, 'availability': 'available',
                       'totals': {side['roster_id']: float(value) for side, value in zip(sides, totals)},
                       'gap': float(abs(difference)),
                       'edge_roster_id': None if difference == 0 else sides[0 if difference > 0 else 1]['roster_id'],
                       'meaning': 'submitted configured-slot projection; FLEX is not a positional rank'})
    return result


def pregame_desk(data, week, matchup_id, projection_service=None, *, prepared_view=None):
    view = prepared_view if prepared_view is not None else season_week_view(data, week, projection_service)
    key = str(matchup_id)
    sides = view['groups'].get(key) or []
    result = {'league_id': view['league_id'], 'season': view['season'], 'week': week,
              'identity': f"matchup/{view['league_id']}/{view['season']}/{week}/{key}",
              'matchup_id': key, 'methodology': METHOD, 'generation': view['generation'],
              'projection_generation': view['projection_generation'], 'availability': 'unavailable',
              'favorite': None, 'underdog': None, 'projected_margin': None,
              'teams': [], 'limitations': [],
              'slot_edges': [], 'angles': [], 'smack_talk': None, 'fact_trace': {},
              'history': {'availability': 'unavailable'},
              'bye_depth': {'availability': 'unavailable'},
              'standings': {'availability': 'unavailable'},
              'playoff': {'round_weeks': view['round_weeks'], 'opponents_locked': view['opponents_locked']}}
    if view['states'].get(key) != 'pregame' or len(sides) != 2:
        result['limitations'].append('PREGAME_PAIR_NOT_ESTABLISHED')
        return result
    identity = f"matchup/{view['league_id']}/{view['season']}/{week}/{key}"
    result['identity'] = identity
    result['fact_trace'][identity] = {'source': 'prepared selected-week Matchups',
        'generation': view['generation'], 'projection_generation': view['projection_generation'],
        'roster_ids': [side['roster_id'] for side in sides]}
    result['teams'] = [{'roster_id': side['roster_id'], 'name': side['team'],
                        'submitted_projection': side['projection'],
                        'supported_slots': side['supported_slots'], 'expected_slots': side['expected_slots'],
                        'projection_coverage': side['coverage'],
                        'lineup_opportunity': _lineup_opportunity(side),
                        'weekly_context': side.get('weekly_context'),
                        'optimal_projected_lineup': side.get('optimal')}
                       for side in sides]
    result['slot_edges'] = _slot_edges(sides)
    result['bye_depth'] = {'availability': 'available' if any(side.get('weekly_context') for side in sides) else 'unavailable',
                           'by_roster': {side['roster_id']: side.get('weekly_context') for side in sides}}
    for team in result['teams']:
        opportunity = team['lineup_opportunity']
        if opportunity.get('opportunity'):
            result['angles'].append({'kind': 'lineup_opportunity', 'reference': identity,
                'text': f"{team['name']} has {opportunity['gain']:.2f} projected points available from the prepared optimal lineup among supported players. The submitted lineup has not changed."})
    edges = [row for row in result['slot_edges'] if row.get('edge_roster_id') is not None]
    if edges:
        edge = sorted(edges, key=lambda row: (-row['gap'], row['slot']))[0]
        team = next(side for side in sides if side['roster_id'] == edge['edge_roster_id'])
        result['angles'].append({'kind': 'configured_slot_edge', 'reference': identity,
            'text': f"{team['team']} has a {edge['gap']:.2f}-point projected edge across submitted {edge['slot']} slots."})
    # Submitted versus optimal remain separately labeled. Unknown starters do
    # not become zero, and a known subtotal cannot establish a favorite.
    if any(side['projection'] is None for side in sides):
        result['availability'] = 'partial'
        result['limitations'].append('INCOMPLETE_SUBMITTED_PROJECTION')
        result['preview_line'] = 'The projected matchup edge is unavailable until both submitted lineups have complete evidence.'
        return result
    result['availability'] = 'available'
    difference = Decimal(str(sides[0]['projection'])) - Decimal(str(sides[1]['projection']))
    result['projected_margin'] = float(abs(difference))
    if difference == 0:
        result['preview_line'] = 'The submitted lineups are level on supported projections; neither side has a projected edge.'
    else:
        favorite, underdog = sides if difference > 0 else reversed(sides)
        result['favorite'], result['underdog'] = favorite['roster_id'], underdog['roster_id']
        result['preview_line'] = f"{favorite['team']} has the projected edge; {underdog['team']} has the gap to close. Projections are not a result."
        result['smack_talk'] = {'reference': identity,
            'text': f"{favorite['team']} leads on paper. {underdog['team']} can leave the congratulations unsent until the games are played."}
    return result


def live_desk(view, matchup_id):
    """One retained score snapshot supports current state, not live movement."""
    key = str(matchup_id)
    sides = view['groups'].get(key) or []
    result = {'mode': 'live', 'availability': 'unavailable',
              'identity': f"matchup/{view['league_id']}/{view['season']}/{view['week']}/{key}",
              'generation': view['generation'], 'methodology': 'matchup-desk-live-v1',
              'observed_at': view.get('observed_at'), 'provider_updated_at': None,
              'leader': None, 'margin': None, 'winner': None,
              'players_remaining': None, 'win_probability': None, 'movement': None,
              'limitations': ['PERIODIC_SCORE_SNAPSHOT', 'LIVE_CHANGE_HISTORY_NOT_ADMITTED'],
              'preview_line': 'Current score comparison unavailable.'}
    if view['states'].get(key) != 'in-game' or len(sides) != 2:
        return result
    scores = [number(side.get('actual')) for side in sides]
    if any(score is None for score in scores):
        result['availability'] = 'partial'
        return result
    difference = Decimal(str(scores[0])) - Decimal(str(scores[1]))
    result.update(availability='available', margin=float(abs(difference)))
    if difference == 0:
        result['preview_line'] = 'Recorded scores are level. This matchup is still in progress.'
    else:
        leader = sides[0 if difference > 0 else 1]
        result['leader'] = leader['roster_id']
        result['preview_line'] = f"{leader['team']} leads by {abs(difference):.2f} in the retained score snapshot. This is not a final result."
    return result


def matchup_desk(data, view, matchup_id):
    """Select mode from the same pinned prepared view as the core page."""
    state = view['states'].get(str(matchup_id))
    if state == 'pregame':
        result = pregame_desk(data, view['week'], matchup_id, prepared_view=view)
        result['mode'] = 'pregame'
        if view['period'] == 'future':
            # Future source-listed starters are not a submitted future lineup.
            for field in ('preview_line',):
                if field in result:
                    result[field] = result[field].replace('submitted', 'source-listed')
            for angle in result['angles']:
                angle['text'] = angle['text'].replace('submitted', 'source-listed')
        return result
    if state == 'in-game':
        return live_desk(view, matchup_id)
    if state == 'final':
        return postgame_desk(data, view['week'], matchup_id)
    return None


def postgame_desk(data, week, matchup_id):
    """Completed component-week recap uses the accepted Report temporal boundary."""
    from services.weekly_report import weekly_facts
    from services.weekly_report_stories import compose_report
    facts = weekly_facts(data, week)
    key = str(matchup_id)
    match = next((row for row in facts['matchups'] if row['matchup_id'] == key), None)
    result = {'identity': f"matchup/{facts['league_id']}/{facts['season']}/{week}/{key}",
              'league_id': facts['league_id'], 'season': facts['season'], 'week': week,
              'matchup_id': key, 'mode': 'postgame', 'availability': 'unavailable',
              'methodology': 'matchup-desk-postgame-v1', 'source_generation': facts['source_generation'],
              'recap': None, 'contributors': [], 'projected_upset': None,
              'lineup_decision': {'availability': 'unavailable',
                                  'reason': 'HISTORICAL_LEGAL_ALTERNATIVES_NOT_ADMITTED'}}
    if not match or not match['weekly_result_available']:
        return result
    selected = {**facts, 'matchups': [match]}
    result.update(availability='available', recap=compose_report(selected, lead_limit=1)['stories'][0],
                  weekly_winner=match['weekly_winner'], round_winner=match['round_winner'],
                  round_result_available=match['round_result_available'])
    for team in facts['franchises']:
        if team['roster_id'] not in match['roster_ids']:
            continue
        players = [row for row in team.get('submitted_players', []) if row['actual'] is not None and row['player_id'] != '0']
        if players:
            best = max(row['actual'] for row in players)
            result['contributors'].append({'roster_id': team['roster_id'], 'actual': best,
                'player_ids': sorted(row['player_id'] for row in players if row['actual'] == best),
                'meaning': 'highest recorded submitted-starter score; ties retained',
                'reference': team['identity']})
    return result

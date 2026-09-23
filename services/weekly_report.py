"""Canonical selected-week report facts. No narrative engine or durable storage."""
from decimal import Decimal
import hashlib
import json

from services.matchup_season import season_week_view
from services.weekly_report_transactions import transaction_facts


METHOD = 'weekly-report-facts-v2'


def weekly_facts(data, week, projection_service=None, *, cached_season=None):
    if type(week) is not int or not 1 <= week <= 18:
        raise ValueError('A supported fantasy week is required')
    view = season_week_view(data, week, projection_service, evidence_through_week=week)
    league, season = view['league_id'], view['season']
    source = f'season_matchups/{league}/{season}/weeks/{week}'
    valid = view['availability'] == 'available' and bool(view['generation'])
    states = set(view['states'].values())
    state = ('unavailable' if not valid else 'completed' if view['period'] == 'historical'
             else 'in_progress' if states & {'live', 'in-game', 'in_progress'} else 'preview')
    packet = {'league_id': league, 'season': season, 'week': week, 'state': state,
              'methodology': METHOD, 'source_generation': view['generation'],
              'observed_at': view['observed_at'], 'matchups': [], 'franchises': [],
              'round_weeks': view['round_weeks'], 'round_complete': view['round_complete'],
              'limitations': ['Standings movement, milestones and historical pregame comparisons are not admitted by this fact packet.'],
              'fact_trace': {}}
    if not valid:
        packet['limitations'].append('Compatible prepared league-week facts unavailable.')
    participation = {}
    for mid, sides in sorted(view['groups'].items()) if valid else []:
        pair = len(sides) == 2 and len({s['roster_id'] for s in sides}) == 2
        final = view['states'][mid] == 'final' and pair and all(s['actual'] is not None for s in sides)
        scores = {s['roster_id']: s['actual'] for s in sides}
        winner = None
        tie = False
        if final:
            a, b = sides
            tie = a['actual'] == b['actual']
            winner = None if tie else max(sides, key=lambda s: s['actual'])['roster_id']
        round_scores = {s['roster_id']: s.get('round_actual') for s in sides}
        round_final = bool(view['round_weeks']) and view['round_complete'] and pair and all(v is not None for v in round_scores.values())
        round_winner = None
        if round_final and len(set(round_scores.values())) > 1:
            round_winner = max(round_scores, key=round_scores.get)
        identity = f'{source}/matchup/{mid}'
        row = {'identity': identity, 'matchup_id': mid, 'state': view['states'][mid],
               'roster_ids': [s['roster_id'] for s in sides], 'scores': scores,
               'weekly_result_available': final, 'weekly_winner': winner, 'weekly_tie': tie,
               'round_result_available': round_final, 'round_winner': round_winner,
               'round_scores': round_scores, 'bracket': view['bracket_labels'].get(mid),
               'margin': float(abs(Decimal(str(sides[0]['actual'])) - Decimal(str(sides[1]['actual'])))) if final else None}
        packet['matchups'].append(row)
        packet['fact_trace'][identity] = {'reference': source, 'generation': view['generation'], 'matchup_id': mid}
        for side in sides:
            rid = side['roster_id']
            participation[rid] = {'matchup_reference': identity, 'actual': side['actual'],
                'projection': side['projection'], 'projection_coverage': side['coverage'],
                'submitted_players': [{k: p[k] for k in ('player_id', 'actual')} for p in side['lineup']],
                'status': 'weekly_tie' if final and tie else 'weekly_win' if final and rid == winner else 'weekly_loss' if final else view['states'][mid]}
    byes = {b['roster_id'] for b in view['byes']} if valid else set()
    identities = {int(t['roster_id']): t for t in data.get('teams') or []}
    for rid in set(participation) | byes:
        identities.setdefault(rid, {'roster_id': rid})
    for team in sorted(identities.values(), key=lambda t: int(t['roster_id'])):
        rid = int(team['roster_id'])
        identity = f'{source}/roster/{rid}'
        fact = {'identity': identity, 'roster_id': rid, 'display_name': team.get('team_name') or f'Franchise {rid}',
                'identity_meaning': 'franchise in admitted season; not historical GM attribution',
                **participation.get(rid, {'status': 'qualified_on_bye' if rid in byes else 'weekly_evidence_unavailable'})}
        packet['franchises'].append(fact)
        packet['fact_trace'][identity] = {'reference': source, 'generation': view['generation'], 'roster_id': rid}
    packet['transactions'] = transaction_facts(cached_season, league_id=league, season=season, week=week)
    if packet['transactions']['availability'] != 'available':
        packet['limitations'].append(packet['transactions']['reason'])
    for fact in packet['transactions']['facts']:
        packet['fact_trace'][fact['identity']] = {
            'reference': fact['identity'], 'generation': fact['source_generation']}
    # Generation describes semantic facts, not when they were reread.
    semantic = {k: v for k, v in packet.items() if k != 'observed_at'}
    packet['semantic_identity'] = hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()
    return packet

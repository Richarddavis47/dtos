"""Proposal-local roster simulation over a single accepted projection generation."""
from copy import deepcopy
from decimal import Decimal

from src.core.intelligence.team_strength import compatible_profile, canonical_rosters, prepare_team_strength


class PinnedProjectionReader:
    def __init__(self, service, snapshot):
        self.service = service
        self.pinned = snapshot

    def snapshot(self):
        return self.pinned

    def week_snapshot(self, week, *, generation_snapshot):
        return self.service.week_snapshot(week, generation_snapshot=self.pinned)


def _delta(before, after):
    if before is None or after is None:
        return None
    return float(Decimal(str(after)) - Decimal(str(before)))


def evaluate_horizon_impact(data, proposal, service):
    """No source refresh, ownership writes, profile publication or history saves.

    An incoming player is hypothetically active, not silently placed on IR/taxi.
    Roster capacity/executability remains a separate legality dimension.
    """
    snapshot = service.snapshot()
    prepared = compatible_profile(data, snapshot)
    if prepared is None:
        return {'availability': 'unavailable', 'reason_codes': ['COMPATIBLE_TEAM_STRENGTH_UNAVAILABLE']}
    rosters = {str(row['roster_id']): row for row in canonical_rosters(data)}
    active, partner = str(proposal.active_roster_id), str(proposal.partner_roster_id)
    if active == partner or active not in rosters or partner not in rosters:
        return {'availability': 'unavailable', 'reason_codes': ['INVALID_BILATERAL_ROSTERS']}
    sent = [a.asset_id.removeprefix('player:') for a in proposal.assets_sent if a.kind == 'player']
    received = [a.asset_id.removeprefix('player:') for a in proposal.assets_received if a.kind == 'player']
    if (len(set(sent + received)) != len(sent + received)
            or not set(sent).issubset(rosters[active]['players'])
            or not set(received).issubset(rosters[partner]['players'])):
        return {'availability': 'unavailable', 'reason_codes': ['PLAYER_OWNERSHIP_MISMATCH']}
    before = [deepcopy(rosters[rid]) for rid in (active, partner)]
    after = deepcopy(before)
    for row, outgoing, incoming in zip(after, (sent, received), (received, sent)):
        for field in ('players', 'starters', 'reserve', 'taxi'):
            row[field] = [pid for pid in row[field] if pid not in outgoing]
        row['players'].extend(incoming)
    # Reconstruct only retained supported bye references, not an inferred bye
    # from a missing/zero projection. No new global evidence read is required.
    byes = {pid: int(week) for team in prepared['teams'].values()
            for week, row in team['weekly'].items() for pid in row['known_bye_player_ids']}
    bye = ({'season': prepared['season'], 'reference': prepared['bye_evidence_reference'],
            'player_weeks': byes} if prepared.get('bye_evidence_reference') else None)
    reader = PinnedProjectionReader(service, snapshot)
    common = dict(league_id=prepared['league_id'], season=prepared['season'],
                  current_week=prepared['current_week'], next_n=prepared['next_n'],
                  roster_positions=data['league']['roster_positions'],
                  regular_season_weeks=prepared['calendar']['regular_season_weeks'],
                  playoff_rounds=prepared['playoff_round_weeks'],
                  calendar_reference=prepared['calendar_reference'], bye_evidence=bye)
    # Compatibility already proves the canonical pre-trade roster/generation.
    # Reuse its accepted lineups rather than solving identical assignments on
    # every proposal. Copy the derived view so callers cannot mutate the cache.
    pre = {'teams': {rid: deepcopy(prepared['teams'][rid]) for rid in (active, partner)}}
    post = prepare_team_strength(reader, rosters=after, **common)
    sides = {}
    for label, rid in (('active', active), ('partner', partner)):
        pre_team, post_team = pre['teams'][rid], post['teams'][rid]
        ordinal = 0 if label == 'active' else 1
        capacity = len([slot for slot in data['league']['roster_positions'] if slot.upper() not in ('IR', 'TAXI', 'RESERVE')])
        def active_count(row):
            return len(set(row['players']) - set(row['reserve']) - set(row['taxi']))
        sides[label] = {
            'roster_id': rid,
            'roster_capacity': {'configured_active_slots': capacity,
                'pre_active_players': active_count(before[ordinal]),
                'post_active_players': active_count(after[ordinal]),
                'additional_spots_to_resolve': max(0, active_count(after[ordinal]) - capacity),
                'meaning': 'configured active roster pressure; cut selection and temporary league exceptions not inferred'},
            'horizons': {name: {
                'pre_total': horizon['total'], 'post_total': post_team['horizons'][name]['total'],
                'delta': _delta(horizon['total'], post_team['horizons'][name]['total']),
                'weeks_requested': horizon['weeks_requested'],
                'pre_supported_weeks': horizon['weeks_supported'],
                'post_supported_weeks': post_team['horizons'][name]['weeks_supported'],
                'availability': 'complete' if horizon['availability'] == post_team['horizons'][name]['availability'] == 'complete' else 'partial_or_unavailable',
            } for name, horizon in pre_team['horizons'].items()},
            'weekly': {week: {'pre': row, 'post': post_team['weekly'][week],
                             'delta': _delta(row['optimal']['projected_points'], post_team['weekly'][week]['optimal']['projected_points'])}
                       for week, row in pre_team['weekly'].items()},
        }
        for horizon in sides[label]['horizons'].values():
            comparable = {week: sides[label]['weekly'][week]['delta']
                          for week in horizon['weeks_requested']
                          if week in sides[label]['weekly'] and sides[label]['weekly'][week]['delta'] is not None}
            horizon['comparable_weeks'] = list(comparable)
            horizon['supported_week_delta_subtotal'] = (
                float(sum((Decimal(str(delta)) for delta in comparable.values()), Decimal(0)))
                if comparable else None)
            horizon['subtotal_meaning'] = 'comparable supported weeks only; not a complete horizon projection'
    return {'availability': 'supported', 'sides': sides,
            'comparison': 'pre_trade_optimal_vs_post_trade_optimal',
            'projection_generation': prepared['projection_generation'],
            'team_strength_generation': prepared['semantic_generation'],
            'methodology': prepared['methodology_version'], 'league_id': prepared['league_id'],
            'hypothetical_only': True, 'canonical_mutations': 0, 'durable_writes': 0,
            'reason_codes': []}

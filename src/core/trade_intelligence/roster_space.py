"""Exact configured active-roster arithmetic, independent of trade quality."""

from src.core.projection_intelligence.sleeper_provider import freshness_state
from src.core.trade_intelligence.lineup import BENCH_SLOTS, FLEX_ELIGIBILITY


_SLEEPER_SLOTS = frozenset(BENCH_SLOTS | FLEX_ELIGIBILITY.keys() | {
    'QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DL', 'LB', 'DB', 'DE', 'DT', 'CB', 'S', 'IDP_FLEX',
})
_MISSING_MEMBERSHIP = 'DTOS could not confirm which players occupy active, IR, and taxi spots in this roster snapshot.'
_IR_OPTIONS = {
    'out': 'reserve_allow_out', 'suspended': 'reserve_allow_sus',
    'na': 'reserve_allow_na', 'dnr': 'reserve_allow_dnr', 'doubtful': 'reserve_allow_doubtful',
}
_IR_ALWAYS = {'ir', 'pup'}
_IR_INELIGIBLE = {'active', 'questionable', 'probable'}
_STATUS_ALIASES = {'o': 'out', 'd': 'doubtful', 'q': 'questionable', 'sus': 'suspended',
                   'injured reserve': 'ir', 'holdout': 'dnr'}


def active_player_ids(roster):
    return set(roster['players']) - set(roster['reserve']) - set(roster['taxi'])


def configured_active_slots(roster_positions):
    return sum(str(slot).upper() not in ('IR', 'TAXI', 'RESERVE') for slot in roster_positions)


def capacity_evidence(before, after, roster_positions):
    capacity = configured_active_slots(roster_positions)
    return {'configured_active_slots': capacity,
            'pre_active_players': len(active_player_ids(before)),
            'post_active_players': len(active_player_ids(after)),
            'additional_spots_to_resolve': max(0, len(active_player_ids(after)) - capacity),
            'meaning': 'configured active roster pressure; cut selection and temporary league exceptions not inferred'}


def _member_ids(values):
    if not isinstance(values, list):
        return None
    if any(type(value) not in (str, int) or not str(value).strip()
           or str(value) != str(value).strip() or value in ('0', 0) for value in values):
        return None
    ids = {str(value) for value in values}
    return ids if len(ids) == len(values) else None


def sleeper_membership_verified(roster):
    """Capture native completeness before normalization replaces missing fields."""
    if not all(key in roster for key in ('players', 'reserve', 'taxi')):
        return False
    players = _member_ids(roster['players'])
    reserve = _member_ids([] if roster['reserve'] is None else roster['reserve'])
    taxi = _member_ids([] if roster['taxi'] is None else roster['taxi'])
    if players is None or reserve is None or taxi is None:
        return False
    starters = roster.get('starters')
    if starters is not None and not isinstance(starters, list):
        return False
    return (reserve.isdisjoint(taxi) and (reserve | taxi) <= players
            and (reserve | taxi).isdisjoint(str(value) for value in starters or ()))


def _prepared_membership(team):
    rows = team.get('players')
    if (team.get('sleeper_membership_verified') is not True or not isinstance(rows, list)
            or any(not isinstance(row, dict) or row.get('roster_slot') not in
                   ('Starter', 'Bench', 'IR', 'Taxi') for row in rows)):
        return None
    ids = [row.get('id') for row in rows]
    if _member_ids(ids) is None:
        return None
    return {
        'players': ids,
        'reserve': [row['id'] for row in rows if row['roster_slot'] == 'IR'],
        'taxi': [row['id'] for row in rows if row['roster_slot'] == 'Taxi'],
    }


def pickup_roster_space(league, team):
    """Report one ordinary add against the admitted roster, independently of lineup fit."""
    slots = league.get('roster_positions')
    if (not isinstance(slots, list) or not slots
            or any(not isinstance(slot, str) or slot.upper() not in _SLEEPER_SLOTS for slot in slots)):
        return {'reason': 'DTOS could not confirm the league’s active roster limit.'}
    capacity = configured_active_slots(slots)
    if not capacity:
        return {'reason': 'DTOS could not confirm the league’s active roster limit.'}
    roster = _prepared_membership(team)
    if roster is None:
        return {'reason': _MISSING_MEMBERSHIP}
    return {'active': len(active_player_ids(roster)), 'capacity': capacity}


def _ir_designation(row, player_id, league):
    if not isinstance(row, dict) or 'injury_status' not in row or any(
        row.get(key) is not None and str(row[key]) != str(expected)
        for key, expected in (('player_id', player_id), ('id', player_id),
                              ('league_id', league.get('league_id')), ('season', league.get('season')))
    ):
        return None
    status = str(row.get('status') or '').strip().casefold()
    injury = str(row['injury_status'] or '').strip().casefold()
    status = _STATUS_ALIASES.get(status, status)
    injury = _STATUS_ALIASES.get(injury, injury)
    if not injury:
        return status if row['injury_status'] is None and status == 'active' else None
    # Sleeper's general Active/Inactive field can coexist with an injury tag.
    # A second, different designation does not establish which rule applies.
    generic = {'', 'active', 'inactive', 'practice squad'}
    if status not in generic and status != injury:
        return None
    if injury in _IR_INELIGIBLE and status != 'active':
        return None
    return injury


def pickup_ir_evidence(league, team, ownership, *, roster_checked_at, players_fetched_at):
    """Evaluate only actual Sleeper IR placements using fresh native evidence."""
    result = {'blockers': [], 'limits': []}
    membership = _prepared_membership(team)
    if membership is None:
        result['limits'].append(('could not confirm which players are in Sleeper IR slots', None))
        return result
    reserve = membership['reserve']
    if not reserve:
        return result
    settings = league.get('settings')
    capacity = settings.get('reserve_slots') if isinstance(settings, dict) else None
    if type(capacity) is not int or not len(reserve) <= capacity <= 10:
        result['limits'].append(('could not confirm Sleeper IR placement against the league’s IR limit', None))
        return result
    roster_freshness = freshness_state(roster_checked_at)
    player_freshness = freshness_state(players_fetched_at)
    if roster_freshness != 'Fresh':
        result['limits'].append((f'roster check is {roster_freshness.lower()}', None))
    if player_freshness != 'Fresh':
        result['limits'].append((f'player status check is {player_freshness.lower()}', None))
    if result['limits']:
        return result
    result['names'] = {str(row['id']): row.get('name') for row in team['players'] if row['roster_slot'] == 'IR'}
    for player_id in sorted(map(str, reserve)):
        owners = ownership.owners.get(player_id, [])
        if len(owners) != 1 or owners[0]['roster_slot'] != 'IR':
            result['limits'].append(('could not confirm Sleeper IR placement', player_id))
            continue
        designation = _ir_designation(ownership.players.get(player_id), player_id, league)
        if designation in _IR_ALWAYS:
            continue
        rule = _IR_OPTIONS.get(designation)
        if rule is not None:
            allowed = settings.get(rule)
            if type(allowed) not in (int, bool) or allowed not in (0, 1):
                result['limits'].append(('could not confirm the league’s IR rule', player_id))
                continue
            if allowed:
                continue
        elif designation not in _IR_INELIGIBLE:
            result['limits'].append(('could not confirm the Sleeper status', player_id))
            continue
        result['blockers'].append(player_id)
    return result

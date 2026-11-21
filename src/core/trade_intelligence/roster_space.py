"""Exact configured active-roster arithmetic, independent of trade quality."""

from src.core.trade_intelligence.lineup import BENCH_SLOTS, FLEX_ELIGIBILITY


_SLEEPER_SLOTS = frozenset(BENCH_SLOTS | FLEX_ELIGIBILITY.keys() | {
    'QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DL', 'LB', 'DB', 'DE', 'DT', 'CB', 'S', 'IDP_FLEX',
})
_MISSING_MEMBERSHIP = 'DTOS could not confirm which players occupy active, IR, and taxi spots in this roster snapshot.'


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


def pickup_roster_space(league, team):
    """Report one ordinary add against the admitted roster, independently of lineup fit."""
    slots = league.get('roster_positions')
    if (not isinstance(slots, list) or not slots
            or any(not isinstance(slot, str) or slot.upper() not in _SLEEPER_SLOTS for slot in slots)):
        return {'reason': 'DTOS could not confirm the league’s active roster limit.'}
    capacity = configured_active_slots(slots)
    if not capacity:
        return {'reason': 'DTOS could not confirm the league’s active roster limit.'}
    rows = team.get('players')
    if (team.get('sleeper_membership_verified') is not True or not isinstance(rows, list)
            or any(not isinstance(row, dict) or row.get('roster_slot') not in
                   ('Starter', 'Bench', 'IR', 'Taxi') for row in rows)):
        return {'reason': _MISSING_MEMBERSHIP}
    ids = [row.get('id') for row in rows]
    if _member_ids(ids) is None:
        return {'reason': _MISSING_MEMBERSHIP}
    roster = {
        'players': ids,
        'reserve': [row['id'] for row in rows if row['roster_slot'] == 'IR'],
        'taxi': [row['id'] for row in rows if row['roster_slot'] == 'Taxi'],
    }
    return {'active': len(active_player_ids(roster)), 'capacity': capacity}

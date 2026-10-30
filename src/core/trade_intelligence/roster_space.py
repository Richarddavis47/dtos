"""Exact configured active-roster arithmetic, independent of trade quality."""


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

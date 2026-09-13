"""Reference-only historical context for preparation-time decision assessment."""
from src.core.history_context.timestamps import canonical_utc_timestamp
from src.core.historical_franchise_state import HistoricalBoundary, BoundaryMode


def roster_context(states, league_id, roster_id, decision):
    exact = canonical_utc_timestamp(decision.get('occurred_at'))
    anchor = exact or canonical_utc_timestamp(decision.get('draft_start_at'))
    if not anchor:
        return None
    state = states.reconstruct(league_id, f'{league_id}:franchise:{roster_id}',
                              HistoricalBoundary(int(decision['season']), occurred_at=anchor,
                                                 mode=BoundaryMode.BEFORE))
    ownership = state.coverage.get('ownership')
    if state.availability.value == 'invalid' or not ownership:
        return None
    return {'reference': state.state_id, 'as_of': anchor, 'league_id': league_id,
            'owner_id': decision.get('owner_id'),
            'precision': 'decision_boundary' if exact else 'pre_draft_anchor_not_exact_selection',
            'ownership_availability': ownership.availability.value,
            'player_count': len(state.players), 'pick_count': len(state.draft_picks),
            'history_generation': state.history_generation,
            'reasons': tuple(ownership.reason_codes)}


def draft_alternatives(decision, draft_rows):
    """Require a sourced eligible pool, then remove earlier selections.

    Later selected players alone do not prove the eligible universe or its
    contemporaneous player identities. No NFL success is consulted.
    """
    pool = decision.get('eligible_pool') or {}
    known = canonical_utc_timestamp(pool.get('as_of'))
    boundary = canonical_utc_timestamp(decision.get('occurred_at') or decision.get('draft_start_at'))
    if not known or not boundary or known > boundary or not pool.get('reference'):
        return ()
    slot = decision.get('pick_number')
    if not isinstance(slot, (int, float)) or isinstance(slot, bool) or slot <= 0:
        return ()
    removed = {str(row['payload']['player_id']) for row in draft_rows
               if row['payload'].get('draft_id') == decision.get('draft_id')
               and isinstance(row['payload'].get('pick_no'), (int, float))
               and row['payload']['pick_no'] < slot and row['payload'].get('player_id')}
    return tuple({'asset_id': str(player), 'available_at_decision': True,
                  'reference': pool['reference'], 'known_at': known}
                 for player in sorted(set(map(str, pool.get('player_ids') or ())) - removed
                                      - {str(decision.get('player_id'))}))

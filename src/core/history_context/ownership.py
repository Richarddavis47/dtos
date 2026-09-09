"""Season-observed franchise/GM continuity, never invented takeover dates."""
from __future__ import annotations

from typing import Iterable, Mapping, Any


def reconcile_ownership(seasons: Iterable[Mapping[str, Any]]) -> dict:
    """Reconcile one provider-backed chain supplied by a background caller.

    Exact continuation links, not names, join roster slots. A season roster
    endpoint proves an observed owner for that season, not their exact joining
    date or every intra-season ownership change. No durable/private global copy.
    """
    inputs = list(seasons)
    leagues = {}
    for facts in inputs:
        league = facts.get('league') or {}
        league_id = str(league.get('league_id') or '')
        if not league_id or not str(league.get('season')).isdigit():
            raise ValueError('Ownership reconciliation requires source league and season identity.')
        if league_id in leagues:
            raise ValueError('Duplicate season league identity.')
        leagues[league_id] = facts
    observations, transitions, gaps = [], [], []
    for league_id, facts in sorted(leagues.items(), key=lambda item: (int(item[1]['league']['season']), item[0])):
        league = facts['league']
        previous_id = str(league.get('previous_league_id') or '')
        previous = leagues.get(previous_id)
        if previous and int(previous['league']['season']) >= int(league['season']):
            raise ValueError('Continuation must point to an earlier source season.')
        if previous_id and previous is None:
            gaps.append({'league_id': league_id, 'reason': 'previous_season_unavailable'})
        previous_rosters = {str(row['roster_id']): row for row in (previous or {}).get('rosters') or []}
        seen = set()
        for roster in facts.get('rosters') or []:
            roster_id = str(roster.get('roster_id') or '')
            if not roster_id or roster_id in seen:
                raise ValueError('Invalid or duplicate source roster identity.')
            seen.add(roster_id)
            owner = str(roster.get('owner_id') or '') or None
            prior = previous_rosters.get(roster_id)
            prior_owner = (str(prior.get('owner_id') or '') or None) if prior else None
            observations.append({'league_id': league_id, 'season': int(league['season']),
                'roster_id': roster_id, 'owner_id': owner,
                'co_owners': sorted(set(map(str, roster.get('co_owners') or ()))),
                'previous_season_league_id': previous_id or None,
                'franchise_continuity': 'source_continuation_roster_slot' if prior else 'unproven',
                'owner_continuity': ('same_observed_owner' if owner == prior_owner else 'changed_observed_owner')
                    if prior_owner and owner else 'unavailable',
                'exact_tenure_start': None})
            if prior_owner and owner and prior_owner != owner:
                transitions.append({'from_league_id': previous_id, 'to_league_id': league_id,
                    'roster_id': roster_id, 'from_owner_id': prior_owner, 'to_owner_id': owner,
                    'observed_season_interval': [int(previous['league']['season']), int(league['season'])],
                    'occurred_at': None, 'availability': 'season_observed_not_exact_timestamp'})
    return {'observations': observations, 'ownership_changes': transitions, 'gaps': gaps,
            'limitations': ['intra_season_owner_changes_not_reconstructible_from_final_rosters',
                           'exact_takeover_time_not_inferred'], 'provider_calls': 0, 'durable_writes': 0}

"""Usage derivation from shared production facts without another durable copy."""
from __future__ import annotations

import math

from .global_evidence import GlobalEvidenceStore
from .recent_workload import recent_workload


def player_usage(store: GlobalEvidenceStore, player_id: str, *, season: int, as_of: str,
                 through_week: int | None = None) -> dict:
    facts = store.read('production', f'sleeper:{player_id}', as_of=as_of, season=season, revision_conflicts=True)
    games = [{'game_id': fact['values'].get('game_id'), 'week': fact['week'],
              'targets': fact['values'].get('rec_tgt'), 'carries': fact['values'].get('rush_att'),
              'target_share': fact['values'].get('target_share'),
              'air_yards_share': fact['values'].get('air_yards_share'),
              'date': fact['effective_at'], 'team': fact['values'].get('team'),
              'knowledge_boundaries': [fact['knowledge_boundary']],
              'evidence_fingerprint': fact['fingerprint']} for fact in facts if through_week is None or (fact["week"] is not None and fact["week"] <= through_week)]

    # Revisions are resolved by the store; alternate source keys for one game
    # must not double-count an observation or conceal contradictory totals.
    unique = {}
    for fact, game in zip((f for f in facts if through_week is None or (f['week'] is not None and f['week'] <= through_week)), games):
        if fact.get('revision_conflict'):
            game['targets'] = game['carries'] = None
        key = game['game_id'] or game['evidence_fingerprint']
        if key not in unique:
            unique[key] = game
        else:
            prior = unique[key]
            for metric in ('targets', 'carries', 'target_share', 'air_yards_share'):
                if prior[metric] != game[metric]:
                    prior[metric] = None
    games = list(unique.values())

    def total(key):
        values = [game[key] for game in games]
        return sum(values) if values and all(type(value) in (int, float) and math.isfinite(value)
            and value >= 0 and value == int(value) for value in values) else None

    # A bounded local schedule read verifies byes; it does not acquire evidence.
    schedule = store.read('schedule', None, season=season, as_of=as_of)
    comparison = recent_workload(facts, season=season, as_of=as_of, through_week=through_week, schedule=schedule)

    return {'recent_workload': comparison, 'player_id': player_id, 'season': season, 'as_of': as_of,
            'completed_week_boundary': through_week,
            'availability': 'cached' if games else 'unavailable',
            'source': 'nflverse production', 'games': games,
            'targets': total('targets'), 'carries': total('carries'),
            'sample_count': len(games), 'denominator': 'available source game records',
            'snaps': None, 'routes': None, 'target_share': None, 'route_participation': None,
            'limitations': ['snap_route_source_not_connected', 'team_opportunity_denominator_unavailable'],
            'storage': 'derived_from_shared_production_no_duplicate_payload'}

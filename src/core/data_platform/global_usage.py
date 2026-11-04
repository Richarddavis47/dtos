"""Usage derivation from shared production facts without another durable copy."""
from __future__ import annotations

from .global_evidence import GlobalEvidenceStore


def player_usage(store: GlobalEvidenceStore, player_id: str, *, season: int, as_of: str) -> dict:
    facts = store.read('production', f'sleeper:{player_id}', as_of=as_of, season=season)
    games = [{'game_id': fact['values'].get('game_id'), 'week': fact['week'],
              'targets': fact['values'].get('rec_tgt'), 'carries': fact['values'].get('rush_att'),
              'target_share': fact['values'].get('target_share'),
              'air_yards_share': fact['values'].get('air_yards_share'),
              'evidence_fingerprint': fact['fingerprint']} for fact in facts]

    def total(key):
        values = [game[key] for game in games]
        return sum(values) if values and all(value is not None for value in values) else None

    return {'player_id': player_id, 'season': season, 'as_of': as_of,
            'availability': 'cached' if games else 'unavailable',
            'source': 'nflverse production', 'games': games,
            'targets': total('targets'), 'carries': total('carries'),
            'sample_count': len(games), 'denominator': 'available source game records',
            'snaps': None, 'routes': None, 'target_share': None, 'route_participation': None,
            'limitations': ['snap_route_source_not_connected', 'team_opportunity_denominator_unavailable'],
            'storage': 'derived_from_shared_production_no_duplicate_payload'}

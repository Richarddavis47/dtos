"""Bounded semantic change records, not explanations or recommendations."""
from hashlib import sha256
import json

from src.core.valuation.config import NORMALIZATION_VERSION
from src.core.valuation.ranking import RANK_METHODOLOGY
from src.core.valuation.intrinsic_profile import PROFILE_VERSION
from src.core.valuation.player_methodology import METHOD_VERSION
from src.core.valuation.consensus import MARKET_SELECTION_VERSION


METHODOLOGY = {
    'contract': 'batch3-player-market-semantics-1',
    'normalization': NORMALIZATION_VERSION, 'rank_scope': RANK_METHODOLOGY,
    'intrinsic_profile': PROFILE_VERSION, 'production': METHOD_VERSION,
    'provider_compatibility': MARKET_SELECTION_VERSION,
    'source_clocks': 'retrieval-source-publication-separated-1',
    'grading': 'roster-evidence-grading-v2', 'missing_data': 'missing-not-zero-1',
}
METHODOLOGY_ID = sha256(json.dumps(METHODOLOGY, sort_keys=True).encode()).hexdigest()


def snapshot(row, identity, league_id, providers=()):
    profile = row.get('intrinsic_evidence_profile') or {}
    projection = row.get('forward_production') or {}
    ranks = {name: {axis: {key: rank.get(key) for key in (
        'rank', 'scope', 'value_basis', 'position', 'universe_size', 'ranked_count')}
        for axis, rank in pair.items()} for name, pair in (row.get('ranks') or {}).items()}
    return json.loads(json.dumps({
        'methodology_id': METHODOLOGY_ID, 'league_id': str(league_id), 'asset_id': row['asset_id'],
        'normalized_market_index': ((row.get('valuation_layers') or {}).get('market_value') or {}).get('value'),
        'market_prices': {item['provider']: item.get('raw_value') for item in providers
            if item.get('provider') not in {'DTOS', 'DTOS Pick'}},
        'market_formats': {item['provider']: [item.get('format'), item.get('format_details')]
            for item in providers if item.get('provider') not in {'DTOS', 'DTOS Pick'}},
        'source_tiers': {item['provider']: item.get('provider_tier') for item in providers
            if item.get('provider') not in {'DTOS', 'DTOS Pick'}},
        'production_quality': profile.get('demonstrated_quality'),
        'production_sample': [profile.get('seasons'), profile.get('effective_games')],
        'usage': profile.get('latest_observed_usage'), 'usage_season': profile.get('usage_season'),
        'projection': projection.get('weekly_projected_points'),
        'projection_boundary': [projection.get('season'), projection.get('week'), projection.get('scoring_profile_id')],
        'status': identity.get('status'), 'role': [identity.get('nfl_team'), projection.get('depth_order')],
        'confidence': (row.get('scores') or {}).get('confidence'), 'ranks': ranks,
    }, sort_keys=True, allow_nan=False))


def compare(before, after):
    if not before:
        return ('SEMANTIC_BASELINE_ESTABLISHED',)
    if before.get('methodology_id') != after['methodology_id']:
        return ('METHODOLOGY_VERSION_CHANGED',)
    if any(before.get(key) != after[key] for key in ('league_id', 'asset_id')):
        return ('CONTEXT_BOUNDARY_CHANGED',)
    reasons = []
    for field, prefix in (('normalized_market_index', 'NORMALIZED_MARKET_INDEX'), ('production_quality', 'PRODUCTION_QUALITY'),
                          ('usage', 'USAGE'), ('projection', 'PROJECTION'), ('confidence', 'CONFIDENCE')):
        old, new = before.get(field), after.get(field)
        if old == new:
            continue
        boundary = 'projection_boundary' if field == 'projection' else 'usage_season' if field == 'usage' else None
        if boundary and before.get(boundary) != after.get(boundary):
            reasons.append(prefix + '_BOUNDARY_CHANGED')
        elif old is None or new is None:
            reasons.append(prefix + '_AVAILABILITY_CHANGED')
        else:
            reasons.append(prefix + ('_UP' if new > old else '_DOWN'))
    for provider in sorted(set(before.get('market_prices') or {}) | set(after.get('market_prices') or {})):
        old, new = (before.get('market_prices') or {}).get(provider), (after.get('market_prices') or {}).get(provider)
        if old != new and (before.get('market_formats') or {}).get(provider) == (after.get('market_formats') or {}).get(provider):
            reasons.append('MARKET_PRICE_AVAILABILITY_CHANGED' if old is None or new is None else 'MARKET_PRICE_UP' if new > old else 'MARKET_PRICE_DOWN')
    if before.get('market_formats') != after.get('market_formats'):
        reasons.append('MARKET_FORMAT_BOUNDARY_CHANGED')
    if before.get('source_tiers') != after.get('source_tiers'):
        reasons.append('SOURCE_TIER_CHANGED')
    for field, reason in (('production_sample', 'PRODUCTION_SAMPLE_UPDATED'), ('status', 'STATUS_CHANGED'), ('role', 'ROLE_CHANGED')):
        if before.get(field) != after.get(field):
            reasons.append(reason)
    if before.get('ranks') != after.get('ranks'):
        def scopes(ranks):
            return {name: {axis: {k: v for k, v in rank.items() if k != 'rank'}
                for axis, rank in pair.items()} for name, pair in ranks.items()}
        same_scope = scopes(before.get('ranks') or {}) == scopes(after.get('ranks') or {})
        own_changes = [reason for reason in reasons if not reason.startswith('NORMALIZED_MARKET_INDEX')]
        reasons.append('RANK_CHANGED_PEER_MOVEMENT' if same_scope and not own_changes else
                       'RANK_CHANGED' if same_scope else 'RANK_UNIVERSE_CHANGED')
    return tuple(dict.fromkeys(reasons))

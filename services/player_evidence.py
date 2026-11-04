"""Background materialization of compact Batch 2 production consumer evidence.

No provider calls, permanent writes or mutable global cache. Publish the returned
object as part of the caller's existing atomic intelligence generation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from itertools import groupby
from pathlib import Path
from statistics import mean
from typing import Any

from config import GLOBAL_EVIDENCE_FILE
from services.global_evidence import retained_global_evidence
from src.core.data_platform.global_evidence import utc
from src.core.data_platform.global_production import GlobalProduction
from src.core.player_value_projection.canonical_production import canonical_production_context

PRODUCTION_ADAPTER_VERSION = "canonical-production-v3"
REFERENCE_SCORING_SETTINGS = {"pass_yd": .04, "pass_td": 4, "pass_int": -2,
    "rush_yd": .1, "rush_td": 6, "rec": 1, "rec_yd": .1, "rec_td": 6, "fum_lost": -2}


def prepare_player_production(data: dict[str, Any], *, expected_league_id: str,
                              as_of: str, path: Path = GLOBAL_EVIDENCE_FILE) -> dict[str, Any]:
    league = data.get('league') or {}
    league_id = str(league.get('league_id') or '')
    if not league_id or league_id != str(expected_league_id):
        raise ValueError('Player preparation requires the selected canonical league.')
    season_text = str(league.get('season') or '')
    scoring = data.get('scoring_settings') or league.get('scoring_settings') or {}
    if not season_text.isdigit() or not scoring:
        return {'availability': 'unavailable', 'reason': 'season_or_scoring_unknown',
                'league_id': league_id, 'players': {}, 'generation': 'unavailable'}
    season = int(season_text)
    boundary = utc(as_of)
    fingerprint = hashlib.sha256(json.dumps(scoring, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    catalog = data.get('normalized_players') or data.get('players') or {}
    member_ids = (data.get('relevant_player_universe') or {}).get('member_ids')
    ids = sorted(set(str(value) for value in (member_ids if isinstance(member_ids, list) else catalog)))
    store = retained_global_evidence(path)
    result: dict[str, Any] = {'method_version': PRODUCTION_ADAPTER_VERSION, 'league_id': league_id,
        'season': season, 'scoring_fingerprint': fingerprint, 'players': {}, 'provider_calls': 0,
        'scoring_basis': 'selected_league_rules_applied_to_each_explicit_season',
        'availability': 'cached' if store else 'not_connected', 'fact_count': 0}
    from src.core.valuation.player_methodology import REFERENCE_SCORING
    result['reference_scoring'] = REFERENCE_SCORING
    digest = hashlib.sha256(json.dumps([PRODUCTION_ADAPTER_VERSION, season, fingerprint, ids], separators=(',', ':')).encode())
    reference_digest = hashlib.sha256(json.dumps([REFERENCE_SCORING, REFERENCE_SCORING_SETTINGS, season, ids], sort_keys=True, separators=(',', ':')).encode())

    def context(player_id):
        return {year: {'league_id': league_id, 'player_id': player_id, 'season': year,
                       'scoring_fingerprint': fingerprint,
                       'production': {'as_of': boundary, 'games': []}} for year in (season, season - 1)}

    if store is not None:
        stream = store.iter_dynasty_production(ids, current_season=season, as_of=boundary)
        for subject, facts in groupby(stream, key=lambda row: row['subject_id']):
            player_id = subject.removeprefix('sleeper:')
            periods = context(player_id)
            reference_seasons = {}
            count = 0
            for fact in facts:
                count += 1
                if count > 208:
                    raise ValueError('Player production exceeds the eight-season game bound.')
                digest.update(fact['fingerprint'].encode())
                reference_digest.update(fact['fingerprint'].encode())
                result['fact_count'] += 1
                if fact['values'].get('season_type') == 'REG':
                    reference_seasons.setdefault(fact['season'], []).append({
                        **GlobalProduction.score_game(fact['values'], REFERENCE_SCORING_SETTINGS),
                        'targets': fact['values'].get('rec_tgt'),
                        'carries': fact['values'].get('rush_att'),
                    })
                if fact['season'] not in periods:
                    continue
                periods[fact['season']]['production']['games'].append({
                    'game_id': fact['values'].get('game_id') or fact['source_record_id'],
                    'season': fact['season'], 'week': fact['week'],
                    'knowledge_boundary': fact['knowledge_boundary'],
                    'raw_stats': fact['values'],
                    **GlobalProduction.score_game(fact['values'], scoring),
                })
            profile = canonical_production_context(periods[season], periods[season - 1])
            # Score the same admitted facts under a fixed comparison reference.
            # No second SQL read, raw fact retention, or league scoring leakage.
            reference_periods = {year: {**periods[year], 'scoring_fingerprint': REFERENCE_SCORING,
                'production': {'as_of': boundary, 'games': [
                    {**game, **GlobalProduction.score_game(game['raw_stats'], REFERENCE_SCORING_SETTINGS)}
                    for game in periods[year]['production']['games']]}} for year in periods}
            result['players'][player_id] = {
                'production': asdict(profile),
                'reference_production': asdict(canonical_production_context(reference_periods[season], reference_periods[season - 1])),
                'current_sample_count': len(periods[season]['production']['games']),
                'previous_sample_count': len(periods[season - 1]['production']['games']),
                'reference_seasons': [_reference_summary(year, games)
                    for year, games in sorted(reference_seasons.items())],
            }
    # Empty players use one immutable-by-contract template in memory. No legacy
    # player dictionary can silently fill a missing canonical season.
    empty = context('unavailable')
    missing = {'production': asdict(canonical_production_context(empty[season], empty[season - 1])),
               'current_sample_count': 0, 'previous_sample_count': 0, 'reference_seasons': []}
    missing['reference_production'] = missing['production']
    for player_id in ids:
        result['players'].setdefault(player_id, missing)
    digest.update(result['availability'].encode())
    result['generation'] = digest.hexdigest()
    reference_digest.update(result['availability'].encode())
    result['reference_generation'] = reference_digest.hexdigest()
    return result


def _reference_summary(year: int, games: list[dict[str, Any]]) -> dict[str, Any]:
    """No partial averages, absent-year zero filling, or durable raw duplication."""
    if len(games) > 26:
        raise ValueError('Canonical season exceeds the game bound.')
    def average(field):
        values = [game.get(field) for game in games]
        return mean(values) if values and all(value is not None for value in values) else None
    targets, carries = average('targets'), average('carries')
    return {'season': year, 'games': len(games),
        'ppg': average('fantasy_points') if all(game['availability'] == 'calculated' for game in games) else None,
        'targets': targets, 'opportunities': targets + carries if targets is not None and carries is not None else None}

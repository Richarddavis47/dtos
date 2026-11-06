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

PRODUCTION_ADAPTER_VERSION = "canonical-production-v5-sleeper-actuals"
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
    completed_week = GlobalProduction.completed_week_boundary(data, season)
    store = retained_global_evidence(path)
    result: dict[str, Any] = {'method_version': PRODUCTION_ADAPTER_VERSION, 'league_id': league_id,
        'season': season, 'completed_week_boundary': completed_week, 'scoring_fingerprint': fingerprint, 'players': {}, 'provider_calls': 0,
        'scoring_basis': 'selected_league_rules_applied_to_each_explicit_season',
        'availability': 'cached' if store else 'not_connected', 'fact_count': 0}
    from src.core.valuation.player_methodology import REFERENCE_SCORING
    result['reference_scoring'] = REFERENCE_SCORING
    digest = hashlib.sha256(json.dumps([PRODUCTION_ADAPTER_VERSION, season, fingerprint, ids, completed_week], separators=(',', ':')).encode())
    reference_digest = hashlib.sha256(json.dumps([REFERENCE_SCORING, REFERENCE_SCORING_SETTINGS, season, ids, completed_week], sort_keys=True, separators=(',', ':')).encode())

    def context(player_id):
        return {year: {'league_id': league_id, 'player_id': player_id, 'season': year,
                       'scoring_fingerprint': fingerprint,
                       'production': {'as_of': boundary, 'games': []}} for year in (season, season - 1)}

    if store is not None:
        checks = {year: store.source_check(f'nflverse/production/{year}') for year in (season, season - 1)}
        checks = {year: receipt for year, receipt in checks.items()
                  if receipt and utc(receipt['checked_at']) <= boundary}
        result['source_checks'] = {str(year): receipt for year, receipt in checks.items()}
        digest.update(json.dumps(result['source_checks'], sort_keys=True, separators=(',', ':')).encode())
        stream = store.iter_dynasty_production(ids, current_season=season, as_of=boundary)
        for subject, facts in groupby(stream, key=lambda row: row['subject_id']):
            player_id = subject.removeprefix('sleeper:')
            periods = context(player_id)
            reference_seasons = {}
            for year, receipt in checks.items():
                if receipt['status'] != 'complete':
                    periods[season].setdefault('limitations', []).append(
                        ('Previous season: ' if year != season else '') + 'Latest canonical production source check is ' + receipt['status']
                        + '; retained admitted observations remain a qualified sample, not newly complete source coverage.')
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
                if (fact['season'] == season and completed_week is not None
                        and (fact['week'] is None or fact['week'] > completed_week)):
                    periods[season].setdefault('limitations', []).append(
                        'Current-week, later or unverified-week source records are excluded from completed-week production windows.')
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
                'non_sleeper_analysis': asdict(profile),
                'reference_production': asdict(canonical_production_context(reference_periods[season], reference_periods[season - 1])),
                'current_sample_count': len(periods[season]['production']['games']),
                'previous_sample_count': len(periods[season - 1]['production']['games']),
                'reference_seasons': [_reference_summary(year, games)
                    for year, games in sorted(reference_seasons.items())],
            }
    # Empty players use one immutable-by-contract template in memory. No legacy
    # player dictionary can silently fill a missing canonical season.
    empty = context('unavailable')
    missing = {'non_sleeper_analysis': asdict(canonical_production_context(empty[season], empty[season - 1])),
               'current_sample_count': 0, 'previous_sample_count': 0, 'reference_seasons': []}
    missing['reference_production'] = missing['non_sleeper_analysis']
    for player_id in ids:
        result['players'].setdefault(player_id, missing)
    digest.update(result['availability'].encode())
    result['generation'] = digest.hexdigest()
    reference_digest.update(result['availability'].encode())
    result['reference_generation'] = reference_digest.hexdigest()
    bind_retained_actuals(data, expected_league_id=league_id, production=result)
    return result


def bind_retained_actuals(data: dict, *, expected_league_id: str,
                         production: dict | None = None) -> dict | None:
    """One bounded binding before publication; never acquire or reconstruct scores.

    Fresh preparation supplies its unpublished analysis envelope. Both cache
    readers reuse the retained envelope, or create only a native-results shell
    when analysis was never prepared. Foreign analysis is not relabeled. The
    existing adapter owns native source compatibility and score interpretation.
    """
    from src.core.player_value_projection.sleeper_actuals import scoring_identity

    result = production if production is not None else data.get('canonical_player_production')
    if (not isinstance(result, dict) or not result) and not data.get('season_matchups'):
        return None
    league = data.get('league') or {}
    lid = str(league.get('league_id') or '')
    if not lid or lid != str(expected_league_id):
        raise ValueError('Actual-results binding requires the selected league.')
    scoring = data.get('scoring_settings') or league.get('scoring_settings') or {}
    if not isinstance(result, dict) or not result:
        result = {'league_id': lid, 'season': league.get('season'), 'players': {},
                  'scoring_fingerprint': scoring_identity(scoring)}
    if (str(result.get('league_id') or '') != lid
            or str(result.get('season')) != str(league.get('season'))
            or result.get('scoring_fingerprint') != scoring_identity(scoring)):
        return result
    attach_sleeper_actuals(data, result)
    if production is None:
        data['canonical_player_production'] = result
    return result


def attach_sleeper_actuals(data: dict, result: dict) -> None:
    """Existing atomic publication/restoration only; no provider IO or scoring."""
    from src.core.player_value_projection.sleeper_actuals import prepare_actual_results
    actuals = prepare_actual_results(data, expected_league_id=result['league_id'])
    result['sleeper_actuals'] = actuals
    result.setdefault('non_sleeper_analysis_availability', result.get('availability', 'unavailable'))
    result['availability'] = actuals['availability']
    result['scoring_basis'] = 'explicit_sleeper_league_matchup_results_not_reconstructed'
    result['generation'] = hashlib.sha256(json.dumps([
        result.get('reference_generation'), actuals['generation']], separators=(',', ':')).encode()).hexdigest()
    # Rebind only the actual-results disclosure in an existing cached Brain
    # report. Do not recompute prices, advice, confidence or historical grades.
    # This runs at publication/restoration, never in a page handler.
    report = data.get('valuation_intelligence') or {}
    assets = report.get('assets') or {}
    if assets:
        from src.core.player_value_projection.canonical_production import prepared_production_context
        from src.core.valuation_intelligence.engine import asset_market_input_revision, _semantic_digest
        for asset_id, asset in assets.items():
            if str(asset_id).startswith('player:') and isinstance(asset, dict):
                asset['canonical_production'] = asdict(prepared_production_context(result,
                    league_id=result['league_id'], player_id=str(asset_id).removeprefix('player:'), data=data))
        report['actual_results_binding'] = {'method': actuals['method_version'],
            'generation': actuals['generation'], 'source_generation': actuals['source_generation'],
            'qualification': 'Result disclosure rebound from retained Sleeper rows; other cached model assessments are not revalidated.'}
        manifest = report.setdefault('input_manifest', {})
        manifest['canonical_production'] = {'semantic_digest': _semantic_digest({'generation': result['generation']}),
            'record_count': 0, 'input_keys': ['canonical_player_production']}
        data['asset_market_semantic_revision'] = asset_market_input_revision(report.get('semantic_generation'), manifest)



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

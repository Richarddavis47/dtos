"""Lazy global evidence access; imports and page reads never initialize storage."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone

from config import GLOBAL_EVIDENCE_FILE
from src.core.data_platform.global_evidence import GlobalEvidenceStore, utc
from src.core.data_platform.global_production import GlobalProduction
from src.core.data_platform.global_usage import player_usage
from src.core.data_platform.global_schedule import team_schedule
from src.core.data_platform.evidence_availability import assess_availability


def retained_global_evidence(path: Path = GLOBAL_EVIDENCE_FILE) -> GlobalEvidenceStore | None:
    try:
        return GlobalEvidenceStore(path, readonly=True)
    except FileNotFoundError:
        return None


def global_evidence_health(path: Path = GLOBAL_EVIDENCE_FILE) -> dict[str, object]:
    store = retained_global_evidence(path)
    if store is None:
        return {"status": "not_connected", "families": {}, "bytes": 0}
    return {"status": "retained", "families": store.counts(), "bytes": path.stat().st_size}


def canonical_player_evidence(player_id: str, data: dict, *, expected_league_id: str,
                              path: Path = GLOBAL_EVIDENCE_FILE, as_of: str | None = None) -> dict:
    """Bounded local evidence read; no provider work or current-value fallback."""
    league = data.get('league') or {}
    league_id = str(league.get('league_id') or '')
    if not league_id or league_id != str(expected_league_id):
        raise ValueError('Canonical evidence requires the selected league context.')
    season_value = league.get('season')
    if not str(season_value).isdigit():
        return {'availability': 'unavailable', 'reason': 'league_season_unknown', 'league_id': league_id}
    season = int(season_value)
    scoring = data.get('scoring_settings') or league.get('scoring_settings') or {}
    if not scoring:
        return {'availability': 'unavailable', 'reason': 'league_scoring_unknown', 'league_id': league_id}
    store = retained_global_evidence(path)
    if store is None:
        return {'availability': 'not_connected', 'reason': 'global_analysis_not_retained', 'league_id': league_id,
                'production': _sleeper_production(data, player_id, as_of or datetime.now(timezone.utc).isoformat()), 'provider_calls': 0}
    boundary = as_of or datetime.now(timezone.utc).isoformat()
    production = GlobalProduction(store).league_scored(player_id, league_id=league_id,
        scoring_settings=scoring, as_of=boundary, season=season,
        through_week=GlobalProduction.completed_week_boundary(data, season) if as_of is None else None)
    receipt = store.source_check(f'nflverse/production/{season}')
    if receipt and utc(receipt['checked_at']) > utc(boundary):
        # A later refresh receipt cannot enter a point-in-time response. The
        # surviving facts still carry their own independently filtered boundary.
        receipt = None
    checked = (receipt or {}).get('checked_at') if (receipt or {}).get('status') == 'complete' else None
    if checked is None:
        checked = max((game['knowledge_boundary'] for game in production['games']), default=None)
    nfl_season = str((data.get('nfl_state') or {}).get('season') or '')
    completed_period = as_of is None and nfl_season.isdigit() and season < int(nfl_season)
    team = None
    team_basis = None
    if as_of is None and nfl_season == str(season):
        team = ((data.get('players') or {}).get(player_id) or {}).get('team')
        team_basis = 'current_sleeper_catalog'
    if not team:
        source_games = sorted(production['games'], key=lambda game: game.get('week') or 0)
        if source_games:
            team = source_games[-1]['raw_stats'].get('team')
            team_basis = 'last_available_game_in_selected_season'
    schedule = (team_schedule(store, team, season=season, as_of=boundary) if team else
                {'availability': 'unavailable', 'reason': 'team_identity_at_boundary_unavailable'})
    schedule['team_basis'] = team_basis
    assessment = assess_availability(connected=True, applicable=True,
        value_present=bool(production['games']), checked_at=checked,
        as_of=boundary, evidence_family='performance', completed_period=completed_period)
    actual = _sleeper_production(data, player_id, boundary)
    return {'league_id': league_id, 'player_id': player_id, 'season': season,
            'availability': actual['availability'], 'analysis_availability_detail': asdict(assessment),
            'production': actual,
            'non_sleeper_analysis': {**production, 'source': 'NFLverse statistics under selected scoring: analysis only, not Sleeper actual results'}, 'usage': player_usage(store, player_id, season=season, as_of=boundary,
                through_week=production.get('completed_week_boundary')),
            'schedule': schedule,
            'scoring_fingerprint': hashlib.sha256(json.dumps(scoring, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'analysis_source_check': receipt, 'provider_calls': 0,
            'limitations': ['historical_publication_time_not_inferred', 'no_current_or_prior_season_substitution']
                + (['latest_source_check_' + receipt['status']] if receipt and receipt['status'] != 'complete' else [])}


def _sleeper_production(data, player_id, as_of):
    from src.core.player_value_projection.canonical_production import prepared_production_context
    league_id = str((data.get('league') or {}).get('league_id') or '')
    snapshot = data.get('canonical_player_production') or {'league_id': league_id}
    context = prepared_production_context(snapshot, league_id=league_id, player_id=player_id, data=data)
    rows = [row for row in context.observations
            if row.get('retrieved_at') and utc(row['retrieved_at']) <= utc(as_of)]
    # A later admitted correction cannot be reconstructed as an earlier score.
    window = next((w for w in context.windows if w.label == 'Season Average'), None)
    current = bool(context.updated_at and utc(context.updated_at) <= utc(as_of))
    return {'source': 'Sleeper league matchup results', 'games': rows,
            'ppg': None, 'points_per_observation': window.fantasy_points if current and window else None,
            'denominator': 'completed-week score observations, not games played',
            'availability': context.status.value if current else 'unavailable'}

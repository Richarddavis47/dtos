"""Bounded, read-only source disclosures for one admitted player context.

Capability is not acquired coverage. No catalog scan, provider IO, preparation,
cache mutation or intelligence decision belongs in this reporting adapter.
"""
from __future__ import annotations

from src.core.player_value_projection.sleeper_actuals import score_number, scoring_identity
from src.core.projection_intelligence.service import projection_row_compatible
from src.core.projection_intelligence.sleeper_provider import freshness_state


def projection_evidence(player_id, data):
    league = data.get('league') or {}
    snapshot = data.get('projection_intelligence') or {}
    row = (snapshot.get('players') or {}).get(str(player_id)) or {}
    scoring = data.get('scoring_settings') or league.get('scoring_settings') or {}
    compatible = bool(league.get('league_id') and scoring
        and str(snapshot.get('league_id')) == str(league['league_id'])
        and str(snapshot.get('season')) == str(league.get('season'))
        and snapshot.get('week') == data.get('week')
        and snapshot.get('scoring_settings') == scoring
        and snapshot.get('projection_snapshot_id')
        and row.get('provider') == 'Sleeper'
        and projection_row_compatible(snapshot, str(player_id), row))
    value = score_number(row.get('canonical_projection')) if compatible else None
    mirror = row.get('weekly_projected_points')
    if compatible and mirror is not None and score_number(mirror) != value:
        value = None
    return dict(value=value, source='Sleeper', availability='cached' if value is not None else 'unavailable',
        league_id=str(league.get('league_id') or ''), season=snapshot.get('season') if compatible else None,
        week=snapshot.get('week') if compatible else None,
        snapshot_id=snapshot.get('projection_snapshot_id') if compatible else None,
        source_updated_at=row.get('source_timestamp') if compatible else None,
        prepared_at=snapshot.get('generated_at') if compatible else None,
        freshness=freshness_state(row.get('source_timestamp')) if compatible else 'Unavailable',
        reason=None if value is not None else row.get('availability_reason')
            or row.get('missing_projection_reason') if compatible else 'Compatible player-week projection not prepared.')


def player_source_health(player_id, data, configured, *, projection_service=None):
    """Report this player's retained sample, never an entire source's completeness."""
    from .provider_activation import provider_catalog
    from src.core.player_value_projection.canonical_production import prepared_production_context

    health = provider_catalog(configured)
    league = data.get('league') or {}
    lid = str(league.get('league_id') or '')
    scope = dict(league_id=lid, player_id=str(player_id), season=league.get('season'),
                 coverage='Selected player only; not complete league or season coverage.')
    projection = projection_evidence(player_id, data)
    refresh = {}
    snapshot = data.get('projection_intelligence') or {}
    if projection['snapshot_id'] and projection_service is not None:
        refresh = projection_service.refresh_evidence(snapshot)

    def disclosure(name, *, source, state, reason, count=0, stamp=None,
                   generation=None, freshness='unknown', failure=None, **extra):
        health[name] = dict(enabled=True, configured_capability=source, status=state,
            refresh_result='retained_after_failure' if failure else 'prepared_evidence' if count else 'not_prepared',
            last_refresh=None, next_refresh=None, records_retrieved=None,
            prepared_observations=count, observation_boundary=stamp,
            generation=generation, freshness=freshness, refresh_failure=failure or None,
            scope=scope, reason=reason, **extra)

    available = projection['value'] is not None
    disclosure('Projections', source='Sleeper', state='available' if available else 'unavailable',
        reason=('Sleeper projection available for this player and week.' if available else
                'No compatible scoring projection for this player and week; missing is not zero.'),
        count=int(available), stamp=projection['prepared_at'], generation=projection['snapshot_id'],
        freshness=projection['freshness'], failure=refresh,
        week=projection['week'], source_updated_at=projection['source_updated_at'])

    production = data.get('canonical_player_production') or {}
    compatible = bool(lid and str(production.get('league_id')) == lid
        and str(production.get('season')) == str(league.get('season'))
        and production.get('scoring_fingerprint') == scoring_identity(
            data.get('scoring_settings') or league.get('scoring_settings') or {}))
    context = prepared_production_context(production, league_id=lid, player_id=str(player_id), data=data) if compatible else None
    rows = context.observations if context else ()
    completed = [row for row in rows if row.get('state') == 'completed']
    known = sum(score_number(row.get('points')) is not None for row in completed)
    disclosure('Production', source='Sleeper league matchup results',
        state='partial' if known and known < len(completed) else 'available' if known else 'unavailable',
        reason=('Retained completed-week Sleeper scores are available; coverage is an observed sample.' if known else
                'No compatible completed-week Sleeper score is prepared for this player.'),
        count=known, stamp=context.updated_at if context else None,
        generation=context.source_generation if context else None,
        freshness='retained' if rows else 'unknown',
        completed_observations=len(completed), live_or_unconfirmed_observations=len(rows)-len(completed))

    analysis = ((production.get('players') or {}).get(str(player_id)) or {}).get('non_sleeper_analysis') or {} if compatible else {}
    windows = analysis.get('windows') or ()
    supported = [w for w in windows if w.get('observation_count', 0)
                 and any(score_number(w.get(k)) is not None for k in ('targets', 'carries', 'receptions'))]
    checks = production.get('source_checks') or {} if compatible else {}
    check = checks.get(str(league.get('season'))) or {}
    disclosure('Usage', source='Auxiliary football statistics; not fantasy results',
        state='available' if supported else 'unavailable',
        reason=('Retained targets, carries or receptions are available. Snap and route detail is not connected.' if supported else
                'No compatible targets, carries or receptions are prepared. Snap and route detail is not connected.'),
        count=max((w.get('observation_count', 0) for w in supported), default=0),
        stamp=analysis.get('updated_at'), generation=production.get('reference_generation') if compatible else None,
        freshness='retained' if supported else 'unknown',
        failure={'status':check['status'], 'checked_at':check.get('checked_at')} if check.get('status') not in {None, 'complete'} else None)
    return health

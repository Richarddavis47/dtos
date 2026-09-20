"""Bounded multi-horizon composition of published weekly legal lineups.

Preparation only: no provider calls, persistence or request-path refresh. Calendar
weeks must come from canonical league-season evidence, never a default playoff
template. No Market/FOIS scalar participates in this projection-only profile.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from decimal import Decimal
from typing import Any
from time import perf_counter

from src.core.trade_intelligence.lineup import optimal_legal_lineup

METHOD_VERSION = 'weekly-optimal-horizons-v2'


def _weeks(values: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    if any(type(week) is not int or not 1 <= week <= 18 for week in values):
        raise ValueError('Team strength requires canonical NFL week identities')
    if len(set(values)) != len(values):
        raise ValueError('Duplicate horizon week')
    return tuple(sorted(values))


def _sum(values: list[float]) -> float:
    return float(sum((Decimal(str(value)) for value in values), Decimal(0)))


def _horizon(requested: tuple[int, ...] | None, weekly: dict[int, dict]) -> dict:
    if requested is None:
        return {'availability': 'unavailable', 'weeks_requested': None,
                'weeks_supported': [], 'weeks_missing': None, 'total': None,
                'supported_week_subtotal': None, 'reason': 'LEAGUE_CALENDAR_UNAVAILABLE'}
    supported = [week for week in requested if weekly.get(week, {}).get('available')]
    missing = sorted(set(requested) - set(supported))
    subtotal = _sum([weekly[week]['optimal']['projected_points'] for week in supported]) if supported else None
    confidences = [value for week in supported for value in weekly[week].get('source_confidence', {}).values() if value is not None]
    return {'availability': 'complete' if requested and not missing else 'partial' if supported else 'unavailable',
            'weeks_requested': list(requested), 'weeks_supported': supported,
            'weeks_missing': missing, 'total': subtotal if requested and not missing else None,
            'supported_week_subtotal': subtotal,
            'supported_week_average': subtotal / len(supported) if supported else None,
            'average_denominator': len(supported),
            'source_confidence_range': [min(confidences), max(confidences)] if confidences else None,
            'confidence_meaning': 'source evidence support and disclosed week coverage; not an outcome probability',
            'weekly_optimal_totals': {str(week): weekly.get(week, {}).get('optimal', {}).get('projected_points') for week in requested},
            'reason': 'INCOMPLETE_WEEKLY_LINEUPS' if missing else 'NO_REMAINING_WEEKS' if not requested else None,
            'weighting': 'equal_week_sum',
            'projection_coverage': {str(week): weekly.get(week, {}).get('coverage') for week in requested}}


def prepare_team_strength(service: Any, *, league_id: str, season: int, current_week: int,
                          rosters: list[dict], roster_positions: list[str],
                          regular_season_weeks: list[int] | None,
                          playoff_rounds: list[list[int]] | None,
                          calendar_reference: str | None, next_n: int = 3,
                          bye_evidence: dict | None = None, timings: dict | None = None) -> dict:
    """Pin one publication, score each team/week once, then compose horizons.

    ``rosters`` contain canonical IDs in players/starters/reserve/taxi. Actual
    submitted starters are retained separately. A future optimal lineup is not
    a prediction that the manager submits those starters. ``playoff_rounds``
    retain all component weeks and do not imply qualification or an opponent.
    """
    if type(next_n) is not int or not 1 <= next_n <= 18:
        raise ValueError('Next-N horizon must be bounded to 1–18 weeks')
    _weeks([current_week])
    started = perf_counter()
    optimization_seconds = 0.0
    pinned = service.snapshot()
    if (not pinned or str(pinned.get('league_id')) != str(league_id)
            or pinned.get('season') != season or pinned.get('week') != current_week
            or not pinned.get('horizon_generation')):
        raise ValueError('Team strength requires a compatible published league/season/week horizon')
    if (regular_season_weeks is not None or playoff_rounds is not None) and not calendar_reference:
        raise ValueError('League calendar requires source provenance')
    byes = (bye_evidence or {}).get('player_weeks') or {}
    if bye_evidence is not None:
        if bye_evidence.get('season') != season or not bye_evidence.get('reference'):
            raise ValueError('NFL bye evidence requires season and provenance')
        for week in byes.values():
            _weeks([week])
    regular = _weeks(regular_season_weeks) if regular_season_weeks is not None else None
    rounds = [_weeks(weeks) for weeks in playoff_rounds] if playoff_rounds is not None else None
    playoff = _weeks([week for weeks in rounds for week in weeks]) if rounds is not None else None
    if regular is not None and playoff is not None and set(regular) & set(playoff):
        raise ValueError('Regular and playoff calendar weeks overlap')
    horizons = {
        'current_week': (current_week,),
        'next_n': tuple(range(current_week, min(18, current_week + next_n - 1) + 1)),
        'rest_of_regular_season': tuple(w for w in regular if w >= current_week) if regular is not None else None,
        'playoff_window': tuple(w for w in playoff if w >= current_week) if playoff is not None else None,
    }
    needed = sorted({week for weeks in horizons.values() if weeks is not None for week in weeks})
    snapshots = {week: service.week_snapshot(week, generation_snapshot=pinned) for week in needed}
    read_seconds = perf_counter() - started
    for week, snapshot in snapshots.items():
        if snapshot is not None and (snapshot.get('league_id') != pinned['league_id']
                or snapshot.get('season') != season or snapshot.get('week') != week
                or snapshot.get('horizon_generation') != pinned['horizon_generation']
                or snapshot.get('scoring_profile_id') != pinned.get('scoring_profile_id')):
            raise ValueError('Mixed projection generation or scope')
    teams = {}
    all_owned = set()
    for roster in rosters:
        roster_id = str(roster['roster_id'])
        if roster_id in teams or (roster.get('league_id') is not None and str(roster['league_id']) != str(league_id)):
            raise ValueError('Conflicting roster identity or league')
        ids = [str(pid) for pid in roster.get('players') or []]
        if len(set(ids)) != len(ids):
            raise ValueError('Duplicate roster player')
        if all_owned.intersection(ids):
            raise ValueError('Player ownership overlaps across franchises')
        all_owned.update(ids)
        excluded = {str(pid) for key in ('reserve', 'taxi') for pid in roster.get(key) or []}
        actual = tuple(str(pid) for pid in roster.get('starters') or [] if str(pid) != '0')
        if len(set(actual)) != len(actual) or not set(actual).issubset(ids):
            raise ValueError('Submitted starter identity is not a unique roster subset')
        weekly = {}
        for week, snapshot in snapshots.items():
            rows = (snapshot or {}).get('players') or {}
            for pid in ids:
                row = rows.get(pid)
                if row is not None and (row.get('week') != week or row.get('season') != season):
                    raise ValueError('Player projection boundary mismatch')
            pool = [{'id': pid, 'position': rows.get(pid, {}).get('position'),
                     'projected_points': rows.get(pid, {}).get('canonical_projection'),
                     'lineup_eligible': pid not in excluded,
                     'bye_week': byes.get(pid)}
                    for pid in ids]
            optimization_started = perf_counter()
            lineup = optimal_legal_lineup(pool, roster_positions, week=week)
            selected = {entry.asset_id for entry in lineup.entries}
            reserves = [player for player in pool if player['id'] not in selected]
            reserve_lineup = optimal_legal_lineup(reserves, roster_positions, week=week)
            optimization_seconds += perf_counter() - optimization_started
            weekly[week] = {'available': lineup.available, 'optimal': asdict(lineup),
                'projection_snapshot_id': (snapshot or {}).get('projection_snapshot_id'),
                'coverage': {'supported_slots': len(lineup.entries), 'unsupported_slots': list(lineup.unsupported_slots),
                             'missing_player_ids': list(lineup.missing_player_ids)},
                'reserve_capacity': {'supported_slots': len(reserve_lineup.entries),
                    'unsupported_slots': list(reserve_lineup.unsupported_slots),
                    'known_subtotal': reserve_lineup.known_starters_subtotal,
                    'meaning': 'supported non-optimal roster coverage, not a future injury forecast'},
                'source_confidence': {entry.asset_id: rows[entry.asset_id].get('projection_confidence') for entry in lineup.entries}}
            weekly[week]['known_bye_player_ids'] = sorted(pid for pid in ids if byes.get(pid) == week)
            covered = sorted(set(ids) & set(byes))
            weekly[week]['bye_evidence_availability'] = 'supported' if len(covered) == len(ids) and ids else 'partial' if covered else 'unavailable'
            weekly[week]['bye_evidence_covered_player_ids'] = covered
        previous = None
        for week, row in sorted(weekly.items()):
            starters = {entry['asset_id'] for entry in row['optimal']['entries']}
            row['optimal_entries_since_previous_week'] = sorted(starters - previous[0]) if previous else []
            row['previous_optimal_players_on_known_bye'] = sorted(previous[0] & set(row['known_bye_player_ids'])) if previous else []
            row['total_change_since_previous_week'] = (_sum([row['optimal']['projected_points'], -previous[1]])
                if previous and previous[1] is not None and row['optimal']['projected_points'] is not None else None)
            row['change_meaning'] = 'whole lineup change; not causally attributed only to NFL byes'
            previous = (starters, row['optimal']['projected_points'])
        teams[roster_id] = {'actual_submitted_starter_ids': list(actual), 'weekly': weekly,
                           'horizons': {name: _horizon(weeks, weekly) for name, weeks in horizons.items()}}
    # Full league ranks require comparable, complete horizons for every team.
    for name in horizons:
        complete = bool(teams) and all(team['horizons'][name]['availability'] == 'complete' for team in teams.values())
        totals = [team['horizons'][name]['total'] for team in teams.values()] if complete else []
        for team in teams.values():
            result = team['horizons'][name]
            result['league_rank'] = 1 + sum(value > result['total'] for value in totals) if complete else None
            result['rank_scope'] = f'league_optimal_projection_{name}'
            result['rank_availability'] = 'available' if complete else 'incomplete_league_horizon'
    result = {'methodology_version': METHOD_VERSION, 'league_id': str(league_id), 'season': season,
              'current_week': current_week, 'next_n': next_n, 'next_n_includes_current': True,
              'projection_generation': pinned['horizon_generation'], 'calendar_reference': calendar_reference,
              'scoring_profile_id': pinned.get('scoring_profile_id'),
              'bye_evidence_reference': (bye_evidence or {}).get('reference'),
              'playoff_round_weeks': [list(weeks) for weeks in rounds] if rounds is not None else None,
              'playoff_opponent': None, 'playoff_meaning': 'opponent_independent_window_not_qualification',
              'teams': teams, 'provider_calls': 0, 'durable_writes': 0}
    result['roster_reference'] = roster_reference(rosters, roster_positions)
    result['semantic_generation'] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if timings is not None:
        timings.update(projection_read_seconds=read_seconds, weekly_optimization_seconds=optimization_seconds,
                       aggregation_seconds=perf_counter() - started - read_seconds - optimization_seconds)
    return result


def roster_reference(rosters: list[dict], positions: list[str]) -> str:
    normalized = [{key: sorted(str(pid) for pid in row.get(key) or [])
                   for key in ('players', 'starters', 'reserve', 'taxi')}
                  | {'roster_id': str(row['roster_id'])} for row in rosters]
    return hashlib.sha256(json.dumps({'rosters': sorted(normalized, key=lambda row: row['roster_id']),
                                     'slots': positions}, sort_keys=True).encode()).hexdigest()


def canonical_rosters(data: dict) -> list[dict]:
    return [{'roster_id': team['roster_id'],
             'players': [str(player['id']) for player in team.get('players') or []],
             'starters': [str(player['id']) for player in team.get('players') or [] if player.get('roster_slot') == 'Starter'],
             'reserve': [str(player['id']) for player in team.get('players') or [] if player.get('roster_slot') == 'IR'],
             'taxi': [str(player['id']) for player in team.get('players') or [] if player.get('roster_slot') == 'Taxi']}
            for team in data.get('teams') or []]


def prepare_for_data(service: Any, data: dict, *, next_n: int = 3, bye_evidence: dict | None = None,
                     timings: dict | None = None) -> dict:
    """Existing background preparation handoff; replace the profile once complete."""
    from .season_calendar import season_calendar
    league = data.get('league') or {}
    scoring = data.get('scoring_settings') or league.get('scoring_settings') or {}
    if (service.snapshot() or {}).get('scoring_settings', {}) != scoring:
        raise ValueError('Team strength requires projections prepared for the current scoring settings')
    calendar = season_calendar(league)
    if calendar['current_week'] != data.get('week'):
        raise ValueError('Current fantasy week and projection preparation week disagree')
    if bye_evidence is None:
        from services.global_evidence import retained_global_evidence
        from src.core.data_platform.global_schedule import schedule_from_facts
        store = retained_global_evidence()
        boundary = (service.snapshot() or {}).get('generated_at')
        if store is not None and boundary:
            facts = store.read('schedule', None, season=int(league['season']), as_of=boundary)
            teams = {player.get('team') or player.get('nfl_team') for team in data.get('teams') or [] for player in team.get('players') or []}
            schedules = {team: schedule_from_facts(facts, team, season=int(league['season']), as_of=boundary) for team in teams if team}
            player_weeks = {str(player['id']): schedules.get(player.get('team') or player.get('nfl_team'), {}).get('bye_week')
                            for team in data.get('teams') or [] for player in team.get('players') or []}
            player_weeks = {pid: week for pid, week in player_weeks.items() if week is not None}
            if player_weeks:
                bye_evidence = {'season': int(league['season']), 'player_weeks': player_weeks,
                    'reference': hashlib.sha256(json.dumps(sorted(row['fingerprint'] for row in facts)).encode()).hexdigest()}
    existing = compatible_profile(data, service.snapshot())
    preparation_key = hashlib.sha256(json.dumps({
        'next_n': next_n, 'bye_evidence': bye_evidence,
    }, sort_keys=True).encode()).hexdigest()
    if existing is not None and existing.get('preparation_key') == preparation_key:
        return existing
    profile = prepare_team_strength(service, league_id=str(league['league_id']), season=int(league['season']),
        current_week=data['week'], rosters=canonical_rosters(data), roster_positions=league.get('roster_positions') or [],
        regular_season_weeks=calendar['regular_season_weeks'], playoff_rounds=calendar['playoff_rounds'],
        calendar_reference=calendar['reference'], next_n=next_n, bye_evidence=bye_evidence, timings=timings)
    profile['calendar'] = calendar
    profile['preparation_key'] = preparation_key
    profile['scoring_reference'] = hashlib.sha256(json.dumps(scoring, sort_keys=True).encode()).hexdigest()
    data['team_strength'] = profile
    return profile


def compatible_profile(data: dict, projection: dict | None) -> dict | None:
    """Read-only consumer admission: no lazy preparation or legacy fallback."""
    from .season_calendar import season_calendar
    profile = data.get('team_strength') or {}
    league = data.get('league') or {}
    if (not projection or profile.get('methodology_version') != METHOD_VERSION
            or profile.get('league_id') != str(league.get('league_id'))
            or str(profile.get('season')) != str(league.get('season'))
            or profile.get('projection_generation') != projection.get('horizon_generation')
            or profile.get('scoring_profile_id') != projection.get('scoring_profile_id')
            or str(projection.get('league_id')) != str(league.get('league_id'))
            or profile.get('scoring_reference') != hashlib.sha256(json.dumps(data.get('scoring_settings') or league.get('scoring_settings') or {}, sort_keys=True).encode()).hexdigest()
            or projection.get('scoring_settings', {}) != (data.get('scoring_settings') or league.get('scoring_settings') or {})
            or profile.get('current_week') != data.get('week')
            or profile.get('calendar_reference') != season_calendar(league)['reference']
            or profile.get('roster_reference') != roster_reference(canonical_rosters(data), league.get('roster_positions') or [])):
        return None
    return profile

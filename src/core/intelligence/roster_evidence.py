"""Generation-pinned roster evidence; no interchangeable player-value scalar."""
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from src.core.trade_intelligence.lineup import BENCH_SLOTS, FLEX_ELIGIBILITY, OptimalLineup, optimal_legal_lineup


@dataclass(frozen=True)
class RosterEvidence:
    league_id: str
    roster_id: int
    generation: str
    projection_generation: str | None
    projection_week: int | None
    actual_starter_ids: tuple[str, ...]
    actual_lineup_projection: float | None
    optimal_starter_ids: tuple[str, ...]
    optimal_lineup_projection: float | None
    projection_covered: int
    roster_count: int
    limitations: tuple[str, ...]
    positions: dict = field(default_factory=dict)


def _points(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if isfinite(value) else None


def build_roster_evidence(context: Any) -> RosterEvidence:
    """Only pinned canonical weekly projections enter the lineup calculation.

    Existing submitted starters remain untouched. Optimal means optimal among
    supported projections; missing players remain explicit coverage limitations.
    Market price, legacy player scores and historic points are never substitutes.
    """
    snapshot = context.projection_snapshot or {}
    if snapshot and str(snapshot.get('league_id') or '') != context.league_id:
        raise ValueError('Roster evidence projection league mismatch')
    roster_id = int(context.roster.get('roster_id') or 0)
    if roster_id != context.active_roster_id:
        raise ValueError('Roster evidence franchise mismatch')
    players = tuple(context.roster.get('players') or ())
    identifiers = tuple(str(row.get('id') or row.get('player_id') or '') for row in players)
    if any(not key for key in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError('Roster evidence requires unique canonical player identities')
    week = snapshot.get('week')
    data = getattr(context, 'cached_data', {})
    league = data.get('league') or {}
    scoring = data.get('scoring_settings') or league.get('scoring_settings') or {}
    incompatible = ((data.get('week') is not None and week != (data['week'] or 1))
                    or (league.get('season') is not None and str(snapshot.get('season')) != str(league['season']))
                    or (scoring and snapshot.get('scoring_settings') != scoring))
    if incompatible:
        week = None
    rows = snapshot.get('players') or {}
    from .roster_diagnostics import team_diagnostics, diagnostic_inputs, _bounded
    diagnostic = team_diagnostics(data, roster_id, snapshot,
        strategy=(getattr(context, 'user_preferences', {}) or {}).get('strategy')) if data.get('teams') else None
    supported_diagnostic = not diagnostic or diagnostic.get('evidence', {}).get('calculation_supported', False)
    excluded = set((diagnostic or {}).get('excluded_player_ids') or [])
    points = {
        key: _points(rows.get(key, {}).get('weekly_projected_points'))
        if supported_diagnostic and week is not None and rows.get(key, {}).get('week') == week else None
        for key in identifiers
    }
    actual = tuple(key for key, player in zip(identifiers, players)
                   if player.get('roster_slot') == 'Starter')
    actual_total = (round(sum(points[key] for key in actual), 2)
                    if actual and all(points[key] is not None for key in actual) else None)
    slots = tuple(str(slot).upper() for slot in context.settings.get('roster_positions') or ())
    slot_count = sum(slot not in BENCH_SLOTS for slot in slots)
    eligible = tuple((key, player) for key, player in zip(identifiers, players)
                     if key not in excluded and str(player.get('roster_slot') or '').upper() not in {'IR', 'TAXI', 'RESERVE'})
    bounded = _bounded(slots, diagnostic_inputs(data, snapshot)[4]) if diagnostic else True
    candidate = optimal_legal_lineup((
        {'id': key, 'position': player.get('position'), 'name': player.get('name'),
         'projected_points': points[key]} for key, player in eligible
    ), slots) if supported_diagnostic and bounded else OptimalLineup((), None, False, 'Detailed lineup diagnostics unavailable.')
    complete = candidate.available and len(candidate.entries) == slot_count
    limitations = []
    limitations.extend((diagnostic or {}).get('limitations') or [])
    if incompatible:
        limitations.append('Published projections do not match the current league week, season or scoring context; reevaluation awaits compatible Sleeper evidence.')
    if any(points[key] is None for key, _ in eligible):
        limitations.append('Optimal lineup is limited to players with supported projections; unknown players are not ranked as zero.')
    if actual_total is None:
        limitations.append('Actual starter projection coverage is incomplete.')
    if not complete:
        limitations.append('A complete optimal projected lineup is unavailable; missing players are not zero.')
    chosen = {entry.asset_id for entry in candidate.entries} if complete else set(actual)
    positions = {}
    for position in ('QB', 'RB', 'WR', 'TE'):
        room = [(key, player) for key, player in eligible if player.get('position') == position]
        starters = [key for key, _ in room if key in chosen]
        reserves = [key for key, _ in room if key not in chosen]
        known = [key for key in reserves if points[key] is not None]
        positions[position] = {
            'starting_players': starters, 'starting_count': len(starters),
            'starting_points': sum(points[key] for key in starters) if starters and all(points[key] is not None for key in starters) else None,
            'required_slots': slots.count(position),
            'eligible_flex_slots': sum(position in FLEX_ELIGIBILITY.get(slot, set()) for slot in slots),
            'reserve_ids': reserves, 'reserve_covered': len(known), 'reserve_expected': len(reserves),
            'best_reserve_points': max((points[key] for key in known), default=None),
            'projection_week': week, 'lineup_basis': 'optimal legal lineup' if complete else 'submitted starters',
            'availability': 'complete' if reserves and len(known) == len(reserves) else 'partial' if known else 'unavailable',
            'surplus': None,
        }
    if diagnostic:
        for position, row in positions.items():
            row['diagnostic'] = diagnostic['positions'].get(position)
    return RosterEvidence(context.league_id, roster_id, context.evidence_generation,
        snapshot.get('projection_snapshot_id') or snapshot.get('generation'), week,
        actual, actual_total,
        tuple(entry.asset_id for entry in candidate.entries) if complete else (),
        candidate.projected_points if complete else None,
        sum(value is not None for value in points.values()), len(players), tuple(limitations), positions)

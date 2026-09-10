"""Generation-pinned roster evidence; no interchangeable player-value scalar."""
from dataclasses import dataclass
from math import isfinite
from typing import Any

from src.core.trade_intelligence.lineup import BENCH_SLOTS, optimal_legal_lineup


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


def _points(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if isfinite(value) else None


def build_roster_evidence(context: Any) -> RosterEvidence:
    """Only pinned canonical weekly projections enter the lineup calculation.

    Existing submitted starters remain untouched. A missing projection for an
    eligible roster player prevents claiming a provably optimal complete lineup.
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
    rows = snapshot.get('players') or {}
    points = {
        key: _points(rows.get(key, {}).get('weekly_projected_points'))
        if week is not None and rows.get(key, {}).get('week') == week else None
        for key in identifiers
    }
    actual = tuple(key for key, player in zip(identifiers, players)
                   if player.get('roster_slot') == 'Starter')
    actual_total = (round(sum(points[key] for key in actual), 2)
                    if actual and all(points[key] is not None for key in actual) else None)
    slots = tuple(str(slot).upper() for slot in context.settings.get('roster_positions') or ())
    slot_count = sum(slot not in BENCH_SLOTS for slot in slots)
    eligible = tuple((key, player) for key, player in zip(identifiers, players)
                     if str(player.get('roster_slot') or '').upper() not in {'IR', 'TAXI', 'RESERVE'})
    candidate = optimal_legal_lineup((
        {'id': key, 'position': player.get('position'), 'name': player.get('name'),
         'projected_points': points[key]} for key, player in eligible
    ), slots)
    complete = (candidate.available and len(candidate.entries) == slot_count
                and all(points[key] is not None for key, _ in eligible))
    limitations = []
    if actual_total is None:
        limitations.append('Actual starter projection coverage is incomplete.')
    if not complete:
        limitations.append('A complete optimal projected lineup is unavailable; missing players are not zero.')
    return RosterEvidence(context.league_id, roster_id, context.evidence_generation,
        snapshot.get('projection_snapshot_id') or snapshot.get('generation'), week,
        actual, actual_total,
        tuple(entry.asset_id for entry in candidate.entries) if complete else (),
        candidate.projected_points if complete else None,
        sum(value is not None for value in points.values()), len(players), tuple(limitations))

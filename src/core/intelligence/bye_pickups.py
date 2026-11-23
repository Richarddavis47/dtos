"""Prepare small league-scoped free-agent results for proven bye shortages."""

from math import isfinite

from src.core.data_platform.normalization.identity import normalize_team
from src.core.intelligence.upcoming_byes import _availability_fit, _fit
from src.core.player_ownership import PlayerOwnershipIndex
from src.core.projection_intelligence.service import (
    UNAVAILABLE_PLAYER_STATUSES,
    player_availability,
    projection_row_compatible,
)
from src.core.projection_intelligence.sleeper_provider import freshness_state
from src.core.trade_intelligence.lineup import _eligible, eligible_positions


def _week_projections(service, pinned, week):
    snapshot = service.week_snapshot(week, generation_snapshot=pinned)
    if not snapshot or snapshot.get('week') != week or any(
        snapshot.get(key) != pinned.get(key)
        for key in ('league_id', 'season', 'horizon_generation', 'scoring_profile_id')
    ):
        return {}
    return snapshot


def _candidates(ownership, games, week, slots, projection, *, fresh):
    for pid, row in ownership.players.items():
        if not isinstance(row, dict) or ownership.resolve(pid)['state'] != 'FREE_AGENT':
            continue
        if any(row.get(key) is not None and str(row[key]) != pid for key in ('id', 'player_id')):
            continue
        team = normalize_team(row.get('team') or row.get('nfl_team') or '')
        if not team or not games.get(f'{week}:{team}'):
            continue
        status = player_availability(row, None)
        if status in UNAVAILABLE_PLAYER_STATUSES:
            continue
        positions = eligible_positions(row)
        eligible = frozenset(index for index, slot in enumerate(slots)
                             if any(_eligible(pos, slot) for pos in positions))
        if not eligible:
            continue
        evidence = (projection.get('players') or {}).get(pid) or {}
        points = evidence.get('canonical_projection')
        if (evidence.get('provider_id') != 'sleeper_projections'
                or not projection_row_compatible(projection, pid, evidence)
                or not isinstance(points, (int, float)) or isinstance(points, bool)
                or not isfinite(points)):
            points = None
        rank = (not (fresh and status == 'active'), points is None, -(points or 0), pid)
        yield rank, eligible, dict(
            player_id=pid, status=status, positions=list(positions), points=points,
            projection_freshness=evidence.get('source_freshness') if points is not None else None,
        )


def prepare_bye_pickups(data, service, pinned, schedule, outlook):
    """Compute once during admission. Retain up to six results per shortfall."""
    weeks = {}
    for record in outlook.values():
        for row in record['weeks']:
            if row['state'] == 'shortfall':
                weeks.setdefault(row['week'], []).append(row)
            else:
                row.pop('pickup_basis', None)
    if not weeks:
        return

    ownership = PlayerOwnershipIndex(data)
    games = (schedule or {}).get('games') or {}
    fresh = freshness_state(data.get('players_fetched_at')) == 'Fresh'
    for week, shortages in weeks.items():
        choices = []
        if ownership.complete and any(row['pickup_slots'] for row in shortages):
            projection = _week_projections(service, pinned, week)
            choices = sorted(_candidates(ownership, games, week, shortages[0]['slots'], projection, fresh=fresh),
                             key=lambda candidate: candidate[0])
        for row in shortages:
            matches = []
            basis = row.pop('pickup_basis')
            paths = row['pickup_slots']
            row['pickup_slots'] = [[index, gap] for index, gap, _ in paths]
            for _, eligible, candidate in choices:
                path = next((path for path in paths if path[0] in eligible), None)
                if path is None:
                    continue
                index, gap, chain = path
                after = dict(basis['fit'])
                after.update(chain)
                after[index] = candidate['player_id']
                prior = {pid: slot for slot, pid in basis['initial'].items()}
                states = basis['statuses'] | {candidate['player_id']: candidate['status']}
                dependencies = [[slot, pid, states.get(pid, 'unknown')] for slot, pid in sorted(after.items())
                                if states.get(pid) != 'active']
                moves = [[slot, pid, prior.get(pid)] for slot, pid in sorted(after.items())
                         if basis['initial'].get(slot) != pid]
                matches.append(dict(candidate, slot=row['slots'][index], gap=row['slots'][gap], gap_index=gap,
                                    dependencies=dependencies, moves=moves))
                if len(matches) == 6:
                    break
            if matches:
                del basis['initial']
            row['pickups'] = dict(ownership_generation=ownership.generation, candidates=matches,
                                  drop_basis=basis if matches else None)


def compare_pickup_drop(row, pickup, drop_id):
    """Run one bounded legal assignment against the prepared target-week roster."""
    basis = row['pickups']['drop_basis']
    pickup_id = pickup['player_id']
    slots = row['slots']
    before = dict(basis['fit'])
    before.update((slot, pid) for slot, pid, _ in pickup['moves'])
    preferred = {slot: pid for slot, pid in before.items() if pid != drop_id}
    playing = {pid: positions for pid, positions in basis['playing'].items() if pid != drop_id}
    playing[pickup_id] = pickup['positions']
    possible = playing | {pid: positions for pid, positions in basis['uncertain'].items() if pid != drop_id}
    statuses = basis['statuses'] | {pickup_id: pickup['status']}
    fresh = row['availability_freshness'] == 'Fresh'
    fit, _ = _availability_fit(slots, playing, preferred, statuses, fresh)
    incomplete = len(fit) < len(_fit(slots, possible, preferred))
    return dict(
        gap=pickup['gap_index'], original_filled=pickup['gap_index'] in fit,
        open_slots=[slot for slot in range(len(slots)) if slot not in fit],
        newly_open=[slot for slot in sorted(before) if slot != pickup['gap_index'] and slot not in fit],
        lost_pickup_plan_player=drop_id in before.values(),
        incomplete=incomplete, lineup=[
            (slot, pid, statuses.get(pid, 'unknown')) for slot, pid in sorted(fit.items())
        ],
    )

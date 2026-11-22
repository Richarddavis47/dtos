"""Prepare schedule-backed roster coverage without using fantasy points."""
from datetime import datetime, timezone

from src.core.data_platform.normalization.identity import normalize_team
from src.core.intelligence.lineup_review import METHOD, timestamp
from src.core.projection_intelligence.service import UNAVAILABLE_PLAYER_STATUSES, player_availability
from src.core.projection_intelligence.sleeper_provider import freshness_state
from src.core.trade_intelligence.lineup import BENCH_SLOTS, _eligible, eligible_positions


def _fit(slots, candidates, preferred=None):
    """Maximum legal slot coverage via augmenting paths, one player per slot."""
    preferred = preferred or {}
    options = [
        sorted((pid for pid, positions in candidates.items()
                if positions is None or any(_eligible(pos, slot) for pos in positions)),
               key=lambda pid: (pid != preferred.get(index), pid))
        for index, slot in enumerate(slots)
    ]
    # Keep verified starters in place where possible. An augmenting path
    # may move a starter if that is needed to fill another slot.
    occupied = {pid: index for index, pid in preferred.items() if pid in options[index]}

    def fill(index, visited):
        for pid in options[index]:
            if pid not in occupied:
                occupied[pid] = index
                return True
        for pid in options[index]:
            if pid not in visited:
                visited.add(pid)
                if fill(occupied[pid], visited):
                    occupied[pid] = index
                    return True
        return False

    for index in range(len(slots)):
        if index not in occupied.values():
            fill(index, set())
    return {index: pid for pid, index in occupied.items()}


def _eligible_roster(team, catalog, league):
    # Roster rows hold assignments; the native catalog supplies fantasy eligibility.
    people, statuses = {}, {}
    for player in team.get('players') or []:
        pid = str(player['id'])
        if player.get('roster_slot') in {'IR', 'Taxi', 'Reserve'}:
            continue
        row = catalog.get(pid) or {}
        if any(row.get(key) is not None and str(row[key]) != str(expected)
               for key, expected in (('player_id', pid), ('id', pid), ('season', league['season']),
                                     ('league_id', league['league_id']))):
            row = {}
        observed = player.get('team') or player.get('nfl_team')
        listed = row.get('team') or row.get('nfl_team')
        club = normalize_team(observed) if observed and listed else None
        if listed and club and normalize_team(listed) != club:
            club = None
        positions = eligible_positions(row)
        slot_known = player.get('roster_slot') in {'Starter', 'Bench'}
        people[pid] = (club, positions, slot_known)
        statuses[pid] = player_availability(row, None)
    return people, statuses


def _starting_slots(players, slots):
    """Read the submitted slot indexes, independent of roster iteration order."""
    starters = [None] * len(slots)
    seen = set()
    for player in players:
        pid = str(player['id'])
        if pid in seen:
            return None
        seen.add(pid)
        if player.get('roster_slot') != 'Starter':
            continue
        index = player.get('starter_index')
        recorded_slot = player.get('starter_slot')
        if (type(index) is not int or not 0 <= index < len(slots) or starters[index] is not None
                or (recorded_slot and str(recorded_slot).upper() != slots[index])):
            return None
        starters[index] = pid
    return starters


def _availability_fit(slots, playing, initial, statuses, fresh):
    """Extend a maximum fit in each better-supported tier before adding another."""
    tiers = [{}, {}, {}, {}]
    for pid, positions in playing.items():
        status = statuses.get(pid)
        if fresh and status == 'active':
            tier = 0
        elif fresh and status in {'questionable', 'doubtful'}:
            tier = 1
        elif status in UNAVAILABLE_PLAYER_STATUSES:
            tier = 3
        else:
            tier = 2
        tiers[tier][pid] = positions

    pool, fit = {}, {}
    for tier, candidates in enumerate(tiers):
        if not candidates:
            continue
        pool.update(candidates)
        # Preserve the better-supported match while admitting other eligible
        # starters in unchanged slots. Augmenting paths only add players.
        matched = set(fit.values())
        preferred = {i: pid for i, pid in initial.items() if i not in fit and pid not in matched}
        fit = _fit(slots, pool, preferred | fit)
        if len(fit) == len(slots):
            return fit, tier == 0
    return fit, False


def _pickup_slots(slots, playing, fit):
    """Map each reachable pickup slot to the vacancy it can help close."""
    paths = {}
    for gap in range(len(slots)):
        if gap in fit:
            continue
        queue = [gap]
        paths[gap] = (gap, [])
        for vacancy in queue:
            _, moves = paths[vacancy]
            for index, pid in sorted(fit.items()):
                if index not in paths and any(_eligible(pos, slots[vacancy]) for pos in playing[pid]):
                    paths[index] = (gap, [*moves, [vacancy, pid]])
                    queue.append(index)
    return [[index, gap, moves] for index, (gap, moves) in
            sorted(paths.items(), key=lambda pair: (pair[0] != pair[1][0], pair[0]))]


def _week(slots, people, games, byes, week, projection, *, starters, statuses=None, fresh=False):
    bye_ids = {pid for pid, (club, _, _) in people.items()
               if byes.get(pid) == week and club and f'{week}:{club}' not in games}
    playing = {pid: positions for pid, (club, positions, slot_known) in people.items()
               if pid not in bye_ids and positions and slot_known and games.get(f'{week}:{club}')}
    initial = {index: pid for index, pid in enumerate(starters or ()) if pid is not None}
    affected = [(index, pid) for index, pid in initial.items() if pid in bye_ids]
    statuses = statuses or {}
    moves, unfilled, dependencies, pickup_slots = [], [], [], []
    pickup_basis = None
    if affected:
        after, supported = _availability_fit(slots, playing, initial, statuses, fresh)
        if len(after) == len(slots):
            state = 'covered' if supported else 'conditional'
            prior = {pid: index for index, pid in initial.items()}
            moves = [[index, pid, prior.get(pid)] for index, pid in sorted(after.items())
                     if pid != initial.get(index)]
            dependencies = [[pid, statuses.get(pid) or 'unknown'] for _, pid in sorted(after.items())
                            if statuses.get(pid) != 'active']
        else:
            # Unconfirmed candidates can prevent a proof of shortfall, but
            # cannot establish positive cover.
            possible = {pid: positions or None for pid, (_, positions, _) in people.items()
                        if pid not in bye_ids}
            upper = _fit(slots, possible, initial)
            state = 'shortfall' if len(upper) < len(slots) else 'unknown'
            if state == 'shortfall':
                fit = upper
                if len(after) == len(upper):
                    fit = after
                    pickup_slots = _pickup_slots(slots, playing, fit)
                    pickup_basis = dict(fit=sorted(fit.items()), initial=initial,
                                        statuses=statuses, playing=playing,
                                        uncertain={pid: pos for pid, pos in possible.items() if pid not in playing},
                                        active_ids=sorted(people))
                unfilled = [slot for index, slot in enumerate(slots) if index not in fit]
    elif len(initial) == len(slots) and all(
        any(_eligible(position, slots[index]) for position in playing.get(pid, ()))
        for index, pid in initial.items()
    ):
        state = 'no_gap'
    else:
        state = 'unknown'
    return {
        'week': week, 'state': state, 'slots': slots,
        'bye_starters': [list(row) for row in affected],
        'unfilled': unfilled, 'moves': moves, 'availability_dependencies': dependencies,
        'pickup_slots': pickup_slots, 'pickup_basis': pickup_basis,
        'projection_ready': projection.get('available') is True,
    }


def _starter_positions(league):
    return [slot.upper() for slot in league.get('roster_positions') or [] if slot.upper() not in BENCH_SLOTS]


def read_upcoming_byes(profile, league, team, *, players_fetched_at=None):
    """Withhold legacy or changed assignments until preparation catches up."""
    record = (profile.get('upcoming_byes') or {}).get(str(team['roster_id']))
    if (not isinstance(record, dict) or not isinstance(record.get('weeks'), list)
            or 'availability_observed_at' not in record
            or record['availability_observed_at'] != players_fetched_at):
        return None
    slots = _starter_positions(league)
    players = team.get('players') or []
    if (len(players) > 100 or 'starting_slots' not in record
            or record['starting_slots'] != _starting_slots(players, slots)):
        return None

    # Retained coverage can age between preparation and a page read.
    now = datetime.now(timezone.utc)
    freshness = freshness_state(players_fetched_at, now=now)
    observed = timestamp(players_fetched_at)
    age = int((now - observed).total_seconds() // 60) if observed and freshness != 'Unavailable' else None
    return [
        dict(row, state='conditional' if row['state'] == 'covered' and freshness != 'Fresh' else row['state'],
             availability_freshness=freshness, availability_age_minutes=age)
        for row in record['weeks']
    ]


def prepare_upcoming_byes(data, calendar, schedule, bye_evidence, profile):
    """Bounded two-week summary derived during existing admitted preparation."""
    league = data['league']
    if league.get('status') != 'in_season' or league.get('sport') != 'nfl':
        return {}
    weeks = sorted(week for week in (
        (calendar.get('regular_season_weeks') or [])
        + [w for round_weeks in calendar.get('playoff_rounds') or [] for w in round_weeks]
    ) if week > data['week'])[:2]
    if not weeks:
        return {}
    slots = _starter_positions(league)
    if not 1 <= len(slots) <= 20:
        return {}
    games = (schedule.get('games') or {}) if (
        schedule and schedule.get('method') == METHOD and schedule.get('season') == profile['season']
    ) else {}
    byes = (bye_evidence or {}).get('player_weeks') or {}
    observed = data.get('players_fetched_at')
    fresh = freshness_state(observed) == 'Fresh'
    result = {}
    for team in data.get('teams') or []:
        if len(team.get('players') or []) > 100:
            continue
        rid = str(team['roster_id'])
        people, statuses = _eligible_roster(team, data.get('players') or {}, league)
        weekly = profile['teams'][rid]['weekly']
        starters = _starting_slots(team.get('players') or [], slots)
        result[rid] = {
            'starting_slots': starters, 'availability_observed_at': observed,
            'weeks': [_week(slots, people, games, byes, week, weekly.get(week) or {},
                            starters=starters, statuses=statuses, fresh=fresh)
                      for week in weeks],
        }
    return result

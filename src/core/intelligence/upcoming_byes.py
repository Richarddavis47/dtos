"""Prepare schedule-backed roster coverage without using fantasy points."""
from src.core.data_platform.normalization.identity import normalize_team
from src.core.intelligence.lineup_review import METHOD
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
    people = {}
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
    return people


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


def _week(slots, people, games, byes, week, projection, *, starters):
    bye_ids = {pid for pid, (club, _, _) in people.items()
               if byes.get(pid) == week and club and f'{week}:{club}' not in games}
    playing = {pid: positions for pid, (club, positions, slot_known) in people.items()
               if pid not in bye_ids and positions and slot_known and games.get(f'{week}:{club}')}
    initial = {index: pid for index, pid in enumerate(starters or ()) if pid is not None}
    affected = [(index, pid) for index, pid in initial.items() if pid in bye_ids]
    moves, unfilled = [], []
    if affected:
        after = _fit(slots, playing, initial)
        if len(after) == len(slots):
            state = 'covered'
            prior = {pid: index for index, pid in initial.items()}
            moves = [[index, pid, prior.get(pid)] for index, pid in sorted(after.items())
                     if pid != initial.get(index)]
        else:
            # Unconfirmed candidates can prevent a proof of shortfall, but
            # cannot establish positive cover.
            possible = {pid: positions or None for pid, (_, positions, _) in people.items()
                        if pid not in bye_ids}
            upper = _fit(slots, possible, initial)
            state = 'shortfall' if len(upper) < len(slots) else 'unknown'
            if state == 'shortfall':
                unfilled = [slot for index, slot in enumerate(slots) if index not in upper]
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
        'unfilled': unfilled, 'moves': moves,
        'projection_ready': projection.get('available') is True,
    }


def _starter_positions(league):
    return [slot.upper() for slot in league.get('roster_positions') or [] if slot.upper() not in BENCH_SLOTS]


def read_upcoming_byes(profile, league, team):
    """Withhold legacy or changed assignments until preparation catches up."""
    record = (profile.get('upcoming_byes') or {}).get(str(team['roster_id']))
    if not isinstance(record, dict) or not isinstance(record.get('weeks'), list):
        return None
    slots = _starter_positions(league)
    players = team.get('players') or []
    if len(players) <= 100 and 'starting_slots' in record and record['starting_slots'] == _starting_slots(players, slots):
        return record['weeks']
    return None


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
    result = {}
    for team in data.get('teams') or []:
        if len(team.get('players') or []) > 100:
            continue
        rid = str(team['roster_id'])
        people = _eligible_roster(team, data.get('players') or {}, league)
        weekly = profile['teams'][rid]['weekly']
        starters = _starting_slots(team.get('players') or [], slots)
        result[rid] = {
            'starting_slots': starters,
            'weeks': [_week(slots, people, games, byes, week, weekly.get(week) or {}, starters=starters)
                      for week in weeks],
        }
    return result

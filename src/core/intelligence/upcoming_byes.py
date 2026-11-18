"""Prepare schedule-backed roster coverage without using fantasy points."""
from collections import Counter

from src.core.data_platform.normalization.identity import normalize_team
from src.core.intelligence.lineup_review import METHOD
from src.core.trade_intelligence.lineup import BENCH_SLOTS, _eligible, eligible_positions


def _fit(slots, candidates, preferred=None):
    """Maximum legal slot coverage via augmenting paths, one player per slot."""
    preferred = preferred or {}
    options = [
        sorted((pid for pid, positions in candidates.items()
                if positions is None or any(_eligible(pos, slot) for pos in positions)),
               key=lambda pid: pid != preferred.get(index))
        for index, slot in enumerate(slots)
    ]
    occupied = {}

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
        fill(index, set())
    return {index: pid for pid, index in occupied.items()}


def _eligible_roster(team, catalog, league):
    # Roster rows hold assignments; the native catalog supplies fantasy eligibility.
    people = {}
    for player in sorted(team.get('players') or [], key=lambda p: p.get('roster_slot') != 'Starter'):
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


def _week(slots, people, games, byes, week, projection):
    bye_ids = {pid for pid, (club, _, _) in people.items()
               if byes.get(pid) == week and club and f'{week}:{club}' not in games}
    playing = {pid: positions for pid, (club, positions, slot_known) in people.items()
               if pid not in bye_ids and positions and slot_known and games.get(f'{week}:{club}')}
    # Unknown schedule, eligibility or assignment gets the benefit of the
    # doubt for the upper bound, and never establishes positive cover.
    possible = {pid: positions or None for pid, (_, positions, _) in people.items() if pid not in bye_ids}
    baseline = _fit(slots, {
        pid: positions for pid, (_, positions, slot_known) in people.items()
        if slot_known and positions and (pid in playing or pid in bye_ids)
    })
    after = _fit(slots, playing, baseline)
    upper = _fit(slots, possible, baseline)
    affected = [index for index, pid in baseline.items() if pid in bye_ids]
    if len(baseline) > len(upper):
        state = 'shortfall'
    elif affected and len(after) == len(slots):
        state = 'covered'
    elif affected or playing.keys() != possible.keys():
        state = 'unknown'
    else:
        state = 'no_gap'
    # Include the whole legal rearrangement, including displaced FLEX players.
    return {
        'week': week, 'state': state,
        'affected': [slots[index] for index in sorted(affected)],
        'byes': [baseline[index] for index in sorted(affected)],
        'unfilled': list((Counter(slots) - Counter(slots[index] for index in upper)).elements())
        if state == 'shortfall' else [],
        'moves': [[slots[index], pid] for index, pid in sorted(after.items())
                  if pid != baseline.get(index)] if state == 'covered' else [],
        'projection_ready': projection.get('available') is True,
    }


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
    slots = [slot.upper() for slot in (league.get('roster_positions') or []) if slot.upper() not in BENCH_SLOTS]
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
        result[rid] = [_week(slots, people, games, byes, week, weekly.get(week) or {}) for week in weeks]
    return result

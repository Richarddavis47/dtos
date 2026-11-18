"""One conditional replacement for a submitted starter, prepared off-request."""

from collections import deque
from datetime import datetime, timezone

from src.core.intelligence.lineup_review import (
    MAX_REVIEW_AGE, METHOD, manual_substitutions_supported, player_identity,
    player_kickoff, timestamp,
)
from src.core.projection_intelligence.service import (
    UNAVAILABLE_PLAYER_STATUSES, player_availability, projection_row_compatible,
)
from src.core.trade_intelligence.lineup import BENCH_SLOTS, _eligible, eligible_positions

UNCERTAIN = {"questionable", "doubtful"}
MAX_STARTERS = 20
MAX_ROSTER = 100


def _replacement_path(slots, starters, target, positions, available):
    """Find one vacancy-to-bench path using the established slot eligibility.

    Each occupied slot is visited once. Swapping along the path preserves all
    other submitted players and requires exactly one bench player.
    """
    starts = {pid: index for index, pid in enumerate(starters)}
    pending = deque([(target, [])])
    visited = {target}
    while pending:
        index, moves = pending.popleft()
        if starters[index] not in available:
            continue
        for pid in available:
            if pid == starters[target] or not any(
                _eligible(pos, slots[index]) for pos in positions.get(pid, ())
            ):
                continue
            path = moves + [(index, pid)]
            occupied = starts.get(pid)
            if occupied is None:
                return path
            if occupied not in visited:
                pending.append((occupied, path))
                visited.add(occupied)
    return None


def prepare_fallbacks(data, snapshot, schedule, profile, *, now=None):
    """Bounded current-week preparation. No provider, persistence or solver calls."""
    now = now or datetime.now(timezone.utc)
    league = data.get("league") or {}
    if league.get("sport") != "nfl" or league.get("status") != "in_season":
        return {}
    week = data.get("week")
    slots = [slot for slot in league.get("roster_positions") or [] if slot.upper() not in BENCH_SLOTS]
    if not slots or len(slots) > MAX_STARTERS:
        return {}
    catalog = data.get("players") or {}
    rows = snapshot.get("players") or {}
    plans = {}
    for team in data.get("teams") or []:
        roster = team.get("players") or []
        if len(roster) > MAX_ROSTER:
            continue
        owned = {str(p.get("id")): p for p in roster}
        statuses = {pid: player_availability(catalog.get(pid) or {}, rows.get(pid)) for pid in owned}
        submitted = sorted(
            (p for p in roster if p.get("roster_slot") == "Starter"),
            key=lambda p: p["starter_index"] if type(p.get("starter_index")) is int else -1,
        )
        target = next((p for p in submitted if statuses[str(p.get("id"))] in UNCERTAIN), None)
        if target is None:
            continue
        rid = str(team["roster_id"])
        pid = str(target["id"])
        starters = [str(p.get("id")) for p in submitted]
        result = plans[rid] = {"starter_id": pid, "submitted": starters, "slots": slots}
        if (len(owned) != len(roster)
                or [p.get("starter_index") for p in submitted] != list(range(len(slots)))):
            result["reason"] = "The submitted slots could not be verified."
            continue
        if not manual_substitutions_supported(league):
            result["reason"] = "This league’s manual lineup lock rules could not be verified."
            continue
        if not schedule or schedule.get("method") != METHOD or schedule.get("season") != snapshot.get("season"):
            result["reason"] = "Verified game times are not prepared."
            continue
        weekly = profile["teams"][rid]["weekly"].get(week) or {}
        byes = set(weekly.get("known_bye_player_ids") or [])
        _prepare_plan(data, snapshot, schedule, now, owned, statuses, byes, result)
    return plans


def _prepare_plan(data, snapshot, schedule, now, owned, statuses, byes, result):
    league = data["league"]
    slots, starters = result["slots"], result["submitted"]
    target = result["starter_id"]
    week = data["week"]
    rows, catalog = snapshot.get("players") or {}, data.get("players") or {}
    allowed = {
        pid for pid, player in owned.items()
        if player.get("roster_slot") in {"Starter", "Bench"}
        and pid not in byes and statuses[pid] not in UNAVAILABLE_PLAYER_STATUSES
    }
    positions = {
        pid: eligible_positions(catalog.get(pid) or {}) for pid in allowed
    }
    target_index = starters.index(target)
    if any(
        not any(_eligible(pos, slot) for pos in positions.get(pid, ()))
        for pid, slot in zip(starters, slots)
    ):
        result["reason"] = "The complete submitted lineup could not be verified."
        return

    def verified(pid):
        row = rows.get(pid) or {}
        status = str(row.get("availability") or "").casefold()
        return (
            projection_row_compatible(snapshot, pid, row)
            and status == statuses[pid]
            and (status in UNCERTAIN if pid == target else status == "active")
            and eligible_positions(row) == positions[pid]
            and player_identity(catalog, pid, season=league["season"], league_id=league["league_id"])["identity_available"]
        )

    kickoffs = {
        pid: player_kickoff(data, schedule, week, pid, rows.get(pid) or {}, owned[pid])
        for pid in sorted(allowed) if verified(pid)
    }
    unlocked = {pid: when for pid, when in kickoffs.items() if when and when > now}
    path = _replacement_path(slots, starters, target_index, positions, unlocked)
    if path is None:
        structurally_possible = _replacement_path(slots, starters, target_index, positions, sorted(allowed))
        if not structurally_possible and all(positions.values()):
            result["reason"] = "No eligible player or legal rearrangement covers this submitted slot."
        elif _replacement_path(slots, starters, target_index, positions, [pid for pid, when in kickoffs.items() if when]):
            result["reason"] = "A required player or slot has already locked. Check Sleeper before making changes."
        else:
            result["reason"] = "A complete fallback could not be verified from the available player evidence and game times."
        return
    # The vacancy path changes only these slots and always terminates at a bench player.
    result["moves"] = [[index, pid] for index, pid in path]


def read_fallback(data, side, snapshot, prepared, *, week, observed_at, retained_projection, now=None):
    """Recheck the recorded moves without searching for another assignment."""
    league = data.get("league") or {}
    if week != data.get("week") or league.get("sport") != "nfl" or league.get("status") != "in_season":
        return None
    plan = ((prepared or {}).get("lineup_fallbacks") or {}).get(str(side["roster_id"]))
    if plan is None:
        players = data.get("players") or {}
        if any(player_availability(players.get(p["player_id"]) or {}, None) in UNCERTAIN
               for p in side.get("lineup") or []):
            return {"reason": "A compatible fallback has not been prepared for the submitted lineup."}
        return None
    now = now or datetime.now(timezone.utc)
    unavailable = {"reason": "The submitted lineup no longer matches this fallback."}
    source = side.get("lineup") or []
    if ([p["player_id"] for p in source] != plan["submitted"]
            or [p["slot"] for p in source] != plan["slots"]):
        return unavailable
    times = [timestamp(observed_at), timestamp((snapshot or {}).get("generated_at"))]
    if retained_projection or any(stamp is None or not 0 <= (now - stamp).total_seconds()
                                  < MAX_REVIEW_AGE.total_seconds() for stamp in times):
        return {"reason": "The roster or projection check needs a fresh update before a fallback can be confirmed."}
    if not manual_substitutions_supported(league):
        return {"reason": "This league’s manual lineup lock rules could not be verified."}
    if not plan.get("moves"):
        return {"reason": plan["reason"]}

    catalog, rows = data.get("players") or {}, snapshot.get("players") or {}
    team = next((t for t in data.get("teams") or [] if t["roster_id"] == side["roster_id"]), {})
    owned = {str(p["id"]): p for p in team.get("players") or []}
    schedule = prepared.get("lineup_review_schedule") or {}
    if schedule.get("method") != METHOD or schedule.get("season") != snapshot.get("season"):
        return {"reason": "Verified game times are not prepared."}
    line = [(source[index], incoming) for index, incoming in plan["moves"]]
    target = plan["starter_id"]
    involved = {incoming for _, incoming in line} | {before["player_id"] for before, _ in line}
    started = {p["player_id"] for section in ("lineup", "bench") for p in side.get(section) or []
               if p.get("actual") not in (None, 0)}
    identities, kickoffs = {}, {}
    for pid in involved:
        row = rows.get(pid) or {}
        player = catalog.get(pid) or {}
        roster_player = owned.get(pid) or {}
        expected_status = UNCERTAIN if pid == target else {"active"}
        expected_slot = "Starter" if pid in plan["submitted"] else "Bench"
        identity = player_identity(catalog, pid, season=league["season"], league_id=league["league_id"])
        if (roster_player.get("roster_slot") != expected_slot
                or not identity["identity_available"]
                or not projection_row_compatible(snapshot, pid, row)
                or row.get("availability") not in expected_status
                or player_availability(player, row) != row.get("availability")
                or eligible_positions(player) != eligible_positions(row)):
            return {"reason": "Player identity, eligibility or availability no longer supports this fallback."}
        when = player_kickoff(data, schedule, week, pid, row, roster_player)
        if when is None:
            return {"reason": "A required player’s kickoff could not be verified."}
        if when <= now or pid in started:
            return {"reason": "A required player or slot may already be locked. Check Sleeper before making changes."}
        kickoffs[pid] = when
        identities[pid] = identity["name"]
    if any(not any(_eligible(pos, before["slot"]) for pos in eligible_positions(catalog[pid]))
           for before, pid in line):
        return unavailable

    kickoff = min(kickoffs.values())
    return {
        "starter": identities[target],
        "moves": [(before["slot"], identities[pid], identities[before["player_id"]])
                  for before, pid in line],
        "kickoff_deadline": kickoff.isoformat(),
        "earlier_game": kickoff < kickoffs[target],
        "valid_until": min(kickoff, *(stamp + MAX_REVIEW_AGE for stamp in times)).isoformat(),
        "verified_at": now.isoformat(),
    }

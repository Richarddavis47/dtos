"""Pure, conservative review of an already prepared optimal lineup.

No solver, provider, storage or mutation. An unconstrained optimum is only an
actionable suggestion when its exact assignment can still be submitted. We do
not search for a second, lock-constrained optimum on an ordinary page read.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.core.trade_intelligence.lineup import _eligible, eligible_positions

MAX_REVIEW_AGE = timedelta(minutes=15)
METHOD = "prepared-lineup-review-v1"


def timestamp(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def player_identity(players, pid, *, season=None, league_id=None):
    """Exact canonical key only; never resolve a different athlete by name."""
    row = players.get(str(pid)) or {}
    if not isinstance(row, dict):
        row = {}
    conflict = any(
        row.get(key) is not None and str(row[key]) != str(pid)
        for key in ("id", "player_id")
    )
    conflict = conflict or any(
        expected is not None
        and row.get(key) is not None
        and str(row[key]) != str(expected)
        for key, expected in (("season", season), ("league_id", league_id))
    )
    name = None if conflict else row.get("full_name") or row.get("name")
    return {
        "name": str(name) if name else "Player name not verified",
        "position": row.get("position") if not conflict else None,
        "identity_available": bool(name) and not conflict,
    }


def prepared_games(facts, season):
    """Compact game facts reused by background preparation's existing read."""
    games = {}
    for fact in facts:
        if (
            fact.get("family") != "schedule"
            or fact.get("season") != season
            or not fact.get("fingerprint")
            or fact.get("provider") != "nflverse"
        ):
            continue
        values = fact.get("values") or {}
        week, kickoff = fact.get("week"), timestamp(values.get("kickoff"))
        if type(week) is not int or not 1 <= week <= 18 or kickoff is None:
            continue
        for team in (values.get("home_team"), values.get("away_team")):
            if not team:
                continue
            key = f"{week}:{team}"
            entry = {"kickoff": kickoff.isoformat(), "reference": fact["fingerprint"]}
            # Multiple conflicting games cannot establish a player's lock.
            games[key] = entry if key not in games or games[key] == entry else None
    return {"method": METHOD, "season": season, "games": games}


def review_lineup(
    data,
    side,
    snapshot,
    prepared,
    *,
    week,
    observed_at,
    now=None,
    retained_projection=False,
):
    now = now or datetime.now(timezone.utc)
    result = {
        "method": METHOD,
        "week": week,
        "state": "unavailable",
        "gain": None,
        "changes": [],
        "actionable": False,
        "reason": "A complete comparable submitted and optimal lineup is not prepared.",
    }
    optimal = side.get("optimal") or {}
    target, baseline = optimal.get("projected_points"), side.get("projection")
    if (
        not optimal.get("available")
        or optimal.get("unsupported_slots")
        or target is None
        or baseline is None
    ):
        return result
    gain = Decimal(str(target)) - Decimal(str(baseline))
    if gain < Decimal("-.005"):
        result["reason"] = (
            "The prepared lineup totals do not agree. Retry after the league refresh."
        )
        return result
    result.update(
        gain=float(gain),
        state="no_improvement",
        reason="No higher-projected lineup is established by this prepared comparison.",
    )
    if gain.quantize(Decimal(".01")) <= 0:
        return result
    result.update(
        state="informational",
        reason="This is an optimal-lineup comparison; current substitution eligibility could not be verified.",
    )
    if retained_projection:
        result["reason"] = (
            "The latest projection refresh did not complete. Last-valid comparisons remain visible, but no current substitution is confirmed."
        )
        return result
    league = data.get("league") or {}
    settings = league.get("settings") or {}
    if (
        week != data.get("week")
        or league.get("sport") != "nfl"
        or league.get("status") != "in_season"
    ):
        result["reason"] = (
            "This comparison is not for the current active week; it is not a lineup-change alert."
        )
        return result
    if (
        settings.get("best_ball") != 0
        or settings.get("sub_start_time_eligibility") not in (None, 0)
        or settings.get("sub_lock_if_starter_active") not in (None, 0)
    ):
        result["reason"] = (
            "Manual substitution rules for this league are not verified here. Review the lineup in Sleeper."
        )
        return result
    roster_time, projection_time = (
        timestamp(observed_at),
        timestamp((snapshot or {}).get("generated_at")),
    )
    if any(
        stamp is None or not timedelta(0) <= now - stamp <= MAX_REVIEW_AGE
        for stamp in (roster_time, projection_time)
    ):
        result["reason"] = (
            "The roster or projection check is older than 15 minutes or its time is unknown. Refresh the league before making changes."
        )
        return result
    schedule = (prepared or {}).get("lineup_review_schedule") or {}
    if schedule.get("method") != METHOD or schedule.get("season") != (
        snapshot or {}
    ).get("season"):
        result["reason"] = (
            "Verified game times are not prepared, so DTOS cannot confirm that these changes are still possible."
        )
        return result
    source = side.get("lineup") or []
    entries = optimal.get("entries") or []
    if len(source) != len(entries) or Counter(p["slot"] for p in source) != Counter(
        e["slot"] for e in entries
    ):
        return result
    team = next(
        (t for t in data.get("teams") or [] if t.get("roster_id") == side["roster_id"]),
        {},
    )
    owned = {
        str(p["id"]): p for p in team.get("players") or [] if p.get("id") is not None
    }
    if not owned:
        return result
    source_ids = [p["player_id"] for p in source if p["player_id"] != "0"]
    selected = [str(e["asset_id"]) for e in entries]
    if (
        len(set(source_ids)) != len(source_ids)
        or len(set(selected)) != len(selected)
        or not set(source_ids + selected).issubset(owned)
        or set(source_ids)
        != {pid for pid, p in owned.items() if p.get("roster_slot") == "Starter"}
    ):
        result["reason"] = (
            "The submitted lineup and current roster do not agree. Refresh the league before making changes."
        )
        return result
    if any(
        owned[p["player_id"]].get("starter_index") is not None
        and owned[p["player_id"]]["starter_index"] != index
        for index, p in enumerate(source)
        if p["player_id"] != "0"
    ):
        result["reason"] = (
            "The source starter assignments changed. Refresh the league before making changes."
        )
        return result
    rows = (snapshot or {}).get("players") or {}
    from src.core.projection_intelligence.service import projection_row_compatible

    def kickoff(pid):
        row = rows.get(pid) or {}
        team_id = (
            row.get("nfl_team")
            or row.get("team")
            or owned[pid].get("nfl_team")
            or owned[pid].get("team")
        )
        game = (schedule.get("games") or {}).get(f"{week}:{team_id}") or {}
        return timestamp(game.get("kickoff")) if game.get("reference") else None

    # Keep equivalent slots stable, especially an already locked starter in a
    # repeated RB/WR/FLEX slot. This changes no selected athlete or total.
    remaining = list(entries)
    assigned = [None] * len(source)
    for index, player in enumerate(source):
        same = next(
            (
                e
                for e in remaining
                if str(e["asset_id"]) == player["player_id"]
                and e["slot"] == player["slot"]
            ),
            None,
        )
        if same:
            assigned[index] = same
            remaining.remove(same)
    for index, player in enumerate(source):
        if assigned[index] is None:
            match = next((e for e in remaining if e["slot"] == player["slot"]), None)
            if match is None:
                return result
            assigned[index] = match
            remaining.remove(match)
    changes, deadlines = (
        [],
        [roster_time + MAX_REVIEW_AGE, projection_time + MAX_REVIEW_AGE],
    )
    for before, after in zip(source, assigned):
        pid = str(after["asset_id"])
        row = rows.get(pid) or {}
        if (
            not projection_row_compatible(snapshot, pid, row)
            or row.get("canonical_projection") != after.get("projected_points")
            or not any(
                _eligible(pos, before["slot"]) for pos in eligible_positions(row)
            )
            or owned[pid].get("roster_slot") in {"IR", "Taxi"}
            or str(row.get("availability") or "").casefold()
            not in {"active", "questionable", "doubtful"}
            or pid in (side.get("weekly_context") or {}).get("known_bye_player_ids", [])
        ):
            return result
        if before["player_id"] == pid:
            continue
        # Both the incoming player and any displaced/moved starter must still
        # be unlocked. No assumptions about bye/Out players unlocking slots.
        involved = [pid] + ([before["player_id"]] if before["player_id"] != "0" else [])
        for involved_pid in involved:
            when = kickoff(involved_pid)
            if when is None or when <= now:
                result["reason"] = (
                    "At least one proposed change involves a started game or an unverified game time. "
                    "This optimum is informational; no currently legal substitution is confirmed."
                )
                return result
            deadlines.append(when)
        identities = [
            player_identity(
                data.get("players") or {},
                x,
                season=league.get("season"),
                league_id=league.get("league_id"),
            )
            for x in involved
        ]
        if not all(identity["identity_available"] for identity in identities):
            result["reason"] = (
                "A player name cannot be verified for these changes. Review the source lineup; no substitution is recommended here."
            )
            return result
        changes.append(
            {
                "slot": before["slot"],
                "in": identities[0],
                "out": identities[1]
                if len(identities) > 1
                else {"name": "Empty slot", "position": None},
            }
        )
    if not changes:
        return result
    result.update(
        state="actionable",
        actionable=True,
        changes=changes,
        observed_at=observed_at,
        projection_observed_at=snapshot["generated_at"],
        valid_until=min(deadlines).isoformat(),
        verified_at=now.isoformat(),
        reason="These moves fit your starting slots and precede their recorded kickoffs. Check Sleeper before submitting.",
    )
    return result

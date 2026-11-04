"""Bounded statistical standings from retained Sleeper facts, never final seeds.

Equal opportunities and equal tie counts admit a wins-descending comparison
(losses then necessarily descend inversely). PF is the only secondary key.
Different tie counts/unequal opportunities lack a verified record comparator.
No PA, roster identity or source list order is a competitive tiebreak.
"""

from decimal import Decimal

from services.matchup_season import METHOD, number
from src.core.history_context.playoffs import playoff_facts
from src.core.intelligence.season_calendar import season_calendar
from src.ui.intelligence_presentation import league_is_preseason

PROVENANCE = "Standings ranked by Sleeper record, then Points For."


def record_fields(settings):
    """Do not turn absent/invalid source records into an undefeated record."""
    return {
        key: value if type(value := settings.get(key)) is int and value >= 0 else None
        for key in ("wins", "losses", "ties")
    }


def standings_order(data):
    teams = list(data.get("teams") or [])
    result = {
        "teams": teams,
        "ranks": {},
        "placements": {},
        "reason": None,
        "provenance": PROVENANCE,
    }
    if not teams or league_is_preseason(data):
        result["reason"] = (
            "Ranking unavailable: current-season results have not started."
        )
        return result
    count = ((data.get("league") or {}).get("settings") or {}).get("num_teams")
    identities = [t.get("roster_id") for t in teams]
    if (
        any(type(rid) is not int or rid <= 0 for rid in identities)
        or len(set(identities)) != len(teams)
        or (type(count) is int and count != len(teams))
    ):
        result["reason"] = (
            "Ranking unavailable: complete unique franchise inventory is required."
        )
        return result
    if any(
        any(record_fields(t)[k] is None for k in ("wins", "losses", "ties"))
        or number(t.get("points_for")) is None
        for t in teams
    ):
        result["reason"] = (
            "Ranking unavailable: complete source records and Points For are required."
        )
        return result
    if len({t["wins"] + t["losses"] + t["ties"] for t in teams}) != 1:
        result["reason"] = (
            "Ranking unavailable: unequal completed-game opportunities require a verified record comparison."
        )
        return result
    if len({t["ties"] for t in teams}) != 1:
        result["reason"] = (
            "Ranking unavailable: differing tied-game records require a verified record comparison."
        )
        return result
    ordered = sorted(teams, key=lambda t: (-t["wins"], -number(t["points_for"])))
    result["teams"] = ordered
    index = 0
    while index < len(ordered):
        end = index + 1
        key = (ordered[index]["wins"], number(ordered[index]["points_for"]))
        while (
            end < len(ordered)
            and (ordered[end]["wins"], number(ordered[end]["points_for"])) == key
        ):
            end += 1
        for team in ordered[index:end]:
            rid = int(team["roster_id"])
            result["placements"][rid] = (index + 1, end)
            if end == index + 1:
                result["ranks"][rid] = index + 1
        index = end
    if len(result["ranks"]) != len(teams):
        result["reason"] = (
            "Some placements are unresolved: records and Points For are equal. Points Against and roster IDs do not break these ties."
        )
    return result


def playoff_position(data, order):
    """Current positions under named standard/division rules, never clinching."""
    settings = (data.get("league") or {}).get("settings") or {}
    result = {"boundary": None, "qualifiers": set(), "kind": None, "reason": None}
    count = settings.get("playoff_teams")
    teams = order["teams"]
    if type(count) is not int or not 0 < count < len(teams):
        result["reason"] = (
            "Playoff positioning unavailable: qualification count is not established."
        )
        return result
    # Published postseason participant identities are separate from statistics.
    league = data.get("league") or {}
    prepared = data.get("season_matchups") or {}
    start = settings.get("playoff_week_start")
    if (
        type(start) is int
        and type(settings.get("last_scored_leg")) is int
        and settings["last_scored_leg"] >= start - 1
    ):
        if (
            prepared.get("league_id") == str(league.get("league_id"))
            and prepared.get("season") == str(league.get("season"))
            and prepared.get("calendar_reference")
            == season_calendar(league)["reference"]
        ):
            facts = playoff_facts(
                (prepared.get("brackets") or {}).get("winners_bracket") or []
            )
            qualified = {
                int(rid)
                for rid in facts["qualified_roster_ids"]
                if str(rid).isdecimal()
            }
            if (
                len(qualified) == count
                and qualified <= {int(t["roster_id"]) for t in teams}
                and set(facts["reason_codes"])
                <= {
                    "championship_missing",
                    "championship_unresolved",
                    "semifinal_dependency_unavailable",
                    "semifinal_participants_incomplete",
                }
            ):
                result.update(
                    qualifiers=qualified,
                    kind="bracket",
                    reason="Published championship-bracket participants; statistical standings are not final seeds or bye assignments.",
                )
                return result
        result["reason"] = (
            "Playoff positioning unavailable: postseason bracket participant evidence is incomplete; statistical order is not final seeding."
        )
        return result
    divisions = settings.get("divisions")
    if type(divisions) is not int or divisions < 0:
        result["reason"] = (
            "Playoff positioning unavailable: division configuration is not confirmed. An absent setting is not assumed to mean zero."
        )
        return result
    if settings.get("playoff_type") != 0 or settings.get("playoff_seed_type", 0) != 0:
        result["reason"] = (
            "Playoff positioning unavailable: custom qualification/seeding rules are not supported."
        )
        return result
    if len(order["ranks"]) != len(teams):
        # A tie wholly inside/outside the cutoff still admits a current boundary.
        placements = order["placements"]
        if (
            not placements
            or divisions
            or any(a <= count < b for a, b in placements.values())
        ):
            result["reason"] = (
                "Playoff positioning unavailable: ranking evidence or placement at the cutoff is unresolved."
            )
            return result
    if divisions == 0:
        result.update(
            boundary=count,
            qualifiers={int(t["roster_id"]) for t in teams[:count]},
            kind="standard",
            reason=f"Current top {count} by record then PF, assuming standard qualification without commissioner overrides. Not a clinch, final seed or guaranteed bye.",
        )
        return result
    if divisions > count or any(
        type(t.get("division")) is not int or not 1 <= t["division"] <= divisions
        for t in teams
    ):
        result["reason"] = (
            "Playoff positioning unavailable: complete division membership and supported qualification rules are required."
        )
        return result
    groups = [
        [t for t in teams if t["division"] == division]
        for division in range(1, divisions + 1)
    ]
    if any(not group for group in groups):
        result["reason"] = (
            "Playoff positioning unavailable: a configured division has no supported membership."
        )
        return result
    winners = {int(group[0]["roster_id"]) for group in groups}
    remaining = [
        int(t["roster_id"]) for t in teams if int(t["roster_id"]) not in winners
    ]
    result.update(
        qualifiers=winners | set(remaining[: count - divisions]),
        kind="divisions",
        reason="Current division leaders plus remaining record/PF positions under standard division qualification, assuming no commissioner overrides. Indicators are per team; not final seeds or clinched berths.",
    )
    return result


def reconstructed_movement(data, current_order):
    """At most 18 prepared weeks; no provider reads or duplicate retained history.

    Both comparison orders use completed weekly actuals. Current reconstructed
    records AND placements must reconcile to source standings before admission.
    PF sums are never substituted for the displayed cumulative source PF/PA.
    """
    if league_is_preseason(data):
        return {
            "ranks": {},
            "period": None,
            "reason": "Standings movement not started: regular-season results have not begun.",
        }
    league = data.get("league") or {}
    settings = league.get("settings") or {}
    prepared = data.get("season_matchups") or {}
    calendar = season_calendar(league)
    unavailable = {
        "ranks": {},
        "period": None,
        "reason": "Standings movement unavailable: comparable complete completed-week evidence is required.",
    }
    done = settings.get("last_scored_leg")
    weeks = calendar.get("regular_season_weeks") or []
    if (
        type(done) is not int
        or done not in weeks
        or len([w for w in weeks if w <= done]) < 2
        or prepared.get("league_id") != str(league.get("league_id"))
        or prepared.get("season") != str(league.get("season"))
        or prepared.get("methodology") != METHOD
        or prepared.get("calendar_reference") != calendar["reference"]
        or settings.get("league_average_match") not in (0, 1)
        or len(current_order["ranks"]) != len(current_order["teams"])
    ):
        return unavailable
    totals = {
        int(t["roster_id"]): {
            "roster_id": int(t["roster_id"]),
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "points_for": Decimal(0),
        }
        for t in current_order["teams"]
    }
    previous = None
    for week in [w for w in weeks if w <= done][:18]:
        evidence = (prepared.get("weeks") or {}).get(str(week)) or {}
        rows = evidence.get("rows") or []
        if (
            evidence.get("availability") != "available"
            or len(rows) != len(totals)
            or {r["roster_id"] for r in rows} != set(totals)
        ):
            return unavailable
        scores = {
            r["roster_id"]: number(
                r.get("custom_points")
                if r.get("custom_points") is not None
                else r.get("points")
            )
            for r in rows
        }
        if any(v is None for v in scores.values()):
            return unavailable
        median_scores = sorted(Decimal(str(v)) for v in scores.values())
        middle = len(median_scores) // 2
        median = (
            median_scores[middle]
            if len(median_scores) % 2
            else (median_scores[middle - 1] + median_scores[middle]) / 2
        )
        for row in rows:
            pair = [r for r in rows if r.get("matchup_id") == row.get("matchup_id")]
            if row.get("matchup_id") is None or len(pair) != 2:
                return unavailable
            own = totals[row["roster_id"]]
            a = Decimal(str(scores[row["roster_id"]]))
            b = Decimal(
                str(
                    scores[
                        next(
                            r["roster_id"]
                            for r in pair
                            if r["roster_id"] != row["roster_id"]
                        )
                    ]
                )
            )
            own["wins" if a > b else "losses" if a < b else "ties"] += 1
            if settings["league_average_match"] == 1:
                own["wins" if a > median else "losses" if a < median else "ties"] += 1
            own["points_for"] += a
        reconstructed = standings_order(dict(data, teams=list(totals.values())))
        if week == done - 1:
            previous = reconstructed
    if any(
        any(t[k] != totals[int(t["roster_id"])][k] for k in ("wins", "losses", "ties"))
        for t in current_order["teams"]
    ):
        return unavailable
    if (
        reconstructed["ranks"] != current_order["ranks"]
        or not previous
        or len(previous["ranks"]) != len(totals)
    ):
        return unavailable
    return {
        "ranks": previous["ranks"],
        "period": f"completed Week {done - 1} to Week {done}",
        "reason": f"DTOS-derived movement: completed Week {done - 1} to Week {done}, reconstructed from weekly actuals. Current records and ordering reconcile to source standings; cumulative PF/PA remain source values. This is not an observed Sleeper historical rank.",
    }

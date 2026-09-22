"""Bounded Sleeper schedule preparation and read-only selected-week evidence.

No valuation, optimizer, provider call or current-roster reconstruction on reads.
The existing league-cache publication owns persistence/atomic replacement.
"""
from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from typing import Any

from src.core.intelligence.season_calendar import season_calendar
from src.core.history_context.playoffs import playoff_facts
from src.core.intelligence.team_strength import compatible_profile
from src.ui.intelligence_presentation import matchup_game_state

METHOD = "matchup-season-presentation-v1"


def number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def compact_week(rows: Any) -> list[dict] | None:
    """Retain source identities/actuals, never duplicate player/Market payloads."""
    if not isinstance(rows, list):
        return None
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or type(row.get("roster_id")) is not int:
            return None
        if row["roster_id"] <= 0 or row["roster_id"] in seen:
            return None
        if row.get("matchup_id") is not None and (type(row["matchup_id"]) is not int or row["matchup_id"] <= 0):
            return None
        for field in ("starters", "players", "starters_points"):
            if row.get(field) is not None and not isinstance(row[field], list):
                return None
        if row.get("players_points") is not None and not isinstance(row["players_points"], dict):
            return None
        seen.add(row["roster_id"])
        result.append({key: row.get(key) for key in (
            "roster_id", "matchup_id", "points", "custom_points", "starters",
            "starters_points", "players", "players_points",
        )})
    return sorted(result, key=lambda row: row["roster_id"])


async def prepare_season_matchups(league: dict, current_week: int, current_rows: list,
                                  fetch, *, observed_at: str) -> dict:
    """Normal synchronization only. At most 18 week and two bracket source reads.

    A failed/withdrawn week is explicit; prior current availability is not revived.
    Observation time is provenance, excluded from semantic generation identity.
    """
    calendar = season_calendar(league)
    weeks = sorted(set(calendar.get("regular_season_weeks") or []) | {
        week for group in calendar.get("playoff_rounds") or [] for week in group
    } | {current_week})
    evidence = {}
    for week in weeks:
        try:
            raw = current_rows if week == current_week else await fetch(
                f"/league/{league['league_id']}/matchups/{week}")
            rows = compact_week(raw)
            evidence[str(week)] = {"availability": "available" if rows is not None else "unavailable",
                                   "rows": rows or [], "reason": None if rows is not None else "INVALID_SOURCE_WEEK"}
        except Exception:
            evidence[str(week)] = {"availability": "unavailable", "rows": [], "reason": "SOURCE_WEEK_UNAVAILABLE"}
    brackets = {}
    # Read bracket facts only after the regular season; early placeholders must
    # not become postseason qualification. This adds at most two source reads.
    regular = calendar.get("regular_season_weeks") or []
    completed = (league.get("settings") or {}).get("last_scored_leg")
    if regular and type(completed) is int and completed >= max(regular):
        for name in ("winners_bracket", "losers_bracket"):
            try:
                rows = await fetch(f"/league/{league['league_id']}/{name}")
                if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
                    brackets[name] = [{key: row.get(key) for key in (
                        "m", "r", "t1", "t2", "t1_from", "t2_from", "w", "l", "p")}
                        for row in rows]
            except Exception:
                pass  # Missing bracket is unavailable, never a projected lock.
    result = {"league_id": str(league.get("league_id") or ""), "season": str(league.get("season") or ""),
              "methodology": METHOD, "calendar_reference": calendar["reference"], "weeks": evidence,
              "brackets": brackets}
    result["semantic_generation"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result["observed_at"] = observed_at
    return result


def current_matchup_groups(data: dict) -> dict:
    """Pairing-only consumers use the same prepared schedule/playoff boundary."""
    return season_week_view(data, int(data.get('week') or 1), None)['groups']


def _postseason(prepared: dict, calendar: dict, week: int, completed: int) -> dict:
    """Presentation lock requires canonical source bracket participants/outcomes."""
    rounds = calendar.get("playoff_rounds") or []
    ordinal = next((i + 1 for i, group in enumerate(rounds) if week in group), None)
    result = {"pairs": {}, "byes": []}
    if ordinal is None or completed < rounds[ordinal - 1][0] - 1:
        return result
    for name, rows in (prepared.get("brackets") or {}).items():
        matches = {str(row.get("m")): row for row in rows}
        if len(matches) != len(rows):
            continue
        for row in rows:
            if row.get("r") != ordinal:
                continue
            sides = []
            for field in ("t1", "t2"):
                value = row.get(field)
                dependency = value if isinstance(value, dict) else row.get(field + "_from")
                if isinstance(dependency, dict):
                    value = None
                    if len(dependency) == 1:
                        outcome, identity = next(iter(dependency.items()))
                        parent = matches.get(str(identity), {})
                        parent_round = parent.get("r")
                        if (outcome in {"w", "l"} and type(parent_round) is int
                                and 1 <= parent_round < ordinal
                                and completed >= max(rounds[parent_round - 1])):
                            value = parent.get(outcome)
                if str(value).isdecimal() and int(value) > 0:
                    sides.append(int(value))
            if len(sides) == 2 and sides[0] != sides[1]:
                result["pairs"][frozenset(sides)] = "Championship bracket" if name == "winners_bracket" else "Consolation bracket"
        if name == "winners_bracket" and ordinal == 1:
            facts = playoff_facts(rows)
            if "bracket_match_identity_conflict" not in facts["reason_codes"]:
                result["byes"] = [int(rid) for rid in facts["first_round_bye_roster_ids"] if str(rid).isdecimal()]
    return result


def season_week_view(data: dict, week: int, projection_service, *, evidence_through_week: int | None = None) -> dict:
    """Pin one projection generation; never substitute another week/league."""
    league = data.get("league") or {}
    calendar = season_calendar(league)
    prepared = data.get("season_matchups") or {}
    league_id, season = str(league.get("league_id") or ""), str(league.get("season") or "")
    compatible = (prepared.get("league_id") == league_id and prepared.get("season") == season
                  and prepared.get("calendar_reference") == calendar["reference"]
                  and prepared.get("methodology") == METHOD)
    evidence = (prepared.get("weeks") or {}).get(str(week), {}) if compatible else {}
    rounds = calendar.get("playoff_rounds") or []
    component = next((group for group in rounds if week in group), [])
    completed = (league.get("settings") or {}).get("last_scored_leg")
    completed = completed if type(completed) is int else 0
    if evidence_through_week is not None:
        if type(evidence_through_week) is not int or not 1 <= evidence_through_week <= 18:
            raise ValueError('Invalid historical evidence boundary')
        completed = min(completed, evidence_through_week)
    historical = week <= completed
    current = int(data.get("week") or 0)
    # A scheduled future playoff placeholder is NOT a locked opponent. Even
    # concrete IDs are withheld until all preceding rounds have completed.
    postseason = _postseason(prepared, calendar, week, completed) if compatible else {"pairs": {}, "byes": []}
    locked = not component or bool(postseason["pairs"] or postseason["byes"])
    pinned = projection_service.snapshot() if projection_service is not None else None
    snapshot = None
    scoring = data.get('scoring_settings') or league.get('scoring_settings') or {}
    if (not historical and pinned and str(pinned.get("league_id")) == league_id
            and str(pinned.get("season")) == season and pinned.get("horizon_generation")
            and pinned.get('scoring_settings', {}) == scoring):
        candidate = projection_service.week_snapshot(week, generation_snapshot=pinned)
        if (candidate and str(candidate.get("league_id")) == league_id
                and str(candidate.get("season")) == season and candidate.get("week") == week
                and candidate.get("horizon_generation") == pinned["horizon_generation"]
                and candidate.get('scoring_profile_id') == pinned.get('scoring_profile_id')
                and candidate.get('scoring_settings', {}) == scoring):
            snapshot = candidate
    teams = {int(t["roster_id"]): t for t in data.get("teams") or [] if str(t.get("roster_id")).isdecimal()}
    strength = compatible_profile(data, pinned) if snapshot and not historical else None
    players = data.get("players") or {}
    slots = [slot for slot in data.get("roster_positions") or league.get('roster_positions') or []
             if slot not in {"BN", "BENCH", "IR", "TAXI", "RESERVE"}]
    groups: dict[str, list] = {}
    for row in evidence.get("rows") or []:
        if component and not locked:
            continue
        rid = row["roster_id"]
        team = teams.get(rid, {})
        starter_ids = [str(pid) for pid in row.get("starters") or []]
        def player_row(pid, slot, actual):
            player = players.get(pid) or {}
            projection = ((snapshot or {}).get("players") or {}).get(pid) or {}
            value = number(projection.get("canonical_projection"))
            return {"player_id": pid, "name": player.get("full_name") or ("Empty slot" if pid == "0" else pid),
                           "position": player.get("position"), "slot": slot,
                           "actual": actual, "projection": value,
                           "projection_display": projection.get("sleeper_web_display_projection") if value is not None else None}
        lineup = []
        for index, pid in enumerate(starter_ids):
            actuals = row.get("starters_points") or []
            actual = number(actuals[index]) if index < len(actuals) else number((row.get("players_points") or {}).get(pid))
            lineup.append(player_row(pid, slots[index] if index < len(slots) else "Source starter", actual))
        bench = [player_row(str(pid), "Non-starter", number((row.get("players_points") or {}).get(str(pid))))
                 for pid in row.get("players") or [] if str(pid) not in starter_ids]
        supported = [p["projection"] for p in lineup if p["projection"] is not None]
        total = float(sum((Decimal(str(value)) for value in supported), Decimal(0))) if supported else None
        complete = bool(slots) and len(lineup) == len(slots) and len(supported) == len(slots)
        score = number(row.get("custom_points"))
        if score is None:
            score = number(row.get("points"))
        side = {"roster_id": rid, "team": team.get("team_name") or f"Franchise {rid}", "lineup": lineup, "bench": bench,
                "actual": score, "projection": total if complete else None,
                "known_subtotal": total, "supported_slots": len(supported), "expected_slots": len(slots),
                "coverage": "complete" if complete else "partial" if supported else "unavailable"}
        weekly_strength = (((strength or {}).get('teams') or {}).get(str(rid), {}).get('weekly') or {})
        weekly_strength = weekly_strength.get(week, weekly_strength.get(str(week))) or {}
        # Consume the accepted prepared optimizer; never optimize on navigation.
        snapshot_id = (snapshot or {}).get('projection_snapshot_id')
        side['optimal'] = weekly_strength.get('optimal') if snapshot_id and weekly_strength.get('projection_snapshot_id') == snapshot_id else None
        side['weekly_context'] = ({key: weekly_strength.get(key) for key in (
            'reserve_capacity', 'known_bye_player_ids', 'bye_evidence_availability',
            'previous_optimal_players_on_known_bye', 'optimal_entries_since_previous_week', 'change_meaning')}
            if side['optimal'] is not None else None)
        if component:
            round_scores = []
            for component_week in component:
                rows = (prepared.get('weeks') or {}).get(str(component_week), {}).get('rows') or []
                source = next((r for r in rows if r['roster_id'] == rid), {})
                value = number(source.get('custom_points'))
                if value is None:
                    value = number(source.get('points'))
                # Future 0-0 source placeholders are not played component scores.
                if component_week > completed and not (component_week == current and value is not None and value != 0
                        and (evidence_through_week is None or component_week <= evidence_through_week)):
                    value = None
                round_scores.append({'week': component_week, 'actual': value})
            full = completed >= max(component) and all(r['actual'] is not None for r in round_scores)
            side['round_actual'] = float(sum((Decimal(str(r['actual'])) for r in round_scores), Decimal(0))) if full else None
            side['round_scores'] = round_scores
        mid = row.get("matchup_id")
        key = str(mid) if mid is not None else f"unassigned-{rid}"
        groups.setdefault(key, []).append(side)
    bracket_labels = {}
    if component:
        # Weekly matchup IDs are not bracket match IDs. Match by the exact pair
        # of roster identities, not a coincidentally equal source number.
        groups = {key: sides for key, sides in groups.items()
                  if len(sides) == 2 and frozenset(s["roster_id"] for s in sides) in postseason["pairs"]}
        bracket_labels = {key: postseason["pairs"][frozenset(s["roster_id"] for s in sides)] for key, sides in groups.items()}
    states = {key: "final" if historical else "pregame" if week > current else matchup_game_state(
        {'week': week}, [{"points": side["actual"]} for side in sides]) for key, sides in groups.items()}
    overview = []
    for selected, source in (prepared.get("weeks") or {}).items() if compatible else []:
        target = int(selected)
        postseason_week = any(target in group for group in rounds)
        label = "Week evidence unavailable" if source.get("availability") != "available" else "No matchups published"
        pairs = {}
        if not postseason_week:
            for row in source.get("rows") or []:
                if row.get("matchup_id") is not None:
                    pairs.setdefault(row["matchup_id"], []).append(teams.get(row["roster_id"], {}).get("team_name") or f'Franchise {row["roster_id"]}')
            if pairs:
                label = "; ".join(" vs ".join(names) for names in pairs.values())
        else:
            label = "Playoff round · open week for bracket-backed status"
        overview.append({"week": target, "summary": label})
    result = {"league_id": league_id, "season": season, "week": week, "calendar": calendar,
              "availability": evidence.get("availability", "unavailable"), "groups": groups,
              "generation": prepared.get("semantic_generation") if compatible else None,
              "projection_generation": (snapshot or {}).get("horizon_generation"),
              "observed_at": prepared.get("observed_at") if compatible else None,
              "period": "historical" if historical else "current" if week == current else "future",
              "round_weeks": component, "round_complete": bool(component) and completed >= max(component),
              "opponents_locked": locked, "methodology": METHOD, "bracket_labels": bracket_labels,
              "states": states, "overview": sorted(overview, key=lambda item: item["week"]),
              "byes": [{"roster_id": rid, "team": teams.get(rid, {}).get("team_name") or f"Franchise {rid}"}
                       for rid in postseason["byes"]]}
    return result

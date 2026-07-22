"""Deterministic Team Headquarters calculations and summaries."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from services.transactions import normalize_transactions
from src.core.intelligence import intelligence_orchestrator

CORE_POSITIONS = ("QB", "RB", "WR", "TE")
POSITION_TARGETS = {
    "QB": {"total": 3, "starters": 1},
    "RB": {"total": 7, "starters": 2},
    "WR": {"total": 9, "starters": 3},
    "TE": {"total": 4, "starters": 1},
}


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _grade_result(score: float, data: str, calculation: str, why: str) -> dict[str, Any]:
    rounded = max(0, min(100, round(score)))
    return {
        "score": rounded,
        "grade": _grade(rounded),
        "data": data,
        "calculation": calculation,
        "why": why,
    }


def _enriched_players(team: dict[str, Any], data: dict[str, Any]) -> list[dict[str, Any]]:
    player_database = data.get("players") or {}
    rows = []
    for player in team.get("players") or []:
        details = player_database.get(str(player.get("id")), {}) if isinstance(player_database, dict) else {}
        age = _number(player.get("age"))
        if age is None:
            age = _number(details.get("age"))
        rows.append(
            {
                **player,
                "age": age,
                "bye_week": player.get("bye_week") or details.get("bye_week"),
            }
        )
    return rows


def _asset_snapshot(players: list[dict[str, Any]], team: dict[str, Any]) -> dict[str, Any]:
    ages = [player["age"] for player in players if player["age"] is not None]
    starter_ages = [
        player["age"]
        for player in players
        if player.get("roster_slot") == "Starter" and player["age"] is not None
    ]
    picks = team.get("picks_owned") or []
    return {
        "total_players": len(players),
        "total_picks": len(picks),
        "first_round_picks": sum(int(pick.get("round") or 0) == 1 for pick in picks),
        "average_age": round(mean(ages), 1) if ages else None,
        "average_starter_age": round(mean(starter_ages), 1) if starter_ages else None,
        "young_players": sum(age <= 24 for age in ages),
        "veteran_players": sum(age >= 28 for age in ages),
        "known_ages": len(ages),
    }


def calculate_team_grades(players: list[dict[str, Any]], team: dict[str, Any], roster: Any | None = None) -> dict[str, dict[str, Any]]:
    """Calculate explainable grades, preferring quality-first Roster Intelligence."""
    if roster is not None:
        grades = {
            position: {
                "score": room.overall.score,
                "grade": room.overall.grade,
                "data": " ".join(room.reasoning),
                "calculation": "; ".join(f"{item.name} {item.score}/100 ({item.grade})" for item in room.dimensions),
                "why": room.advantage or "Quality, leverage, longevity, market value, championship impact, and depth are evaluated independently.",
                "dimensions": room.dimensions,
            }
            for position, room in roster.rooms.items()
        }
    else:
        grades = {position: _grade_result(50, f"{position} intelligence unavailable.", "Neutral fallback.", "No quality evaluation was available.") for position in CORE_POSITIONS}
    known_ages = [player.get("age") for player in players if player.get("age") is not None]
    young = sum(age <= 24 for age in known_ages)
    old = sum(age >= 28 for age in known_ages)
    if known_ages:
        youth_score = 50 + (young / len(known_ages) * 50) - (old / len(known_ages) * 25)
        youth_why = "More age-24-and-under players raise the grade; age-28-and-older players reduce it modestly."
    else:
        youth_score = 50
        youth_why = "No player ages are available, so the neutral baseline is used and confidence is limited."
    grades["Youth"] = _grade_result(
        youth_score,
        f"Ages known for {len(known_ages)} of {len(players)} players; {young} are 24 or younger and {old} are 28 or older.",
        "50 baseline + young-player share × 50 − veteran-player share × 25.",
        youth_why,
    )

    core_players = [player for player in players if player.get("position") in CORE_POSITIONS]
    bench_core = sum(player.get("roster_slot") != "Starter" for player in core_players)
    rooms_covered = sum(any(player.get("position") == pos for player in players) for pos in CORE_POSITIONS)
    depth_score = min(bench_core / 12, 1) * 70 + rooms_covered / 4 * 30
    grades["Depth"] = _grade_result(
        depth_score,
        f"{bench_core} non-starting QB/RB/WR/TE players; {rooms_covered} of 4 core position rooms represented.",
        "70% reserve coverage against a 12-player benchmark + 30% core-room coverage.",
        "The grade measures roster coverage, not projected production.",
    )

    picks = team.get("picks_owned") or []
    firsts = sum(int(pick.get("round") or 0) == 1 for pick in picks)
    draft_score = min(len(picks) / 12, 1) * 60 + min(firsts / 3, 1) * 40
    grades["Draft Capital"] = _grade_result(
        draft_score,
        f"{len(picks)} future picks owned, including {firsts} first-round picks.",
        "60% total-pick coverage against 12 picks + 40% first-round coverage against 3 firsts.",
        "Earlier picks receive extra weight because they preserve more future roster-building options.",
    )

    flexibility_score = grades["Youth"]["score"] * 0.45 + grades["Draft Capital"]["score"] * 0.55
    grades["Flexibility"] = _grade_result(
        flexibility_score,
        f"Youth score {grades['Youth']['score']}; Draft Capital score {grades['Draft Capital']['score']}.",
        "45% Youth + 55% Draft Capital.",
        "Younger rosters and owned picks are objective proxies for future optionality; no trade-value claim is made.",
    )

    overall_inputs = [grades[position]["score"] for position in (*CORE_POSITIONS, "Youth", "Depth", "Draft Capital", "Flexibility")]
    overall_score = mean(overall_inputs)
    grades["Roster Construction"] = _grade_result(
        overall_score,
        "Scores used: " + ", ".join(f"{name} {grades[name]['score']}" for name in (*CORE_POSITIONS, "Youth", "Depth", "Draft Capital", "Flexibility")) + ".",
        "Equal-weight average of all eight foundation grades.",
        "This legacy-compatible construction grade summarizes observable coverage and assets; it is not a combined current/future team score.",
    )
    return grades


def generate_front_office_summary(
    snapshot: dict[str, Any], grades: dict[str, dict[str, Any]], decision: Any, team_card: Any | None = None,
) -> dict[str, str]:
    """Create a deterministic, fact-limited front-office summary."""
    construction = grades["Roster Construction"]
    component_names = (*CORE_POSITIONS, "Youth", "Depth", "Draft Capital", "Flexibility")
    ordered = sorted(component_names, key=lambda name: (-grades[name]["score"], name))
    strongest, weakest = ordered[:2], ordered[-2:]
    age_note = (
        f"Age data is available for {snapshot['known_ages']} players."
        if snapshot["known_ages"]
        else "Player age data is unavailable, so age-based conclusions are limited."
    )
    if team_card is not None:
        return {
            "Overall Assessment": f"League-relative Overall Grade is {team_card.overall.grade} ({team_card.overall.score}/100), ranked #{team_card.overall.rank} of {team_card.overall.league_size}. Current Window: {team_card.current_window.value}. {age_note}",
            "Current Strengths": team_card.explanation[0],
            "Current Weaknesses": team_card.explanation[1],
            "Short-Term Outlook": f"Current Championship Outlook uses the league-relative Current Contending Grade: {team_card.current_contending.grade} ({team_card.current_strength}/100), #{team_card.current_contending.rank} in the league, evaluated independently from future assets. " + " ".join(team_card.current_contending.reasons),
            "Long-Term Outlook": f"Future Outlook Grade is {team_card.future_outlook.grade} ({team_card.future_strength}/100), #{team_card.future_outlook.rank} in the league and remains an independently calculated future horizon. " + " ".join(team_card.future_outlook.reasons),
        }
    return {
        "Overall Assessment": f"Current Championship Outlook is {decision.current_outlook.grade} ({decision.current_outlook.score}/100); Future Outlook is {decision.future_outlook.grade} ({decision.future_outlook.score}/100). The separate roster-construction grade is {construction['grade']} ({construction['score']}/100). {age_note}",
        "Current Strengths": "The strongest observable areas are " + " and ".join(f"{name} ({grades[name]['score']}/100)" for name in strongest) + ".",
        "Current Weaknesses": "The lowest observable areas are " + " and ".join(f"{name} ({grades[name]['score']}/100)" for name in weakest) + "; this identifies coverage gaps, not individual-player quality.",
        "Short-Term Outlook": f"The Decision Engine rates the current horizon {decision.current_outlook.grade} ({decision.current_outlook.score}/100). {decision.current_outlook.summary}",
        "Long-Term Outlook": f"The independently calculated future horizon is {decision.future_outlook.grade} ({decision.future_outlook.score}/100). {decision.future_outlook.summary}",
    }


def _timeline(data: dict[str, Any], roster_id: int) -> list[dict[str, Any]]:
    items = []
    for transaction in normalize_transactions(data):
        involved = {str(team["roster_id"]) for team in transaction["teams"]}
        assets = [
            asset for asset in transaction["assets"]
            if str(asset.get("source_id") or "") == str(roster_id)
            or str(asset.get("destination_id") or "") == str(roster_id)
        ]
        if str(roster_id) not in involved and not assets:
            continue
        actions = Counter(asset["action"] for asset in assets)
        items.append(
            {
                "id": transaction["id"],
                "type": transaction["type_label"],
                "timestamp": transaction["timestamp"],
                "created_ms": transaction["created_ms"],
                "assets": assets,
                "actions": ", ".join(f"{count} {action.lower()}" for action, count in sorted(actions.items())) or "Team involved",
            }
        )
    return sorted(items, key=lambda item: item["created_ms"], reverse=True)[:12]


def build_team_headquarters(
    data: dict[str, Any], roster_id: int, last_updated: Any = None
) -> dict[str, Any] | None:
    """Build the presentation-neutral Team Headquarters view model."""
    teams = data.get("teams") or []
    team = next((item for item in teams if int(item.get("roster_id") or 0) == roster_id), None)
    if team is None:
        return None
    players = _enriched_players(team, data)
    snapshot = _asset_snapshot(players, team)
    intelligence = intelligence_orchestrator.analyze(data, roster_id)
    grades = calculate_team_grades(players, team, intelligence.roster)
    decision = intelligence.decision
    organization = intelligence.front_office_model.reports[roster_id]
    team_intelligence = intelligence.roster.team_intelligence[roster_id]
    rank = team_intelligence.overall.rank
    if isinstance(last_updated, datetime):
        updated = last_updated.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    elif last_updated:
        try:
            updated = datetime.fromisoformat(str(last_updated)).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            updated = str(last_updated)
    else:
        updated = "Unavailable"
    roster_groups = {
        position: [
            {**player, "intelligence": intelligence.roster.players.get(str(player.get("id")))}
            for player in players if player.get("position") == position
        ]
        for position in CORE_POSITIONS
    }
    return {
        "team": team,
        "rank": rank,
        "last_updated": updated,
        "snapshot": snapshot,
        "grades": grades,
        "summary": generate_front_office_summary(snapshot, grades, decision, team_intelligence),
        "decision": decision,
        "front_office_intelligence": organization,
        "unified_recommendation": intelligence.recommendation,
        "roster_intelligence": intelligence.roster,
        "team_intelligence": team_intelligence,
        "roster_groups": roster_groups,
        "other_players": [player for player in players if player.get("position") not in CORE_POSITIONS],
        "picks_by_year": {
            year: sorted(picks, key=lambda pick: (int(pick.get("round") or 99), str(pick.get("original_team") or "")))
            for year, picks in _group_picks(team.get("picks_owned") or []).items()
        },
        "timeline": _timeline(data, roster_id),
        "performance": {
            "record": f"{team.get('wins', 0)}-{team.get('losses', 0)}-{team.get('ties', 0)}",
            "points_for": float(team.get("points_for") or 0),
            "points_against": float(team.get("points_against") or 0),
            "max_points": float(team.get("max_points") or 0),
            "streak": "Unavailable",
            "standing": f"#{rank} of {len(teams)}",
        },
    }


def _group_picks(picks: list[dict[str, Any]]) -> dict[Any, list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for pick in picks:
        grouped.setdefault(pick.get("season") or "Unknown", []).append(pick)
    return grouped

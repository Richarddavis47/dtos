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


def build_team_directory(data: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Return one league-relative, offseason-aware directory card per franchise."""
    teams = data.get("teams") or []
    if not teams:
        return {}
    active_id = min(int(team.get("roster_id") or 0) for team in teams)
    intelligence = intelligence_orchestrator.analyze(data, active_id).roster.team_intelligence
    return {
        roster_id: {
            "preseason": card.preseason,
            "rank": card.overall.rank,
            "projected_wins": card.projected_wins,
            "playoff_odds": card.playoff_odds,
            "championship_odds": card.championship_odds,
            "grade": card.overall.grade,
        }
        for roster_id, card in intelligence.items()
    }


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


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
    """Present the existing canonical team dimensions; never recompute grades."""
    card = (roster.team_intelligence.get(int(team.get("roster_id") or 0))
            if roster is not None else None)
    dimensions = {
        **{position: card.positions.get(position) if card else None for position in CORE_POSITIONS},
        "Youth": card.youth if card else None,
        "Depth": card.depth if card else None,
        "Draft Capital": card.draft_capital if card else None,
        "Flexibility": card.roster_flexibility if card else None,
        "Roster Construction": card.overall if card else None,
    }
    return {
        name: {
            "score": dimension.score if dimension else None,
            "grade": dimension.grade if dimension else "Unavailable",
            "data": " ".join(dimension.reasons) if dimension else "Canonical assessment unavailable.",
            "calculation": dimension.category if dimension else "No fallback calculation.",
            "why": "Uses the canonical generation-bound dimension; unrelated evidence is not substituted.",
            "generation": card.generation if card else None,
            "league_id": card.league_id if card else None,
        }
        for name, dimension in dimensions.items()
    }


def generate_front_office_summary(
    snapshot: dict[str, Any], grades: dict[str, dict[str, Any]], decision: Any, team_card: Any | None = None,
) -> dict[str, str]:
    """Create a deterministic, fact-limited front-office summary."""
    construction = grades["Roster Construction"]
    component_names = (*CORE_POSITIONS, "Youth", "Depth", "Draft Capital", "Flexibility")
    ordered = sorted(component_names, key=lambda name: (grades[name]["score"] is None, -grades[name]["score"] if grades[name]["score"] is not None else 0, name))
    strongest, weakest = ordered[:2], ordered[-2:]
    age_note = (
        f"Age data is available for {snapshot['known_ages']} players."
        if snapshot["known_ages"]
        else "Player age data is unavailable, so age-based conclusions are limited."
    )
    if team_card is not None:
        if team_card.overall.score is None:
            return {
                "Overall Assessment": "Overall assessment unavailable. Supported dimensions are shown separately; Market strength is not lineup strength.",
                "Current Strengths": " ".join(team_card.starting_lineup.reasons),
                "Current Weaknesses": " ".join(team_card.depth.reasons),
                "Short-Term Outlook": "Optimal projected lineup: " + team_card.starting_lineup.grade + ". " + " ".join(team_card.starting_lineup.reasons),
                "Long-Term Outlook": "Long-term utility unavailable. Future capital and longevity context remain distinct evidence, not a fabricated dynasty scalar.",
            }
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
        "brain": intelligence.brain,
        "assessment": intelligence.team_assessment,
        "brain_recommendation": intelligence.brain_decision,
        "decision_confidence": intelligence.brain_decision.confidence,
        "roster_intelligence": intelligence.roster,
        "team_intelligence": team_intelligence,
        "competitive_window": team_intelligence.competitive_window,
        "preseason": team_intelligence.preseason,
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

"""Contextual team profile construction and orchestration."""
from __future__ import annotations

from statistics import mean
from typing import Any

from src.core.decision_engine.assets.market_context import build_market_context
from src.core.decision_engine.assets.pick_evaluator import evaluate_pick_assets
from src.core.decision_engine.assets.player_evaluator import evaluate_player_assets
from src.core.decision_engine.models.decision import DecisionContext, TeamDecision
from src.core.decision_engine.models.evaluation import Evaluation, EvaluationFactor, EvaluationHorizon
from src.core.decision_engine.models.team_profile import PositionRoom, TeamProfile
from src.core.decision_engine.recommendations.recommendation_engine import build_recommendations
from src.core.decision_engine.team.competitive_window import classify_competitive_window
from src.core.decision_engine.team.contender_score import evaluate_current_outlook
from src.core.decision_engine.team.depth_analyzer import evaluate_depth
from src.core.decision_engine.team.future_score import evaluate_future_outlook
from src.core.decision_engine.team.scoring import clamp, grade


def _age(player: dict[str, Any], player_database: dict[str, Any]) -> float | None:
    details = player_database.get(str(player.get("id")), {}) if isinstance(player_database, dict) else {}
    value = player.get("age") if player.get("age") is not None else details.get("age")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_team_profile(data: dict[str, Any], roster_id: int, context: DecisionContext) -> TeamProfile:
    team = next((team for team in data.get("teams") or [] if int(team.get("roster_id") or 0) == roster_id), None)
    if team is None:
        raise ValueError(f"Roster {roster_id} is not available in league {context.league_id}.")
    player_database = data.get("players") or {}
    players = team.get("players") or []
    ages = tuple(age for player in players if (age := _age(player, player_database)) is not None)
    starter_ages = tuple(age for player in players if player.get("roster_slot") == "Starter" and (age := _age(player, player_database)) is not None)
    rooms = {}
    for position in ("QB", "RB", "WR", "TE"):
        members = [player for player in players if player.get("position") == position]
        member_ages = [age for player in members if (age := _age(player, player_database)) is not None]
        injured = 0
        for player in members:
            details = player_database.get(str(player.get("id")), {}) if isinstance(player_database, dict) else {}
            if details.get("injury_status"):
                injured += 1
        rooms[position] = PositionRoom(position, len(members), sum(player.get("roster_slot") == "Starter" for player in members), injured, round(mean(member_ages), 1) if member_ages else None)
    picks = team.get("picks_owned") or []
    teams = data.get("teams") or []
    return TeamProfile(
        roster_id=roster_id,
        owner_name=str(team.get("owner") or "Unassigned"),
        team_name=str(team.get("team_name") or f"Team {roster_id}"),
        league_id=context.league_id,
        active_front_office_id=context.active_front_office_id,
        league_settings=context.league_settings,
        strategy=context.team_strategy,
        wins=int(team.get("wins") or 0), losses=int(team.get("losses") or 0), ties=int(team.get("ties") or 0),
        points_for=float(team.get("points_for") or 0), points_against=float(team.get("points_against") or 0), max_points=float(team.get("max_points") or 0),
        league_points_for=tuple(float(item.get("points_for") or 0) for item in teams),
        league_max_points=tuple(float(item.get("max_points") or 0) for item in teams),
        roster_size=len(players), known_ages=ages, starter_ages=starter_ages,
        young_player_count=sum(age <= 24 for age in ages), veteran_player_count=sum(age >= 28 for age in ages),
        draft_pick_count=len(picks), first_round_pick_count=sum(int(pick.get("round") or 0) == 1 for pick in picks),
        position_rooms=rooms,
        market_context=context.market_conditions or build_market_context(data),
        players=tuple({**(player_database.get(str(player.get("id")), {}) or {}), **player} for player in players),
        picks=tuple(picks),
    )


def _asset_health(profile: TeamProfile) -> Evaluation:
    player_score, player_factors, player_limits = evaluate_player_assets(profile)
    pick_score, pick_factors, pick_limits = evaluate_pick_assets(profile)
    represented = sum(room.total_players > 0 for room in profile.position_rooms.values())
    balance_score = represented / 4 * 100
    score = pick_score * 0.50 + player_score * 0.30 + balance_score * 0.20
    value = clamp(score)
    factors = tuple(EvaluationFactor(item.name, item.value, item.contribution * 0.30, item.explanation, item.source) for item in player_factors) + tuple(EvaluationFactor(item.name, item.value, item.contribution * 0.50, item.explanation, item.source) for item in pick_factors) + (EvaluationFactor("Positional balance", f"{represented}/4 core rooms represented", balance_score * 0.20, "20% asset-health balance component.", "Sleeper roster"),)
    return Evaluation(EvaluationHorizon.ASSET_HEALTH, value, grade(value), 78, "Draft capital, age flexibility, and positional balance are evaluated without market-value assumptions.", factors, tuple(dict.fromkeys((*player_limits, *pick_limits, "A live dynasty market-value provider is not connected."))))


def evaluate_team(data: dict[str, Any], roster_id: int, context: DecisionContext) -> TeamDecision:
    profile = build_team_profile(data, roster_id, context)
    current = evaluate_current_outlook(profile)
    future = evaluate_future_outlook(profile)
    depth, positions = evaluate_depth(profile)
    assets = _asset_health(profile)
    window, explanation = classify_competitive_window(current, future)
    recommendations = build_recommendations(profile, current, future, depth, assets, positions, window)
    return TeamDecision(profile, current, future, depth, assets, positions, window, explanation, recommendations)

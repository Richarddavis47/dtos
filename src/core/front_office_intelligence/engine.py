"""Deterministic organizational behavior analysis from cached fantasy actions."""
from __future__ import annotations

from itertools import combinations
from typing import Any

from src.core.asset_intelligence import AssetContext, Evidence
from src.core.asset_intelligence.portfolio import evaluate_pick_portfolio, evaluate_player_portfolio
from src.core.decision_engine import DecisionContext, TeamDecision, TeamWindow, evaluate_team
from src.core.front_office_intelligence.models import (
    ActivityProfile, AssetPreference, CompatibilityReport, FrontOfficeReport,
    LeagueFrontOfficeModel, NegotiationForecast, RelationshipEdge,
)


def _roster_ids(item: dict[str, Any]) -> set[int]:
    values = item.get("roster_ids") or []
    for mapping in (item.get("adds"), item.get("drops")):
        if isinstance(mapping, dict):
            values = [*values, *mapping.values()]
    result = set()
    for value in values:
        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue
    return result


def _activity(data: dict[str, Any], roster_id: int, pick_count: int) -> ActivityProfile:
    counts = {"trade": 0, "waiver": 0, "free_agent": 0, "drop": 0}
    for item in data.get("transactions") or []:
        if roster_id not in _roster_ids(item):
            continue
        kind = str(item.get("type") or "").lower()
        if kind in counts:
            counts[kind] += 1
        if isinstance(item.get("drops"), dict) and roster_id in _roster_ids({"roster_ids": item["drops"].values()}):
            counts["drop"] += 1
    total = sum(counts.values())
    level = "High observed activity" if total >= 12 else "Moderate observed activity" if total >= 5 else "Limited observed history"
    evidence = (
        Evidence("Completed trades", str(counts["trade"]), counts["trade"], "Counts cached transactions involving this roster.", "Sleeper cached transactions"),
        Evidence("Roster transactions", str(total - counts["trade"]), total - counts["trade"], "Counts cached waiver, add, and drop actions involving this roster.", "Sleeper cached transactions"),
        Evidence("Draft assets owned", str(pick_count), pick_count, "Current owned picks provide observable draft-strategy context.", "Sleeper cached pick ledger"),
    )
    return ActivityProfile(level, counts["trade"], counts["waiver"], counts["free_agent"], counts["drop"], pick_count, evidence)


def _window(decision: TeamDecision) -> str:
    if decision.window == TeamWindow.CHAMPIONSHIP:
        return "Championship Favorite" if decision.current_outlook.score >= 85 else "Contender"
    if decision.window == TeamWindow.PLAYOFF:
        return "Playoff Team"
    if decision.window == TeamWindow.TRANSITION:
        return "Re-tooling"
    if decision.window == TeamWindow.ASCENSION:
        return "Rebuilding"
    return "Full Rebuild" if decision.current_outlook.score < 45 else "Rebuilding"


def _profile(decision: TeamDecision, data: dict[str, Any]) -> FrontOfficeReport:
    profile = decision.profile
    activity = _activity(data, profile.roster_id, profile.draft_pick_count)
    asset_context = AssetContext(profile.league_id, profile.roster_id, profile.league_settings, decision.window.value, profile.strategy)
    player_portfolio = evaluate_player_portfolio(profile.players, asset_context)
    pick_portfolio = evaluate_pick_portfolio(profile.picks, asset_context)
    philosophies: list[str] = []
    if decision.current_outlook.score >= decision.future_outlook.score + 10:
        philosophies.append("Win Now")
    elif decision.future_outlook.score >= decision.current_outlook.score + 10:
        philosophies.append("Long-Term Builder")
    else:
        philosophies.append("Balanced")
    if profile.draft_pick_count >= 10:
        philosophies.append("Draft-Centric")
    if abs(player_portfolio.score - pick_portfolio.score) <= 10:
        philosophies.append("Value Investor")
    if activity.trades >= 5:
        philosophies.append("Aggressive Trader")
    elif activity.trades == 0:
        philosophies.append("Conservative Trader")
    known = len(profile.known_ages)
    young_share = profile.young_player_count / known if known else 0
    veteran_share = profile.veteran_player_count / known if known else 0
    preferences: list[AssetPreference] = []
    if known and young_share >= .35:
        preferences.append(AssetPreference("Values youth", "Observed", (Evidence("Age 24 and under", f"{profile.young_player_count} of {known}", young_share * 100, "Current roster construction contains a meaningful young-player share.", "Sleeper roster ages"),)))
    if known and veteran_share >= .35:
        preferences.append(AssetPreference("Values veterans", "Observed", (Evidence("Age 28 and older", f"{profile.veteran_player_count} of {known}", veteran_share * 100, "Current roster construction contains a meaningful veteran share.", "Sleeper roster ages"),)))
    if profile.draft_pick_count >= 10:
        preferences.append(AssetPreference("Pick collector", "Observed", (Evidence("Draft assets owned", str(profile.draft_pick_count), profile.draft_pick_count, "Owned draft capital exceeds the v1 ten-pick observation threshold.", "Sleeper cached pick ledger"),)))
    if not preferences:
        preferences.append(AssetPreference("No strong preference established", "Neutral", (Evidence("Preference sample", "Insufficient differentiating evidence", 0, "DTOS does not assign an asset preference without an observable threshold.", "Cached roster and transaction history", False),)))
    style = "Active trade participant" if activity.trades >= 5 else "Selective trade participant" if activity.trades else "Neutral default — insufficient trade history"
    confidence = min(90, 35 + min(known, 20) + min(activity.trades * 5, 25) + (10 if profile.draft_pick_count else 0))
    evidence = activity.evidence + tuple(item for pref in preferences for item in pref.evidence) + (
        Evidence("Current/Future outlook", f"{decision.current_outlook.score}/{decision.future_outlook.score}", decision.current_outlook.score - decision.future_outlook.score, "Independent Decision Engine horizons determine competitive direction.", "Decision Engine"),
        Evidence("Player/Pick portfolio", f"{player_portfolio.score}/{pick_portfolio.score}", player_portfolio.score - pick_portfolio.score, "Asset Intelligence portfolio outputs provide a shared asset-balance signal without duplicating valuation logic.", "Asset Intelligence"),
    )
    strengths = tuple(position for position, evaluation in decision.position_evaluations.items() if evaluation.score >= 70) or ("No position crossed the v1 strength threshold.",)
    constraints = tuple(position for position, evaluation in decision.position_evaluations.items() if evaluation.score < 55) or ("No position crossed the v1 need threshold.",)
    window = _window(decision)
    summary = f"{profile.team_name} is currently classified as {window} with a {', '.join(philosophies).lower()} approach. {style}. This profile describes cached fantasy-football actions only."
    return FrontOfficeReport(profile.roster_id, profile.owner_name, profile.team_name, summary, window, tuple(philosophies), style, activity, tuple(preferences), strengths, constraints, confidence, evidence, decision)


def _needs(decision: TeamDecision) -> set[str]:
    return {position for position, evaluation in decision.position_evaluations.items() if evaluation.score < 55}


def _surpluses(decision: TeamDecision) -> set[str]:
    targets = {"QB": 2, "RB": 4, "WR": 5, "TE": 2}
    return {position for position, room in decision.profile.position_rooms.items() if room.total_players > targets[position]}


def _compatibility(data: dict[str, Any], first: FrontOfficeReport, second: FrontOfficeReport) -> CompatibilityReport:
    first_matches = _needs(first.decision) & _surpluses(second.decision)
    second_matches = _needs(second.decision) & _surpluses(first.decision)
    bilateral = sum(str(item.get("type") or "").lower() == "trade" and {first.roster_id, second.roster_id}.issubset(_roster_ids(item)) for item in data.get("transactions") or [])
    score = min(100, 40 + 15 * len(first_matches) + 15 * len(second_matches) + min(bilateral, 3) * 5)
    shared = tuple(sorted(first_matches | second_matches))
    conflicts = tuple(sorted(_needs(first.decision) & _needs(second.decision)))
    themes = tuple((["Roster Balance"] if shared else ["Value Discovery"]) + (["Established Trade Channel"] if bilateral else []))
    enough_history = bilateral >= 3 and first.activity.trades >= 5 and second.activity.trades >= 5
    probability = min(65, 35 + bilateral * 5 + len(shared) * 3) if enough_history else None
    evidence = (
        Evidence("Complementary position needs", ", ".join(shared) or "None", len(shared) * 15, "Decision Engine needs are compared with the other roster's observable depth surplus.", "Decision Engine"),
        Evidence("Conflicting priorities", ", ".join(conflicts) or "None", -len(conflicts) * 5, "Shared needs may reduce easy asset matches.", "Decision Engine"),
        Evidence("Previous bilateral trades", str(bilateral), min(bilateral, 3) * 5, "Completed cached trades provide a limited familiarity signal, not a personal inference.", "Sleeper cached transactions"),
    )
    forecast = NegotiationForecast(
        "Open with a balanced Asset Intelligence package addressing an observed roster need.",
        "Expect a counter emphasizing this Front Office's documented asset preferences." if any(p.strength == "Observed" for p in second.asset_preferences) else "No evidence-supported counter pattern is available; use a neutral value-balanced structure.",
        probability,
        "Do not exceed the Trade Intelligence package boundary or sacrifice the Active Front Office's independent future outlook.",
        ("Player plus pick", "Tier-down package", "Equivalent positional target"),
        tuple(second.constraints[:2]),
        (("Acceptance probability is conservative and based only on sufficient completed trade history.",) if probability is not None else ("Acceptance probability is unavailable because cached trade history is insufficient.",)),
        evidence,
    )
    difficulty = "Favorable" if score >= 75 else "Workable" if score >= 55 else "Difficult"
    return CompatibilityReport(first.roster_id, second.roster_id, score, difficulty, shared, conflicts, themes, bilateral, forecast, evidence)


def build_league_model(data: dict[str, Any], decisions: dict[int, TeamDecision] | None = None) -> LeagueFrontOfficeModel:
    teams = data.get("teams") or []
    league = data.get("league") or {}
    league_id = str(league.get("league_id") or "configured-league")
    settings = {**(data.get("league_settings") or {}), "roster_positions": league.get("roster_positions") or []}
    decisions = decisions or {int(team.get("roster_id") or 0): evaluate_team(data, int(team.get("roster_id") or 0), DecisionContext(int(team.get("roster_id") or 0), league_id, settings)) for team in teams}
    reports = {roster_id: _profile(decision, data) for roster_id, decision in decisions.items()}
    compatibilities = {}
    relationships = []
    for first_id, second_id in combinations(sorted(reports), 2):
        report = _compatibility(data, reports[first_id], reports[second_id])
        compatibilities[(first_id, second_id)] = report
        relationships.append(RelationshipEdge(first_id, second_id, report.bilateral_trades, report.score))
    return LeagueFrontOfficeModel(reports, compatibilities, tuple(relationships))


class FrontOfficeIntelligence:
    def league(self, data: dict[str, Any], decisions: dict[int, TeamDecision] | None = None) -> LeagueFrontOfficeModel:
        return build_league_model(data, decisions)

    def report(self, data: dict[str, Any], roster_id: int, decision: TeamDecision | None = None) -> FrontOfficeReport:
        if decision is not None:
            if decision.profile.roster_id != roster_id:
                raise ValueError("The supplied Decision Engine report belongs to a different Front Office.")
            return _profile(decision, data)
        model = self.league(data)
        if roster_id not in model.reports:
            raise ValueError(f"Front Office {roster_id} is not available.")
        return model.reports[roster_id]


front_office_intelligence = FrontOfficeIntelligence()

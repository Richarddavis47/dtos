"""Deterministic organizational behavior analysis from cached fantasy actions."""
from __future__ import annotations

from itertools import combinations
from typing import Any
from src.core.fois.configuration import DEFAULT_FOIS_CONFIGURATION

from src.core.asset_intelligence import AssetContext, Evidence
from src.core.asset_intelligence.portfolio import evaluate_pick_portfolio
from src.core.decision_engine import TeamDecision
from src.core.front_office_intelligence.models import (
    ActivityProfile, AssetPreference, CompatibilityReport, FrontOfficeReport,
    LeagueFrontOfficeModel, NegotiationForecast, RelationshipEdge,
)


def _canonical_transactions(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only synchronized current actions; history arrives via Step 5 evidence."""
    return list(data.get("transactions") or [])


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
    shared = (data.get("front_office_evidence") or {}).get(str(roster_id))
    if shared is not None:
        counts["trade"] = int(shared.get("transaction_count") or 0)
    transactions = (
        list(data.get("transactions") or ())
        if shared is not None else _canonical_transactions(data)
    )
    for item in transactions:
        if roster_id not in _roster_ids(item):
            continue
        kind = str(item.get("type") or "").lower()
        if kind in counts and not (kind == "trade" and shared is not None):
            counts[kind] += 1
        if isinstance(item.get("drops"), dict) and roster_id in _roster_ids({"roster_ids": item["drops"].values()}):
            counts["drop"] += 1
    total = sum(counts.values())
    level = f"{counts['trade']} observed completed trades; observation period not established"
    evidence = (
        Evidence("Completed trades", str(counts["trade"]), counts["trade"], "Counts cached transactions involving this roster.", "Sleeper cached transactions"),
        Evidence("Roster transactions", str(total - counts["trade"]), total - counts["trade"], "Counts cached waiver, add, and drop actions involving this roster.", "Sleeper cached transactions"),
        Evidence("Draft assets owned", str(pick_count), pick_count, "Current owned picks provide observable draft-strategy context.", "Sleeper cached pick ledger"),
    )
    return ActivityProfile(level, counts["trade"], counts["waiver"], counts["free_agent"], counts["drop"], pick_count, evidence)


def _profile(decision: TeamDecision, data: dict[str, Any]) -> FrontOfficeReport:
    profile = decision.profile
    activity = _activity(data, profile.roster_id, profile.draft_pick_count)
    if decision.competitive_window is None:
        raise ValueError("Front Office Intelligence requires the canonical competitive-window contract.")
    asset_context = AssetContext(profile.league_id, profile.roster_id, profile.league_settings, decision.competitive_window.classification.value, profile.strategy)
    pick_portfolio = evaluate_pick_portfolio(profile.picks, asset_context)
    philosophies: list[str] = []
    if decision.current_outlook.score is None or decision.future_outlook.score is None:
        philosophies.append("Competitive direction unavailable")
    elif decision.current_outlook.score >= decision.future_outlook.score + 10:
        philosophies.append("Win Now")
    elif decision.future_outlook.score >= decision.current_outlook.score + 10:
        philosophies.append("Long-Term Builder")
    else:
        philosophies.append("Balanced")
    if profile.draft_pick_count >= 10:
        philosophies.append("Draft-capital holdings")
    # Portfolio magnitude cannot establish a manager's investment philosophy.
    minimum_tendencies = DEFAULT_FOIS_CONFIGURATION.minimum_sample_sizes['tendencies']
    known = len(profile.known_ages)
    young_share = profile.young_player_count / known if known else 0
    veteran_share = profile.veteran_player_count / known if known else 0
    preferences: list[AssetPreference] = []
    if known and young_share >= .35:
        preferences.append(AssetPreference("Youth-heavy current roster", "Current holdings", (Evidence("Age 24 and under", f"{profile.young_player_count} of {known}", young_share * 100, "Current holdings do not establish a historical preference for acquiring youth.", "Sleeper roster ages"),)))
    if known and veteran_share >= .35:
        preferences.append(AssetPreference("Veteran-heavy current roster", "Current holdings", (Evidence("Age 28 and older", f"{profile.veteran_player_count} of {known}", veteran_share * 100, "Current holdings do not establish a historical preference for acquiring veterans.", "Sleeper roster ages"),)))
    if profile.draft_pick_count >= 10:
        preferences.append(AssetPreference("Draft-capital holdings", "Current holdings", (Evidence("Draft assets owned", str(profile.draft_pick_count), profile.draft_pick_count, "Owned picks describe current capital, not an observed acquisition preference.", "Sleeper cached pick ledger"),)))
    if not preferences:
        preferences.append(AssetPreference("No strong preference established", "Neutral", (Evidence("Preference sample", "Insufficient differentiating evidence", 0, "DTOS does not assign an asset preference without an observable threshold.", "Cached roster and transaction history", False),)))
    shared_behavior = (data.get("gm_behavioral_intelligence") or {}).get(str(profile.roster_id)) or {}
    first, last = shared_behavior.get("first_observed_at"), shared_behavior.get("last_observed_at")
    period = f" from {str(first)[:10]} to {str(last)[:10]}" if first and last else "; observation period unavailable"
    style = f"{activity.trades} observed completed trades{period}. Activity does not establish skill or selectivity."
    confidence = min(90, 35 + min(known, 20) + min(activity.trades * 5, 25) + (10 if profile.draft_pick_count else 0))
    evidence = activity.evidence + tuple(item for pref in preferences for item in pref.evidence) + (
        Evidence("Negotiation style sample", str(activity.trades), activity.trades,
                 f"Behavioral tendencies require at least {minimum_tendencies} relevant trade observations. Roster ages and pick holdings do not establish trading habits.",
                 "League-specific cached trade history", activity.trades >= minimum_tendencies),
        Evidence("Competitive window", decision.competitive_window.classification.value, 0,
            "Shared generation-bound assessment; missing direction is not rebuild behavior.", "Canonical team assessment",
            decision.competitive_window.classification.value != "Unavailable"),
        Evidence("Future capital", str(pick_portfolio.score), 0,
            "Independent pick evidence; no player/pick scalar comparison.", "Asset Intelligence"),
    )
    strengths = tuple(position for position, evaluation in decision.position_evaluations.items() if evaluation.score >= 70) or ("No position crossed the v1 strength threshold.",)
    constraints = tuple(position for position, evaluation in decision.position_evaluations.items() if evaluation.score < 55) or ("No position crossed the v1 need threshold.",)
    window = decision.competitive_window
    summary = f"{profile.team_name} is currently classified as {window.classification.value} with a {', '.join(philosophies).lower()} approach. {style}. This profile describes cached fantasy-football actions only."
    shared = (data.get("front_office_evidence") or {}).get(str(profile.roster_id))
    return FrontOfficeReport(profile.roster_id, profile.owner_name, profile.team_name, summary, window, tuple(philosophies), style, activity, tuple(preferences), strengths, constraints, confidence, evidence, decision, shared)


def _needs(decision: TeamDecision) -> set[str]:
    return {position for position, evaluation in decision.position_evaluations.items() if evaluation.score < 55}


def _surpluses(decision: TeamDecision) -> set[str]:
    targets = {"QB": 2, "RB": 4, "WR": 5, "TE": 2}
    return {position for position, room in decision.profile.position_rooms.items() if room.total_players > targets[position]}


def _compatibility(data: dict[str, Any], first: FrontOfficeReport, second: FrontOfficeReport) -> CompatibilityReport:
    first_matches = _needs(first.decision) & _surpluses(second.decision)
    second_matches = _needs(second.decision) & _surpluses(first.decision)
    if first.front_office_evidence is not None:
        bilateral = int((first.front_office_evidence.get("partner_counts") or {}).get(str(second.roster_id)) or 0)
    else:
        bilateral = sum(str(item.get("type") or "").lower() == "trade" and {first.roster_id, second.roster_id}.issubset(_roster_ids(item)) for item in _canonical_transactions(data))
    score = min(100, 40 + 15 * len(first_matches) + 15 * len(second_matches) + min(bilateral, 3) * 5)
    shared = tuple(sorted(first_matches | second_matches))
    conflicts = tuple(sorted(_needs(first.decision) & _needs(second.decision)))
    themes = tuple((["Roster Balance"] if shared else ["Value Discovery"]) + (["Established Trade Channel"] if bilateral else []))
    evidence = (
        Evidence("Complementary position needs", ", ".join(shared) or "None", len(shared) * 15, "Decision Engine needs are compared with the other roster's observable depth surplus.", "Decision Engine"),
        Evidence("Conflicting priorities", ", ".join(conflicts) or "None", -len(conflicts) * 5, "Shared needs may reduce easy asset matches.", "Decision Engine"),
        Evidence("Previous bilateral trades", str(bilateral), min(bilateral, 3) * 5, "Completed cached trades provide a limited familiarity signal, not a personal inference.", "Sleeper cached transactions"),
    )
    forecast = NegotiationForecast(
        "Open with a balanced Asset Intelligence package addressing an observed roster need.",
        "Current roster needs can inform an offer, but holdings do not establish documented acquisition preferences or a counteroffer pattern.",
        None,
        "Do not exceed the Trade Intelligence package boundary or sacrifice the Active Front Office's independent future outlook.",
        ("Player plus pick", "Tier-down package", "Equivalent positional target"),
        tuple(second.constraints[:2]),
        ("Acceptance probability is unavailable: attempted/rejected offer evidence and calibration are not available. Compatibility is an uncalibrated roster-context indicator, not a probability.",),
        evidence,
    )
    difficulty = "Favorable" if score >= 75 else "Workable" if score >= 55 else "Difficult"
    return CompatibilityReport(first.roster_id, second.roster_id, score, difficulty, shared, conflicts, themes, bilateral, forecast, evidence)


def build_league_model(data: dict[str, Any], decisions: dict[int, TeamDecision] | None = None) -> LeagueFrontOfficeModel:
    from src.core.intelligence.league_scope import league_id_from_data, scoped_evidence

    league_id = league_id_from_data(data)
    private_evidence = scoped_evidence(
        data, "front_office_evidence", expected_league_id=league_id,
    )
    if "front_office_evidence" in data:
        data = {**data, "front_office_evidence": private_evidence.rows}
    if data.get("front_office_evidence") is None:
        data = {
            **data, "transactions": _canonical_transactions(data),
            "_canonical_history_transactions_loaded": True,
        }
    teams = data.get("teams") or []
    if decisions is None:
        from src.core.intelligence.orchestrator import intelligence_orchestrator

        first_roster = int(teams[0].get("roster_id") or 0)
        # Building canonical Front Office context must not trigger a second,
        # legacy recommendation search as an incidental dependency.
        return intelligence_orchestrator.analyze(data, first_roster, include_trade_opportunities=False).front_office_model
    if any(str(decision.profile.league_id) != league_id for decision in decisions.values()):
        raise ValueError("Decision Engine output belongs to a different league.")
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

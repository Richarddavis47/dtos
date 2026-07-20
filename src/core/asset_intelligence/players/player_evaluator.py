"""Comprehensive deterministic player dossier builder."""
from __future__ import annotations

from typing import Any

from src.core.asset_intelligence.evidence import evidence_engine
from src.core.asset_intelligence.models import AssetContext, AssetEvaluation, AssetRecommendation, CoreValues, PlayerReport
from src.core.asset_intelligence.players.player_archetype import classify_archetypes
from src.core.asset_intelligence.players.player_profile import build_player_profile
from src.core.asset_intelligence.players.risk_analysis import analyze_risk
from src.core.asset_intelligence.players.value_models import dynasty_value, market_value, redraft_value, team_fit


def _recommendation(values: CoreValues, risk_level: str) -> AssetRecommendation:
    score = values.team_fit.score
    if score >= 72 and risk_level != "High":
        action, priority = "Buy", "High"
    elif score >= 58:
        action, priority = "Hold", "Medium"
    elif score <= 38:
        action, priority = "Shop Aggressively", "High"
    elif score < 50:
        action, priority = "Sell", "Medium"
    else:
        action, priority = "Hold", "Low"
    evidence = values.team_fit.evidence + values.redraft.evidence[:1] + values.dynasty.evidence[:1]
    confidence = evidence_engine.confidence(evidence)
    return AssetRecommendation(action, f"{action} is the contextual v1 posture for this Front Office; the GM makes the final decision.", priority, confidence, evidence)


def evaluate_player(player: dict[str, Any], context: AssetContext) -> PlayerReport:
    profile = build_player_profile(player)
    dynasty = dynasty_value(profile, context)
    redraft = redraft_value(profile)
    market = market_value(dynasty)
    fit = team_fit(profile, context, dynasty, redraft)
    values = CoreValues(dynasty, redraft, market, fit)
    risk = analyze_risk(profile)
    archetypes = classify_archetypes(profile, risk, dynasty.score, redraft.score)
    strengths = tuple(item.explanation for item in (*dynasty.evidence, *redraft.evidence) if item.available and item.impact > 0) or ("No evidence-backed strength exceeds the v1 baseline.",)
    weaknesses = tuple(item.explanation for item in risk.evidence if item.available and item.impact > 0) or ("No current evidence-backed weakness exceeds the v1 threshold.",)
    opportunity = {
        "Current Season": redraft,
        "2-Year Outlook": AssetEvaluation("2-Year Outlook", round((dynasty.score + redraft.score) / 2), min(dynasty.confidence, redraft.confidence), "Balanced current and dynasty horizon.", dynasty.evidence + redraft.evidence),
        "Long-Term Outlook": dynasty,
    }
    recommendation = _recommendation(values, risk.level)
    return PlayerReport(
        profile,
        f"{profile.name} is a {profile.position} evaluated from observable age, NFL status, injury status, league rules, and Front Office context.",
        redraft.summary,
        dynasty.summary,
        values,
        archetypes,
        strengths,
        weaknesses,
        risk,
        opportunity,
        recommendation,
        tuple(dict.fromkeys((*dynasty.limitations, *redraft.limitations, *market.limitations, *risk.limitations))),
    )

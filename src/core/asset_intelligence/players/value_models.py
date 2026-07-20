"""Transparent player value calculations."""
from __future__ import annotations

from src.core.asset_intelligence.evidence import evidence_engine
from src.core.asset_intelligence.models import AssetContext, AssetEvaluation, Evidence, PlayerProfile
from src.core.asset_intelligence.players.league_context import league_adjustment

LONGEVITY_PEAK = {"QB": 29, "RB": 24, "WR": 26, "TE": 27}


def _age_signal(profile: PlayerProfile) -> tuple[float, Evidence]:
    if profile.age is None:
        return 50.0, Evidence("Age curve", "Age unavailable", 0, "Age cannot contribute, so the signal remains neutral.", "Sleeper player record", False)
    peak = LONGEVITY_PEAK.get(profile.position, 26)
    distance = profile.age - peak
    score = max(15.0, min(90.0, 75 - max(distance, 0) * 7 + max(-distance, 0) * 2))
    return score, Evidence("Age curve", f"Age {profile.age:g}; {profile.position} reference {peak}", score - 50, "The value is adjusted against a documented position-specific longevity reference.", "Sleeper age and DTOS v1 age curve")


def dynasty_value(profile: PlayerProfile, context: AssetContext) -> AssetEvaluation:
    age_score, age_evidence = _age_signal(profile)
    roster_signal = 55 if profile.nfl_team != "Free Agent" else 35
    format_adjustment, format_evidence = league_adjustment(profile, context)
    evidence = (
        age_evidence,
        Evidence("NFL roster status", profile.nfl_team, roster_signal - 50, "An active NFL team supplies a modest opportunity signal; it does not imply a starting role.", "Sleeper NFL team"),
        format_evidence,
    )
    score = round(age_score * 0.70 + roster_signal * 0.30 + format_adjustment)
    return AssetEvaluation("Dynasty Value", score, evidence_engine.confidence(evidence), "Long-term age and roster-status signals; production and market feeds are intentionally excluded.", evidence, ("Production, contract detail, usage, and dynasty market data are unavailable.",))


def redraft_value(profile: PlayerProfile) -> AssetEvaluation:
    team_score = 60 if profile.nfl_team != "Free Agent" else 30
    injury_score = 65 if profile.injury_status == "No reported designation" else 35
    evidence = (
        Evidence("NFL opportunity", profile.nfl_team, team_score - 50, "Active NFL roster status is the available opportunity proxy.", "Sleeper NFL team"),
        Evidence("Injury designation", profile.injury_status, injury_score - 50, "A current designation reduces the present-season availability signal without predicting missed games.", "Sleeper injury status"),
        Evidence("Production and usage", "Unavailable", 0, "No production or usage feed is connected; this factor stays neutral.", "Not available", False),
    )
    score = round(team_score * 0.45 + injury_score * 0.35 + 50 * 0.20)
    return AssetEvaluation("Redraft Value", score, evidence_engine.confidence(evidence), "Current-season availability and opportunity proxy, kept separate from dynasty value.", evidence, ("Live projections, production, depth-chart role, and usage are unavailable.",))


def market_value(dynasty: AssetEvaluation) -> AssetEvaluation:
    evidence = (
        Evidence("Dynasty market consensus", "Provider unavailable", 0, "No external market feed is connected; the neutral market baseline is not inferred from the dynasty score.", "Not available", False),
    )
    return AssetEvaluation("Market Value", 50, evidence_engine.confidence(evidence, 30), "Neutral placeholder until a traceable market-consensus provider is connected.", evidence, (f"The independent dynasty evaluation is {dynasty.score}/100 but is not presented as market consensus.",))


def team_fit(profile: PlayerProfile, context: AssetContext, dynasty: AssetEvaluation, redraft: AssetEvaluation) -> AssetEvaluation:
    depth = (context.position_depth or {}).get(profile.position, 0)
    need = profile.position in context.team_needs or depth < 2
    window = context.team_window.casefold()
    if "championship" in window or "playoff" in window:
        horizon_score = redraft.score
        horizon = "current-season"
    elif "rebuild" in window or "ascension" in window:
        horizon_score = dynasty.score
        horizon = "long-term"
    else:
        horizon_score = round((dynasty.score + redraft.score) / 2)
        horizon = "balanced"
    need_score = 75 if need else 50
    evidence = (
        Evidence("Front Office window", context.team_window, horizon_score - 50, f"The {context.team_window} applies the {horizon} value horizon.", "Decision Engine team window"),
        Evidence("Position need", f"{profile.position}: {depth} rostered", need_score - 50, "A thin or explicitly identified position increases contextual fit.", "Active Front Office roster"),
        Evidence("Strategic direction", context.team_strategy, 0, "Strategy is retained as context without an unsupported numeric adjustment.", "Active Front Office context", context.team_strategy != "Unspecified"),
    )
    score = round(horizon_score * 0.75 + need_score * 0.25)
    return AssetEvaluation("Team Fit Value", score, evidence_engine.confidence(evidence), f"Fit for Front Office {context.active_front_office_id}, not a universal player ranking.", evidence)

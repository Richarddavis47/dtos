"""Observable player risk analysis."""
from __future__ import annotations

from src.core.asset_intelligence.models import Evidence, PlayerProfile, RiskReport


def analyze_risk(profile: PlayerProfile) -> RiskReport:
    evidence: list[Evidence] = []
    score = 25
    if profile.injury_status != "No reported designation":
        score += 25
        evidence.append(Evidence("Injury risk", profile.injury_status, 25, "A current injury designation increases observable availability risk.", "Sleeper injury status"))
    else:
        evidence.append(Evidence("Injury risk", "No reported designation", 0, "No current designation is reported; historical injury risk remains unknown.", "Sleeper injury status"))
    peak = {"QB": 32, "RB": 27, "WR": 29, "TE": 30}.get(profile.position, 29)
    if profile.age is None:
        evidence.append(Evidence("Age-decline risk", "Age unavailable", 0, "Age risk cannot be calculated.", "Sleeper player record", False))
    elif profile.age >= peak:
        impact = min(30, round((profile.age - peak + 1) * 8))
        score += impact
        evidence.append(Evidence("Age-decline risk", f"Age {profile.age:g}; threshold {peak}", impact, "Age is at or above the position-specific v1 risk threshold.", "Sleeper age and DTOS threshold"))
    else:
        evidence.append(Evidence("Age-decline risk", f"Age {profile.age:g}; threshold {peak}", 0, "Age is below the position-specific v1 risk threshold.", "Sleeper age and DTOS threshold"))
    evidence.extend((
        Evidence("Role security", "Unavailable", 0, "Depth-chart and contract feeds are not connected.", "Not available", False),
        Evidence("Market volatility", "Unavailable", 0, "Historical market movement is not connected.", "Not available", False),
    ))
    bounded = max(0, min(100, score))
    level = "High" if bounded >= 65 else "Moderate" if bounded >= 40 else "Low"
    return RiskReport(bounded, level, tuple(evidence), ("Coaching changes, role competition, team changes, and historical injuries are not modeled.",))

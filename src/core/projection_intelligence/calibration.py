"""Deterministic player-specific calibration for Forward Production."""
from __future__ import annotations

from statistics import mean, pstdev
from typing import Any


POSITION_PRIORS = {"QB": 16.0, "RB": 10.0, "WR": 9.5, "TE": 7.0, "K": 7.0, "DEF": 7.0}
UNAVAILABLE = {"out", "ir", "pup", "suspended", "inactive"}


def _numbers(value: Any) -> list[float]:
    if not isinstance(value, (list, tuple)):
        return []
    rows = []
    for item in value:
        try:
            if item is not None:
                rows.append(float(item))
        except (TypeError, ValueError):
            continue
    return rows


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def role_context(player: dict[str, Any]) -> tuple[str, float, int]:
    """Return a public role label, prior multiplier, and certainty score."""
    slot = str(player.get("roster_slot") or "").casefold()
    depth = _number(player.get("depth_chart_order"))
    status = str(player.get("injury_status") or player.get("status") or "active").casefold()
    nfl_team = str(player.get("team") or player.get("nfl_team") or "").strip()
    if status in UNAVAILABLE:
        return "Unavailable", 0.0, 90
    if not nfl_team or nfl_team.casefold() in {"fa", "free agent", "none"}:
        return "Free agent", 0.20, 80
    if slot == "starter" or depth == 1:
        return "Starter", 1.08, 85
    if slot in {"taxi", "ir"}:
        return "Developmental reserve", 0.30, 80
    if slot == "bench" or (depth is not None and depth >= 3):
        return "Reserve", 0.48, 75
    if depth == 2:
        return "Committee / backup", 0.68, 65
    return "Role uncertain", 0.72, 35


def raw_projection(
    player: dict[str, Any], scoring: dict[str, Any], season: int, week: int | None,
) -> dict[str, Any]:
    """Build the independent DTOS forecast before external calibration."""
    player_id = str(player.get("id") or player.get("player_id"))
    position = str(player.get("position") or "").upper()
    bye = player.get("bye_week") == week and week is not None
    availability = str(player.get("injury_status") or player.get("status") or "active").casefold()
    recent = _numbers(player.get("fantasy_points_history") or player.get("recent_points"))[-8:]
    recent_short = recent[-4:]
    season_average = _number(player.get("season_average") or player.get("fantasy_points_per_game"))
    previous_average = _number(player.get("previous_season_average"))
    role, role_multiplier, role_certainty = role_context(player)
    prior = POSITION_PRIORS.get(position, 5.0)
    evidence: list[tuple[str, float, float]] = []
    if season_average is not None:
        evidence.append(("current-season production", season_average, 0.45))
    if recent_short:
        evidence.append(("recent production", mean(recent_short), 0.40))
    if previous_average is not None:
        evidence.append(("previous-season production", previous_average, 0.15))
    if evidence:
        weight = sum(row[2] for row in evidence)
        player_rate = sum(value * item_weight for _, value, item_weight in evidence) / weight
        base = player_rate * 0.82 + prior * role_multiplier * 0.18
        fallback_state = "player_specific" if len(evidence) >= 2 else "partially_individualized"
    else:
        base = prior * role_multiplier
        fallback_state = "role_adjusted_prior" if role != "Role uncertain" else "position_baseline"
    reception = _number(scoring.get("rec")) or 0.0
    te_premium = (_number(scoring.get("bonus_rec_te") or scoring.get("rec_te")) or 0.0) if position == "TE" else 0.0
    pass_td = _number(scoring.get("pass_td")) or 4.0
    scoring_multiplier = 1 + ((reception - 0.5) * 0.10 if position != "QB" else (pass_td - 4) * 0.05) + te_premium * 0.06
    injury_multiplier = 0.0 if availability in UNAVAILABLE else 0.72 if availability in {"doubtful", "questionable"} else 1.0
    median = None if bye else max(0.0, base * scoring_multiplier * injury_multiplier)
    evidence_depth = min(100, len(recent) * 7 + (28 if season_average is not None else 0) + (12 if previous_average is not None else 0) + role_certainty // 4)
    confidence = max(15, min(90, round(24 + evidence_depth * 0.55 + role_certainty * 0.18 - (18 if availability not in {"", "active", "none"} else 0))))
    spread = max(2.5, pstdev(recent_short) if len(recent_short) > 1 else (median or prior) * (0.28 if evidence else 0.42))
    weekly = round(median, 2) if median is not None else None
    games = max(0, 18 - int(week or 1))
    return {
        "player_id": player_id, "position": position, "week": week, "season": season,
        "raw_dtos_projection": weekly, "weekly_projected_points": weekly,
        "weekly_floor": round(max(0.0, median - spread), 2) if median is not None else None,
        "weekly_median": weekly,
        "weekly_ceiling": round(median + spread * 1.35, 2) if median is not None else None,
        "rest_of_season_points": round(median * games, 2) if median is not None else None,
        "rest_of_season_games": games,
        "season_projected_points": round(median * 17, 2) if median is not None else None,
        "expected_points_per_game": weekly,
        "expected_usage": "Player-specific production and current role" if evidence else "Current role applied to a positional prior",
        "expected_role": role,
        "projection_confidence": confidence,
        "projection_agreement": None,
        "projection_coverage": "available" if weekly is not None else ("bye" if bye else "unavailable"),
        "sources": ["dtos_forward_production"],
        "status": "bye" if bye else "unavailable" if availability in UNAVAILABLE else fallback_state,
        "availability": availability,
        "fallback_state": fallback_state,
        "evidence_depth": evidence_depth,
        "evidence_fields": [name for name, _, _ in evidence] + (["current role"] if role_certainty >= 60 else []),
        "role_certainty": role_certainty,
        "limitations": [] if evidence else ["Verified player production history is unavailable; current role and external evidence carry more weight."],
    }


def calibrate(
    raw: dict[str, Any], sleeper_value: Any, *, sleeper_freshness: str,
) -> dict[str, Any]:
    """Combine independent DTOS evidence with cached Sleeper evidence."""
    raw_value = _number(raw.get("raw_dtos_projection"))
    sleeper = _number(sleeper_value)
    if raw_value is None:
        return {**raw, "sleeper_projection": sleeper, "dtos_projection": None,
                "canonical_projection": None, "calibration_adjustment": None,
                "calibration_reason": "No active weekly projection is available.",
                "projection_difference": None, "large_disagreement": None,
                "sleeper_zero_state": "numeric_zero" if sleeper == 0 else "missing" if sleeper is None else "projected"}
    if sleeper is None:
        return {**raw, "sleeper_projection": None, "dtos_projection": raw_value,
                "canonical_projection": raw_value, "calibration_adjustment": 0.0,
                "calibration_reason": "Sleeper evidence is unavailable; DTOS uses its documented player and role evidence.",
                "projection_difference": None, "projection_agreement": "Unavailable",
                "large_disagreement": None, "sleeper_zero_state": "missing"}

    depth = int(raw.get("evidence_depth") or 0)
    role = str(raw.get("expected_role") or "Role uncertain")
    if depth >= 70:
        sleeper_weight = 0.28
    elif depth >= 45:
        sleeper_weight = 0.48
    else:
        sleeper_weight = 0.72
    if sleeper_freshness != "Fresh":
        sleeper_weight *= 0.65
    if sleeper == 0:
        if role in {"Free agent", "Reserve", "Developmental reserve", "Unavailable"}:
            sleeper_weight = max(sleeper_weight, 0.82)
            zero_state = "verified_low_opportunity"
        else:
            sleeper_weight = min(sleeper_weight, 0.35)
            zero_state = "possible_feed_gap"
    else:
        zero_state = "projected"
    calibrated = raw_value * (1 - sleeper_weight) + sleeper * sleeper_weight
    if role in {"Reserve", "Developmental reserve", "Free agent"} and sleeper <= 4:
        calibrated = min(calibrated, sleeper + 2.5)
    calibrated = round(max(0.0, calibrated), 2)
    adjustment = round(calibrated - raw_value, 2)
    difference = round(calibrated - sleeper, 2)
    magnitude = abs(difference)
    agreement = "High" if magnitude <= 2 else "Moderate" if magnitude < 5 else "Low"
    severity = "extreme" if magnitude >= 12 else "large" if magnitude >= 8 else "meaningful" if magnitude >= 5 else None
    if abs(adjustment) < 0.01:
        reason = "DTOS player-specific evidence already agrees with the cached Sleeper projection."
    elif calibrated > raw_value:
        reason = f"Sleeper projects {sleeper:.1f}; DTOS raises its raw forecast because external evidence and the player's {role.lower()} context support more production."
    else:
        reason = f"Sleeper projects {sleeper:.1f}; DTOS lowers its raw forecast because cached external evidence and the player's {role.lower()} context support less production."
    confidence = max(20, min(95, round((int(raw.get("projection_confidence") or 20) * (1 - sleeper_weight * 0.35)) + (72 if sleeper_freshness == "Fresh" else 50) * sleeper_weight * 0.35 - min(magnitude, 12))))
    raw_floor = _number(raw.get("weekly_floor")) or max(0.0, raw_value * 0.65)
    raw_ceiling = _number(raw.get("weekly_ceiling")) or raw_value * 1.35
    floor_ratio = raw_floor / raw_value if raw_value else 0.65
    ceiling_ratio = raw_ceiling / raw_value if raw_value else 1.35
    games = int(raw.get("rest_of_season_games") or 0)
    return {
        **raw,
        "sleeper_projection": round(sleeper, 2),
        "dtos_projection": calibrated,
        "canonical_projection": calibrated,
        "weekly_projected_points": calibrated,
        "weekly_median": calibrated,
        "weekly_floor": round(max(0.0, calibrated * floor_ratio), 2),
        "weekly_ceiling": round(calibrated * ceiling_ratio, 2),
        "expected_points_per_game": calibrated,
        "rest_of_season_points": round(calibrated * games, 2),
        "season_projected_points": round(calibrated * 17, 2),
        "calibration_adjustment": adjustment,
        "calibration_weight_sleeper": round(sleeper_weight, 3),
        "calibration_reason": reason,
        "projection_difference": difference,
        "projection_difference_percent": round(difference / abs(sleeper) * 100, 2) if sleeper else None,
        "projection_agreement": agreement,
        "projection_confidence": confidence,
        "large_disagreement": {"severity": severity, "absolute_difference": round(magnitude, 2), "supported_by": list(raw.get("evidence_fields") or ())} if severity else None,
        "sleeper_zero_state": zero_state,
        "sources": ["dtos_forward_production", "sleeper_projections"],
    }

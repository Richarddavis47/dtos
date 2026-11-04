"""Candidate, market-independent player methodology and auditable contributions.

This pure model accepts already-pinned STANDARD reference evidence, never league
PPG, provider prices, owner identity or a player name. It is not yet the published
production methodology. Empirical panel acceptance is required before promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite
from typing import Any


METHOD_VERSION = "batch3-production-lifecycle-candidate-3"
REFERENCE_SCORING = "ppr1-pass4-reference-v1"


@dataclass(frozen=True)
class PositionCurve:
    production_scale: float
    usage_scale: float | None
    longevity_reference: float
    decline_per_year: float
    recency_weights: tuple[float, ...]


# Transparent candidate reference scales, NOT fitted player targets or claims
# about empirical retirement probabilities. Audit before production promotion.
CURVES = {
    "QB": PositionCurve(18, None, 29, 3, (1, .8, .6, .4)),
    "RB": PositionCurve(12, 18, 24, 7, (1, .55, .25, .10)),
    "WR": PositionCurve(12, 8, 26, 4, (1, .7, .45, .25)),
    "TE": PositionCurve(9, 6, 27, 3.5, (1, .8, .55, .35)),
}


@dataclass(frozen=True)
class ReferenceSeason:
    season: int
    games: int
    ppg: float | None
    usage: float | None = None
    scoring: str = REFERENCE_SCORING


@dataclass(frozen=True)
class ModelComponent:
    name: str
    score: float
    weight: float
    contribution: float


@dataclass(frozen=True)
class IntrinsicAssessment:
    value: int | None
    confidence: int
    components: tuple[ModelComponent, ...]
    seasons: tuple[int, ...]
    limitations: tuple[str, ...]
    method_version: str = METHOD_VERSION
    scoring_reference: str = REFERENCE_SCORING
    season_weights: tuple[tuple[int, float], ...] = ()
    effective_games: float = 0
    usage_season: int | None = None


def _finite(value: float | None) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value)):
        raise ValueError("Model inputs must be finite canonical numbers or unavailable.")


def _saturating(value: float, scale: float) -> float:
    # Smooth response prevents arbitrary tier cliffs and unbounded outliers.
    return 100 * (1 - exp(-max(0, value) / scale))


def assess_intrinsic(*, position: str, age: float | None, current_season: int,
                     seasons: tuple[ReferenceSeason, ...]) -> IntrinsicAssessment:
    """Current dynasty quality, not retrospective decision-time intelligence.

    Production is the primary performance signal. Usage is a bounded supporting
    role signal from the SAME sample, not an independent confidence vote. Age
    affects remaining horizon modestly; young age alone never creates a value.
    Sample depth controls confidence, not a hidden penalty on measured quality.
    Season weights cap game-count influence at eight games so a short season
    does not erase an established season; missing seasons are never zero-filled.
    Last season can inform today's dynasty assessment but stays labelled
    last season and cannot populate a current-season actual statistic.
    """
    _finite(age)
    curve = CURVES.get(position)
    if curve is None:
        return IntrinsicAssessment(None, 0, (), (), ("Unsupported position.",))
    if len(seasons) > 8 or len({row.season for row in seasons}) != len(seasons):
        raise ValueError("At most eight distinct season summaries are supported.")
    for row in seasons:
        if row.scoring != REFERENCE_SCORING or not current_season - 7 <= row.season <= current_season:
            raise ValueError("Reference scoring/season boundary mismatch.")
        if isinstance(row.games, bool) or not isinstance(row.games, int) or not 0 <= row.games <= 26:
            raise ValueError("Invalid canonical season sample count.")
        _finite(row.ppg)
        _finite(row.usage)
        if row.usage is not None and row.usage < 0:
            raise ValueError("Usage cannot be negative.")
    usable = [row for row in sorted(seasons, key=lambda row: row.season) if row.ppg is not None and row.games > 0]
    if not usable:
        return IntrinsicAssessment(None, 0, (), (), (
            "No scored NFL sample; age, rookie status and Market price do not fabricate intrinsic performance.",))
    # Use at most four recent seasons for quality, with position-specific decay.
    # Older history can establish career depth but cannot override recent quality.
    latest_year = max(row.season for row in usable)
    career_depth = len(usable)
    usable = [row for row in usable if latest_year - row.season < len(curve.recency_weights)]
    weights = [curve.recency_weights[latest_year - row.season] * min(row.games, 8) / 8 for row in usable]
    total = sum(weights)
    effective_games = sum(row.games * curve.recency_weights[latest_year - row.season] for row in usable)
    reliability = 1 - exp(-effective_games / 20)
    ppg = sum(row.ppg * weight for row, weight in zip(usable, weights, strict=True)) / total
    performance = _saturating(ppg, curve.production_scale)
    inputs = [("reference_production", performance, .75)]
    limitations = ["Candidate reference scales require empirical calibration; confidence is evidence support, not outcome probability."]
    # Production smooths demonstrated performance; supporting role uses the
    # latest observed season, not a career average that masks a role transition.
    # Never replace missing latest usage with an older role or invented future.
    latest = usable[-1]
    usage_season = None
    if curve.usage_scale is not None and latest.usage is not None:
        usage = latest.usage
        usage_season = latest.season
        inputs.append(("supporting_usage", _saturating(usage, curve.usage_scale), .10))
        limitations.append(f"Usage describes observed season {latest.season}; it is not proof of the current or future role.")
    else:
        limitations.append("Comparable usage unavailable; omitted rather than inferred.")
    if age is not None:
        lifecycle = max(10, 75 - max(0, age - curve.longevity_reference) * curve.decline_per_year)
        inputs.append(("position_lifecycle", lifecycle, .15))
    else:
        limitations.append("Age unavailable; lifecycle contribution omitted.")
    if not any(row.season == current_season for row in usable):
        limitations.append("Performance is prior-season evidence, not current-season production.")
    total_weight = sum(weight for _, _, weight in inputs)
    components = tuple(ModelComponent(name, round(score, 4), round(weight / total_weight, 6),
        round(score * weight / total_weight * 10, 4)) for name, score, weight in inputs)
    value = round(sum(component.contribution for component in components))
    gap = max(0, current_season - 1 - latest_year)
    if gap:
        limitations.append("No recent-season production; retained older quality is not proof of current health or role.")
    confidence = round(90 * reliability * min(1, .75 + .1 * career_depth)
        * .75 ** gap * (1 if age is not None else .9))
    return IntrinsicAssessment(value, confidence, components, tuple(row.season for row in usable), tuple(limitations),
        season_weights=tuple((row.season, round(weight / total, 6)) for row, weight in zip(usable, weights, strict=True)),
        effective_games=round(effective_games, 4), usage_season=usage_season)


def assess_prepared_intrinsic(*, prepared: dict[str, Any], league_id: str,
                              player_id: str, position: str, age: float | None) -> IntrinsicAssessment:
    """Read only pinned reference summaries; never use the league-scored PPG."""
    if str(prepared.get("league_id") or "") != league_id:
        raise ValueError("Prepared evidence belongs to another league context.")
    if prepared.get("reference_scoring") != REFERENCE_SCORING:
        return IntrinsicAssessment(None, 0, (), (), ("Canonical reference-scored evidence has not been prepared.",))
    season = int(prepared["season"])
    player = (prepared.get("players") or {}).get(player_id) or {}
    if 'reference_seasons' in player:
        summaries = tuple(ReferenceSeason(row['season'], row['games'], row['ppg'],
            row.get('opportunities') if position == 'RB' else row.get('targets') if position in {'WR', 'TE'} else None)
            for row in player['reference_seasons'])
        return assess_intrinsic(position=position, age=age, current_season=season, seasons=summaries)
    windows = {row["label"]: row for row in (player.get("reference_production") or {}).get("windows") or ()}
    seasons = []
    for label, year, sample_key in (("Season Average", season, "current_sample_count"),
                                    ("Previous Season Average", season - 1, "previous_sample_count")):
        window = windows.get(label) or {}
        usage = window.get("opportunities") if position == "RB" else window.get("targets") if position in {"WR", "TE"} else None
        seasons.append(ReferenceSeason(year, player.get(sample_key, 0), window.get("fantasy_points"), usage))
    return assess_intrinsic(position=position, age=age, current_season=season, seasons=tuple(seasons))

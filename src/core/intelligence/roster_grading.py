"""Explicit roster dimensions; price, points and quality never share a scalar."""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class PlayerGradingEvidence:
    player_id: str
    market_price: float | None
    production_quality: float | None
    projected_points: float | None
    longevity_context: float | None
    evidence_confidence: int
    market_confidence: int = 0
    projection_confidence: int = 0


@dataclass(frozen=True)
class GradeDimension:
    concept: str
    value: float | None
    units: str
    confidence: int
    covered: int
    expected: int


@dataclass(frozen=True)
class RosterGradingEvidence:
    league_id: str
    roster_id: int
    generation: str
    dimensions: Mapping[str, GradeDimension]
    actual_starter_ids: tuple[str, ...]
    optimal_starter_ids: tuple[str, ...]
    intrinsic_dynasty_value: None = None
    overall_grade: None = None
    competitive_window: str = 'Unavailable'
    reason: str = 'An overall competitive window requires a validated multi-horizon aggregation; dimensional grades are not interchangeable.'


def grade_roster_evidence(*, league_id: str, roster_id: int, generation: str,
                         players: tuple[PlayerGradingEvidence, ...],
                         actual_starter_ids: tuple[str, ...], optimal_starter_ids: tuple[str, ...],
                         actual_points: float | None, optimal_points: float | None,
                         legal_backup_points: float | None) -> RosterGradingEvidence:
    """Publish supported dimensions without inventing an overall letter grade.

    Optimal and legal-backup points come from the canonical legal-lineup solver,
    not sums of bench prices. Production quality and longevity are descriptive
    means only; neither is an intrinsic asset valuation or a future forecast.
    """
    if not league_id or not generation:
        raise ValueError('League and semantic generation are required')
    ids = {player.player_id for player in players}
    if len(ids) != len(players) or '' in ids:
        raise ValueError('Unique player identities required')
    for selected in (actual_starter_ids, optimal_starter_ids):
        if len(set(selected)) != len(selected) or not set(selected) <= ids:
            raise ValueError('Lineup must belong to this roster without duplicates')
    for player in players:
        for value in (player.market_price, player.production_quality, player.projected_points, player.longevity_context):
            if value is not None and (isinstance(value, bool) or not isfinite(value)):
                raise ValueError('Evidence must be finite or unavailable')
    for value in (actual_points, optimal_points, legal_backup_points):
        if value is not None and (isinstance(value, bool) or not isfinite(value)):
            raise ValueError('Lineup evidence must be finite or unavailable')
    dimensions = {}

    def aggregate(key: str, field: str, units: str, *, average: bool = False):
        values = [getattr(player, field) for player in players if getattr(player, field) is not None]
        complete = bool(players) and len(values) == len(players)
        value = sum(values) / (len(values) if average else 1) if complete else None
        confidence_field = 'market_confidence' if field == 'market_price' else 'evidence_confidence'
        dimensions[key] = GradeDimension(key, value, units,
            min((getattr(player, confidence_field) for player in players), default=0) if complete else 0,
            len(values), len(players))

    aggregate('Market asset strength', 'market_price', 'canonical Market price units')
    aggregate('Production quality', 'production_quality', 'mean demonstrated quality /100', average=True)
    aggregate('Longevity context', 'longevity_context', 'mean position-specific age context /100; not a forecast', average=True)
    for name, value, count in (
        ('Actual lineup expectation', actual_points, len(actual_starter_ids)),
        ('Optimal projected lineup', optimal_points, len(optimal_starter_ids)),
        ('Useful projected depth', legal_backup_points, len(players) - len(optimal_starter_ids)),
    ):
        dimensions[name] = GradeDimension(name, value, 'weekly projected points',
            min((p.projection_confidence for p in players), default=0) if value is not None else 0,
            count if value is not None else 0, count)
    return RosterGradingEvidence(league_id, roster_id, generation, dimensions,
                                actual_starter_ids, optimal_starter_ids)


def rank_roster_dimension(rows: tuple[RosterGradingEvidence, ...], concept: str) -> dict[int, int | None]:
    """Only compare the same concept in the same league and generation."""
    if len({(row.league_id, row.generation) for row in rows}) > 1:
        raise ValueError('Cannot compare cross-league or mixed-generation assessments')
    if len({row.roster_id for row in rows}) != len(rows):
        raise ValueError('Duplicate franchise assessment')
    values = {row.roster_id: row.dimensions[concept].value for row in rows}
    return {key: None if value is None else 1 + sum(other is not None and other > value for other in values.values())
            for key, value in values.items()}

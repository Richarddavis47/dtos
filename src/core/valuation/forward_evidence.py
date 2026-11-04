"""Pinned, public forward context. No inferred recovery time or market priors.

This boundary distinguishes what is observed now from historical quality. A
weekly projection cannot become a season/dynasty expectation by multiplication.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

from .player_methodology import REFERENCE_SCORING


@dataclass(frozen=True)
class ForwardEvidence:
    player_id: str
    observed_at: str
    expires_at: str
    generation: str
    team: str | None = None
    status: str | None = None
    injury_designation: str | None = None
    depth_order: int | None = None
    projection_player_id: str | None = None
    projection_season: int | None = None
    projection_week: int | None = None
    projected_points: float | None = None
    projection_reference: str | None = None
    projection_row_present: bool | None = None
    projection_stats_present: bool | None = None
    projection_applicable: bool | None = None


def _time(value):
    timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if timestamp.tzinfo is None:
        raise ValueError('Evidence times must carry an explicit timezone.')
    return timestamp.astimezone(timezone.utc)


def assess_forward_context(evidence: ForwardEvidence, *, player_id: str,
                           season: int, week: int, as_of: str) -> dict:
    if evidence.player_id != player_id or not evidence.generation:
        raise ValueError('Forward evidence identity/generation mismatch.')
    observed, expires, boundary = map(_time, (evidence.observed_at, evidence.expires_at, as_of))
    if expires <= observed:
        raise ValueError('Forward evidence expiry must follow observation.')
    fresh = observed <= boundary < expires
    projection_matches = (evidence.projection_player_id == player_id
        and evidence.projection_season == season and evidence.projection_week == week
        and evidence.projection_reference == REFERENCE_SCORING)
    if evidence.projected_points is not None and (isinstance(evidence.projected_points, bool)
        or not isinstance(evidence.projected_points, (int, float)) or not isfinite(evidence.projected_points)):
        raise ValueError('Projection must be finite or missing.')
    if not fresh:
        projection_state = 'unavailable_at_boundary'
    elif evidence.projection_applicable is False:
        projection_state = 'not_applicable'
    elif evidence.projection_row_present is False:
        projection_state = 'provider_missing_player'
    elif not projection_matches:
        projection_state = 'boundary_mismatch'
    elif evidence.projection_stats_present is not True or evidence.projected_points is None:
        projection_state = 'no_projection'
    elif evidence.projected_points == 0:
        unavailable = {'out', 'ir', 'pup', 'suspended', 'inactive'}
        projection_state = ('zero_with_unavailable_status' if
            str(evidence.injury_designation or '').casefold() in unavailable or
            str(evidence.status or '').casefold() in unavailable else 'supported_numeric_zero')
    else:
        projection_state = 'projected'
    points = evidence.projected_points if projection_state in {
        'projected', 'supported_numeric_zero', 'zero_with_unavailable_status'} else None
    # Neither "Active" nor depth order is a probability of playing/starting.
    # Missing team metadata does not prove retirement or zero future value.
    return {'player_id': player_id, 'generation': evidence.generation,
        'availability': 'current' if fresh else 'unavailable_at_boundary',
        'current_team': evidence.team if fresh else None,
        'current_status': evidence.status if fresh else None,
        'injury_designation': evidence.injury_designation if fresh else None,
        'depth_order': evidence.depth_order if fresh else None,
        'weekly_reference_projection': points, 'projection_season': season, 'projection_week': week,
        'projection_state': projection_state,
        'forward_dynasty_utility': None,
        'reason_codes': tuple(code for code, applies in (
            ('FORWARD_CONTEXT_NOT_CURRENT', not fresh),
            ('PROJECTION_BOUNDARY_UNSUPPORTED', not projection_matches),
            ('WEEKLY_PROJECTION_UNAVAILABLE', points is None),
            ('INJURY_DESIGNATION_NOT_RECOVERY_FORECAST', fresh and bool(evidence.injury_designation)),
            ('DEPTH_ORDER_NOT_USAGE_SHARE', fresh and evidence.depth_order is not None),
            ('SCALAR_HORIZON_COMBINATION_NOT_VALIDATED', True)) if applies)}

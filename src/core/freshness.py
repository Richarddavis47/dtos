"""Canonical, family-aware freshness semantics.

Exact evidence age is operational metadata.  DTOS semantics change only when an
observation crosses one of the documented evidence-quality boundaries below.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final


FRESHNESS_POLICY_VERSION: Final = "2.0"


@dataclass(frozen=True)
class FreshnessPolicy:
    fresh_until_hours: float
    aging_until_hours: float
    stale_until_hours: float
    immutable: bool = False


@dataclass(frozen=True)
class FreshnessAssessment:
    age_hours: float | None
    tier: str
    semantic_weight: int
    next_tier: str | None
    next_threshold_hours: float | None
    hours_until_threshold: float | None
    policy_version: str = FRESHNESS_POLICY_VERSION

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


# Projections must react within an active scoring day. Dynasty markets move more
# slowly, league transactions have medium-lived relevance, and completed
# historical evidence is immutable rather than time-decaying.
_PROJECTION = FreshnessPolicy(1, 6, 24)
_MARKET = FreshnessPolicy(36, 72, 168)
_TRADES = FreshnessPolicy(6, 48, 168)
_PERFORMANCE = FreshnessPolicy(168, 336, 720)
_HISTORICAL = FreshnessPolicy(0, 0, 0, immutable=True)
_DEFAULT = FreshnessPolicy(24, 72, 168)

_POLICIES: Final = {
    "optional_external_projection": _PROJECTION,
    "internal_forward_model": _PROJECTION,
    "independent_projection": _PROJECTION,
    "fantasycalc_observed_market": _MARKET,
    "fantasypros_derived_market": _MARKET,
    "ktc_crowd_market": _MARKET,
    "sleeper_league_observed": _TRADES,
    "mfl_observed": _TRADES,
    "fleaflicker_observed": _TRADES,
    "nflverse_open_performance": _PERFORMANCE,
    "dtos_intrinsic": _HISTORICAL,
    "historical": _HISTORICAL,
}

_WEIGHTS: Final = {
    "Fresh": 100,
    "Aging": 90,
    "Stale": 65,
    "Very Stale": 30,
    "Unavailable": 40,
    "Immutable": 100,
}


def freshness_policy(evidence_family: str | None) -> FreshnessPolicy:
    """Return the explicit policy for an evidence family."""
    return _POLICIES.get(str(evidence_family or ""), _DEFAULT)


def assess_freshness(
    age_hours: float | int | None,
    evidence_family: str | None,
) -> FreshnessAssessment:
    """Classify exact age into a stable semantic evidence-quality tier."""
    policy = freshness_policy(evidence_family)
    if policy.immutable:
        return FreshnessAssessment(age_hours, "Immutable", 100, None, None, None)
    if age_hours is None:
        return FreshnessAssessment(None, "Unavailable", 40, None, None, None)

    age = max(0.0, float(age_hours))
    boundaries = (
        (policy.fresh_until_hours, "Fresh", "Aging"),
        (policy.aging_until_hours, "Aging", "Stale"),
        (policy.stale_until_hours, "Stale", "Very Stale"),
    )
    for threshold, tier, next_tier in boundaries:
        if age < threshold:
            return FreshnessAssessment(
                age, tier, _WEIGHTS[tier], next_tier, threshold,
                round(threshold - age, 3),
            )
    return FreshnessAssessment(age, "Very Stale", 30, None, None, None)


def freshness_policy_manifest() -> dict[str, object]:
    """Return bounded public policy metadata without runtime observations."""
    return {
        "version": FRESHNESS_POLICY_VERSION,
        "tiers": dict(_WEIGHTS),
        "families": {
            family: asdict(policy) for family, policy in sorted(_POLICIES.items())
        },
        "default": asdict(_DEFAULT),
    }

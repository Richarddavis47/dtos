"""Candidate intrinsic-quality bands, independent of external price and support.

Bands summarize the continuous score; they never change it or imply league
starter status. Thresholds require cohort acceptance before consumer promotion.
"""
from dataclasses import dataclass
from math import isfinite


TIER_METHOD_VERSION = 'intrinsic-quality-bands-candidate-1'
# Broad quality regions, not equal-sized quantiles or Market's franchise tiers.
# Keep exceptional quality distinct; a cohort need not populate every band.
BANDS = ((750, 'Exceptional quality'), (650, 'High quality'),
         (500, 'Solid quality'), (350, 'Moderate quality'), (200, 'Limited quality'),
         (0, 'Low measured quality'))


@dataclass(frozen=True)
class IntrinsicTier:
    number: int | None
    label: str
    lower_bound: int | None
    method_version: str = TIER_METHOD_VERSION
    scope: str = 'intrinsic_quality'


def intrinsic_tier(value: int | float | None) -> IntrinsicTier:
    """Missing is unavailable, never replacement; confidence is a separate axis."""
    if value is None:
        return IntrinsicTier(None, 'Unavailable', None)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 1000:
        raise ValueError('Intrinsic tiers require a finite 0–1000 intrinsic value.')
    for number, (boundary, label) in enumerate(BANDS, 1):
        if value >= boundary:
            return IntrinsicTier(number, label, boundary)
    raise AssertionError('The intrinsic band policy must cover zero.')

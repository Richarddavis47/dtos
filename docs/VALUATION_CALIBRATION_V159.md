# Valuation Calibration v1.5.9

DTOS evaluates an asset from observable evidence and keeps two concepts separate:

- **Intrinsic value** is DTOS's independent, deterministic assessment.
- **Calibrated value** combines intrinsic value with normalized public market
  consensus when supported evidence exists.

The calibrated value is the shared downstream contract for roster construction,
positional ranking, contender and rebuild profiles, and Trade Intelligence.
Market evidence never overwrites the intrinsic value.

## Player calibration

Provider values enter the existing canonical 0–1000 normalization and consensus
pipeline. The calibrated value gives market consensus between 35% and 75% weight,
bounded by consensus confidence. The remaining weight belongs to DTOS intrinsic
value. The exact weights and evidence status are returned as reasoning.

When market evidence is unavailable or insufficient, calibrated value equals
intrinsic value and DTOS withholds elite and cornerstone classification. This is
an explicit uncertainty policy, not a fabricated estimate.

Market-backed tier thresholds are 790, 675, 550, 425, 300, 200, and 100 for
Elite Franchise Player through Developmental.

## Draft-pick calibration

The deterministic round baselines are 78, 48, 25, and 12 on the internal
0–100 scale. A disclosed early or late projection changes the baseline by eight
points; an unknown slot remains neutral. Future years retain the existing small,
bounded liquidity discount.

This curve preserves the option value of first-round picks while preventing
multiple third- or fourth-round picks from being treated as an elite centerpiece.

## Golden benchmark

`tests/fixtures/golden_valuation_v159.json` is the permanent calibration set. It
contains 40 representative player profiles and 10 draft picks spanning all
supported tiers, positions, rounds, and projected slots. It asserts relationships
rather than special-casing production player IDs.

Future valuation changes must update this benchmark deliberately and explain any
changed relationship in release documentation.

## Current limitations

- DTOS does not infer an unknown rookie-pick slot.
- Sparse or stale providers reduce confidence and can prevent premium labels.
- Production projections and injury evidence remain limited to supported,
  attributable sources.
- The calibration is deterministic; it does not predict market movement.

# Valuation Intelligence Engine

DTOS v1.7.3 converts the immutable, cached Provider Network evidence contract into explainable valuation intelligence. The engine is generated after provider synchronization and never performs network I/O during application requests.

## Architecture

`Provider Network → Valuation Intelligence Engine → Valuation APIs, asset reports, calibration dashboard, DINS`

Provider observations remain immutable. The engine creates a separate read model for every canonical player and pick, preserving Market, DTOS Intrinsic, League Adjusted, Contender, and Rebuilder valuation layers independently.

## Evidence categories

Evidence is classified as Market, Trades, Performance, Historical, League Context, Team Context, Projection, or Metadata. No category automatically overrides another, and missing categories remain explicit.

## Reproducible scores

- **Coverage (0–100)** measures represented categories, independent provider families, observation availability, and intrinsic support. It measures breadth, not correctness.
- **Confidence (0–100)** combines provider agreement, measured provider reliability, identity quality, freshness, coverage, and sample size using fixed documented coefficients.
- **Agreement (0–100)** is derived from normalized dispersion across independent evidence families. Single-source assets receive deliberately limited agreement.

Provider contributions are dynamically weighted from provider reliability, freshness, observation confidence, and identity-match confidence. Correlated providers retain family lineage and do not masquerade as independent confirmation.

## Explanations and diagnostics

Every asset report includes its sources, categories, provider weights, independent-family count, missing evidence, five independent valuation layers, measurable scores, and a plain-language explanation. Diagnostics identify high-coverage/low-confidence assets, low-coverage/high-confidence assets, disagreement, missing evidence, weak historical support, missing market support, and future calibration candidates.

## Timeline

The background build stores a bounded per-asset timeline when coverage, confidence, agreement, provider count, or represented categories change. Identical regeneration is idempotent. Timeline records are explanatory observations and never mutate historical provider evidence.

## Safety and extensibility

The engine consumes cached state only, covers every canonical asset, preserves identity integrity, and cannot apply valuation adjustments. Future providers extend the immutable evidence contract; future decision systems consume the intelligence report rather than duplicating scoring logic.

# DTOS Valuation Calibration

DTOS v1.4.4 introduces a single comparison boundary for player, pick, consensus, and trade-package calculations. Raw provider observations remain available for transparency, but raw values are never compared across incompatible scales.

## Canonical scale

Comparable values use a deterministic 0–1000 scale:

- 900–1000: elite cornerstone
- 750–899: premium dynasty asset
- 600–749: strong starter or high-value asset
- 450–599: useful starter or meaningful pick
- 300–449: depth asset or secondary pick
- 150–299: speculative asset
- 1–149: minimal trade value
- 0: no reliable trade value

Risk, liquidity, and confidence remain directional 0–100 scores. Higher liquidity and confidence are better; higher risk is worse.

## Existing sources and raw scales

| Source | Raw scale | Normalization |
| --- | ---: | --- |
| FantasyCalc public dynasty API | 0–12,000 configured range | 70% provider-range position plus 30% provider-distribution percentile when at least 10 observations exist; otherwise linear |
| DynastyProcess public 2QB dataset | 0–10,000 configured range | Same provider-specific range/percentile blend |
| DTOS Asset Intelligence | 0–100 | Deterministic ×10 conversion; retained as intrinsic rather than market evidence |
| DTOS Draft Pick Intelligence | 0–100 | Deterministic ×10 conversion plus explicit round-tier adjustment |

Every normalization record retains provider, raw value, configured range, normalized value, timestamp, season, confidence, freshness, method, and normalization version.

## Consensus and confidence

Consensus accepts normalized values only. Provider weights combine configured reliability, source confidence, and exponential freshness decay. Confidence combines provider confidence, normalized agreement, and provider coverage. Spread is reported on the canonical scale. Results are labeled `calibrated`, `partially_calibrated`, `uncalibrated`, `insufficient_data`, or `stale`.

Strong buy/sell language and precise packages are suppressed when confidence or calibration is insufficient.

## Trade safety

Trade packages sum canonical trade values, then apply diminishing marginal credit, roster-slot/consolidation penalties, and an additional discount to repeated low-value pieces. Guardrails expose machine-readable rejection reasons for market-floor failures, elite-asset mismatch, low-value aggregation, superflex quarterback scarcity, low confidence, and uncalibrated data.

The engine separates market fairness from Front Office fit. It remains advisory: DTOS explains the evidence and the GM decides.

## Cache contract

Normalized crawl outputs use the normalization version in their cache namespace. A version change creates a new namespace, so values produced by an earlier method cannot survive as current calibrated results. Provider and Sleeper synchronization continue to invalidate shared crawl/intelligence caches.

## Known limits

- Provider ranges require periodic review as provider distributions evolve.
- Public sources do not provide every production, contract, injury, or liquidity input.
- Pick values do not assume an early/mid/late slot when that evidence is unavailable.
- Calibration confidence reports uncertainty; it does not predict trade acceptance.

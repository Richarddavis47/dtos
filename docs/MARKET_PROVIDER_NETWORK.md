# Multi-Source Market Intelligence Provider Network

## Philosophy and boundaries

No single provider is truth. Each approved source contributes evidence whose effective weight depends on freshness, coverage, identity quality, sample size, format relevance, reliability, and independence. Market evidence remains separate from performance evidence and DTOS intrinsic value. League-local evidence adjusts liquidity and demand only after the general market baseline.

External refreshes run with background Sleeper synchronization. Public routes read `data.provider_network`; they never call a provider or regenerate consensus. A failed source retains prior disclosed evidence, cannot erase another provider, and cannot block ordinary pages. Missing evidence is unavailable—not zero.

## Contracts and registry

Provider Registry `1.0` records access, authentication, compliance, redistribution, formats, asset types, refresh policy, lineage, identity method, reliability prior, runtime health, coverage, and explanatory status. Evidence Contract `1.0` records canonical identity, raw and normalized observations, ranks, tiers, format, timestamps, freshness, confidence, identity status, source version, provenance, evidence family, and redistribution permission. Observations are append-only evidence; corrections require replacement provenance.

Identity statuses are `exact`, `strong`, `provisional`, `ambiguous`, `unmatched`, and `conflicting`. Only exact or strong observations enter automatic consensus. Unmatched and conflicting counts remain visible. Restricted observations redact raw values and provenance from public responses.

## Reliability and consensus

Reliability is bounded from 0–100 and reported independently for overall, QB, RB, WR, TE, rookies, veterans, picks, contender/rebuilder utility, and market-movement prediction. Conservative priors are updated by observable availability, freshness, coverage, identity match, and source confidence. Future time-aware backtests can add rank correlation, prediction accuracy, and value retention without changing the contract.

Consensus normalizes provider scales, calculates a weighted value inside each evidence family, then combines independent families. DynastyProcess declares its FantasyPros lineage, preventing circular double-counting. Results expose raw provider count, independent-family count, effective provider count, dispersion, disagreement, confidence interval, and confidence. One family can inform a page but cannot authorize automatic calibration.

## Observed trades and league-local evidence

Completed Sleeper trades are deduplicated and isolated by league. Failed transactions, waivers, incomplete swaps, duplicate IDs, and non-two-party records are excluded with counts. Multi-asset trades retain package shape and quality; large packages are marked for review. Public APIs expose aggregates only—never private cross-league details or manager-level personal inference.

## Calibration safety and rollback

Automatic calibration remains model-level and bounded. It requires 100% canonical asset integrity, enough comparable assets, enough assets supported by multiple independent families, fresh healthy evidence, exact/strong identities, no conflicts, strong confidence, acceptable agreement, and a bounded adjustment. Previous category parameters remain persisted for rollback. Most refreshes should report `No calibration required`.

## Credentials, licensing, and troubleshooting

- FantasyCalc: approved public machine-readable evidence; attributed, observed-market purpose.
- DynastyProcess: approved open-data CSV; derived market model with FantasyPros lineage.
- FantasyPros: official API only; set `FANTASYPROS_API_KEY` only with suitable production and redistribution rights. DTOS exposes only a boolean configuration state, never the secret or restricted raw records.
- KeepTradeCut: `unsupported_no_public_interface`; no scraping, reverse engineering, or undocumented endpoint use.
- Sleeper: official API and retained Historical Memory; public output is aggregated.
- nflverse: approved open releases ingested by Historical Memory under source attribution.

When a provider is Pending, Refreshing, Healthy, Stale, Disabled, Credentials Required, Unsupported, or Failed, the dashboard renders that state and reason safely. Check `/api/valuation/providers/{provider_id}/status`, then coverage, freshness, identity match, and error state. Never interpret absent runtime metrics as valid zero-value evidence.

## Adding a New Provider Safely

A provider must not be enabled until:

- official access is confirmed;
- terms, license, production use, and redistribution are documented;
- identity mapping and conflict behavior are tested;
- freshness and zero-coverage failures are measurable;
- failure isolation and cached fallback are safe;
- evidence category, purpose, family, and lineage are known;
- restricted public fields are redacted;
- normalization and deterministic consensus tests pass;
- calibration safety and rollback tests pass.

Adapters may be registered as disabled extension points before approval. Technical accessibility alone is never permission.

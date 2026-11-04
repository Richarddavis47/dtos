# Matchup Performance

## Scope

DTOS v1.5.8 optimizes the existing `/matchups` intelligence fast path without
changing fantasy calculations, historical-memory behavior, response markup, or
cache lifetime.

## Measured pipeline

Profiling used the production-shaped cached league snapshot: 10 rosters, 314
rostered player profiles, 12,202 canonical players, and five matchup cards.

| Stage | Before | After |
|---|---:|---:|
| Decision evaluation | 0.078 s | 0.082 s |
| Asset evaluation | 0.071 s | 0.066 s |
| Market evaluation | 0.777 s | 0.429 s |
| Player Value evaluation | 0.055 s | 0.119 s |
| Median direct matchup fast path | 0.837 s | 0.437 s |
| Local `/matchups` HTTP range | Not measured | 0.405-0.618 s |

Individual timings vary with CPU scheduling and warmed Python state. The
deterministic work count is the stronger regression signal: profiled function
calls fell from 2,891,266 to 773,970.

## Root cause

For every player and every market provider, normalization rebuilt the same
provider-wide value distribution, sorted it, and linearly counted values below
and equal to the player's raw value. With `A` assets, `P` providers, and `N`
provider records, the repeated percentile work was approximately
`O(A * P * N log N)`.

## Optimization

Each Market evaluation now:

1. prepares each provider's valid sorted distribution once;
2. reuses that immutable tuple for every asset;
3. uses binary search for below/equal percentile counts.

The work is now approximately `O(P * N log N + A * P * log N)`. The canonical
normalization range, percentile definition, freshness, confidence, consensus,
ordering, and serialized matchup output are unchanged.

## Request and background isolation

- Decision evaluation still runs once per matchup request.
- Asset, Market, and Player Value evaluation still run once per unique roster.
- Trade Intelligence and package generation remain excluded.
- No global matchup cache was introduced.
- Prepared distributions live only for the duration of one Market evaluation.
- Historical imports retain their existing bounded worker and transaction
  behavior; matchup requests continue to run CPU-heavy intelligence off the
  event loop.

## Validation contract

Regression coverage verifies prepared and legacy normalization output
equivalence, one-time distribution iteration, deterministic concurrent matchup
projections, per-request cache isolation, and the existing full-orchestrator
projection equivalence.

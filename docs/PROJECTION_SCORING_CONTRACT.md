# Projection scoring and display contract

## One evidence model, two numeric purposes

`projected_stats` is the source's weekly stat evidence, retaining its supported
precision and source order. Provider update time is not retrieval/knowledge time.
The league's scoring configuration remains unmodified in provenance.

`canonical_projection` (including compatibility aliases `weekly_projected_points`
and `sleeper_projection`) is the **decimal league-scored stat total**. It feeds
Player evidence, Team HQ, legal lineup optimization and Trade Intelligence.
It is not an annual forecast, dynasty scalar, or a scraped UI string.

`sleeper_web_display_projection` is a **presentation string** from that same
evidence. It is never summed, ranked or used to select starters. Matchups and
Market player presentation use it when available; dossier evidence distinguishes
it from the underlying unrounded total. Aggregate team totals remain aggregates
of canonical numbers, not sums of individually rounded display strings.

## Proven Sleeper web rule

The inspected public Sleeper web bundle
(`bundle-a35e7887837453b55e8d4dd0cfdccea5.js`, September 2026) normalizes each
scoring coefficient with `Math.round(coefficient * 10000) / 10000`, scores the
source stats, adds contributions sequentially in source stat order using
JavaScript Numbers, and renders game-log points with `toFixed(2)`.

This is not blanket truncation, half-up rounding of the exact decimal total,
rounding every contribution, or rounding source stats before scoring. Binary
summation can land on opposite sides of a half-cent boundary. DTOS reproduces
that behavior only for display compatibility and uses decimal arithmetic for
canonical scoring. Source-order metadata is required; older records lacking it
cannot establish exact web display equality and return no compatibility string.
The scoring/display method identities and projection policy invalidate earlier
prepared artifacts. Historical source observations are not rewritten.

Supported offensive stat scoring was checked against authenticated QB/RB/WR/TE
examples in two differently scored leagues over two weeks. All 16 current
matchup values match. The sample includes multiple half-cent boundary cases;
the source rule was not tuned per player. Private provenance records retain
observed displays, source timestamps, statistics and scoring contributions.

One previously differing matchup observation converged to the player-log/current
source value after a fresh league load. The original source snapshot behind the
old display was not captured. This supports an observation/cache discrepancy,
not an independently defined matchup forecast. DTOS does not create separate
matchup and player-log projection universes from that incident.

## Availability and scope

Missing evidence remains unavailable; a supported zero remains numeric zero.
The display string cannot revive a missing canonical value. League scoring,
season/week and the published semantic generation must agree at every consumer.
No unproven custom source calculation is implied by the sampled offensive rules.
No unsupported future weeks are extrapolated.

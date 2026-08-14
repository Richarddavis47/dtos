# Projection Intelligence contract

## Canonical production contract (v1.10.21)

Sleeper is the sole canonical weekly fantasy projection provider. DTOS converts
Sleeper projected football statistics with the requested league scoring profile
and interprets that value for league intelligence. Missing provider evidence is
unavailable, never a positional average or fabricated number. A legitimate
Sleeper zero remains a projected zero.

The former DTOS-calibrated weekly model is legacy, non-canonical, and retained
only for rollback/research compatibility. No production consumer blends or
double-counts it with Sleeper.

DTOS has one Projection Intelligence system and one canonical Brain. Cached
Sleeper projection evidence is the only weekly expected-points input. Provider
refresh is background-only; compatible cached evidence may be served under the
documented freshness policy when the provider is temporarily unavailable.

```text
Official Sleeper league data -> league / roster / matchup state

Sleeper projection evidence -> league scoring profile
                                             v
                              Canonical Projection Intelligence
                                             v
                                      Canonical Brain
                                             v
                  Valuation / Team / Trade / Advice / current FOIS context
```

## Source classification and synchronization

The bulk weekly interface is classified as **Sleeper Canonical Weekly Projection
Evidence**. The interface remains undocumented by Sleeper, so DTOS validates it
defensively. DTOS performs bounded background requests for available Weeks 1–18,
defensively validates the response, normalizes Sleeper player IDs, preserves only
the projected statistics needed for reproducibility, and records a semantic
fingerprint. The provider can be disabled with
`DTOS_SLEEPER_PROJECTIONS_ENABLED=0`; without compatible cached evidence,
Projection Intelligence then reports unavailable rather than inventing points.

Only one refresh can run at a time. Identical semantic content produces no new
canonical snapshot or downstream invalidation. Retrieval timestamps, request
metadata, and counters are observational and excluded from semantic identity.
Malformed responses are rejected; the last valid snapshot is retained and
marked stale. External work never occurs in a page or API request.

## Scoring and canonical value

Raw projected football statistics are converted through the loaded league's
actual scoring settings, including passing scoring, receptions, bonuses, and TE
premium where configured. Generic PPR totals are retained separately for
reconciliation and are never silently substituted for the league-scored value.

Each player contract exposes `canonical_projection` with Sleeper provenance,
availability, confidence, freshness, scoring-profile identity, and snapshot
identity. Deprecated projection aliases may mirror that same value for wire
compatibility, but they are not separate forecasts. Historical accuracy
infrastructure records projection/actual pairs without changing production.

## Relevance and isolation

Projection evidence is high relevance for Matchups, projected lineup strength,
replacement production, Contender Value, and current-production advice;
moderate for Intrinsic Value, team grades, odds, Competitive Window, and current
FOIS roster context; low for Rebuilder Value and Dynasty Power; and prohibited
for historical standings, champions, immutable past results, and historical FOIS
decisions without timestamp-valid projection evidence.

Market Value remains market evidence. A weekly projection does not redefine the
dynasty market or long-term value. Historical snapshots are immutable, and the
final pregame snapshot can later anchor accuracy evaluation without hindsight.

## Presentation and APIs

The UI labels the value precisely as **Sleeper canonical projection**. Matchup
totals use legal starters only, retain
full precision internally, and expose complete/partial coverage. Bye and
unavailable states are not represented as fabricated zero projections.

Read-only APIs include `/api/projections/health`, `/api/projections/providers`,
`/api/projections/players/{player_id}`, `/api/projections/weeks/{week}`, and
`/api/projections/accuracy`. Technical details disclose parser/model versions,
freshness, fingerprints, and snapshot identities without exposing the
undocumented URL in normal UI.

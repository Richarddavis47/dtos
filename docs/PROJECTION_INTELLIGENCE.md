# Projection Intelligence contract

DTOS has one Projection Intelligence system and one canonical Brain. The DTOS
Forward Production Model remains independent and always available from cached
canonical application state. Sleeper projection evidence is an optional input,
never a readiness dependency or request-time call.

```text
Official Sleeper league data -> league / roster / matchup state

Undocumented Sleeper projection evidence -> Projection Provider Layer
                                             |
DTOS Forward Production Model ---------------+
                                             v
                              Canonical Projection Intelligence
                                             v
                                      Canonical Brain
                                             v
                  Valuation / Team / Trade / Advice / current FOIS context
```

## Source classification and synchronization

The bulk weekly interface is classified exactly as **Sleeper Unofficial
Projection Feed — Optional External Evidence**. It is undocumented by Sleeper.
DTOS performs one bounded background request for the relevant season/week,
defensively validates the response, normalizes Sleeper player IDs, preserves only
the projected statistics needed for reproducibility, and records a semantic
fingerprint. The provider can be disabled with
`DTOS_SLEEPER_PROJECTIONS_ENABLED=0` without disabling Projection Intelligence.

Only one refresh can run at a time. Identical semantic content produces no new
canonical snapshot or downstream invalidation. Retrieval timestamps, request
metadata, and counters are observational and excluded from semantic identity.
Malformed responses are rejected; the last valid snapshot is retained and
marked stale. External work never occurs in a page or API request.

## Scoring and consensus

Raw projected football statistics are converted through the loaded league's
actual scoring settings, including passing scoring, receptions, bonuses, and TE
premium where configured. Generic PPR totals are retained separately for
reconciliation and are never silently substituted for the league-scored value.

Each player contract keeps `sleeper_projection`, `dtos_projection`, and
`canonical_projection` separately, together with difference, agreement,
confidence, freshness, and snapshot provenance. The initial external weight is
bounded and freshness-sensitive; it is not a permanent 50/50 average. Historical
accuracy infrastructure records projection/actual pairs, while automatic
provider-weight calibration remains disabled until adequate samples exist.

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

The UI labels sources precisely as **Sleeper Projection**, **DTOS Projection**,
and **DTOS Consensus Projection**. Matchup totals use legal starters only, retain
full precision internally, and expose complete/partial coverage. Bye and
unavailable states are not represented as fabricated zero projections.

Read-only APIs include `/api/projections/health`, `/api/projections/providers`,
`/api/projections/players/{player_id}`, `/api/projections/weeks/{week}`, and
`/api/projections/accuracy`. Technical details disclose parser/model versions,
freshness, fingerprints, and snapshot identities without exposing the
undocumented URL in normal UI.

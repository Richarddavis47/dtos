# Projection Intelligence contract

DTOS v1.10.0 introduces one persisted Forward Production snapshot shared by
Brain consumers. It is an optional intelligence subsystem: startup, readiness,
Asset Market, and Matchups retain their last valid state if generation fails.
Read routes never contact a provider or regenerate a snapshot.

## Provider decision

Sleeper's documented public API was reviewed before implementation. It documents
league, roster, matchup, transaction, draft, player, trending-player, and NFL
state interfaces, but no supported projection interface or public projection
dataset. DTOS therefore does not call private Sleeper UI endpoints and never calls
its internal output “Sleeper Projections.” Sleeper remains the canonical source
for league settings, identities, rosters, lineups, matchups, drafts, transactions,
availability metadata, and current NFL state.

The enabled source is the first-party **DTOS Forward Production Model**, derived
from already-cached canonical evidence. Licensed external projection sources stay
disabled until their licensing and credentials are explicitly approved.

## Snapshot and scoring contract

Snapshots are immutable and keyed by league, season, week, model version, exact
league scoring settings, and canonical player output. A repeated identical input
reuses the persisted snapshot. Updates create a new row; actual results are stored
separately for MAE, RMSE, and bias calculations.

Raw statistical inputs, when an approved provider supplies them, are scored by
DTOS using the league's passing, rushing, receiving, turnover, bonus, PPR, and TE
premium rules. Missing evidence remains null. A bye is `bye`, not a zero-point
projection. Out/IR/PUP/suspended players remain explicitly unavailable.

## Value boundaries

Forward Production is distinct from Market Value. It has a meaningful near-term
weight in Contender Value, a bounded weight in Rebuilder Value, and a bounded
football-production weight in Intrinsic Value. Provider market consensus is not
rewritten by projection changes. Historical FOIS records do not consume current
projections; only future decisions can record the current snapshot identifier.

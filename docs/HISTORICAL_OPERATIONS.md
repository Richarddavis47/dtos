# Historical Import Operations

DTOS v1.5.1 stores import jobs, granular checkpoints, and leases in the same SQLite
database as historical evidence. Production must set `DTOS_HISTORY_DB_FILE` to a
durable Render disk path; temporary storage cannot survive redeployment.

## Recovery

Startup schedules recovery without waiting for it. Expired `running` jobs return to
`queued`; permanent failures remain failed. Leases identify league, season scope,
data types, provider, and importer version. Only the worker holding that persistent
lease may process the scope.

Provider calls retry connection, timeout, rate-limit, and supported 5xx failures with
bounded exponential backoff and jitter. Authentication, malformed responses, data
conflicts, and unsupported data do not retry forever. Successful bounded segments
are committed before later work begins.

Read-only monitoring is available at:

- `/api/crawl/history/import-status`
- `/api/crawl/history/completeness`
- `/api/crawl/history/providers`
- `/api/crawl/history/data-quality`

Write controls intentionally remain command-line operations because DTOS has no
authenticated admin plane. Use `python -m tools.history_backfill --league ID` from a
trusted worker or Render job. Do not expose a public write endpoint.

## Production runbook

1. Confirm durable `DTOS_HISTORY_DB_FILE`.
2. Run the trusted backfill command.
3. Observe job/checkpoint progress via the read-only APIs.

## Player enrichment season and exit-code contract

`python -m tools.history_enrich` classifies NFL seasons using the Thursday
following Labor Day as the regular-season opening boundary and an injected
clock in tests. January remains part of the preceding NFL season rather than
being classified by calendar year alone.

- A missing nflverse file for a completed, eligible historical season is a
  failure and produces a nonzero exit code.
- Before the current regular season, the unpublished weekly file is persisted
  as `pending`; a future season is `not_yet_available`.
- During an active season, a missing snapshot is pending only when DTOS already
  has provider coverage for that season. With no prior coverage it remains a
  failure.
- Pending segments do not consume retry budget or increment failure counts.
  Their next eligibility date is persisted when it can be determined.
- The command exits zero when all eligible segments succeed and the only
  remaining segments are pending, not yet available, or explicitly unsupported.
  The JSON result lists every segment and its reason.

Scheduled synchronization and an operator-requested rerun re-evaluate pending
segments. A later published file replaces the checkpoint with `completed`
without duplicating immutable player-week records.
4. Retry incomplete work after its persisted retry eligibility time.
5. Require zero blocking data-quality issues before declaring completion.
6. Compare categories with the v1.5.0 local 30,051-record reference; explain provider
   corrections rather than requiring exact equality.

# Historical Storage Recommendation

DTOS v1.7.9 does not change production infrastructure. The immediate memory correction is validated against the retained production-scale dataset and is designed to complete one clean import within the current 512 MB service limit.

| Option | Cost implication | Operational tradeoffs | Migration risk | v1.7.9 immediate import |
|---|---|---|---|---|
| Current ephemeral SQLite | No added infrastructure charge | Simplest deployment, but every redeploy, restart, or OOM discards history, checkpoints, and leases | None | Expected to complete if the worker remains alive; an interruption restarts the import from an empty filesystem |
| Render persistent disk | Requires a paid Render service and separately billed disk capacity | Keeps SQLite and checkpoints across restarts; single-instance attachment limits horizontal scaling and disk-backed deploys lose zero-downtime behavior | Low to moderate: mount-path configuration, one controlled data copy, backup and rollback verification | Not required for the immediate memory correction, but materially improves restart recovery |
| External durable database | Separate database compute and storage charges | Best durability, backups, concurrency, observability, and future scaling; adds network latency, connection management, and another managed resource | High: SQLite-specific SQL/JSON behavior, migrations, transaction semantics, and reconciliation must be ported and validated | Not required for v1.7.9 and not authorized in this release |

Recommendation: complete v1.7.9 on the existing free ephemeral deployment and verify one uninterrupted 2021–2026 import. Treat durable storage as a separately approved reliability project. A Render persistent disk is the smallest durability step; an external managed database is the stronger long-term architecture when multi-instance reads or larger history require it.

Current pricing and constraints should be confirmed immediately before approval through the [Render pricing page](https://render.com/pricing) and [persistent disk documentation](https://render.com/docs/disks); DTOS does not encode a dollar estimate that can become stale.

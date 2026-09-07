# Storage prerequisite (v1.15.1)

Batch 1 recovery only. Batch 2 and all automated visual-publication systems remain off.

## Representation and retention

FOIS retains every observation and every full semantic state. Only top-level
`generated_at` and `brain_snapshot_id` are publication provenance; nested dates,
evidence, missing values, versions, tenure, GM, franchise, league and unknown
fields remain in the semantic identity. Shared compressed state is scoped by
the entire semantic payload, not rendered grade. Existing history remains readable.
Current evaluations are bounded by existing score/period/model keys and remain
directly readable. No arbitrary historical age cutoff is introduced.

Projection snapshots retain every existing boundary and actual-outcome link.
Each snapshot stores its complete envelope and player-state references. Exact
player evidence is compressed and shared across snapshots within the same
league/scoring/model scope. Publication timestamps/IDs remain in each player
observation. Unknown evidence fields and as-of dates remain semantic. Provider
week cache retains its existing six-season/18-week policy; unique derived
historical evidence is not deleted. Global provider/market evidence stays in the
existing shared provider/checkpoint stores, never copied per account.

Growth is proportional to unique evidence plus compact observation references,
not repeated full FOIS payloads. This is not a promise of constant storage for
unlimited unique history: resource cost still grows with unique league-specific
intelligence. Global NFL datasets must remain global in future batches.

## Compute and publication

FOIS scratch contains only one league's current evaluations, tenures and takeover
records. It excludes accumulated history. Publication uses one SQLite transaction
and a same-league boundary check; concurrent unrelated league updates survive.
Scratch is removed on normal completion/failure. The existing one-worker compute
model, checkpoint freshness gate and intelligence semantics remain unchanged.

## Migration safety

`python -m tools.storage_migration KIND DATABASE --maximum-mib N` is read-only.
`--apply` requires the corrected deployment and measured disk admission. It is
an explicit maintenance operation, never a startup/request-time operation.

The tool fences all cooperating FOIS/projection connections, reads a stable
source, and streams into a bounded compact target. It does not copy the original
database. SQLite max_page_count caps output, and admission reserves twice that
cap plus an explicit disk reserve for compact output/journal. All logical tables
are hashed and compared, with historical payloads decoded before hashing.
Integrity checks and equivalence must pass before atomic replacement. Unknown
tables or journal modes stop without replacing the source.

Connections are closed before replacement, preventing stale-inode writes.
An interrupted pre-publication run preserves the original. Recognized abandoned
scratch for this exact database is removed on retry under the exclusive fence;
unrecognized contents fail closed. After publication, the compact database is
the complete recoverable representation. `--restore-legacy` reverses payload
normalization using the same logical-equivalence gate and explicit disk admission;
it must precede a rollback to software that cannot read compact references.
No full duplicate backup is required. Do not roll back blindly to v1.15.0.

Maintenance may briefly wait for or block database connections; perform it at a
settled operational boundary, then rerun authenticated acceptance. No request
threshold or resource tier changes are authorized by this tool.

## Measured pre-migration classification (2026-09-07)

Read-only production FOIS: 8,598 observations; 2,745 semantic states; 5,853
duplicate observations. Original payload 723,538,714 bytes; compressed states
40,424,577 bytes; observation references 2,266,098 bytes. Estimated payload saving
680,848,039 bytes, before SQLite/index overhead. Classifier took 17.793 seconds.
An unchanged observation averages about 264 payload bytes rather than 84,151.
At 400 unchanged observations/day, that is about 103 KiB/day plus small index
overhead, not 34–49 MiB/day. Truly changed states still consume new storage and
must be budgeted; deduplication does not justify promising infinite capacity.

Read-only projections: 294 snapshots; 242,301 player observations; 217,327 unique
states; 24,974 reused observations. Original payload 261,104,572 bytes; proposed
states 118,187,730; envelopes 14,835,848. Estimated payload saving 128,080,994
bytes before SQLite/index overhead. Classifier took 15.198 seconds.

Admission proposal: FOIS compact cap 128 MiB plus 128 MiB disk reserve requires
384 MiB free. Projection cap 256 MiB plus 128 MiB reserve requires 640 MiB free.
Last measured free space is about 702 MiB; remeasure immediately before applying.
Caps are enforced, not optimistic estimates. Run FOIS first to reclaim headroom.

## Disposable data and observability

Only explicitly verified old validation directories and retired live_visual are
eligible for the separately approved cleanup. Never age-delete accounts,
checkpoints, unique evidence, canonical history or current restart artifacts.
No new Current Visual/DINS/Mirror artifacts are produced. Temporary migration
artifacts have a scoped lifecycle; diagnostic evidence contains counts/hashes,
never private payloads. Existing disk warning ratios are preserved; operational
health adds FOIS state/observation counts and projection state/storage counts.

Production migration, actual reclaimed bytes, release and acceptance results
must be recorded after they are performed; these estimates are not completion.

# Bounded request and memory attribution

These diagnostics observe existing work. They do not change source admission,
Market values, projections, legal lineups, FOIS methods, saved user intent or
runtime/worker ownership. No diagnostic endpoint, database, local log archive,
cache allowance or infrastructure is added.

## Correlation and clocks

The ASGI request boundary selects a bounded request ID and carries it through
account resolution, runtime admission, synchronization, thread dispatch and Home
rendering. Cold admission activates a small buffered prelude; ordinary warm reads
remain quiet unless the existing diagnostic header is selected. Activity outside
a live request receives its own ID, with an origin request ID where applicable.
Maintenance cannot keep reusing an exhausted request budget indefinitely.

`dtos.attribution` records contain wall-clock UTC timestamps and monotonic elapsed
milliseconds, span IDs and parent IDs. Durations are inclusive; nested, parallel
and asynchronous activity must not be added as sequential request costs. A task
can outlive its context parent. Calling-thread CPU is cumulative CPU on that
thread during the interval, including unrelated concurrent work; it is not a
per-request CPU profiler. A source parse without awaits has a narrower meaning.

The HTTPX request hook marks initiation. The transport trace marks received
headers before HTTPX logging; the later response hook has a separate marker.
Their difference bounds intermediate client/log/hook work rather than attributing
a stalled log sink to provider waiting. Existing transport trace callbacks are
preserved, while their sensitive information dictionaries are never recorded.
An observing async stream marks EOF separately. The observed transfer includes
HTTP content decoding between stream yields; it is not asserted to be pure
network waiting. JSON decoding/parsing is a separate span associated with the
source span ID. Preloaded controlled responses are identified at their already
completed boundary. An interrupted stream is incomplete, never a completed
zero-byte observation. Hooks neither refetch nor copy response bodies.

Incremental synchronization checkpoints distinguish lock/lifecycle waits,
source acquisition, identity transformation, historical preparation, ranks,
relevance, provider preparation, projection publication, team strength,
production/valuation preparation, calibration, checkpoints and publication.
Cache sizing, admission, lifecycle waiting, encoding/write, fsync and replacement
have separate clocks. CSV provider normalization remains inside its named
preparation span; do not call that entire span network time.

The response boundary records headers and the final ASGI body handoff separately.
Handoff means the body was accepted by the next ASGI layer, not acknowledged by a
remote browser. The final request record also includes any remaining ASGI cleanup.
Existing diagnostic duration headers are generated at response headers and are
not retroactively described as full-transfer durations. The liveness handler does
not start a diagnostic trace, sample processes or hydrate intelligence.

## Memory and lifetimes

One lazy daemon sampler observes existing cold hydration, synchronization, FOIS
coordination/compute and selected heavy lifecycle work. It exits when those
activities and their queued boundaries end. Sampling is every two seconds while
eligible work remains, capped at 60 captures per activity. At most eight active
activities and sixteen queued boundaries are retained. Overflow is counted.
Boundary requests can be coalesced; requested and actual capture timestamps are
separate. A snapshot is not asserted to precede work merely because its request
was enqueued at the start boundary.

Samples report parent/child RSS, qualified PSS/USS, process counts, cgroup current,
anonymous/file/shmem/kernel memory, OOM counters and cgroup lifetime peak where
supported. Full PSS is requested at boundaries or every fifth periodic capture;
otherwise it remains unavailable. Zombies are filtered before the sixteen-live-
process cap. Explicit worker registration identifies owned FOIS children.
Per-process offsets and durations make sequential sampling visible. Do not sum
PSS as an atomic simultaneous cgroup total, and do not add shared RSS mappings.
`memory.peak` is cgroup lifetime peak, not a new per-request peak. Existing legacy
FOIS fields named peak RSS are not substituted for these qualified measurements.

Residency telemetry uses a weak manager reference and cheap counts/hashed
generation identities. It does not retain source graphs, deep-size caches,
prepare facts, revalidate grades or mutate cache ownership. Process enumeration,
PSS and resource reads run on the sampler thread. Access-denied PSS falls back to
RSS with PSS unavailable; missing measurements are never fabricated as zero.

## Bounds and security

Each trace emits at most 512 diagnostic records and buffers at most 32 prelude
records. Event indices, limits and known drops are explicit. The shared hosted-log
queue holds at most 512 records; a blocked sink drops telemetry without blocking
navigation, and subsequent records report the queue's drop count. Records are
best-effort hosted stdout logs: an abrupt kill or collector failure can still lose
queued data. No durable-delivery guarantee or complete peak claim is made.

Only fixed span/resource classes, hashes, IDs, timestamps, statuses and numeric
measurements are recorded. No source body, URL/query, credentials, cookies,
environment, account identity, command line or full user state is captured by the
new telemetry. Diagnostic headers do not authorize access. Operators obtain logs
through the existing authorized hosting tools; no public private-data endpoint
was added. Existing hosted-log retention remains the storage boundary.

## Controlled and production evidence

Barrier-controlled HTTPX and real loopback transfers verify that header arrival
does not imply body completion. ASGI controls verify final-body timing, while
failure, authorization, queue saturation, process-cap and worker-cleanup controls
preserve the existing contracts. Measurements on captured source fixtures are
not a replay of production retained archives or proof of production OOM safety.

After deployment, use normal startup and a bounded authenticated read following
quiescence. Do not clear production caches, change account selections, force
historical regeneration or intentionally approach an OOM. Preserve original
incident evidence. If no matching slow request or memory event occurs during the
window, the old 44.230-second interval and production OOM cause remain unknown.

The validation-only Node heap policy is documented separately in
[validation architecture](VALIDATION_ARCHITECTURE.md). It does not apply to Render.

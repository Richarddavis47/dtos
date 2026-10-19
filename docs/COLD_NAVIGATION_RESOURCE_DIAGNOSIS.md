# Cold navigation and resource diagnosis

Baseline: v1.21.72/build2172, `1f421c2906b36549030c5aec176d68b77565336e`.
This work preserves FOIS failure isolation. Neither deployment nor green tests
close the earlier production OOM or establish a universal cold-start bound.

## Confirmed request-lifetime defect

Three authenticated, separately scoped readers can temporarily protect three
secondary runtimes plus the pinned default. Previously, request completion only
decremented `active_requests`; the manager did not retry eviction. Four warm
runtimes could therefore remain after all readers finished despite a limit of two.
Simultaneous cold hydration also allowed eviction between becoming warm and the
middleware claiming its reader reference.

`LeagueRuntimeManager.acquire_request` now reserves that reference under the
existing manager lock before waiting for the shared hydration. Middleware returns
it after the response. `release_request` restores the existing bound through the
existing close protocol. Temporary excess still protects active readers; limits
were not raised. Cancellation drains the shared writer and cleanup without
cancelling another reader or leaving a later unowned warm publication.

## Cold request evidence and diagnostics

The original production request returned 200 server-side after 49,999.537 ms,
following Sleeper sync. Its client had timed out at 35 seconds. About 44 seconds
separated the last visible provider response and sync completion. FOIS subsequently
failed independently; navigation no longer converts that failure into HTTP 500.

A disposable replay captured public Sleeper data (12,229 players, three leagues)
and existing public Market observations once, then ran offline under 2 GiB.
Fresh-store cold Home took 6.9 seconds and warm reads 42–44 ms; projection
publication was the largest measured stage at 2.55 seconds, followed by cache
publication at 0.89 seconds. This is not a reproduction or improvement of the
50-second production request. Production has different retained stores and load.

`dtos.sync_profile` now emits one `sleeper_sync_profile` record per synchronization:
fixed phase clocks, hashed league scope, parent/child point samples, cgroup
current/lifetime peak, anonymous/file memory and OOM counters where supported.
PSS is unavailable on unsupported platforms, not fabricated as zero. The phase
clock includes scheduling/wait time; samples are not a continuous peak trace.
Sixteen phases and sixteen process samples bound the record. No source facts,
tokens, user settings, diagnostic database or new on-disk history are added.

## Independent disposable controls

Run the ordinary focused suite with validation dependencies installed:

```sh
python -m unittest tests.test_navigation_residency tests.test_sync_diagnostics tests.test_fois_navigation_reliability tests.test_cold_league_recovery tests.test_resident_league_maintenance_v1131
```

Within a disposable Linux container using `--memory 2g --memory-swap 2g`:

```sh
python -m tools.validation.navigation_residency_probe --fixture-root /fixture --output /output/navigation-residency.json
```

The resource control refuses a larger/unbounded cgroup. It uses 12,322 generated
canonical assets and three disposable authenticated accounts, never production
accounts/providers/FOIS. It checks own-league responses, active-reader protection,
quiescent residency, canonical-reference release, OOM counters and temporary
cleanup. Logical deep sizes are estimates and can double-count shared objects;
RSS/PSS can remain high because of allocator retention. This is a residency
control, not a production cold-navigation benchmark.

## Open acceptance boundaries

The historical Render OOM and supplemental Python 3.14 full-regression OOM remain
unattributed. Cache over-residency is a demonstrated risk, not proof of either
event's cause. Capture the bounded stage logs and process/cgroup samples during
the next representative cold read before optimizing a suspected stage. Private
operational inspection returned 401; no authorization bypass or token change
was attempted. Retained FOIS grades remain RETAINED / NOT REVALIDATED.

Keep author-run fixtures, authenticated production observations and independent
Scout evidence separate. No physical iPhone/Safari, human usability or human
screen-reader acceptance is implied by these controls.

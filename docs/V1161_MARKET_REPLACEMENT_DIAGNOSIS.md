# v1.16.1 replacement probe diagnosis

Original candidate: `9498e45b7bff1c34b2eb4a1d6a07d1c55924dd07`.
Required PR run: 34321932712, archive-warmed job 102370308568.
The red run is retained; it was not rerun before diagnosis.

## Original evidence limits

At 07:05:31.414082 UTC the fixture mutation request was accepted. It returned
at 07:05:32.868384. The assets request entered at 07:05:32.909420 and returned
200 at 07:05:32.967009 (57.609 ms). The assertion discarded its local profile
before saving the summary. Thus the original recording cannot prove replacement
admission, publication, or the handler's lifecycle branch. It cannot support a
claim that replacement completed before the request, nor a proven product defect.

## Focused unchanged-source reproduction

A single synthetic production-shaped local HTTP reproduction traced the real
cache entry/return, worker start and publication. It reproduced 200:

- Old complete model published at 07:21:21.403162 UTC, build count 1.
- Material mutation returned at 07:21:24.020813.
- Probe entered the cache at 07:21:24.667981.
- Lifecycle phase was idle but `heavy_work.state=FOIS_GENERATION`;
  `market_build_allowed=false` and `build_active=false`.
- Cache returned with `last_miss_reason=heavy_phase_last_valid`, build count 1,
  unchanged old generation; no replacement had started or published.
- Probe returned 200 at 07:21:24.770993. Cleanup left zero children.

This is **C: contract mismatch** for the reproduced state: the fixture inferred
active replacement merely from a material input mutation. The original Linux
event lacks the trace needed to assert its identical cause; the deterministic
fixture correction removes this demonstrated ambiguity rather than accepting 200
as an active-replacement success. The local reproduction is not a Linux resource
or timing acceptance run.

## Authoritative boundaries

`AssetMarketCache.get()` deliberately serves a complete last-valid model while
`market_build_allowed()` is false; `test_last_valid_market_is_served_during_heavy_phase`
already asserts this behavior. FOIS reservations are one admission blocker.
When eligible, a changed marker starts a single replacement flight and the route
maps `MarketWarmingError` to 503. `_publish()` switches the model, marker and
health metadata together under its lock after complete artifact construction.
The candidate's authentication change does not participate in this boundary.

## Fixture-only correction

Hold the existing shared intelligence-preparation lock through the probes (so a
new FOIS flight cannot enter between admission and the request). Reserve the
existing Market-priority mechanism, wait boundedly for current
maintenance to finish, mutate the attached canonical input, and explicitly start
reconciliation. Hold only publication until the existing ten warming probes
finish. Semantic preparation/construction still run normally during the probes;
no CPU workload, threshold, dimension or resource limit is removed. Release the
barrier and require the existing one-child/one-build/digest/payload/artifact checks.
Timeout fails closed before publication. Capture failed probe timing/state rather
than discarding it. No production code imports the barrier.

Focused regressions cover FOIS admission, reservation cleanup, publication timeout,
complete old model during maintenance, ten 503s while replacement is held, and
one atomic publication followed by a complete new-generation 200. Existing
account/league isolation and artifact equivalence tests remain mandatory.

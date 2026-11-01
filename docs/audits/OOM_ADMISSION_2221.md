# November1 production OOM admission correction

Production source118269a2b3c6a6e812422d79818c55d088aff191. Held K/DEF PR310/source225337446e5fb81b05299afc0869db6b3f07fa5e is separate and not merged here. Incident candidate reserves v1.22.6/build2221; held build2220 is not reused.

Authorized Render observations: sync completed13:46:57UTC; application RSS remained approximately1.788GB, worker approximately243MB. At13:47:15.107 container current2147450880, limit2147483648 (32768bytes headroom); anonymous2010533888/file125702144. New FOIS coordination/generation began at that pressure. Two runtimes remained resident, one pinned, nine recorded source generations each. Restart logged13:47:18; startup complete13:47:45. User's Render event identifies OOM kill13:47:17/recovery13:47:47. Exact fatal allocation and object-versus-allocator ownership are not established. Anonymous pressure dominates; this is not the old fixture-preparation file-cache observation.

Baseline submission has no memory gate. Lifecycle reservation fences Market/history responses but not Sleeper sync. Mocked code controls reproduce near-limit executor submission and concurrent sync/FOIS reservation. These are not production failure injections.

Prototype: raw cgroup headroom gate before scratch copying and again under executor lock;512MiB working reserve plus256MiB margin. No file-cache subtraction. FOIS waits for the active heavy phase; sync immediately defers if FOIS owns its lease so the event loop cannot deadlock waiting for FOIS completion. Sync reaps only an idle worker before source allocation. Deferred generation does not publish grades and retains prior qualifications. A60-second retry cooldown prevents repeated automatic attempts; no polling job is added.

Controlled Docker enforces2147483648bytes memory/swap and two CPUs, network disabled.1.4GiB declared padding triggers deferral; a real app liveness endpoint succeeds in~15ms; releasing padding allows readmission. Padding is not production headroom evidence.25 worker/admission/residency controls pass unpressured in that container, extended to47 lifecycle/maintenance controls. Host shared-workspace attempt failed4 assertions/7 errors due genuine deferral and is retained, not counted as completion. Initial lint failures retained. Full release validation still required. Do not claim full real-source sync/FOIS worst-case capacity from these controls.


## Validation recovery

The original eb2020 Product run completed 550 tests with two actual-worker admission failures. Beginner navigation completed 174 tests with one failure/four errors. Linux scratch preparation had six failures/two errors; Windows could not supply bounded container telemetry. These controls were not allowed to count deferral as execution. Archive-warmed lifecycle assertions passed; artifact finalization failed with ECONNRESET. Original logs and canceled runs remain evidence.

Worker controls now run with an actual 2 GiB Linux cgroup or a measured, enforced Windows Job aggregate committed-memory limit. Native Windows accounting requires a bounded Job; an unknown/unbounded Job still defers. Linux production continues using raw cgroup current memory, including file pages. Browser controls run in disposable 2 GiB containers, with historical worker modules in a fresh process/container to avoid unrelated browser heap carry-over. The original module multiset and assertions are unchanged.

A separate focused workflow (78a381cc4859572f22bee1b35c000d40f2fb6b80, run 41345988676) passed 35 controls on each platform; Windows retains its two pre-existing POSIX-only skips. A local enforced-container replay passed 29 historical, scratch, cancellation and timeout controls. These results precede the final candidate and do not replace its mandatory full validation.

A real two-grade historical worker completed, then 1400 MiB declared pressure caused deferral while old grades remained retained. Ten repeated automatic calls produced no retries during cooldown. After pressure release and 61 real seconds, the deferred operation retried, completed, removed scratch state and reaped its worker. Liveness during pressure was approximately 15 ms. Synthetic workload and padding are explicitly separate from production capacity claims.

The reserve remains 512 MiB working plus 256 MiB safety. Incident worker RSS was 243,073,024 bytes (232 MiB); the tiny recovery worker used approximately 48 MiB. Neither establishes the maximum for all permitted historical workloads. These measurements support conservative admission relative to observed demand, not universal capacity clearance or protection against every possible allocation elsewhere in the application.

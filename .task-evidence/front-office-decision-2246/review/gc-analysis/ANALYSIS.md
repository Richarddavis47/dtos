The bounded diagnostic reproduces the latency failure through Python 3.14
incremental garbage collection. It supports preparing the test fixture before
starting its unchanged 100 ms timer. It does not establish the exact cause of
the historical 157.622579 ms sample, whose original observer lacked GC events.

The actual audit handler delegates its synchronous construction and rendering
through `run_manager_read` to `asyncio.to_thread`. The test holds that worker on
its existing two-second event wait, then sends the separate lightweight request.
The original failed run already confirmed the lightweight response was 200 and
the audit remained pending. The response log was created about 0.6 ms before the
158 ms slow-task warning, so a slow log handler after log-record creation cannot
explain that historical interval. Its full heap was about 705 MB. Module-boundary
cleanup had just collected 354 objects in 532 ms; it did not run inside the timer.

The diagnostic loaded all 4,358 tests without executing the suite. It retained
one connected graph of 2,450,000 tracked dictionaries throughout three fixed
cases, reaching about 707 MB before observer allocation and 717–724 MB during
the cases. The container enforced 2 GiB, two CPUs, no network, and UID 1000.
Each case ran the real 12-test production-readiness predecessor, the five actual
audit methods preceding the target, then the target once. There were no retries.

| Case | Actual 100 ms assertion | Lightweight HTTPX span | In-request GC |
| --- | --- | --- | --- |
| Original source | Failed at 186.369 ms | 185.759 ms | Generation 1: 184.088 ms wall, 184.069 ms thread CPU |
| Collect setup immediately before timer | Passed | 1.475 ms | None |
| Same setup collection, actual 120 ms sleep in foreground handler | Failed at 121.965 ms | 121.715 ms | None |

The original reproduction's generation-1 collection reported zero reclaimed
objects. Its captured caller was HTTPX `_send_single_request`, reached through
the real `wait_for(client.get(...))`, before the lightweight ASGI transport
began. Thus the pause was collector traversal on the event-loop thread, rather
than computation in the audit worker or lightweight application handler.
Collection accounted for more than 98% of that lightweight HTTPX span.

The positive variant performed one full collection in 429.140 ms before starting
the request timer. The worker's two-second wait, 250 ms request timeout, 100 ms
assertion, pending-audit check, response checks, and context propagation check
were unchanged. GC stayed enabled with its default thresholds `[2000, 10, 0]` in
all cases. The negative control still detected real foreground blocking.

The integrated fixture at commit `de1420347607f94f54de22694f81f4af16977693`
matches the tested positive variant's Python AST after normalizing its ordinary
`import gc` against the evidence copy's `__import__('gc')`. Its remaining changes
are explanatory comments. The archived original isolated worktree remains clean
at `836d036464bfb1e13cf350e44635620b0978f05d`, tree
`d35a21d697d603d4eb4b4f46cf88e8a514c50d77`; its test-file SHA-256 is
`e5a763887b5208d1e71289b8b39ecf5dfaabe205e77766a35fd5d8f6f2622e0b`.

This is a modeled old-heap causal control. Its graph shape and instrumentation
differ from the historical accumulated fixtures, and observer wrappers can move
an allocation threshold. It proves a concrete mechanism and checks that the
fixture correction still rejects foreground blocking. It neither measures an
application performance improvement nor replaces the required complete local
canonical validation on the final integrated source.

`summary.json` contains the compact measurements and captured GC stack.
`result.json`, `events.json`, and `derived-analysis.json` retain all three results
and observations, including both expected assertion failures. No events were
dropped. The container exited 0 without an OOM; its sanitized configuration and
state are in `container.json`. After validating the external evidence, only that
stopped disposable container was removed, as recorded in `cleanup-state.json`.

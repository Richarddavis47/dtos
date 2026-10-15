# Home read execution and liveness

The final v1.21.52 local combined-read run observed a 743.436 ms liveness request (713.217 ms server time), above the unchanged 500 ms gate. It exited 1 on responsiveness, with zero recorded OOM events and sampled working memory below the threshold. No -9 or OOM cause is inferred.

Home awaited freshness, then executed its complete synchronous prepared view pipeline on the HTTP event loop. This includes directory/context fingerprints, canonical championship reads, synchronous cache single-flight waits, Attention/news reads and shell construction. Market HTML already uses a synchronous worker route; other manager views reuse `run_manager_read`.

An instrumented pre-fix combined run passed, demonstrating timing variability rather than erasing the failure. Its measured Home stages included directory and championship/context work; Market publication detachment was negligible in that fixture. The exact slow substage of the original uninstrumented request cannot be recovered, and a Market-copy or OOM explanation is not claimed.

The authenticated HTTP regression deterministically admits a blocked prepared Home read and checks that real liveness can finish before Home is released. Before correction it fails because that work runs on the event-loop thread. After correction it passes, including account and league context across two selected leagues.

The correction keeps freshness admission on the request coroutine and uses the existing context-propagating `run_manager_read` boundary for synchronous Home view construction. All source admission, publication coherence, cache keys/bounds, evidence, prices, discovery behavior and authorization remain unchanged. No new executor, cache, provider loop or permanent store is introduced.

Validation-only `DTOS_VALIDATION_HOME_PROFILE=1` records stage wall times and worker identities. It is disabled normally; at most 64 temporary JSON lines are retained beside the benchmark output. These observations are independent of the bounded server-log tail. They do not change the 500 ms assertions or the 2 GiB/2 CPU lifecycle limits. Normal uninstrumented final lifecycle runs remain required.

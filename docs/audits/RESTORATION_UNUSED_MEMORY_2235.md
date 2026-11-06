# Cached restoration: bounded unused-memory recovery

## Evidence and scope

Baseline: v1.22.19/build 2234, `9c1886c40c9697da0be3b5f06ede0bf9f45f4682`, tree `6ca249dddd6c798b56e1d2a067c63afa9b759a4f`.

The owner's November 6 15:05 UTC Render-local observation reported a 26,864,873-byte Granite cache, 309,542,912-byte raw headroom and 564,055,696-byte restoration requirement. It proves insufficient policy capacity at that moment, not actual decode demand, retained-object ownership, a leak, other workers' idleness or a historical rejection reason. This session did not reproduce that private snapshot. The Render connector has no Shell/SSH operation and the browser runtime is unavailable here. The unchanged external 401 was not retried.

Source inspection confirms that expired IntelligenceResult contexts can retain source graphs. The existing post-request reclaimer requires a changed request count, so quiet/inspection-only intervals need not drain that backlog before a new cold request. Explicit Trade already attempts bounded unused-memory recovery. Cached restoration previously deferred immediately. It did not attempt that recovery, even where measured reclaimable application objects could satisfy its unchanged guard.

## Correction

Share the existing explicit Trade cleanup: retire a truly idle local FOIS pool only when no FOIS owner remains (including gaps between submissions), expire already expired intelligence and lineup entries, and return unused allocator pages. Retain the cache's existing 512-entry bound and nonblocking entry lock. Do not collect live graphs, evict runtimes, invalidate fresh publications, invoke providers or credit inactive file pages as capacity.

Only an initially negative, known-memory restoration plan with its existing safety margin still available attempts cleanup. The caller retains the existing cache-persistence lease and opened file generation. It performs one pass, remeasures raw cgroup memory and FOIS ownership, and calls the exact same restoration_admission function. Unknown or insufficient capacity still defers before JSON decoding. Counts are never converted into capacity. Optional cleanup failure is not a source failure or permission to decode. Owned-reader cancellation still drains the restoration thread before state can be released.

The advisory private preflight remains read-only and grants no reservation. Entry can change unused-object retention after the snapshot, then must pass a fresh unchanged guard. It may still defer when live resources consume capacity. No periodic retry or user preference change is introduced.

## Measurements and limits

Reuse the sealed prior PARTIAL study archive SHA-256 `df5c88eda13a0671104c76a943b05032d7adfa089d11e738785b11e35a932439`; do not regenerate its contents. The resource tool extracts only its two synthetic caches and projection database. These contain a 10,000-identity catalog and two projection weeks. Their serialized size and structure do not establish equivalence to Granite's private payload. The prior 79.6 MiB fixture peak is not a production reservation bound.

The new experiment tests expired ownership and cleanup, not another allowance study. Actual cache/context types hold expired and fresh source graphs; explicit separately reported harness padding applies container pressure. All padding remains included in admission telemetry. No completed FOIS analysis is claimed for those ownership objects. Warm live runtimes and fresh results must remain untouched. Kernel lifetime peak and sampled incremental changes have separate meanings; 5 ms samples may miss brief peaks. Record anonymous/file/inactive-file counters and local process ownership without claiming process-local idleness covers other workers.

The clean-baseline probe released 213,716,992 bytes using existing explicit Trade cleanup, then restored under the same 486,292,112-byte requirement. This is less than the supplied production deficit of 254,512,784 bytes, so it does not prove Granite would now enter. The new archive-based acceptance records its own exact file size, hashes, before/after plans, active/fresh preservation, genuine completion, unexpired-pressure deferral, explicit retry after relief, FOIS reservation protection, worker exit and scratch cleanup. Actual production restoration peak remains unmeasured.

## Validation and independent acceptance

Focused regression covers the unchanged formula, failed/unknown telemetry, active FOIS and competing phases, atomic file replacement, cleanup failure, actual owned-reader cancellation, real decode, native Sleeper zero/negative results, exact picks, one-QB/K/DEF and Superflex identity. Mandatory canonical, Product, lifecycle and tooling gates remain required on the final exact source tree. The Product workflow runs the new real 2 GiB/offline recovery tool using the checksum-pinned existing archive; it preserves failures independently.

The first new resource run reached successful restore/deferral/retry/FOIS protection but failed an overbroad no-child assertion: Python's multiprocessing resource tracker remains owned by the test process. Corrected coverage records that helper separately, permits only that identified tracker, and still requires both actual FOIS worker PIDs to exit. It does not treat a deferred operation as completion. The first Ruff invocation failed to write its cache on the intentional read-only source mount; --no-cache performs the same lint without that write. Original attempts remain in the evidence archive.

After release, Main Chat/Scout should use the existing Render-local private preflight without exposing its configured token. Record fresh process/container scope, cache size, raw headroom, requirements and reason. Do not force entry under unsafe capacity. If safe normal entry completes, compare an actually retained league/season/player-week Sleeper score against the deployed dossier and the matching prepared consumer; a historical replay is insufficient for live parity. Do not force sync, FOIS or Trade searches. Diagnostic shipment or fixture recovery does not establish live Granite recovery or the cause of an earlier 503.

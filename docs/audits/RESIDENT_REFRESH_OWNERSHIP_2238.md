# Completed resident-refresh ownership

Production/main was verified as v1.22.22/build2237, commit1e1234fbcf7ca18f3862e5cdeac1451780e51b49/tree4051883efb1f225dcd71e07f1998e45c9d96fb39. The accepted decoder-only reconciliation is reused, not repeated. Its synthetic results do not establish Granite recovery.

## Confirmed boundary

services.league_maintenance.ensure_periodic_refresh kept its local completed worker throughout the next interval sleep. dtos_app._refresh_resident_league returns the entire prepared source dictionary. After a separate normal publication replaced runtime.state data and consumer contexts, the sleeping maintenance coroutine still owned that old graph through Task.result. A failed or timed-out worker could similarly retain a source/candidate through its exception traceback. This is unnecessary ownership, distinct from the current warm context, legitimate old readers, persistent caches or allocator retention.

Weak-reference controls reproduce both success and exception retention until the maintenance loop closes. Full source-compatible one-QB/K/DEF controls exercise two actual cache restores, native binding, projection restoration and canonical publication in an enforced2GiB/no-swap/twoCPU/offline container. The second fixture differs only by a synthetic league display name. Native result/disclosure digests agree; all source facts remain retained. A prototype changing only the completed-task reference releases the obsolete generation and materially reduces settled memory. Active-reader controls intentionally retain it until that reader releases its reference. Original results, exact source/method/input hashes and final-source measurements are sealed separately in release evidence.

## Correction

The existing refresh loop releases its worker reference in finally, after completion/error handling and after any cancellation drain. Nothing evicts a runtime or discards a publication. The current source, request pins, background ownership, saved workspace and persistent recovery files remain unchanged. The next ordinary interval still runs, including after failure; there is no automatic retry loop or new provider work.

The same boundary now drains through asyncio.shield until the writer finishes even when cancellation repeats. The previous gather in the cancellation handler could propagate a second cancellation to the writer. The writer's terminal exception is observed, the cancellation is preserved and only then is the task reference released. Tests verify a real pending writer remains alive until explicitly allowed to finish.

Seven new regression methods fail on the old source in five cases, covering superseded success/error/timeout retention, a legitimate reader and repeated cancellation. All new and existing maintenance methods must pass on the final source, followed by full mandatory local/canonical/hosted and enforced2GiB controls. Fixture setup errors and original before-fix failures are retained separately.

## Preservation and limitations

No catalog sharing, blind pre-entry eviction, cache-format change, allowance reduction, file-cache credit or source reconstruction shortcut is included. Cache JSON, the full16× physical-size basis,2GiB cap, FOIS768MiB and Trade256+128MiB policies are unchanged. Source generation, scoring, exact picks, account isolation, missing/zero/negative results, neutral/Custom valuation, submitted lineups, FOIS grades and active-reader evidence remain independent and unchanged.

Authorized Render management access confirms the live baseline and provides retained logs/metrics, not a complete current runtime-ownership snapshot. Render memory_usage is not substituted for raw cgroup admission inputs. One existing Opera capability check reports not connected; no Render Shell/SSH executor is available in this session. The unchanged external401binding is not retried. Main Chat's earlier Render-local token200 is supplied evidence, not reproduced. No Granite entry, forced sync, Trade discovery, FOIS rebuild, cache clearing, manual restart, preference mutation or infrastructure change is performed for diagnosis.

This demonstrated lifecycle defect can leave more headroom after superseded publications are released. It does not prove that it caused Granite's reported production deferral, that an eligible production runtime could be evicted, that the private cache has a particular peak, or that Granite entry/live Sleeper parity is recovered. Final acceptance requires one fresh existing Render-local preflight and, only if it permits, one normal guarded entry and an independent completed-week source-score comparison.

## Global evidence scheduler owner

A bounded authorized retained-log read subsequently found one pinned default warm runtime with no runtime-owned background tasks in that serving process at01:43UTC. This was not a fresh preflight or proof of other workers' idleness. Source trace of the separately owned global maintenance path found `refresh_global_evidence` retains its whole `STATE` data local across a six-hour delay despite needing only scalar season identity. A later default publication can therefore leave an obsolete full source generation reachable outside the runtime background-task set. Four new real-coroutine tests reproduce six failing success/failure/deferred/not-ready/absent-season/reader scenarios before correction. The scheduler now releases its unnecessary data local immediately after extracting season, before acquisition or waiting. Source acquisition, cadence, locks, readiness and source facts remain unchanged.

This and the completed resident-worker fix are one sleeping-maintenance ownership correction; no catalog sharing or eviction is introduced. The global owner receives separate matched full-source memory controls and a fourth enforced-container restoration/publication case. Acquisition is mocked in that case to avoid provider work; it is not counted as real ingestion completion. Actual cache restoration, canonical publication and admission remain real. Current production stack locals are not inspected, so neither retained logs nor fixture gains establish Granite recovery or the historical503cause.

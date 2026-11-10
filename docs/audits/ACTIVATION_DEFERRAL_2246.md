# Connected-league activation deferral — build 2246

## Verified baseline and incident evidence

Production v1.22.30/build2245 at commit abbe723a0566cf84a8fff947cf7320cb66567a77, tree cf649ee06ec3228d51d251ce7afbdbb15866f398, was ready at the initial read-only check. Existing authorized Render logs for three November 10 activation failures show restoration starting, acquisition of cache_persistence and failure before meaningful restoration. The retained runtime status is DEFERRED. In the deployed manager, HeavyWorkDeferred and LeagueRuntimeDeferred take that path; other exceptions mark FAILED. Acquiring the cache phase excludes a lease conflict at that acquisition, but does not prove all other processes idle.

Nearby queued serving-process samples report raw container usage about 1.50GB of 2GiB, inactive-file about599MB and anonymous about875MB. Those samples occurred after the request and are not the exact original guard inputs. The hosting working-set metric about902MB excludes memory included in raw cgroup usage and must not be substituted. No OOM was recorded. One intentionally pinned warm runtime and the deferred target were observed; nine source-generation keys do not imply nine resident copies. No eligible production runtime eviction or allocator leak is established.

The supplied earlier cache size35,839,104bytes requires707,643,392bytes with the unchanged16x allowance and128MiB safety margin, before any FOIS outstanding demand. Applying that file size to a nearby raw sample gives a roughly60MiB deficit; this is an illustration using non-atomic historical inputs, not a recovered original admission decision or measured restoration peak. The retained logs do not expose the original exception traceback, guard inputs, cleanup count or reclaimed bytes. The existing private preflight is current advisory metadata, not historical reconstruction. New logging cannot retroactively fill these gaps.

## Confirmed shared defect and narrow correction

The activation handler caught the deferred subtype with all LeagueRuntimeError failures and returned a generic preparation-failed page/API status. It discarded existing deferral and cooldown semantics. Catching the subtype first retains the existing manager decision and safe retry path. The saved account selection is changed only after preparation succeeds, through the unchanged authorized/revision-checked store operation. Deferred requests neither activate the requested league nor run Trade searches. No automatic retry is introduced.

A single prospective bounded log event records the already-calculated final restoration plan and already-performed cleanup counts. It reads no extra telemetry or source data, does not change the predicate, and is not an admission grant. Missing inputs remain unknown, negative measured headroom is preserved, and optional sink failure cannot authorize or abort restoration. Exception logs use the existing safe type/location helper without messages, locals or payloads. No file paths, account/player identifiers or private cache contents are logged by the new event.

## Deterministic acceptance and limitations

Disposable authenticated route controls reproduce the original misleading response and verify the corrected HTML/API result, sixty-second retry guidance, cooldown, no duplicate hydration, unknown-memory deferral, real lease contention, actual guarded safe retry, incompatible publication failure, authorization and unchanged account selection. Phone controls submit the actual league form at320x432,375x667,390x844 and1280x900, verify no overflow, visible feedback, focus and return navigation. Modelled telemetry controls are not measured production pressure. A small compatible real restore proves execution but is not the private Granite payload or a representative restoration demand study.

The existing enforced2GiB lifecycle suites still require actual safe restoration, unsafe pressure deferral, FOIS outstanding-reserve protection, recovery, worker exit, scratch cleanup and server liveness. Full canonical and hosted results, exact source tree, original logs and checksums are recorded externally. Failed commands and earlier assertions remain distinct. Physical iPhone/Safari and owner authenticated live entry/search are not implied by fixture controls.

## Preserved policy and customer outcome

No memory optimization or reserve reduction is made:2GiB effective cap,16x restoration allowance,FOIS768MiB,Trade256+128MiB, raw cgroup accounting, admission rechecks, lifecycle ownership and bounded cleanup are unchanged. Pinned or active contexts are not evicted; inactive-file memory is not arbitrarily credited. Cache compatibility, Sleeper-only scores/projections, explicit zero/negative/missing values, exact picks, neutral/Custom valuations, Trade bilateral thresholds, saved settings and submitted lineups retain their existing behavior.

This release makes a deferred attempt truthful and diagnosable. It does not resolve sustained capacity pressure, establish the original exact allocation, or promise Granite entry. Read-only live entry/search require fresh safe admission and an existing authorized session; stop on deferral. No forced sync, cache clear, restart, FOIS rebuild, Trade search or production preference mutation is performed for publication.

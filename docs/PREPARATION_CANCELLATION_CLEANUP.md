# Temporary preparation cancellation — v1.21.63

Baseline main and production: v1.21.62/build 2162, `5efd3d5085d0db20ce2b1279a998377c21f83f72`. Scout independently accepted its unmatched-franchise recovery; that account/UI behavior is preserved.

## Reproduction and cause

`generate_fois_isolated` owns one temporary scratch directory and starts the existing league-scoped SQLite preparation with `asyncio.to_thread`. Its first wait was shielded. After cancellation, however, its drain awaited the preparation task directly. A second cancellation could cancel that task while its underlying thread continued. The enclosing temporary-directory cleanup ran first; the still-running real preparation then recreated its target directory, leaving residue.

Deterministic barriers around actual scratch storage and actual preparation reproduce one remaining directory after two cancellations. A controlled child process handling a real SIGTERM with repeated cancellation reproduces the same residue. Tests release and join the writer before inspecting residue; they do not rely on timing sleeps or delete files while a copy is active.

## Narrow correction

Keep every drain wait shielded until the owned preparation task completes, observe its result/error, then propagate the original cancellation. Do not clear cancellation, restart work, submit abandoned computation or publish from an abandoned request. Normal success/error behavior, copy contents, publication validation, league scope, worker shutdown and resource thresholds are unchanged. The event loop remains free while the existing thread finishes.

No new persistent state, schema, cleanup worker, archive, source copies or infrastructure. No sweeping or deleting another active operation's scratch directory.

## Controls and limits

`tests.test_fois_preparation_cleanup` covers success with real compute/publication, preparation failure, two/twenty cancellation requests, cancellation plus preparation failure, and thirty mixed operations sharing one source directory with zero remaining scratch directories/bytes after every completed operation. Rejected/failed/cancelled operations preserve canonical/cache bytes and never submit or publish. Existing FOIS semantic/process tests remain in force.

Linux additionally tests a real graceful SIGTERM and a forced SIGKILL. The graceful child drains repeated cancellation and leaves no scratch. **SIGKILL/power loss cannot execute Python cleanup:** the hard-kill control deliberately confirms one residual disposable directory and unchanged canonical data. Its fixture owner removes those known test files only after process exit. This is not evidence of automatic production orphan recovery. Forced event-loop/process termination and permanently blocked I/O are not given a cleanup guarantee; adding an ownership-aware orphan policy would be separate work, not an unsafe directory sweep in this patch.

The new module runs in the existing Linux recovery/lifecycle gate and isolated Linux/Windows tooling. POSIX signal controls are explicitly Linux-only. Full canonical, source/API/browser, onboarding/account isolation, Commissioner, Trade and source-recovery gates still apply.

Acceptance distinguishes controlled source/process tests, authenticated live read-only journeys, author-operated responsive Chromium and independent Scout review. Physical iPhone/Safari, human screen-reader/assistive-technology testing and genuine unfamiliar-user comprehension remain open unless independently completed. This release does not establish unconditional public readiness.

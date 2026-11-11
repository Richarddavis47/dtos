# Granite activation: held release and resume checkpoint

Recorded 2026-11-11 UTC after the managed Codex execution environment became unavailable. This is a new factual handoff, not reconstructed validation output.

## Status

HELD. PR #335 remains open, draft and unmerged. No new release draft, version tag, merge, immutable publication or deployment was performed. Existing Render read-only deployment inspection still reports live commit abbe723a0566cf84a8fff947cf7320cb66567a77 (v1.22.30/build2245). No production sync, cache clear, restart, Trade search, preference write, credential change or infrastructure purchase occurred.

Candidate: 836d036464bfb1e13cf350e44635620b0978f05d
Tree: d35a21d697d603d4eb4b4f46cf88e8a514c50d77
Branch: fix/activation-deferral-2246
Proposed version: v1.22.31/build2246 (not released)
Baseline tree: cf649ee06ec3228d51d251ce7afbdbb15866f398

## Findings and correction

The three supplied November10 failures are present in retained authorized Render logs. The last acquired cache_persistence before hydration failed, and the target runtime was DEFERRED. This supports a typed resource-deferral path. The retained records do NOT contain the exact original exception traceback, guard inputs or bounded cleanup result. They must remain unknown rather than being reconstructed from newer samples.

A nearby queued raw sample was 1,502,986,240 bytes of 2,147,483,648. Applying the separately supplied 35,839,104-byte cache size to the unchanged production formula gives 707,643,392 bytes required versus 644,497,408 bytes of illustrative headroom: approximately 60.22 MiB short. These are non-atomic historical inputs, not the exact original guard decision or fresh capacity. Working-set metrics around 902 MB are not raw cgroup usage. One intentionally pinned warm runtime is not proof of an eligible eviction or leak. No OOM was recorded.

The confirmed shared application defect is that accounts.prepare_activation caught LeagueRuntimeDeferred with all LeagueRuntimeError failures and rendered a generic failure. The candidate catches the typed outcome first, preserves private/no-store deferred API status and Retry-After60, and gives a waiting/manual-retry page without changing the saved league on deferral. No automatic retry or Trade search is added.

A bounded prospective log records already-calculated final restoration-plan inputs and already-performed cleanup counters. It adds no memory sampling, payload decoding, source calls or lease. Safe exception logging includes type/locations, not messages or private data. Future records cannot recover historical facts that were never emitted.

No memory optimization, active-context eviction, reserve reduction or admission-policy change is included. The effective2GiB cap,16x restoration allowance, FOIS768MiB, Trade256+128MiB, source compatibility, account isolation and fantasy calculations are unchanged. Shipping this patch would not itself establish Granite recovery.

## Completed evidence

Exact candidate focused validation: 47 passing route/preservation tests, including 12 new controls, four responsive sizes and keyboard return. The separate 12-test working-source run repeats that coverage and is not 12 additional unique tests. Local constrained native preflight, unused-memory/native-actuals and runtime-ownership guards passed with actual2GiB enforcement; cleanup and server liveness are fixture evidence. These are not private Granite demand measurements or live acceptance.

Unfrozen publisher guard checks:85 tests plus lint/compile passed. Final sealed publisher validation has not run.

Published original baseline/focused logs, patch, numeric incident facts, screenshots and checksums:
https://github.com/Richarddavis47/dtos/tree/5ec5e8149aa9d191d3204da29977c31fb15da460/.task-evidence/activation-deferral-2246/review

All61 manifest payloads and the checksum sidecar were read back byte-for-byte at that fixed commit. Manifest SHA256:
ec9b84d966a2fefe5be764e710c3ece69e6514106444bf3a3fe11d697073d620

Direct original focused console:
https://raw.githubusercontent.com/Richarddavis47/dtos/5ec5e8149aa9d191d3204da29977c31fb15da460/.task-evidence/activation-deferral-2246/review/focused-final-original.log

Patch:
https://raw.githubusercontent.com/Richarddavis47/dtos/5ec5e8149aa9d191d3204da29977c31fb15da460/.task-evidence/activation-deferral-2246/review/candidate.patch

Checksums:
https://raw.githubusercontent.com/Richarddavis47/dtos/5ec5e8149aa9d191d3204da29977c31fb15da460/.task-evidence/activation-deferral-2246/review/SHA256SUMS

Raw production Render reports remain private because they contain unrelated account/request context. Published incident-observations.json is an explicit numeric/event selection with original checksum, not a purported full original exception log.

Evidence-path corrigendum: the preliminary resource-preservation report lists two guessed nonexistent paths, src/platform/trade_admission.py and src/core/trades. Before disconnection these were corrected locally to existing src/platform/trade_execution.py and src/core/trade_intelligence with path-existence and unchanged-diff assertions. Native resource results and application source did not change. The original report remains preserved; the local corrected report and policy-review-path-correction.json must be included in the final evidence supplement. Do not silently rewrite the earlier fixed commit.

Earlier failures are separate: two expected failing-before route assertions; a wrong working-directory setup attempt; first focused40 executions with4 errors (three artifact Git-mount errors and one nonexistent test module), then corrected47passes; and initial evidence readback404 because ten ignored .log files were not staged. A new evidence commit included those originals and passed complete readback. No assertions, resource guards or compatibility requirements were weakened.

## Mandatory validation still incomplete

Exact source GitHub runs:
- Canonical: https://github.com/Richarddavis47/dtos/actions/runs/42924917437
- Product: https://github.com/Richarddavis47/dtos/actions/runs/42924917416
- Tooling: https://github.com/Richarddavis47/dtos/actions/runs/42924917333
- Linux lifecycle: https://github.com/Richarddavis47/dtos/actions/runs/42924917339

At the last remote reconciliation,11of13 required jobs passed; canonical and Product remained running. All six other Product jobs, both tooling jobs and three Linux lifecycle jobs passed. Expected final regression is4358 tests, not a claimed result. All ten canonical gates have NOT been established. Six uploaded original hosted archives were downloaded with API size/SHA256 and CRC checks; full15-archive/native guard reconciliation remains incomplete.

Local canonical began23:38:19UTC November10 in an actual2GiB/noextraSwap/twoCPU/network-none/UID1000 container, Python3.14.3. It uses the official unchanged ten-gate CLI. Last directly observed local progress was838started/837completed with no failure at that checkpoint; the full result and process cleanup are unverified after disconnection. Do not report either a pass or an assertion failure from lost execution access.

Container: dtos-activation-local-2246
ID: 9e7e3018e19dd8384266ba70d8a6916271eadad4d1e66eaf81cdac07bd33fc26
Image: dtos-canonical314:2245
Image digest: sha256:f70a0c6402700dfb954c99d8163d4164926f74435c34d2e7e462407151663ae6
Local outer observation budget120minutes, unchanged application/worker timeouts and2GiB policy. Never restart a completed run just because its console was interrupted.

## Exact execution blocker and recovery

The exec-server transport disconnected; command creation then returned "exec-server transport disconnected". Managed-environment status reported connectivity offline, observed_phase running, observations_current true, with no failure diagnosis. The selected environment is now explicitly unavailable. Retained environment diagnostic metadata returned history_status not_found and no capture. No reconnect/request_changes control is exposed. This does not establish a production failure, OOM, local test failure or a cause for the transport loss.

Required operator action: restore/reattach this task's existing authorized Codex execution environment. No production change or credential is needed. Recover the existing workspace before using a fresh checkout; do not reset or overwrite it.

Source: /workspace/dtos-2246-investigation
Local validation: /workspace/dtos-2246-local-validation
Evidence/methods: /workspace/2246-granite-activation
Durable detailed resume guide: /workspace/2246-granite-activation/NEXT_ACTIONS.md
Latest watcher checkpoint: /workspace/2246-granite-activation/WORK_STATUS.json
Canonical originals: /workspace/2246-granite-activation/local-canonical
Guarded controller: /workspace/dtos-publisher-2246
Established evidence checkout: /workspace/cache-sharing-handoff

Application source is committed/pushed. Final controller/evidence methods have uncommitted local work; their availability cannot be confirmed while the environment is offline. They are not claimed lost or remotely backed up. The baseline-derived controller was never pushed, dispatched or merged. An initial candidate-based controller was preserved separately and corrected before any dispatch; controller diffs must contain only the eight approved publishing paths.

After reconnection, inspect real container state/results and original logs first. Verify exact4358tests/all10gates/manifest/source/2GiB/noOOM/process exit and cleanup. Reconcile the already-running hosted runs and reuse trustworthy passing results; do not dispatch duplicate successful suites. If local originals are unavailable, identify that loss explicitly and rerun only required missing validation. No merge until complete.

Finish15native archives, source/tree checks, original readable consoles, corrected evidence supplement, sealed85publisher tests and immutable checksums. Use the established baseline-derived Actions controller with GITHUB_TOKEN contents:write: prepare exact draft/23attachments, verify every byte, expected-head squash PR335, assert merged tree unchanged, then publish/tag immutable v1.22.31 on the actual merged commit. Never merge the controller, use the legacy2191 publisher, retry Cloud direct asset credentials or waive a missing gate.

## Live acceptance and capacity options

No fresh authorized running-process preflight or owner browser entry/search was obtained in this session. Existing Render-local token200 is supplied MainChat evidence, not reproduced by Codex. The external Cloud401 was not retried. The associated owner-browser control and Render Shell/SSH capability are absent here.

Reliable live Granite access and the protected-search journey are NOT established. A successful fixture or zero live offers is not proof of protected exclusion.

When existing authorized access and fresh resources permit, Scout should:
1.Verify actual deployed release/commit/tree against final immutable evidence.
2.Use the existing Render-local token, without printing/exporting it, for one metadata-only GET /api/inspect/operations/restoration-preflight?league_id=1314695233040052224. No new coordinator, payload decode or lease; snapshot is advisory/non-atomic.
3.If it safely would admit and the owner session exists, make one normal connected-league entry. Stop on deferral, unknown telemetry or unsafe capacity. A cold context alone is not an engine failure.
4.For a deferred entry, verify truthful waiting/manual retry, typed503 API, Retry-After60, private/no-store and unchanged saved league, with no automatic heavy retry. Actual incompatible/source failure must remain distinct.
5.If entry succeeds, verify1QB/FLEX/K/DEF prepared compatibility. Separately verify current Trade readiness. Run one explicit protected search only if Trade capacity permits; resolve an actually owned exact player/pick ID and preserve settings/draft/comparison.
6.Record exact protected identity, applied settings and actual returned outgoing packages, including exploratory results. Same-year/round picks from other original franchises remain distinct. With zero returned offers, report live exclusion as unproven.
7.When results allow, open offer detail/comparison/history and return to the same offer/draft, ordered assets, mode and filters. Do not manufacture results or launch additional searches for navigation. Preserve saved goals, rankings, Custom method and submitted lineups.
8.Separate all live observations from deterministic fixture controls and physical Safari from emulated phone widths.

No forced sync, cache clearing, active eviction, restart, FOIS rebuild or real trade submission. Prospective authorized logs may identify the next actual admission reason/cleanup counters; absent records do not reconstruct history or establish reclaimed bytes.

Capacity options, not authorized actions: staying on2GiB may retain deferrals; measured ownership/catalog sharing needs representative compatibility/mutation/concurrency evidence; isolated background workers add infrastructure and are not demonstrated to solve this incident. Render list prices observedNovember10:2GiB standard$25/month,4GiB pro$85/month (+$60compute). A larger plan alone does not raise DTOS's explicit2GiB effective admission cap. A cap/policy change and representative validation require separate product authorization. No plan purchase, policy change or speculative memory optimization occurred.

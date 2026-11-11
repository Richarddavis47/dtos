Current execution location and state: see [LOCATION_AND_STATE.md](LOCATION_AND_STATE.md).

# Final-source local resource method

This is a prepared method, not an execution receipt. `run-local-resource.py` was authored without executing its Docker commands or native validation. It uses the sibling `common.py` contract: `BASE`, `IMAGE`, `SOURCE_CHECKOUT`, `load_source()`, `assert_checkout(source)`, `docker_base(source, readonly=True)`, `image_record()`, `write_json()` and `digest()`. `docker_base` returns the `docker run` flags ending in `--workdir /app`; this runner appends the immutable inspected image ID and Python command. `image_record()` requires the existing pinned image ID.

Run the method only after final/source.json identifies the clean final application candidate/tree and actual expected test count. The runner records that whole source specification; it does not use old4358/859 counts to certify expanded source. It requires all destination resource directories/receipts to be absent and refuses to overwrite any previous attempt. Preserve an unsuccessful attempt intact before preparing another destination.

The runner copies three retained native fixture files from `/workspace/2246-granite-activation/local-resident-refresh-candidate588/inputs` into new `final/local-resource-inputs`. It hashes the original and copied bytes before use and again at completion:

| Input | SHA256 |
| --- | --- |
| oneqb.json | 98d76b8452431ff3e6f961b6bddd9a654f7b6d23129d96cce60e52cbf79cb11b |
| superflex.json | 49915270f727cd3eb6a3a792b8531a487d7da96a06c031ee0e5a176887f69c81 |
| projections.sqlite3 | 43541f6a3c738d0ebeac0794cdfd7c009bd27f450816919315b824b512a7b708 |

It copies the existing 9,072,793-byte `/workspace/2246-granite-activation/local-restoration-unused/prior-study.zip` into new `final/local-restoration-unused/prior-study.zip`. The accepted full SHA256 is `df5c88eda13a0671104c76a943b05032d7adfa089d11e738785b11e35a932439`, matching the source workflow and native publisher guard. This archive is consumed as a frozen tool input. The method does not rerun the old profiling study, retrieve a production cache, profile Granite or establish live source parity. Native-actuals uses the existing tool's explicitly fictional matchup rows on disposable copies.

The common Docker prefix must enforce non-root1000:1000, memory2GiB, no additional swap, two CPUs, no network, read-only source at /app, shared Git metadata read-only and BASE at /evidence. The runner records the configured image reference, Docker-inspected immutable image ID/digests and actual Python runtime, then uses that immutable image ID for each invocation. It runs the unchanged final-source entry points sequentially:

1. `python -m tools.validation.restoration_preflight_gate --output /evidence/local-preflight`
2. `python -m tools.validation.restoration_unused_memory --archive /evidence/local-restoration-unused/prior-study.zip --output /evidence/local-restoration-unused/evidence --native-actuals`
3. `python -m tools.validation.resident_refresh_ownership --fixtures /evidence/local-resource-inputs --output /evidence/local-resident-refresh/evidence`

`DTOS_EXPECTED_HEAD` binds each invocation to the final candidate. Clean source is asserted before and after each case. Actual combined stdout/stderr and exact command/exit/timing/runtime/image/source receipts remain in each new local case directory. Failures stop sequential work and remain recorded without a pass claim. The shared guard module is loaded read-only with bytecode writes disabled from `/workspace/dtos-publisher-2246/tools/release/publish.py`; its hash is retained and checked for change.

For each successful native command, the runner writes the unchanged guard-compatible SHA256SUMS member population, seals a new ZIP in `final/local-resource-native-archives`, and applies the current publisher's native verifier: `verify_preflight`, `verify_actuals_restoration` or `verify_resident_refresh`. The original guards retain enforced cgroup, liveness, pressure/FOIS, cleanup/ownership, source identity and actual-score parity requirements. No threshold or reservation is relaxed. Guard receipts and archive/member hashes are retained in `resource-native-guards.json`.

Only all three actual command exits and all three native verifiers permit `resource-preservation-verified.json` with `source=load_source()` and `all_native_guards_passed=true`. This receipt is local resource acceptance only; complete final-source local/hosted canonical, product/capture, source-policy review and release publisher gates remain separately mandatory. The method makes no new claim about unchanged application policies merely because these native controls pass.

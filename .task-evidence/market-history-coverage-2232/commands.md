# Exact commands and evidence scopes

Baseline: bb71de7faa4ff112500d01f2e3547dbc4652715e; tree 4e0351fa02f2a3890f1ea15b97e73274d5f56808. Candidate: 08816b7419e350e95317de5f0268c23ac82bd717; tree d2d7ff68b22b855f9bd822400031a350ae6952e7. PR321.

All container commands use the verified Python3.14.3/Chromium156 runtime, enforced2147483648bytes/no swap, two CPUs, no network and UID1000. Source is read-only for focused controls; the full canonical checkout is clean and writable as required for compilation. No elevated tests or broad permission changes.

- Existing producer/store/compatibility controls:69passed (investigation/existing-focused.log).
- Original matched cache reproduction: investigation/baseline-cache-probe.log/json. Same current publication; API updates +100/two checkpoints to +120/three; cached HTML incorrectly stays old. Original new baseline controls and intermediate errors are separate, never final mandatory acceptance.
- Broad focused controls:102passed43.409s (investigation/focused-complete.log). Later added excluded-future and player-dossier controls are included in final exact-source scope.
- Exact committed controls: `DTOS_EXPECTED_HEAD=08816b7419e350e95317de5f0268c23ac82bd717 DTOS_MARKET_HISTORY_EVIDENCE=/evidence/browser-final python /workspace/2232-release/run-constrained.py -m unittest -v tests.test_market_history_coverage tests.test_market_history_coverage_browser`;16passed31.985s. Browser report8records/24screenshots.
- Canonical: `python /workspace/2232-release/run-clean.py`, unchanged `python -m tools.validation.validate_release` harness. Original full consoles and machine test/gate events retained. 8GiB scratch prerequisite retained.
- Existing5case preflight: `DTOS_RESOURCE_SOURCE=/workspace/current-season-history-candidate DTOS_EXPECTED_HEAD=08816b7419e350e95317de5f0268c23ac82bd717 python /workspace/2232-release/run-constrained.py -m tools.validation.restoration_preflight_gate --output /evidence/local-preflight`; original stdout copied byte-for-byte to required raw.log with checksum sidecar.
- Scoped separate Actions publisher: `python -m unittest -v tests.test_release_publisher`;43tests. Ruff in same pinned runtime. Publisher is isolated tooling, never merged application code.

Hosted normal workflows run on the exact candidate. The extended retained-history lane keeps the original29history controls and adds16Market controls. Source and evidence identity, all12required jobs, original ZIP digests/CRC and canonical manifests must be verified before the guarded publisher prepares. No direct Cloud credential asset upload is used.

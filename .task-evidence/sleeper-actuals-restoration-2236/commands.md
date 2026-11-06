# Exact-source commands

Baseline:4e63bfbf605c7a1cdd5ce1dc039424e862ab7efd/tree7b2dd610add3a536ba1112f92943ae5ccff5999c. Candidate:source.json.

- Matched source-to-render proof: source-to-screen.py against clean baseline then final candidate using the identical frozen restoration_fixture.py. Native source requests zero.
- Focused: see focused-exact.log;71tests including new12restore/render controls, existing native results, production and admission controls.
- Full local: python /workspace/2236-actuals-restoration/run-clean-final.py; exact invocation-final.json pins Docker/runtime, UID1000, real2GiB/no swap/2CPU/offline and unchanged canonical harness.
- Local native resource: DTOS_EXPECTED_HEAD=<candidate> DTOS_RESOURCE_SOURCE=<clean candidate> python run-constrained.py -m tools.validation.restoration_unused_memory --native-actuals --archive /prior/Granite-cache-restoration-memory-profile.zip --output /evidence/native-resource-final.
- Local metadata preflight: same constrained runtime, python -m tools.validation.restoration_preflight_gate --output /evidence/local-preflight.
- Hosted exact commands are preserved in source workflows and raw Actions logs.
- Publisher verification is separate: unittest tests.test_release_publisher, scoped Ruff and py_compile, then finalized-plan native recovery verification. Application validation is never replaced by publisher tests.

Original command/log bytes and source identities control where this descriptive index abbreviates paths. No production provider or heavy search commands are part of this validation.

The original e10f local run is retained separately. The final runner uses its own canonical-final output and fixture-final directory. Host-side evidence directory renaming after completion changes no payload bytes or source identity. Its unchanged actual invocation and script are preserved.

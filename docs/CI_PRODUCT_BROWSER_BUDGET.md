# Product-browser CI wall-clock budget

PR #241 initially ran on a ten-minute whole-job budget. GitHub job 116631445358 was cancelled while tests still made successful requests. Job 116636796584 spent approximately 45 seconds in setup and dependency installation, then reported all 296 tests OK in 558.868 seconds. Setup plus legitimate test execution exceeded the 600-second whole-job deadline. Cancellation followed the summary by less than a second; checkout cleanup finished within one second and final runner cleanup within seconds.

This establishes insufficient whole-job headroom, not a demonstrated cleanup hang. The first forced cancellation reaped still-running test/browser processes; that does not establish a natural shutdown leak. The Playwright route-cancellation callback also appears in an earlier passing run. No OOM or runner pressure telemetry establishes a memory cause. Different runner identities and concurrent jobs are observable, but their causal contribution to duration variation is unknown. The workflow defines no concurrency cancellation group.

Only product-browser changes: fifteen-minute overall job timeout and an explicit twelve-minute test-step timeout. The exact 296-test module command, assertions, other jobs, runner class and 2 GiB application/resource gates remain intact. The separate test-step bound preserves finite failure detection while leaving time for setup and ordinary cleanup.

Acceptance requires genuine GitHub SUCCESS, all 296 tests completed, normal post-actions/runner completion, and all other required CI checks green. Full regression and lifecycle/resource validation remain mandatory; a successful unittest summary alone never overrides a cancelled job. No production application behavior changes in this CI correction.

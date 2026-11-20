# Scout acceptance for DTOS build 2272

Candidate `05669cf734d6f002b769682f0e286b2b6cb1fd2d`

Validated source tree to require `86eb797b00d2214bd9bb676e9a2b5330d695f95c`

Scope is the prepared bye-week pickup shortlist in PR #361. Use a disposable prepared league for the deterministic cases. A production owner check should use an already prepared context and should leave the roster and saved settings untouched.

1. Open My Team, expand **See weeks and possible moves**, and verify the confirmed Week 9 RB gap in the fixture.
2. Open **Find Week 9 RB cover**. In the Free Receiver result, verify that the plan starts Free Receiver at FLEX and moves Example W 1 from FLEX to RB. The card must name Example W 1 and Sleeper's injured-reserve status and say the plan is conditional. Check that the status age and the waiver/lock notice remain visible.
3. Use contextual **Back**. Verify the same Week 9 details are open. Revisit My Team normally and verify its disclosure starts compact and can be opened with the keyboard.
4. Repeat with Example W 1 recently confirmed Active. Both moves should remain available on demand without the conditional warning. A stale or missing status must qualify the same plan. Verify the separate roster planner prefers a recently confirmed Active player over an IR alternative.
5. Confirm that each player occupies one legal slot, the acquired player is unrostered in the selected league, target-week projections retain their own source qualification, and a pickup addressing one gap does not promise to fill several. Preview at 320 and 390 pixels and desktop.
6. On a released build, verify `/health/ready` reports the expected version, build and deployment commit, and compare the deployment commit's tree to the final source receipt. An owner acceptance observation requires an authorized already-prepared league. Separate it from the disposable Chromium browser checks. Physical iPhone/Safari is a separate test.

Earlier focused failures are retained separately. The first candidate restored the disclosure on Back, but adding its ID also enrolled it in My Team’s separate session preferences. As a result, fresh visits reopened it, and established fixtures’ open gestures closed it instead. A navigation-only change still reproduced that issue. The final change scopes restoration to Back and reserves this disclosure for the navigation ledger, while leaving other My Team preferences in their existing path.

## Verified release and review evidence

DTOS v1.22.57 build 2272 is ready on production commit `c0c087ecf61a43849341216fa2eca14e97a456f0`. That merge has the expected validated application tree `86eb797b00d2214bd9bb676e9a2b5330d695f95c`. The released tag resolves to the deployed merge.

- Check [local original console pieces](checks/local-canonical/readable-console), [hosted canonical originals](checks/hosted-canonical), and [Product Browser originals](checks/hosted-product). Validate the files against [SHA256SUMS](SHA256SUMS).
- Check [guarded prepare](https://github.com/Richarddavis47/dtos/actions/runs/44834631572), [guarded publish](https://github.com/Richarddavis47/dtos/actions/runs/44835346864), and [production smoke results](release/production-smoke.json). The [immutable release](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.57) has 23 checksum-verified attachments.
- The first local canonical attempt completed all 4,663 tests with one existing 320×483 Trade Shop browser timeout. An isolated control rendered five offers and an isolated full rerun passed all ten gates. The original failing response's offer count was unavailable, so overlap with the concurrent capture remains an observation. The [failed originals](prior-attempts/final-source-local-320-shop-timeout) remain separate.
- The bye route was verified with disposable prepared Chromium fixtures at 320px, 390px and desktop. Public live readiness, the deployed navigation scripts and five read-only production smokes were verified. This workspace had no authorized signed-in owner session in Chromium. Physical iPhone/Safari was unavailable.

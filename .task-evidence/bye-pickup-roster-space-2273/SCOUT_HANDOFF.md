# Scout acceptance for build 2273

Candidate `93c249b22ff46f4eb3827022d00041f4ae06eb33`  
Expected validated application tree `e4914d82bd08938e7605df4be77037a422e7d3d8`

1. In a prepared disposable team, open My Team, expand **See weeks and possible moves**, and follow the Week 9 pickup link.
2. Check the roster-space line next to the pickup’s lineup fit and target-week Sleeper projection. The open fixture shows 5 of 6 active spots used. The Superflex fixture shows 5 of 5 and tells you to make room. That fixture has a spare IR place and spare taxi places. Neither adds an active spot.
3. Use the incomplete Sleeper membership fixture. Confirm the cards still show supported lineup fit and explain that active, IR and taxi occupancy could not be confirmed. An unsupported slot rule also yields an unknown limit. Older publications without source-verified roster membership stay unknown until a normal refresh records it.
4. Confirm the player is described as unrostered. Sleeper still determines eligibility to claim, waiver timing and locks. Where a lineup depends on an injured player, confirm that availability remains conditional.
5. Use contextual Back. Week 9 should still be expanded. Check that a stale league or franchise link cannot show the other team's shortlist.
6. From production, use an already prepared signed-in owner context if available. Verify any observed roster numbers independently against that league’s Sleeper configuration and current roster. Keep fixture, owner and physical-device results separate.

The verified public baseline was build 2272 on commit `c0c087ecf61a43849341216fa2eca14e97a456f0`.

## Release and evidence

- [PR #362](https://github.com/Richarddavis47/dtos/pull/362) shipped in [immutable v1.22.58 / build 2273](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.58), merge commit `2cf52c454e28fe0ac9442dd006473a3807c2f4ab`. GitHub’s annotated tag and the deployed commit resolve to the validated application tree above.
- The exact-source original local and hosted canonical runs each passed 4,665 tests and all ten gates under the enforced 2 GiB limit with zero OOM kills. All 13 required hosted checks passed. The 21 targeted tests include rendered 390px Chromium fixtures and native roster evidence through admitted preparation and restoration. The publisher unit run passed 181 tests.
- [Guarded prepare](https://github.com/Richarddavis47/dtos/actions/runs/44853151958) verified 23 draft attachments. [Guarded publish](https://github.com/Richarddavis47/dtos/actions/runs/44853451556) verified the immutable release and production readiness. Public smoke checks also confirmed the welcome and sign-in pages respond, and that private endpoints reject unsigned requests.
- Original consoles are under [checks](checks/), final screenshots are under [screenshots](screenshots/), the deployment proof is under [release](release/), and the superseded attempt is under [prior-attempts](prior-attempts/). From this directory, run `sha256sum -c SHA256SUMS` to check the readable evidence. The immutable release includes the full archives and its evidence manifest.
- Production acceptance was public and read-only. No signed-in owner session or physical iPhone/Safari run was available. The phone screenshots and Back checks are Chromium fixtures with prepared test leagues.

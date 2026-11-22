# Scout acceptance for build 2274

Candidate `3ffc907fd2340100afb762b133a5533fe0ad52dc`
Validated application tree `137d5aa04f710a36bcf1bb54008d0f915ab880fc`
[PR #363](https://github.com/Richarddavis47/dtos/pull/363)

1. In the prepared test league, open My Team and expand **See weeks and possible moves**. Tap **Find Week 9** to open the pickup shortlist.
2. Check that **Free Runner** still shows the verified roster count of 5 of 6 active spots used, the lineup benefit and a Sleeper target-week projection. The separate **Sleeper IR blocker** identifies Example IR 1. Moving that player to active uses the last spot, so the manager would need to make room for this pickup.
3. With 5 of 7 active spots used, an Out player in IR blocks adds when the league disallows Out on IR. Returning the player then leaves one active spot. Turn that rule on in the fixture, or use the verified PUP tag. The player remains eligible and the blocker disappears.
4. Check cases with stale status, stale roster placement, missing or conflicting status, and a missing league rule. The active count remains visible and the IR panel gives the specific qualification without asserting a lock. Current evidence does not predict future IR status, waiver timing or player claimability. All real actions stay in Sleeper.
5. Use contextual Back and check that Week 9 remains expanded. Check the shortlist at 390px for overflow. Test a real prepared owner league only if already safely available, and report it separately from the disposable Chromium fixtures.

Production baseline was v1.22.58 / build 2273, commit `2cf52c454e28fe0ac9442dd006473a3807c2f4ab`, tree `e4914d82bd08938e7605df4be77037a422e7d3d8`.

## Release and verification

- [PR #363](https://github.com/Richarddavis47/dtos/pull/363) shipped in [immutable v1.22.59 / build 2274](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.59), merge commit `d18abdcf6c9f8a83abf0a63a422b617f8b4801fb`. The annotated tag and deployed commit resolve to the validated application tree above.
- Local and hosted canonical validation each passed 4,666 tests and all ten gates under an actual 2 GiB cap. All 13 required hosted checks passed. The exact candidate passed 22 focused tests, including the Chromium phone journey. The publisher unit run passed 181 checks.
- [Guarded prepare](https://github.com/Richarddavis47/dtos/actions/runs/44987197147) and [guarded publish](https://github.com/Richarddavis47/dtos/actions/runs/44987582774) verified all 23 attachments and the immutable publication. Public readiness, welcome and sign-in checks passed. Private routes rejected unsigned requests.
- Read the [original consoles](checks/), [screenshots](screenshots/), [release records](release/) and [earlier attempts](prior-attempts/). To check the readable evidence from this folder, run `sha256sum -c SHA256SUMS`. The immutable release includes the full archives and its evidence manifest.
- The first hosted run correctly deferred a Trade request under pressure. An isolated Chromium process for each viewport lowered measured overhead while preserving the full test and admission policy. See the [first run](prior-attempts/hosted-canonical-44969401958/) and [matched replay](prior-attempts/trade-viewport-isolation-control/).
- Production acceptance was public and read-only. A signed-in owner session and physical iPhone/Safari were unavailable. The short-list and Back checks use Chromium fixtures with disposable prepared leagues.

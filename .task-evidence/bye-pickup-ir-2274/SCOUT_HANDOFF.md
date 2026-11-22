# Scout acceptance for build 2274

Candidate `d882a8b50554cf08d0f2c32346eb75cbb051f0bd`
Validated application tree `28719d3404610dc584e353e0b21c91a7969d84f5`
[PR #363](https://github.com/Richarddavis47/dtos/pull/363)

1. In the prepared test league, open My Team and expand **See weeks and possible moves**. Tap **Find Week 9** to open the pickup shortlist.
2. Check that **Free Runner** still shows the verified roster count of 5 of 6 active spots used, the lineup benefit and a Sleeper target-week projection. The separate **Sleeper IR blocker** identifies Example IR 1. Moving that player to active uses the last spot, so the manager would need to make room for this pickup.
3. With 5 of 7 active spots used, an Out player in IR blocks adds when the league disallows Out on IR. Returning the player then leaves one active spot. Turn that rule on in the fixture, or use the verified PUP tag. The player remains eligible and the blocker disappears.
4. Check cases with stale status, stale roster placement, missing or conflicting status, and a missing league rule. The active count remains visible and the IR panel gives the specific qualification without asserting a lock. Current evidence does not predict future IR status, waiver timing or player claimability. All real actions stay in Sleeper.
5. Use contextual Back and check that Week 9 remains expanded. Check the shortlist at 390px for overflow. Test a real prepared owner league only if already safely available, and report it separately from the disposable Chromium fixtures.

Production baseline was v1.22.58 / build 2273, commit `2cf52c454e28fe0ac9442dd006473a3807c2f4ab`, tree `e4914d82bd08938e7605df4be77037a422e7d3d8`.

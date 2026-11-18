# Weekly lineup recheck — v1.22.52 / build 2267

My Team and Matchups show the submitted-lineup check time and local fallback deadlines. Recheck lineup uses guarded Sync League and confirms a newer observation for the same session, league and week before reloading the same view. Unconfirmed or deferred refreshes withhold the old advice. Use Sleeper for any lineup change.

- PR #356. Candidate `50425621b657012cfcfab20cd459c88b1871b4c9`.
- Validated tree `81c163b88696ed1f8957fc3cdd24f39440b13e11`.
- Deployed commit `a2ab131751e6cc2c7c6c8aa13e0b09bcfe5dea25`.
- Immutable release https://github.com/Richarddavis47/dtos/releases/tag/v1.22.52 with 23 verified attachments.

The 49 focused checks passed. Local and hosted canonical validation each passed 4,645 tests and ten gates, with 13 required hosted jobs and 181 publisher controls passing. The enforced limit remained 2 GiB. The original navigation gate retained its 600px roster limit and overflow assertions. Public readiness and smoke checks passed. Individually recorded failed and superseded attempts remain separate.

The stale-to-fresh RB swap, Superflex, expiry, scope changes, failure and deferred cases used disposable fixtures. Screenshots came from Chromium. Physical iPhone/Safari and live prepared-owner verification remain untested. The session lacked an authorized prepared owner browser or Render Shell. No forced entry, sync or lineup mutation occurred.

# Scout acceptance — Weekly lineup recheck

PR #356. Candidate `50425621b657012cfcfab20cd459c88b1871b4c9`, tree `81c163b88696ed1f8957fc3cdd24f39440b13e11`. Verified starting build 2266 at `e64b59c22c71cb3378f40f2dbf69b0379ad42255`. Proposed build 2267. Confirm the final release and receipts before documenting production acceptance.

1. In an already prepared authorized owner session, open My Team and the current week in Matchups. Find **Recheck lineup** and **Submitted lineup last checked**. Compare the displayed submitted lineup with Sleeper. Observe whether the fallback is present and compare the local kickoff and recheck times with the underlying UTC timestamps.
2. Use the prepared RB fixture for the stale-to-fresh replay. Example BQ 1 is questionable and initially on the bench. Normal page visits preserve that prepared lineup. One explicit scoped recheck publishes the updated RB starter. Both pages show Example R 1 covering RB after the guarded response and refresh. Returning Example BQ 1 to the bench removes the fallback. The retained Superflex control verifies both moves in the same plan.
3. Trigger the fixture’s capacity deferral and source failure. The status stays on the same page, the last check time remains visible, and the previous plan is withheld. An unchanged observation or a changed week or league must never yield success. Historical weeks and another franchise must not expose the control.
4. At 320px, compare the localized date with the UTC `datetime` attribute using the supplied fixture captures. Confirm the earlier kickoff and expiry remain clear, the new control sits below the My Team roster, and the original 600px and overflow tests retained their assertions.
5. If an already prepared production context is safely available, use the existing guard for one normal authorized recheck. Leave submitted lineups, account settings and selections untouched. Record whether current evidence supports a fallback. Keep production smoke, authenticated observations, Chromium fixture evidence and physical device testing distinct.

No paid infrastructure, forced entry, credential export or Sleeper lineup change is needed.

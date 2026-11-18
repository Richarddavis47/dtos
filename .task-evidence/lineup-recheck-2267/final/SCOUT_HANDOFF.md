# Scout acceptance — Weekly lineup recheck

PR #356. Candidate `50425621b657012cfcfab20cd459c88b1871b4c9`, tree `81c163b88696ed1f8957fc3cdd24f39440b13e11`. Verified starting build 2266 at `e64b59c22c71cb3378f40f2dbf69b0379ad42255`. Proposed build 2267. Confirm the final release and receipts before documenting production acceptance.

1. In an already prepared authorized owner session, open My Team and the current week in Matchups. Find **Recheck lineup** and **Submitted lineup last checked**. Compare the displayed submitted lineup with Sleeper. Observe whether the fallback is present and compare the local kickoff and recheck times with the underlying UTC timestamps.
2. Use the prepared RB fixture for the stale-to-fresh replay. Example BQ 1 is questionable and initially on the bench. Normal page visits preserve that prepared lineup. One explicit scoped recheck publishes the updated RB starter. Both pages show Example R 1 covering RB after the guarded response and refresh. Returning Example BQ 1 to the bench removes the fallback. The retained Superflex control verifies both moves in the same plan.
3. Trigger the fixture’s capacity deferral and source failure. The status stays on the same page, the last check time remains visible, and the previous plan is withheld. An unchanged observation or a changed week or league must never yield success. Historical weeks and another franchise must not expose the control.
4. At 320px, compare the localized date with the UTC `datetime` attribute using the supplied fixture captures. Confirm the earlier kickoff and expiry remain clear, the new control sits below the My Team roster, and the original 600px and overflow tests retained their assertions.
5. If an already prepared production context is safely available, use the existing guard for one normal authorized recheck. Leave submitted lineups, account settings and selections untouched. Record whether current evidence supports a fallback. Keep production smoke, authenticated observations, Chromium fixture evidence and physical device testing distinct.

No paid infrastructure, forced entry, credential export or Sleeper lineup change is needed.

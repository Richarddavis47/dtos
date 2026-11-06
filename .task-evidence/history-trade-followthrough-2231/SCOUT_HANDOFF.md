# Scout acceptance: Franchise History to trade follow-through

Verify this release independently. Fixture success is not authenticated live acceptance.

- Candidate: `0c37dfd70bdcca68ddea2a3bf75cbd3a47e60f0f`.
- Validated tree: `4e0351fa02f2a3890f1ea15b97e73274d5f56808`.
- Baseline: v1.22.15 / build 2230, `3639a5f51270522c9f6a73971cb52226df343bef`, tree `c251edcf8a6d2a35b157deb916a8cfb7869d6344`.
- Target: v1.22.16 / build 2231, PR #320.

This prepared document alone does not establish release completion. Verify the final immutable release, merged-source record and production smoke evidence.

## Release integrity

1. Verify the annotated tag resolves to the approved PR #320 squash merge and its tree equals the validated tree above. Require all 12 hosted jobs and both complete ten-gate canonical runs against this exact candidate. Do not count the skipped legacy publish-2191 job or platform-inapplicable steps as executed tests.
2. Download the original archives; check the complete manifests and SHA256SUMS. Read the full canonical consoles or concatenate their numbered line-boundary parts and compare hashes. A progress counter does not establish successful completion.
3. Verify Actions preparation passed before merge. Publication must use the same frozen publisher, exact source and artifact digests, and unchanged merged tree. Verify immutability and every release attachment. The separate public handoff manifest and publication receipt cover its accessible copies.
4. Inspect the complete patch and protected-object identities. The only application behavior change preserves the read-only `events_page` parameter in the existing contextual Back URL allowlist. Core history, Trade, prices, grading, scoring, routes, authentication and admission code are unchanged. No new timeline engine was built.

## Reproduced defect and original evidence

5. Read the original matched baseline probe: History page 1 -> page 2 -> completed trade -> Back returns to page 2, but the next Back incorrectly points to League. The navigation ledger discarded events_page and treated both history pages as identical. The corrected matched probe preserves page 1 as the preceding meaningful page.
6. The first baseline JSON snapshot was overwritten by the first after-probe. Its original failing console survives. A separately labelled baseline-source replay is another execution on the same baseline tree, not recovered original bytes. Import/router setup, future-clock, fixture store-binding, canonical string-type and publisher setup errors remain separate.
7. Candidate 606d45851990697194863facc2fa263245a91d4e passed 620 Product tests in 1191.990 seconds and 16 historical-worker tests in 14.115 seconds, exceeding their aggregate 20-minute CI step before overhead. Later steps were skipped, never accepted as passed. The final candidate permits 25 minutes for that aggregate step, preserving both commands, every assertion, application/browser timeouts and resource controls. A structural comparison verifies this. Superseded local and hosted canonical runs were cancelled and their original partial evidence retained separately.

## Actual fixture/browser journey

8. Inspect eight screenshots and the browser report at 320x432, 375x667, 390x844 and 1280x900. The Day Traders retained replay supplies original trade 1333655835015942144, exact pick PICK-2026-R2-ORIG7, selected player DTOS-P-13346 and later trade 1414718106177122304. The 26 pagination waivers and test accounts are disposable, not live transactions.
9. Follow the clicked chain: paginated Franchise History -> original multi-asset package -> pick dossier -> selected player -> later trade -> original-trade link. Confirm pick season 2026, round 2 and original franchise 7 remain distinct from holder and selecting franchise. Later exchanges must remain separate packages; the model says Package relationship only rather than inventing one-to-one lineage or descendant value.
10. Follow contextual Back through the entire chain and both history pages. Test native Forward and reload preserving page 2 and its Back target. Check keyboard focus, touch emulation, disclosures with no extra requests, and no horizontal overflow. Physical iPhone/Safari is untested.
11. Each Day trace includes the final subsequent Arkham membership-switch URL as complete chronology; it is not a claim that Arkham supplied the Day trade. Separate Arkham records check retained-source qualification and scope reset. Real account/session middleware and the existing navigation-context endpoint are used. A disposable selected-league switch must not replay Day history. Foreign league/franchise destinations remain unavailable; an untrusted original-trade origin loses its return link.
12. Inspect current-season fixtures using real owned publication, cache restoration, eviction and reopening. Retrieved Weeks 1–8 stay Partial and supported original/later trade links remain available. Existing actual sync/save controls remain mandatory. No private production cache was decoded; fixture provider replies and account/preparation adapters are disposable.
13. Missing event clocks retain original consideration while withholding unsupported continuation. Pending/failed records are proven retained via the API but cannot appear as completed asset movements. Missing periods, uncertain ownership/takeover timing, observed current ownership versus uninterrupted holdings, and current prices versus historical quotes remain qualified. FOIS grades retain RETAINED / NOT REVALIDATED. No retrospective decision grade or causal championship credit is inferred.

## Resources and safe live check

14. Verify actual 2 GiB / no-swap / two-CPU / network-none enforcement, normal worker completion, capacity deferral, recovery, cancellation and cleanup. Preserve independent FOIS and Trade policies. Pressure-fixture peaks do not represent ordinary navigation demand, and bounded cleanup observations do not establish long-term leak freedom.
15. Confirm public readiness/version/commit independently. Codex public smoke establishes deployment and authentication boundaries, not private history completeness. This session has no associated owner-browser or Render Shell/SSH execution capability. The previously rejected external Cloud inspection binding was not retried. Do not request repetition of the already completed Render-local credential check.
16. Only if an authorized signed-in browser and safely warm compatible publication already exist, inspect Franchise History in a supported connected league. Do not force cold hydration, Sync Now, FOIS rebuild, cache clearing, restart or Trade search to obtain acceptance. If safe entry cannot be established, mark live acceptance unverified and stop that attempt.
17. Select an actually retained completed trade. Record sanitized league, season, source and observation time. Follow a supported later movement and exact pick conversion where available, then return through the original-trade link and contextual Back, including pagination. Missing branches must remain qualified. Do not infer historical prices, decision quality or championship causality.
18. Confirm correct account/league/franchise context and no mutation of rankings, valuation method, goals, submitted lineups, trades or source data. No new source acquisition or history reconstruction is authorized by this handoff.

Report PASS, PARTIAL or HELD separately for source inspection, fixtures, hosted artifact integrity, public deployment and authenticated live observations. This navigation correction does not fill missing historical periods or establish live Granite recovery.

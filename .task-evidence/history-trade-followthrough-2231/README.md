# Franchise History to trade follow-through — v1.22.16 / build 2231

Released through [PR #320](https://github.com/Richarddavis47/dtos/pull/320) and the [immutable release](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.16). Candidate `0c37dfd70bdcca68ddea2a3bf75cbd3a47e60f0f`; validated tree `4e0351fa02f2a3890f1ea15b97e73274d5f56808`; deployed merge `bb71de7faa4ff112500d01f2e3547dbc4652715e`. [Complete patch](candidate-production.patch), [source/patch integrity](source-integrity.json), [production smoke](production-readonly-smoke.json), [Render live deploy](render-deployed.json), [verified publication/attachments](publication-verified.json), [full Scout acceptance prompt](SCOUT_HANDOFF.md).

## Customer outcome and confirmed defect

The original exchange, observed later trades, exact pick conversion, current observed ownership, source limitations and original-trade links already worked. They are reused. The reproduced integration defect was contextual Back: its URL filter dropped events_page, stored History pages 1 and 2 as identical and skipped page 1 after returning from a trade. The only application behavior change preserves that existing read-only pagination parameter in the existing bounded navigation mechanism. Routes, canonical history/graph/timeline, prices, grades, scoring, source acquisition and admission policies are unchanged.

The original matched baseline console fails at the next Back target (League instead of the preceding History page). The corrected matched probe passes. Actual clicked controls follow History -> original multi-asset trade -> exact pick -> selected player -> later package -> original trade, then Back through every prior page and both History pages, native Forward and reload. Real disposable account/session middleware and the navigation-context endpoint verify scope. A selected-league switch resets former-league return context.

## Final exact-source validation

| Evidence | Result |
|---|---|
| Broad focused source/timeline/navigation controls |123 passed (122.179 s)|
| Exact-candidate new source/render/browser controls |7 passed on the final source (see focused-exact.log); 8 viewport/league records and 8 screenshots|
| Local mandatory regression |4,136 passed; all 10 canonical gates passed|
| Hosted mandatory canonical |4,136 passed; all 10 canonical gates passed|
| Required hosted jobs |12 of 12 passed|
| Main Product executions |665 passed (620 + 16 + 29)|
| Publisher scoped integrity/security controls |42 passed|
| Canonical manifest payloads |590 local / 594 hosted; all checksums verified|

[Original full local console](original-local-canonical/unittest-console.log?raw=1), [original full hosted console](original-host-canonical/unittest-console.log?raw=1), [readable numbered logs](LOG_INDEX.md), [all hosted records](hosted-final-records.json), [local result](local-verified.json), [hosted result](host-canonical-verified.json). Original failed/incomplete/intermediate attempts remain [separate](prior-originals) and in [2231-prior.zip](2231-prior.zip). No unexecuted gate or deferred worker is counted as successful completion.

Both canonical runs use an actual 2,147,483,648-byte memory/no swap/two CPUs/network none. Local kernel peak 2,026,446,848 bytes; hosted 2,043,236,352 bytes; no OOM/OOM-kill. Dedicated existing Trade/league-entry/FOIS worker execution, deferral, recovery, cancellation and cleanup controls pass on this exact source. Peaks from deliberately pressured fixtures do not represent ordinary navigation demand, and cleanup observations do not prove long-term leak freedom. [Protected-object identities](preservation.json) establish unchanged core/platform/routes/services/components. The 8 GiB validation scratch prerequisite remains intact; scratch cleanup removed only a recorded obsolete dependency-image backup, not original validation evidence.

## Evidence categories and remaining limits

Day Traders' bounded retained replay supplies original trade 1333655835015942144, pick PICK-2026-R2-ORIG7, selected player DTOS-P-13346 and later trade 1414718106177122304. Pagination waivers and accounts are explicitly disposable. Arkham retained history is an independent scope/qualification control, not an invented auction-pick conversion. Day traces include the final subsequent Arkham membership-switch URL as the full chronology; separate records verify scope reset. Four sizes 320×432, 375×667, 390×844 and 1280×900 pass keyboard/touch emulation, focus, overflow and disclosure-request controls. Physical Safari is untested.

Current-season disposable Weeks 1–8 survive real fresh owned publication, cache restoration, eviction and reopening through rendered history/trade routes. Existing actual sync/save tests remain mandatory. Missing clocks preserve original consideration while withholding continuation; pending/failed API records never become completed movements. Exact pick originals remain distinct from holders/selecting franchises. Missing periods, ambiguous manager tenure, current observations versus uninterrupted holdings, current prices versus historical quotes and FOIS RETAINED / NOT REVALIDATED stay qualified. No retrospective decision grade or championship credit is inferred.

The initial baseline JSON snapshot was overwritten by the first after-probe; its original failing console remains. A separately labelled baseline-source replay is another actual execution on the same source tree, not a recovered original snapshot. Import/navigation-router, future-clock, fixture store-binding, canonical API type and publisher lint setup failures are preserved and corrected without relaxing application assertions or resource policy. No immutable historical evidence was replaced. The first guarded preparation correctly refused a recovery archive missing the local preflight raw-log subpath. The original console already existed; its exact bytes were copied to the required subpath and a new checksum sidecar was generated. No test was rerun or reconstructed. The original failed publisher revision, logs and outcome are retained; only evidence packaging and its guard were corrected. The initial 606 candidate passed 620 + 16 Product assertions but exceeded the aggregate 20-minute CI deadline. Later gates were skipped, never accepted as passing. The bounded 25-minute CI deadline correction retains both commands, every assertion, application/browser timeouts and resource policy. Superseded 606 local/hosted canonical attempts were cancelled; their partial original bytes and archive remain separate from final acceptance. The structural verifier initially failed on an unnamed YAML step, and a publisher host-runner path/host Ruff availability issue were corrected using the pinned validation runtime. Original errors remain preserved.

Public readiness, immutable publication and bounded guest smoke are live observations. Private authenticated history was not inspected: this session has no associated owner-browser control or Render Shell/SSH capability, and the previous external Cloud inspection 401 was not retried. Fixture/replay success does not establish a new live Granite/Day/Arkham result. No production sync, FOIS rebuild, Trade search, cache clear, restart, user-data or saved-setting mutation was initiated. Source gaps remain genuine limitations; this release does not acquire missing periods.

[SHA256SUMS](SHA256SUMS) · [Complete manifest](manifest.json) · [Scout prompt](SCOUT_HANDOFF.md).

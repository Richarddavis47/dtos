# Current-season franchise history — v1.22.15 / build2230

Released via [PR319](https://github.com/Richarddavis47/dtos/pull/319) and the [immutable release](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.15). Candidate `bd456e40fc4ab9ef1925369f82f9b72ca45589ad`; validated tree `c251edcf8a6d2a35b157deb916a8cfb7869d6344`; deployed merge `3639a5f51270522c9f6a73971cb52226df343bef`. [Complete patch](candidate-production.patch), [patch/tree reproduction](patch-verified.json), [source identity](source-integrity.json), [deployment/readiness](production-readonly-smoke.json), [Render live deploy](render-deployed.json), [publication and verified attachments](publication-verified.json), [complete Scout prompt](SCOUT_HANDOFF.md).

## Confirmed cause and correction

Saved-runtime restoration and cached default startup published compatible source data without registering that owned reference with canonical current-season history. Fresh sync did register it. The actual baseline source tree failed all three matched restoration controls despite retained Weeks1–8 and a completed trade. The shared publication hook fixes both restored entry paths. Owned eviction releases the same source reference; a late old close cannot remove a replacement. No provider request or historical backfill runs merely to render history.

Acquisition metadata was also discarded: failed prior-week requests could retain old evidence without retaining the acquisition/failure qualification. The same bounded source requests now record compatible per-period observations and actual completion timestamps, keeping observed-empty, failed, unavailable, malformed and unacquired separate. Retained rows stay usable and truthfully qualified. Legacy dates remain unknown. A foreign league or season cannot supply fallback evidence. Coverage/freshness participates in the canonical view fingerprint. Current seasons remain Partial when evidence exists and Unknown when no acquisition is established, never Complete merely because they are ongoing.

## Final exact-source acceptance

| Evidence | Outcome |
|---|---|
| Focused history/source/runtime/render checks |117passed,49.022s|
| Local complete regression |4129passed,all10canonical gates passed|
| Hosted complete canonical |4129passed,all10canonical gates passed|
| Required hosted jobs |12of12passed|
| Main Product job |658executions passed,including22new current-history controls|
| Separate publisher integrity/security controls |41passed|
| Canonical manifest payloads |581local / 585hosted; every byte/checksum verified|
| Responsive current-history controls |12:3independent league shapes×320x432,375x667,390x844,1280x900; keyboard/touch emulation,nooverflow or extra disclosure requests|

[Local result](local-verified.json), [original full local console](original-local-canonical/unittest-console.log), [readable local parts](readable-console), [original full hosted console](original-host-canonical/unittest-console.log), [readable hosted parts](readable-host-console), [Product decoded original](hosted-logs/127485496255.log), [readable Product parts](readable-product-console), [all hosted records](hosted-final-records.json). Each split concatenates byte-identically to the original. Additional large decoded job logs also have readable-job directories. Native Actions release archives preserve original downloaded ZIPs and verified digests.

Local kernel peak2008510464bytes; hosted kernel peak2067222528bytes. Both run under actual2147483648-byte memory/no swap/two CPUs/network none; no OOM/OOM-kill. Dedicated existing Trade, league-entry and FOIS lifecycle controls remain mandatory and independently verified. Full-suite pressure-test peaks are not normal navigation demand or a production worst-case profile. Cleanup observations do not establish indefinite leak freedom.

## Preserved behavior and limitations

Controls exercise real sync/save/restore/render, manager eviction/reopening, default startup, isolated accounts/leagues, source mismatch, legacy caches, current-only refresh and retained failures. Existing completed-season pagination, deduplication, pending/rejected separation, exact moved-pick original franchise/year/round, qualified ownership and FOIS RETAINED / NOT REVALIDATED remain covered. [Preserved object identities](preservation.json) establish unchanged Trade/valuation/scoring/resource source. No saved settings, rankings, goals, valuation methods, lineups or trades were modified.

Granite-shaped1QB/K/DEF and Day/Arkham-shaped Superflex evidence is disposable, not authenticated live history or an exported production cache. Supplied live build2229 Granite Unknown2026 coverage did not establish which weeks had been acquired. This release fixes a demonstrated reusable source path but does not retrospectively prove that particular live cause. This session lacks an authorized owner-browser or Render Shell execution surface; the prior external Cloud inspection401 was not repeated. Public production smoke proves deployed identity and authentication boundaries, not private season completeness. Physical iPhone/Safari is untested. No live sync, FOIS rebuild, Trade search, cache clear, restart or user-data write was used.

[Original prior logs](prior-original-logs) and [separate prior archive](2230-prior.zip) preserve every intermediate failure and setup limitation. The first nonnumeric-ID probe is distinct from the matched baseline reproduction. An intermediate timestamp-placement serialization defect and Playwright-loop fixture setup error were corrected and rerun; no admission guard or assertion was weakened. Earlier release evidence and immutable histories remain untouched.

[SHA256SUMS](SHA256SUMS) · [Full manifest](manifest.json) · [Complete Scout acceptance prompt](SCOUT_HANDOFF.md).

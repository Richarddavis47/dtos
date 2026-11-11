# Read-only Recovery offer-copy reuse audit

Exact candidate `4cf524c488efb36c77defd78bfd7acf84a3f6ddd`, tree `79fe9268fb3394604559bbcbe1119616a080b71b`. Current Recovery is **114,866,370 bytes**, exceeding the unchanged 100 MiB cap by **10,008,770 bytes**.

The smallest sufficient change is omitting only its **26 standalone offer-comparison copies** (**11,600,941 stored compressed bytes**). Those copies match the existing `capture-extraction.json` SHA256 records and the already-required, whole-ZIP/SHA-verified `trade-resource-original.zip` under `browser/offer-comparison/`. Original/Recovery central-directory sizes and CRCs also agree for every selected member. No member was decompressed by this audit.

Subtracting only that data estimates **103,265,429 bytes**, leaving **1,592,171 bytes** before small metadata changes. This is not final archive acceptance; real sealing/native verification remains required.

Keep the other three standalone families, all **687** local canonical payloads and sidecars, all **15** native originals, all **13** hosted jobs and **23** attachments. The publisher already calls the same offer guard on the downloaded original after API head/run/SHA/size/ZIP checks (publish.py:1274–1300). Retain that return value, require it present, and use it in VALIDATION instead of the duplicate Recovery call at line1326. Offline verification should check the exact plan-bound original and call the unchanged default `browser/offer-comparison/` guard. `make-recovery.py:24–25` removes only this one copied folder.

The other producer mapping is important: partner-history belongs to `public-welcome-security.zip` / `trade-partner-history/`, not the Trade artifact. That mapping and those copies remain untouched in this minimal choice.

Existing `OfferComparisonEvidenceTests` already reject foreign/dirty source, missing images/views, false gains/costs, missing depth/stale/custom controls and missing real qualification. Extend existing positive-control/plan missing-artifact subtests to verify default native namespace, reject wrong namespace and require the original Trade artifact, without changing predicate bodies or the existing102 method population unnecessarily. Then run all scoped publisher tests/Ruff/compile and actual sealed offline/native preparation controls.

No application, method, controller or archive was modified. No tests, Docker, imports or network requests ran. Full details and source hashes are in `recovery-offer-reuse-readonly-audit.json`.

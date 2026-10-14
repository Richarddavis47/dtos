# Home Trade News corrections — v1.21.46 / build 2146

Starting baseline v1.21.45 / 2145, a9e433d7e92a0508f8fdacda02ce6e1240338273. Main reconciled before implementation. This follows the supplied October 13 mockup, previous release handoff and Scout's detailed controlled/live findings. The private complete acceptance report was not supplied as a separate repository file.

## Corrections

Home now presents the controlled franchise, official record/standing and My Team/Trade actions before News. The accepted strength label remains available; advanced assessment context stays optional. Large trades (more than four original consideration items) preview one received item per participant and disclose how many additional items they received. Independent **Complete Assets** contains every admitted original player, exact pick and directed FAAB item, including the previewed items. Counts describe unique original consideration, not transaction legs. Evaluation and Source & pricing remain independent, closed native disclosures. Smaller Boston packages remain fully visible. Existing player headshots/initials and position letters are reused; readable typography and 44px controls remain.

The reported Market race was reproduced through `refresh_public_market`, canonical normalization and the real news consumer: coherent old 1138, coherent new 1125, interrupted 1150. The previous consumer accepted that mixed total. Normalization now builds detached replacement provider/pick tables, checks that its source has not changed and commits both tables under a shared preparation/read lock. Failure leaves prior references untouched; fallback tables shared with another league are not modified. The league sync finishes normalization before publishing its new league data. There is no new pricing formula or permanent publication store.

Home captures a detached, fingerprint-checked canonical publication before building its cache key. The same publication feeds batched player facts, exact-pick prices, source qualifications, comparison and ranking. A concurrent replacement can leave the completed old publication visible for that read; the next read uses the new publication. Two bounded capture attempts detect legacy edits outside the preparation lock. Unstable or incompatible evidence keeps qualified individual observations but withholds comparable subtotals, full totals, advantage, bar and value ranking. Asset-specific fact IDs are not treated as a shared source identity. Canonical normalization reference/version/provider/format and population-generation safeguards remain required.

Existing canonical freshness, fallback, warning, provider/context, normalization references and independent observation/retrieval clocks flow into compact primary qualifications and full Source & pricing. Missing, incomparable, stale/fallback and retrieval-only source timing remain distinct. No new confidence calculation; values remain current displayed evidence, never trade-date grades. FAAB remains unpriced original consideration.

## Controlled rendered measurements

Same captured Boston and eleven-item transaction, authenticated isolated actual router, controlled prices and identical Chromium/viewports. These are not authenticated production measurements.

| Viewport | Eleven-item card, before → after | Boston, before → after | Primary actions, before → after (page Y) |
| --- | --- | --- | --- |
| 320×568 | 1,279 → 623 px | 684 → 581 px | 2,674 → 399 px |
| 375×667 | 1,022 → 571 px | 630 → 546 px | 2,345 → 381 px |
| 390×682 | 1,022 → 550 px | 630 → 546 px | 2,345 → 381 px |
| 1280×900 | 749 → 462 px | 517 → 458 px | 2,004 → 501 px |

The eleven items are verified after pointer expansion at every width; keyboard collapse and independent Evaluation/Source activation, hit targets and document containment are checked. Tall 390×844 and short 390×432 are included. Small headshots use the existing image renderer; portrait fixtures test layout/fallback, not real face-image accuracy. No physical iPhone/Safari claim.

## Preserved contracts

Completed/status-update clock admission; exact rolling `(now−168 hours, now]`; per-trade expiry before warm cache lookup; six-card maximum; complete comparable value ordering with stable time/ID ties; qualified unknown-size placement; first two cards visible and More completed trades; Boston receiving direction; multi-party direction without a false two-sided winner; FAAB once; original trade/Home return; selected-league isolation; historical lineage/Market/FOIS/standings/projection/Trade protections.

Caches remain the existing process-local 24-entry/2 MiB news cache and bounded shared facts. Snapshot copies last only for preparation/read work. No feed archive, transaction copy database, read/unread state, provider polling/backfill, scoring or pricing model, migration, grade regeneration or Sleeper mutation.

## Independent Scout handoff

Report authenticated live, actual source replay, controlled prices/concurrency, responsive Chromium and physical device coverage separately.

1. Day Home at 390×682: own franchise, record, supported standing and primary actions before News. Check 320/375/390, tall/short portrait and desktop with actual pointer hit-testing and keyboard focus.
2. Eleven-item transaction **1415021723840966656**: concise received previews; Complete Assets closed initially, count 11, full five players/six exact picks with original franchises and directed owners. Opening it must not open Evaluation. Closing/reopening must preserve all items and links.
3. Boston **1414718106177122304**: Chase receives Denzel Boston; Week3 receives De’Zhaun Stribling and Chase's exact original 2029 R2. Requery current values; do not expect the old mockup prices. Current-value totals/gap/bar and trade-date caveat remain visible.
4. Historical FAAB **965057520920260608**: three players, five picks and one 100 FAAB 3→6 in its source league/time. It is not a current seven-day news item. Source-time fixtures should retain all nine consideration items; no Market price for FAAB or artificial multi-party winner.
5. Source & pricing: failed provider refresh retains allowed prices with fallback qualification; stale/unknown source time remains qualified. Inspect provider/format, canonical units, normalization version/generation, source observation and retrieval independently.
6. Canonical producer/consumer race: old 1138/new 1125/interrupted 1150 case must retain coherent old/new values or unavailable comparison. No mixed 525/625 gap 100 or bar in actual HTTP output. Failed normalization, concurrent source replacement, repeated same source, incompatible scale/format, missing prices and six-card ordering must fail closed appropriately.
7. Cache: refresh changes next Home read; an aging trade disappears without league sync; unstable capture recovers once stable. Day→Arkham→Day, matching roster IDs and quiet Arkham remain isolated.
8. Native independent disclosures, no nested asset/evaluation requirements, original completed trade→Home, reload/Back/Forward, More completed trades, six cap, no document overflow/sticky obstruction.
9. Existing standings/trophies, Weekly Report, My Team/Matchups, Trade/Calculator/Balance/Shop/Trade For, exact protections/strategy, Boston/Love history and retained FOIS NOT REVALIDATED remain regression gates.
10. Settled unchanged producer/consumer/HTTP reads must leave source and durable-file sizes/hashes unchanged. Existing 2 GiB ordinary/archive-warmed/combined-read and recovery/quiescence gates remain unchanged.

Measurements and final gate/release evidence are reported separately after execution. Local controlled timings are not production latency or a physical iPhone/Safari pass. Scout's independent deployed acceptance remains separate.

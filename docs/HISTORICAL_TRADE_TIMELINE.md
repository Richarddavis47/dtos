# Historical Trade Timeline Foundation — v1.21.37 / build 2137

Baseline: v1.21.36 / 2136 / 93c74af40952e906fecfac570454739239196289. This release extends existing canonical history and historical trade dossiers. It adds no permanent database, projection/pricing model, historical grade regeneration, provider backfill or legacy history migration.

## Source and identity contracts

Selections have exact source league/draft/selection identity. Selecting roster and original franchise are separate; `picked_by` remains a manager user ID. Explicit source originals and supported linear draft `slot_to_roster_id` mappings establish future-pick conversion. Auction selections remain distinct selection events, never synthetic franchise-pick exercises. Current and completed-season producers retrieve draft detail once per draft and share the selection decoder with the existing exact-lineage writer/read contract. Old ambiguous lineage rows remain untouched.

The source-backed fixture identifies Love (13287), selection 1, original roster 4, selecting roster 5; Boston (13346), selection 12, original roster 7, selecting roster 4, followed by completed transaction 1414718106177122304. Draft 1313066632167325696 provides the exact mapping. Arkham's auction provides 260 independent selections. Fixture data is an explicitly partial read-only October 12 source capture, not a second application archive.

Actual source-season league IDs accompany archived transactions/selections; root league/franchise scope remains separate. Missing origin is not replaced by current holder. Existing cached seasons lacking a validated draft mapping remain unconfirmed; there is no bulk cache repair or legacy reinterpretation. Ordinary existing source preparation can supply new compatible facts.

## Quote clocks and historical admission

Trade reference time, provider quote observation time and source knowledge time remain distinct. New shared observations retain their provider clock; later quotes cannot become prior-event evidence. Current reads recheck raw provider clocks independently of legacy attachment dates, preserving old rows. Explicit knowledge clocks govern admission; otherwise a provider publication observation is the available knowledge boundary, never application retrieval substituted as historical publication.

Historical dossiers use the existing strict comparison identity (provider, canonical concept/scale, format and normalization) and typed exact pick lookup. `future_pick` and legacy `pick` contexts are explicitly searched without context-free fallback. Missing pick prices, unknown clocks, foreign explicit league context and incomparable scales withhold fairness totals. Genuine zero remains valid.

Exact compatible evidence is distinguished from dated estimates. Age/confidence and original source evidence are disclosed. Snapshot proximity alone does not establish stability. No current price, drafted-player price, range average or extra-year discount is substituted. No automatic winner or process grade is created by the timeline. The evidence tag advances to `fois-evidence-integrity-3` solely to extend the existing same-key retention guard across the corrected quote-clock contract. Earlier scores, fingerprints and snapshots remain byte-for-byte unchanged and NOT REVALIDATED; model 5.1, scoring weights and category definitions remain unchanged. No grade regeneration is authorized or initiated.

## Ownership, production and chronology

Observed roster state, historical intervals and last franchise with scored production are distinct. A scored week does not prove season-end ownership. Missing clocks/overlapping draft bounds do not establish exact order; deterministic display sorting is null-safe but not chronology proof. Missing original time or ambiguous subsequent clocks qualify/stop affected continuation. Missing transaction times are not replaced with retrieval time when capturing new intelligence.

Canonical player-week membership retains missing starter scores. Known zero, unknown, conflicts and duplicate observations are reconciled separately. Scored coverage does not become complete through unscored starts. Season production is not attributed automatically to a trade or holding period; no championship causality is asserted.

## Timeline and navigation

Existing `/trades/history/{transaction_id}` shows league, date, season-associated franchises/managers and exact sent/received assets, then expandable observed movements and confirmed pick-to-player transitions. Later packages link to their actual trade dossier. No descendant values or consideration shares are summed. Current source holdings are displayed separately from last observed movements; unsupported continuity remains incomplete.

Completed-trade and exact-pick actions reuse existing Transactions/player/pick/history routes. Player/pick `from_trade` return context is validated against selected-league evidence. Directed player movement legs are grouped for readability. Historical-page disclosures wrap within phone panels. Explicit My Team roster return fragments open the roster even when its saved disclosure state is closed; no new navigation framework or strategy write is introduced.

## Bounds and persistence

Canonical event preparation retains at most two generation indexes, projects relevant source families before constructing rows, caps event preparation at 100,000 event-family records and excludes the player-week universe from that index. A 100,100-score stress case verifies that irrelevant scoring rows do not block a small timeline. Graphs retain one read-model generation, 128 player summaries and 32 timeline results. Timelines cap original assets at 40 and emitted subsequent events at 100, with bounded conversion depth and explicit limit disclosures. Per-draft exact evidence is read in batches, capped at 1,000 selections. One bounded canonical player-week generation (100,000 rows) is prepared/reconciled once and shared by totals and targeted player reads; legacy SQL adapters retain lazy targeted reads. Larger player-week datasets withhold league-wide comparison ranks while preserving bounded targeted individual score reads and an explicit qualification.

Active operational history retains bounded transaction-week facts under existing current cache/session infrastructure, using the normal Sleeper preparation cycle. It does not append a permanent transaction archive or introduce page-level polling. Semantic transactions/drafts/picks and immutable sparse Market observation publication invalidate historical read state; unchanged reads do not publish new intelligence or history snapshots. Current-season coverage, unavailable buckets and retained evidence stay distinct. Older source-week completeness is not universally asserted: Codex and Scout audit coverage differed, and missing source access is not a product defect by itself.

## Scout acceptance

Verify deployed identity before product QA. Live: completed transaction → exact assets → subsequent pick transfers → Love/Boston selection → Boston's later trade; human names, historical franchise/user distinctions, current holder versus last scored owner, contextual dossier return, partial/missing evidence and dated price explanations. Challenge 320/375/390, short/tall portrait and desktop; keyboard disclosure/focus and local overflow.

Controlled/source: real v2136 quote publisher/new reader (future, stale, compatible, opaque units, future_pick), original rows unchanged and steady-state no growth; missing started scoring, real zero, duplicate/conflicting weeks, null/equal clocks, original versus selecting franchise, auction and same-round identity, source-season provenance, absent origins, two-league isolation and cache invalidation.

Regression: Trade/Calculator/Balance, exact locks, Preview/Keep Original/Adopt, strategy intent, Shop/Trade For, My Team statuses/picks, Matchups, standings, canonical Market/Sleeper projections and retained FOIS labels. Responsive Chromium is not physical iPhone/Safari. Controlled source replays do not establish authenticated live acceptance or exhaustive five-year scoring coverage.

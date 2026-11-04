# Home League Trade News — v1.21.45 / build 2145

Baseline v1.21.44, 262abb639ce24cab65819687113cccd78e01dbb6. Main reconciled before implementation. Scope follows the supplied Blueprint contracts, October 13 audit/voice text, current shared services and Richard's supplied mockup. The image guides layout; jerseys are replaced by the established Sleeper headshot renderer with initials fallback. The private full Blueprint is not a locally supplied file.

## Source and time admission

Home reads prepared selected-league `transactions` and at most 19 active-season `season_transactions` buckets, bounded to 10,000 source rows. It makes no provider requests, archive preparation, backfill or preference writes. Completed trade status, transaction identity, league scope and supported `status_updated` are required. Creation-only, invalid/future/contradictory clocks and conflicting duplicate copies are withheld with coverage qualifications. Missing buckets do not erase independently supported rows.

Sleeper's completed-row status-update clock is a supported status observation, **not a separately verified completed-at time**. Primary cards label the displayed time “status update”; source details explain this admission. Creation time is never promoted to completion. Eligibility is `(now − 168 hours, now]`; at exactly 168 hours the card expires. It is recomputed on every Home request, even if the league and body cache are unchanged. This is a dated feed over prepared evidence, not a claim of comprehensive historical acquisition.

## Canonical Market and ranking

Batch `cached_market_facts` is the player boundary shared with Market/Trade. Exact picks use the canonical current pick ledger and `canonical_pick_market`; no pick pricing formula, drafted-player substitution, raw provider sum or current-owner assumption about historical trade actors. Per-player generations are intentionally asset-specific. Comparison uses one league-scoped Market publication fingerprint plus valid prepared normalization references/version; references must agree within each selected provider population. Pick references must belong to the same provider population. Qualified individual prices survive when complete comparisons are withheld.

Six-card maximum. Complete compatible player/pick totals rank by descending unique-asset value, descending supported status-update time, then transaction ID. Partial/incompatible/unavailable-size trades are a separate recent-first group; at least one slot is reserved for that group when present. Their position does not establish smaller size. Known zero remains zero; entirely unpriced packages display unavailable, not a fabricated zero. FAAB is directed original consideration, separate from player/pick totals. Three-party trades receive no artificial two-party advantage.

Home shows the first two selected cards; remaining cards are accessible under “More completed trades.” Each card leads with each franchise's **received** package and current player/pick prices. Fully compatible two-party cards show text, totals, gap and accessible red/green or neutral bar. Labels: **CURRENT DISPLAYED MARKET** and **Current values, not trade-date grades.**

## Evaluation and navigation

Native keyboard/pointer disclosure is closed initially. It provides source-supported positional options, exact draft capital and surrendered assets/costs. These facts do not establish reliable depth, roster improvement, historical competitive fit, motives, acceptance odds, overall winners or causal championships. Full current-roster strategic fit and decision-time strategy are explicitly unavailable here; no heavy Trade discovery or FOIS reconstruction runs on Home.

All original-trade links use the existing `/trades/history/{transaction_id}?from_home=1` dossier. A source-league-validated Home return is shown. Existing `from_trade` return takes precedence; mismatched source league cannot claim Home origin. Exact player/pick links preserve original-trade identity through established dossier context. Historical prices and retained FOIS grades remain separate / NOT REVALIDATED.

## Cache and storage

The additional news model cache is process-local, generation-aware, limited to 24 entries and 2 MiB. Its fingerprint includes league, prepared transactions, roster/identity context and Market facts; shared provider-freshness and pick-quote time admission are rechecked on every read (including expiry inside a minute), with a minute boundary as an additional bounded refresh. Time-qualified candidate selection runs before cache lookup, so seven-day expiry is exact at read time. No read/unread state, per-user news database, duplicate archive, ownership snapshot, projection model, pricing engine, new polling or paid service. Existing authentication, canonical source refresh and 2 GiB resource gates remain required.

## Scout independent handoff

Report signed-in live, source/fixtures, responsive Chromium and physical-device findings separately.

1. Day Traders 1313066632158924800 Home: News directly under Home heading, compact headshots, received direction, collapsed Evaluation. Front-office summary, standings, matchup/report links preserved.
2. Boston transaction 1414718106177122304: Chase receives Boston; other side receives Stribling and Chase's exact original 2029 R2. Requery current values; do not expect historical mockup 408/310/242. Inspect status-update clock separately from creation / original trade date.
3. Current canonical compatible snapshot: individual values, complete two-side totals, correct advantaged receiving franchise and absolute gap; no historical winner label. Partial/incompatible evidence withholds definitive comparison/bar; entirely unpriced remains unavailable.
4. Source controls: pending/nontrade/foreign league excluded; creation-only/invalid/future time qualified; exactly 168-hour expiry on warm Home; independent expiration and fresh canonical publication.
5. Six cap, ties, price-descending complete group; separate unknown-size recent group; reserved unknown-size slot; first two visible and remaining deliberate disclosure.
6. Actual FAAB source 965057520920260608 remains historical (not eligible for current seven-day news). Controlled source-time feed: three players, five exact picks, one 100 FAAB 3→6; no player/pick price invented for FAAB, zero cash distinct from absent.
7. Home → original trade → Back to Home; reload and native Back/Forward keep selected league. Existing My Team/Market/historical multi-hop contexts unaffected.
8. Arkham 1319750579458686976: own transactions/identities/Market context and quiet state; A→B→A, matching local roster IDs, no feed contamination.
9. 320/375/390, tall portrait, short-height stress and desktop: settled cards, long names/picks, loaded/failed portraits, readable balance text/bar, 44px disclosures, visible keyboard focus, no document overflow or sticky obstruction.
10. Evaluation: supported gains and concrete costs only; no supposed motives, tanking, past strategy, trade-date fairness, automatic overall winner or full descendant/production allocation.
11. Regressions: own team, standings/trophy provenance, Weekly Report, My Team, Trade/Shop/Trade For, Calculator/Balance/Preview/Adopt, exact protections/strategy, historical Boston/Love/FAAB/production, FOIS retained grades and projection policy.
12. Source/fixture settled repeated reads: unchanged file sizes/hashes, cache limits, no provider requests or broad canonical scans. Independent production storage/latency measurements require appropriate read-only access; local timings are not a production SLA.

Independent product acceptance remains pending Scout review. Responsive Chromium does not establish physical iPhone/Safari acceptance.

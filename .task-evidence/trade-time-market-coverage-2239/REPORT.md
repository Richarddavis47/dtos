# Trade-time Market evidence coverage — no production change

The completed trade detail already contains an “At the time: Market evidence” section. A useful extension is **HELD because real quote/trade overlap is not established**, rather than because a fixture failed to calculate values. No application code, preferences, prices, policy, schema, version or deployment changed. Production remains v1.22.24 / build 2239.

Verified production and clean current main: b982e49ded18455e2fcc4fab58610569cc784343; tree 0ca79a715f697147c8081d4d69f1afd7efca9bb4. Render management confirms that commit live; public readiness independently agrees. No related unfinished PR exists. The environment was resumed before reading its existing checkout.

## What exists already

`routes/historical_assets.py` serves the existing completed-trade HTML and JSON through `HistoricalAssetGraph`. `src/ui/trade_timeline.py` renders original consideration, subsequent movements, exact-pick conversion, current observed ownership, source qualifications, production disclosures and return links. Its existing Market section presents per-asset admitted values, provider/format, quote and knowledge dates, raw excluded observations and missing-package reasons. It keeps present prices, production, later outcomes and retained FOIS grades separate.

`src/core/history_context/timestamps.py` uses Sleeper `created`, falling back to `status_updated`, without substituting retrieval time. `_trade_time_intelligence` in `src/core/historical_memory/graph.py` maps exact asset identities, uses the existing sparse Market store and provider comparison identity, and withholds later quote or knowledge clocks. `observation_clocks` and `comparison_reason` are in `src/core/historical_intelligence/market_comparison.py`. Exact picks use season, round and original roster; conversion never substitutes the selected player's quote. An explicitly foreign league quote is rejected; global neutral provider data is distinct from private franchise facts and Custom values.

Opening this surface reads prepared history and retained observations; it does not invoke the provider resolver, sync, FOIS generation or recommendation search. Timeline bounds remain 40 assets and 100 events; this audit adds no application work or storage.

## Real retained coverage: what can and cannot be counted

The bounded inventory reuses four existing files with original capture provenance and checksum: `trade_timeline_sources.json`, `trade_faab_source.json`, `historical_archive_source.json`, and `home_news_recent_trades.json`. Deduplicating completed trades by source league and transaction ID gives **25 trades / 104 asset appearances**: 22 dated in 2023 and 3 in 2026; 62 exact-pick appearances and 42 player appearances. One package contains FAAB. Repeated assets across different trades count as appearances, not distinct assets. Duplicate fixture copies do not increase trade counts.

**None of these retained source captures supplies a paired Market observation population.** There are zero demonstrated real quote/trade overlaps in these inputs. This is **not a measured 0/25 production coverage rate**, not proof all 104 prices are missing, and not proof the production store is empty. Real price coverage, ages, provider compatibility and complete-package counts remain UNKNOWN. Arkham supplies a retained history/draft/isolation control but no completed trade in its timeline capture; that does not mean Arkham had no trades. The actual Day pick-to-player chain is retained source evidence; its prices are not.

No copy of the production Market SQLite store exists at either checked local default storage path. Managed runtime capabilities are empty; the existing browser connector returned “Browser not connected.” No authorized Render Shell/SSH executor is attached. Authorized Render management provides deployment metadata, not private SQLite contents. The unchanged external inspection binding's prior 401 was not retried. Previously supplied Render-local token validity is not a newly reproduced observation or a private-data session. We did not call private history/Market APIs through a cold-league middleware path and risk hydration.

## Disposable logic checks, not evidence of real prices

Eight isolated cases characterize current behavior using constructed canonical-shaped prices:

| Control | Observed existing behavior |
| --- | --- |
| Complete player + exact pick, same instant | 700 and 350 admitted separately; comparable side totals available in the model |
| Player present, pick missing | 1/2 admitted; no package totals |
| Post-trade quote | Excluded |
| Pre-trade quote with later source knowledge | Excluded |
| Opaque/incompatible units | Excluded |
| Two old quotes | Kept as dated estimates with low temporal confidence; package comparison still permitted |
| Explicit incompatible latest retained row plus older compatible row | Latest clock candidate is then rejected; older compatible candidate remains unused |
| Explicit foreign league quote | Excluded |

A date-only provider observation remains unknown under the timestamp guard. The actual retained pick `PICK-2026-R2-ORIG7` converts to `DTOS-P-13346`; a separately constructed 600-valued quote for that converted player cannot fill the exact original pick's missing quote. Original franchise and package identity are retained. These constructed price values are not actual historical Market evidence or proof of historical league-format parity.

The incompatible-latest case deliberately injects a legacy-shaped incompatible observation in a disposable store. It identifies a reader limitation, **not an observed production incident**. There is no production mutation or historical-record rewrite.

## Gaps before a useful extension could ship

The existing page does not show calculated quote age or received/sent package totals, although its model can contain complete totals. Current package admission does not impose a maximum quote age: low temporal confidence and the DATED_ESTIMATE warning are not the documented freshness policy requested for a new package comparison. Latest temporal selection precedes final semantic admission, so some legacy incompatible latest records can hide older compatible ones. Matching provider format across assets does not by itself establish exact historical league-format parity. No fixes are shipped on the basis of synthetic prices alone.

After real overlap is established, the smallest future scope is the existing shared reader and existing disclosure: choose the latest actually compatible pre-trade quote with proven clock precision; preserve individually supported values; enforce a documented freshness/compatibility policy before package totals; show age and clear missing reasons; keep decision quality and outcomes separate. Do not add acquisitions, reconstruct old values, substitute today's price or infer a price from conversion. This is a conditional design boundary, not an authorization request or speculative implementation.

## Validation and failed-method provenance

On the unchanged verified source, 53 existing history, FAAB, timestamp/isolation and Market compatibility unit/HTTP tests passed. The existing actual route/navigation browser test passed (one test, 8 viewport/control records), covering original trade, exact pick, converted player, subsequent trade, original return, paginated contextual Back, native Forward/reload and league-scope reset. Requested 320×432, 375×667, 390×844 and 1280×900 controls passed. A separate route-layout probe exercises those sizes in both contexts; no overflow, existing keyboard disclosure/focus and pick-return assertions passed. Physical iPhone/Safari, comprehensive screen-reader review and authenticated live acceptance are unverified.

The eight characterization cases and date-only/conversion controls completed separately. They characterize current behavior; the stale-estimate and latest-incompatible results are **not acceptance of the proposed feature's stricter requirements**. The wrapper uses the previously verified Python 3.14.3 runtime image, actual 2 GiB memory limit, zero additional swap, two CPUs, no external network, read-only application source and disposable scratch. A separate container limit sample confirms enforcement, not production process idleness or peak memory of every browser step. No restoration-memory or long-term leak claim is made. Browser server cleanup was verified; no audit container remains.

Original author-method failures remain separate. Initial capture times put the quote after the helper's midnight event; the legitimate guard refused it. Subsequent attempts assumed a second helper capture created another observation, but the helper reuses `event_id=asset`, and the store correctly deduplicates that event; a SQL lookup then had no row. Increasing a fixture value did not fix that event-identity mistake. The corrected extra case uses a distinct event ID and deliberately explicit incompatible semantics. No application guard or assertion was relaxed. These failed methods are not counted as passing tests. The final conversion assertion also confirms a converted-player quote actually exists before checking that the original pick stays unpriced.

Full regression, ten canonical gates, hosted release checks and publisher were **not rerun** because no application change or release is justified. Prior build-2239 validation is existing baseline evidence, not a new result of this task. No PR, tag or release was created. Calculations, thresholds, preferences, scoring, submitted lineups, source acquisition, 2 GiB limits, FOIS/Trade reserves and lifecycle guards remain byte-unchanged.

## Outcome

Real current coverage is HELD/UNKNOWN; existing behavior is partly verified; fixtures identify bounded improvement opportunities. Keep production unchanged. The prerequisite for reopening implementation is a bounded, authorized retained-data read establishing compatible real observations at/before completed trades, with clock/format/provenance and freshness facts. Do not force league hydration or provider acquisition to obtain that evidence. See SCOUT_HANDOFF.md for an independent acceptance boundary.

# Completed franchise trade observations — build 2241

## Baseline and existing behavior

Production v1.22.25/build 2240 reports ready on commit 55eeb20f27c7e3380c1c4f70e3f2151a7ea1d5e8, tree f620d835c7b687d79d602ee5304f328aae95edef. Clean current main and existing work were checked before editing; no related unfinished PR was found. Tag/release v1.22.26 was unused. The repository roadmap and release contracts were reviewed.

League already shows franchise completed-trade participation, supported aggregate pick transfers, source coverage, manager-attribution limits and sampled original-trade links. Team HQ reuses that source-qualified context. Franchise History has the stronger existing source-linked season, transaction/attempt, exact-pick and ownership qualifications. FOIS and Trade Center retain their own prepared manager evidence; they are not replaced or rescored.

The addition belongs to the existing Franchise History surface: first-round transfers and their transaction denominators, completion-date window and all-page sample were not previously summarized there. This avoids a duplicate League intelligence pipeline or new Trade input.

## Retained source coverage

The existing read-only October 12, 2026 Sleeper capture `tests/fixtures/trade_timeline_sources.json` contains two Day Traders completed trades, four first-round transfers in one trade, and partial acquired periods. In the existing canonical replay, franchise 4 has two supported completed trades, three firsts acquired in one trade and one first sent in one trade. Completion observations run from March 1 to October 11, 2026. Exact original franchises remain 5, 7 and 8 rather than their sending or receiving owners. These are retained replay facts, not a fresh production sample or complete season coverage.

The Arkham capture in the same file has no completed trades; partial coverage means unknown history, not zero trading. The separate `home_news_recent_trades.json` capture overlaps a Day event and must not be summed with it as independent activity. `historical_archive_source.json` contains 22 older completed source trades and eight first-round transfers in seven trades; that raw screen does not establish current-franchise continuity for every record. Only the existing timeline's compatible, source-linked franchise records enter the feature. No provider acquisition or historical backfill was performed.

## Counting and scope contract

The factual timeline already deduplicates source league plus transaction ID, withholds conflicting versions, admits only completed source movements and preserves source-season compatibility. The new bounded, display-only accumulator consumes those existing rows before pagination. Only completed trades with linked source-season continuity, observed franchise identity and supported participant membership count. Unconfirmed continuity is explicitly excluded. Waivers, non-trade corrections, draft selections and pending/rejected/cancelled/unknown attempts cannot count as completed trades.

Exact directed consideration and completion clocks reuse the existing shared `_movement_evidence` and `_clock` contracts. First-round transfer counts distinguish assets from deals. Multiple firsts in one deal are multiple transfers but one participating transaction; duplicate legs collapse; conflicting directions remain unknown. The same exact pick moved in a later completed deal is another transfer. Every supported pick year is included; a same-season first is not inferred to be future capital. Exact year, round and original-franchise identities survive the link to the existing trade dossier.

Known positive counts remain supported subsets when pick consideration is incomplete. A zero requires complete consideration within the observed trade sample; an empty history supports zero only with complete compatible source coverage. Undated completed trades contribute to the season sample without receiving a creation-based completion window. The outer source-revision check withholds the summary if evidence changes during assembly. References remain bounded to 12 trades and four listed picks per direction; the existing full timeline/pagination remains available.

No manager-specific attribution is asserted. All observations are franchise history and do not establish current intent, willingness to accept, acceptance probability, skill or decision quality. These fields are not consumed by Trade qualification, counterparty scores, valuation or FOIS. Retained grades remain RETAINED / NOT REVALIDATED.

## Resources, navigation and validation boundaries

The accumulator uses the already-read canonical transaction archive and constant counters plus bounded references. No extra retained source store, provider request, source synchronization, worker/lease or intelligence build is added on page render. Existing account/league scope and authenticated contextual Back are preserved. Trade/FOIS reserves, restoration allowance, the 2 GiB cap, scoring, Sleeper results/projections, exact picks, submitted lineups and saved settings are unchanged.

The first 14-test focused run had one test-only failure comparing equivalent `Z` and `+00:00` UTC spellings. The control now compares the canonical timestamp to the retained source instant; original count/identity assertions are preserved. The subsequent 44-test focused run passed. The broader 106-test preliminary run, including browser journeys, also passed before final metadata/source sealing. An additional 18-test feature/browser pass completed after the compact presentation and repeated-pick-transfer control were added; it is also preliminary until the exact committed source is tested. Final exact-source focused, full local/canonical and hosted validation remain required; this source note does not claim their future outcomes.

Read-only public production identity is verified. The existing browser connector was checked and reports disconnected; no Render Shell executor is attached. The unchanged external inspection 401 was not retried. Private live franchise acceptance remains unverified. No production entry, sync, FOIS rebuild, Trade search, restart, cache clear, credential change or saved-data mutation was performed. Chromium phone/touch emulation is not physical iPhone/Safari acceptance.

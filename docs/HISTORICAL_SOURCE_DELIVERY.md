# Historical Trade Tracker source delivery and observation integrity

Release: v1.21.40 / build 2140. Accepted baseline: v1.21.39 / build 2139, `224022f0a6433a0417c405571269cecfa2a7f08a`.

## Released asset and production disclosure

The historical-assets router serves `/static/js/history-production.js` using the same explicit response and no-cache policy as existing released scripts. The historical test app no longer mounts a filesystem static directory. A separate test requests the actual DTOS application route and compares the entire response with the released file.

Opening the production disclosure requests existing recipient-franchise scoring evidence once. Successful empty, partial, zero, unknown-role and conflicted evidence reach a terminal display. HTTP errors, interrupted requests and the bounded 15-second timeout show an accessible Retry action. Closing and reopening an already loaded disclosure reuses its content. Requests are aborted on page exit; a response must match the connected disclosure, original page URL, exact trade, league and source generation before replacing content. Source changes require reloading the trade. No polling, new scoring model or retained response store is added.

Production remains recipient-roster-week evidence with interval limits. The 170-season/150-season-start control is distinct from the recipient's 30 rostered points, 10 started and 20 explicit bench. Unknown role is not bench; missing/conflicted score is not zero. Reacquisition intervals remain independent. Complete holding-period benefit, precise intraweek allocation and causal championship credit remain unavailable.

## Current observed ownership timing

The shared prepared-data read boundary carries `last_sync` from the state that publishes that exact data object, together with its league and existing roster/pick generations. It never writes the metadata into a new ownership store. Default and secondary resident runtimes use their own state; unrelated default-runtime clocks cannot date a secondary league's holding.

Trade, pick and player-history views consume the same observation boundary. Player dossiers read observation metadata after their cached historical summary so retrieval-only changes remain fresh. Ownership still comes from current scoped rosters or the exact current pick ledger. Original franchise, historical holder, selecting roster and manager remain distinct. Consumed picks retain their conversion and show the drafted player's observation separately. Missing or invalid observation timestamps remain unavailable.

Dates are explicitly DTOS Sleeper retrieval/sync observations. They are not Sleeper ownership-change times, acquisition times, historical transfer dates or page-render times. Retrieval-only changes clear the bounded timeline presentation cache without rebuilding historical indexes or writing the retained read-model manifest. Ownership changes participate in the semantic cache identity. League/source changes remain isolated.

## Optional playoff outcomes

Canonical bracket admission accepts positive integer/digit-string roster IDs. Nested values, booleans, invalid strings, unsupported roster identities and conflicting outcomes are withheld with reason codes. Independent regular-season, draft and transaction sections continue rendering. Raw Sleeper evidence is preserved; no champion, placement or advancement is synthesized. Retained checkpoint reads apply the same identity qualification without modifying old records. Missing, observed-empty and malformed sources remain separate coverage states.

## Bounded presentation corrections

- Transaction bucket Week 0 is a supported offseason bucket. Zero remains selected in the form, accepts resubmission and renders as Week 0; missing/blank values remain omitted and negatives are invalid.
- Historical Market source observation confidence is separate from comparison eligibility. Dated-estimate limitations appear only for that classification. ISO attachment timestamps and opaque legacy attachment references are distinguished; quote, knowledge and attachment clocks remain separate. Price admission and values are unchanged. FAAB remains unpriced original consideration.
- FOIS profiles resolve at most 25 retained evidence references to existing completed-trade routes. Only matching-league participant-franchise events receive direct links; duplicates are collapsed. Unresolved or unsupported references retain a qualified history fallback. Links do not assign exact trade-time manager tenure or revalidate retained grades.

## Independent Scout acceptance

1. Request the production JavaScript URL: HTTP 200, JavaScript content and current released hash. On trades `965057520920260608` and `1414718106177122304`, open the production disclosure by pointer and keyboard. Confirm terminal partial/unavailable evidence, visible error/retry and no permanent placeholder. Reopen, reload and use browser Back.
2. Follow original Boston trade `1333655835015942144` → `PICK-2026-R2-ORIG7` → player `13346` → subsequent trade `1414718106177122304` → original. Verify current owner Chase Bank and the scoped sync observation, separately from acquisition/transfer dates. Repeat Love `PICK-2026-R1-ORIG4` → `13287` and an active exact future pick.
3. Replay malformed bracket winner object/loser list, null, invalid, conflicting and valid controls through season HTML/API and franchise/trade routes. Independent content must stay HTTP 200; no false champion or placement.
4. Replay Week 0 form submission, blank/one/later/negative controls, retained incompatible/exact/dated/missing quote cards and supported FOIS event links.
5. Preserve 100 FAAB roster 3 → 6 exactly once in the named three-team trade; all original players/picks, Love/Boston/repeated 2028 original-7 third identities, archive filters/pagination, partial-source admission, multi-hop context, score conflicts, historical quote gates and FOIS NOT REVALIDATED.
6. Verify 320/375/390, short/tall portrait and desktop: terminal production, retry, owner date, evidence disclosures, readable identities, local table containment, no document overflow and visible keyboard focus. Responsive Chromium does not establish physical iPhone/Safari acceptance.

Local source, actual-router, browser and no-growth fixtures are implementation evidence. Authenticated live acceptance is separate and remains Scout's responsibility. No new permanent database, ownership snapshot, projection/pricing engine, provider backfill, legacy rewrite, FOIS regeneration, paid service or Sleeper mutation is authorized or introduced.

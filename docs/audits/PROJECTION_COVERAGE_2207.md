# Projection coverage and legal eligibility

## Evidence classes and access

Baseline: build 2206, commit 2dee39f26924f53c66d35214ce90262a173a05ba. The connected browser requires app reauthentication; the existing inspection credential returns generic private/no-store 401. No authenticated production publication, saved preference or account record was retrieved or changed. A read-only public Sleeper source check is independently available under the user's authorization. It is not access to DTOS's protected inspection service.

Sleeper's current NFL state and the user's matched Day Traders league identify season 2026, Week 8. League, roster, catalog and projection responses were retrieved on 2026-10-28 at approximately 17:52 UTC. Projection records were fetched from the existing canonical client's Sleeper endpoint and supported position query. The existing nflverse schedule source supplies observed bye evidence. Provider response hashes and acquisition timestamps survive in private author evidence; public handoff redacts owner identities and raw rosters.

The original DTOS observation of 182.03 points cannot be source-pinned. A fresh source replay produces 185.4278 for the user's franchise, second among seven supported lineups. This is a local disposable publication of the newly retrieved source, not the original production generation. Current source observations, offline replay and wholly synthetic HTTP/browser controls must remain separately labeled.

## Five uncovered players

| Player / exact Sleeper ID | Verified Week 8 evidence | Interpretation |
|---|---|---|
| Jalen Hurts / 6904 | ADP-only projection record; PHI; IR/inactive catalog context | No usable scoring statistics. PHI bye is Week 10, not Week 8. |
| Woody Marks / 12474 | ADP-only record; HOU; questionable | No usable scoring statistics; verified HOU Week 8 bye. |
| Nico Collins / 7569 | ADP-only record; HOU | No usable scoring statistics; verified HOU Week 8 bye. |
| Tyreek Hill / 3321 | ADP-only record; catalog has no NFL team | No usable scoring statistics. No claim about future signing or participation. |
| Xavier Restrepo / 12520 | ADP-only record; TEN | No usable scoring statistics. TEN bye is Week 9, not Week 8. |

Each record has adp_dd_ppr=1000 and no recognized scoring statistics. All remain missing, never zero. Provider update timestamps are absent on those records; acquisition time is not substituted for provider freshness. No five-player numerical projection recovery is claimed.

## Confirmed defects and corrections

1. The canonical projection pipeline dropped Sleeper fantasy_positions. Real source identifies Travis Hunter (12530) with primary NFL position DB and explicit fantasy eligibility DB/WR. Preserve primary position and Market policy; carry separately validated fantasy eligibility into the existing highest-projected legal lineup solver. A player is processed once, so dual eligibility cannot fill two slots. Explicit malformed/empty eligibility cannot manufacture another position. Legacy absent eligibility retains its single primary position.
2. Prepared Team Strength admitted a current Out player's nonzero quote as playable while current roster diagnostics excluded that same player. Current-week preparation now excludes unavailable statuses consistently. Original quoted points are preserved. Future projections remain conditional rather than inventing permanent absence.
3. Current roster diagnostics did not consume already prepared, compatible known-bye evidence. They now reuse the generation/league/scoring/roster/calendar-qualified profile. They do not fetch schedules or prepare profiles on read. Excluded Out/bye players are also withheld from useful reserve contribution.
4. Explicit player/week/season/scoring/leaf-publication conflicts are rejected at shared row admission, preparation and weekly presentation. No foreign projection is substituted. Separate legacy parent-publication inheritance remains supported.

Parser and prepared diagnostic/method identities change to invalidate incompatible derived output; no cache capacity, retention policy or data warehouse is added. Canonical scoring and Sleeper display calculations do not change.

The full Product gate caught source-string reference builders that still expected the old three-field eligibility loop. Adapt their reference construction to the explicit assigned fantasy position while retaining every seeded exact-assignment, order-symmetry and eligibility-count assertion. The production loop also avoids redundant eligibility checks: one check per fantasy-position/slot pair, outside the dynamic-programming states. Existing single-position check bounds remain unchanged.

## Ten-franchise fresh-source replay

Exact source starting slots: QB, RB, RB, WR, WR, WR, TE, FLEX, FLEX, FLEX, SUPER_FLEX. The source's complete scoring settings, including PPR and TE bonus, are used directly. No default scoring template is substituted. Teams below use franchise numbers, not private owner names.

| Franchise | Roster numeric coverage | Baseline optimal | Corrected optimal | Supported starting slots after correction | Exclusion |
|---|---:|---:|---:|---:|---|
| 1 | 26/31 | 185.4278 | 185.4278 | 11/11 | None |
| 2 | 23/32 | 189.8898 | 189.8898 | 11/11 | None |
| 3 | 22/32 | 141.9916 | 141.9916 | 11/11 | None |
| 4 | 17/31 | Missing | Missing | 10/11 | QB |
| 5 | 24/30 | 170.7026 | 170.7026 | 11/11 | None |
| 6 | 25/28 | 177.8308 | 177.8308 | 11/11 | None |
| 7 | 17/27 | Missing | Missing | 10/11 | QB |
| 8 | 24/32 | 176.0474 | 176.0474 | 11/11 | None |
| 9 | 21/32 | 147.6856 | 147.6856 | 11/11 | None |
| 10 | 8/16 | Missing | Missing | 6/11 (was 5) | QB, WR, FLEX, FLEX, FLEX |

Hunter's supported receiver eligibility restores one actual playable slot; it does not resolve the other missing starting positions. Seven comparable lineups remain seven. Incomplete bench coverage alone does not exclude a complete legal lineup. Genuine zero can fill a slot; no empty required slot is declared legal.

Zero complete-roster positional-needs assessments is a different standard: those require complete eligible replacement evidence and supported availability. All ten fresh-source teams have missing or uncertain eligible evidence; even the one without missing eligible projections has uncertain players. The release preserves those stricter reserve safeguards and explains 0/10 full-needs coverage alongside 7/10 starting-lineup coverage. It does not relabel unknown depth as weak depth.

## Customer explanations and costs

My Team's compact comparison states supported denominator and total league population. The existing disclosure names excluded franchises and their unfilled starting slots, and separates roster numeric coverage from playable lineup eligibility. Official record/PF standings remain unchanged. League needs explains its additional replacement evidence requirement. Weekly projection HTML distinguishes a missing record, an ADP-only record, unsupported scoring, observed bye, current Out/IR and no recorded NFL team; compatible numeric quotes stay intact.

Prepared comparison coverage is composed from existing solved results, without an additional optimizer call. Ordinary weekly reads reuse the pinned snapshot/profile, and have negative controls against preparation, source generation and solver factories. No provider synchronization, discovery, FOIS, historical reconstruction, preference write or background task is added. Existing cache bounds, 2 GiB service budget and 500 ms liveness contract remain in place.

## Acceptance and limits

Disposable source-compatible tests cover full-lineup/incomplete-bench, true missing QB, alternate Superflex, dual eligibility, single-use identity, explicit zero, malformed eligibility, current Out versus conditional future, compatible bye propagation, source conflicts, neutral price/record preservation and no extra preparation. Actual private HTTP and controlled Chromium cover 320x432, 375x667, 390x844 and desktop, native keyboard/touch disclosure, visible focus, shortcuts and no overflow. Weekly browser checks include the actual embeddable projection fragment; they are not represented as full dossier or live tenant browser acceptance.

Original failing fixtures and subsequent reruns remain evidence. Complete canonical, hosted, resource and security results must be verified against the final source before release. No sustained production capacity, physical iPhone/Safari or unfamiliar-human study is claimed. No saved rankings, production trades, rosters, historical source records or retained FOIS grades are changed.

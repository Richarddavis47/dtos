# DTOS v1.21.33 / build 2133 — Standings and Playoff Positioning

Starting pin: v1.21.32 / 2132 / `325bf5f04dcc36614b3c2e11d7383d4e13542851`. Both October 11 standings audits and Richard's latest record/PF decision govern this release. The branch started at unchanged current main.

## Source and ordering contract

`services/standings.py` supplies the common Home/League order. Current wins, losses, ties and cumulative PF/PA come from Sleeper roster settings; the existing `standing_points` normalizer preserves integer/decimal source totals. Missing/invalid records remain unavailable during ingestion. Division membership is retained separately from league configuration.

The admitted record comparison is wins descending when every roster has equal completed-game opportunities and the same number of ties. Loss counts then vary inversely with wins. PF is the only secondary comparator. Equal record/PF groups display an unresolved position range; no PA or roster-ID competitive tiebreak, medal or movement is assigned to an unresolved placement. Presentation within an equal group preserves source order without giving individual ranks. Unequal opportunities or different tie counts withhold statistical ranks with a specific explanation pending a verified comparator. Source median-game records are reused, never replaced by head-to-head counts.

Provenance: **Standings ranked by Sleeper record, then Points For.** These are DTOS-organized source facts, not API-reported playoff seeds. A complete, unique explicit source rank set, if supplied, appears separately. Sleeper's published default includes higher PA after PF; Richard's authorized product contract intentionally stops at PF. Exact PF ties therefore remain unresolved rather than pretending this statistical view reproduces that additional default rule.

Public contracts: [rosters](https://docs.sleeper.com/#getting-rosters-in-a-league), [football tiebreaks](https://support.sleeper.com/en/articles/4238872-can-i-set-tiebreakers), [qualification](https://support.sleeper.com/en/articles/2203518-how-do-playoff-teams-get-determined), [commissioner seeding](https://support.sleeper.com/en/articles/2528718-can-i-customize-my-league-s-playoff-seeding), [median games](https://support.sleeper.com/en/articles/3971690-extra-game-each-week-against-league-median). No reviewed contract establishes an absent division setting as zero, or a universal tied/unequal-record comparator.

## Playoff positioning

Before the postseason boundary, complete standard qualification configuration plus an admitted statistical order supports **Current playoff-position cutoff**. Explicit zero divisions wins over residual roster division tags. A tie crossing the cutoff withholds the boundary; a tie wholly inside/outside does not manufacture an individual rank. Counts must be positive and smaller than the roster inventory.

Complete configured divisions use each division's resolved record/PF leader plus the remaining highest record/PF teams for available wildcard positions. Per-team indicators replace the line, accommodating noncontiguous qualifiers. Missing membership, unresolved division/rank evidence, unknown division settings and unsupported custom qualification withhold these claims. The standard interpretation explicitly assumes no commissioner overrides; numeric seed settings do not prove the absence of manual overrides. No final seed, clinched berth, elimination, guaranteed bye or probability is calculated.

After regular-season completion, the existing compatible prepared championship bracket may separately identify published participants, including explicit byes. Full participant count, roster/league/season/calendar compatibility and absence of contradictory bracket evidence are required. These are bracket participants, not statistical final seeds. No early provisional bracket is promoted into qualification.

## Completed-week movement and streaks

Movement uses bounded, already prepared regular-season actual/custom scores, comparing the most recent completed week with its predecessor. Both reconstructions use the same record/PF comparison; complete coverage is required. Median-game records include the extra regular-season result when explicitly configured. Current reconstructed records and complete resolved ordering must reconcile with source standings. Ambiguity, missing weeks, incompatible league/season/calendar, postseason or record/order disagreement withholds movement.

Movement is labeled **DTOS-derived** with comparison weeks, never an observed historical Sleeper rank. Small source-versus-weekly PF differences can exist: Arkham source PF 297.43 versus weekly 297.45 is preserved. Reconstruction is only an ordering cross-check; source cumulative totals always remain displayed. Current agreement does not establish historical contemporaneous source accuracy. Commissioner corrections can revise this reconstruction.

Existing head-to-head W/L streaks retain their completion/provenance gates and remain separate from movement. Singular wording is corrected. Historical archived roster records, FOIS grades and championship lineage are not rewritten.

## Cache and presentation

Canonical runtime generations include `season_matchups.semantic_generation`. The Home presentation identity also directly reads that retained identity, with an explicit unavailable sentinel, in context and no-context paths. Thus default publication does not depend on a separate runtime generation refresh having already occurred. Historical corrections, withdrawals and recovery invalidate affected Home bodies; identical evidence and retrieval-only timestamps remain stable. League already reads retained facts directly. Existing bounded render caches remain unchanged; no new polling or storage is introduced.

The shared table shows rank, franchise, record, cumulative PF/PA and authenticated You highlighting. Rank medals describe resolved statistical placements. The previous completed championship retains its league-specific trophy provenance. Badge explanations occupy a full-width table row when expanded rather than a narrow identity cell. Matchup portrait rules remain unchanged; avatars appear where phone width permits.

## Source-backed reference fixtures and independent acceptance

The sanitized October 11 source fixture retains only league settings, public franchise identity, source record/points and compact weekly results. It omits account IDs and player inventories. It is a dated regression reference, never a production constant:

- Day Traders `1313066632158924800`: `2,6,8,1,5,3,9,4,7,10`; explicit divisions 0, six playoff positions. Chase Bank roster 1 is highlighted only when authenticated membership matches.
- Arkham `1319750579458686976`: `5,1,8,9,3,7,6,2,10,4`; division setting absent, cutoff withheld independently of valid ranking.

Fresh public source reads at implementation time still matched these orders. Captures are multi-request observations, not an atomic source generation or authenticated UI acceptance.

Scout should independently:

1. Verify deployed version/build/commit; compare Home/League with current Sleeper records and cumulative PF/PA in both leagues. Confirm source-derived provenance, correct membership and current-generation ordering, not permanent fixture orders.
2. In Day Traders inspect the sixth-position line and its conditional wording. In Arkham confirm useful ranks with the missing-division explanation unless newly supported source evidence changes that context. No clinch/seed/bye claim.
3. Compare movement arrows with disclosed completed weeks and retained weekly actuals. Verify incomplete evidence/ties withhold movement. Keep W/L streaks separate; check singular loss wording.
4. Open the Day Traders trophy by keyboard at 320/375/390 and desktop, including short/tall portrait heights. The preceding 2025 championship explanation must span the panel; inspect ranks, PF/PA, You, focus and page overflow.
5. Challenge division/wildcard/noncontiguous and unresolved-cutoff scenarios in controlled fixtures. No general live division/custom-seeding correctness is claimed from these two leagues.
6. Reproduce timeout/recovery, withdrawal and corrected-history warm Home scenarios using isolated evidence. Home and League must agree even if current records/matchups remain unchanged and retained runtime generations have not refreshed. Retrieval-only time must not churn the cache.
7. Recheck Matchups/player navigation, canonical Sleeper projections, Trade/Calculator protections/preview/Shop/Trade For, and FOIS RETAINED / NOT REVALIDATED.

Distinguish authenticated live behavior, public source reads, deterministic fixtures, responsive Chromium and physical iPhone/Safari. No physical-device test or complete accessibility certification is claimed.

Validation and deployment results are recorded in the final release report. No passing fixture alone proves live official seeding or historical standings correctness.

## Controlled performance sample

Identical dated ten-team evidence, baseline renderer loaded from the accepted commit and current renderer, 100 calls each; full-page TestClient samples use 30 calls with unrelated intelligence isolated. Times are milliseconds, p50 / worst observed, excluding provider retrieval and authenticated production latency:

| Operation | Day Traders before → after | Arkham before → after |
|---|---|---|
| Standings renderer | 0.300 / 0.722 → 0.839 / 1.558 | 0.326 / 1.922 → 0.767 / 1.190 |
| Warm Home | 2.383 / 5.908 → 3.617 / 10.376 | 2.534 / 3.982 → 2.445 / 5.825 |
| League | 4.323 / 15.363 → 3.547 / 10.866 | 2.669 / 5.315 → 3.261 / 5.249 |

Shared ranking p50: 0.034 / 0.020 ms; movement p50: 0.455 / 0.288 ms; retained Home generation lookup p50: 0.0045 / 0.0039 ms. Isolated local timing variance does not establish a production SLA. There are no additional page-time provider calls, permanent derived snapshots or new caches. The existing Home cache budget and 2 GiB validation limits are unchanged.

## Release validation

The final local canonical validator passed all ten gates in 726.621 seconds: 2,695-test full regression, authoritative Ruff, compilation, dependency integrity, committed/working/staged whitespace, 260 route registrations without duplicates / 239 OpenAPI paths, tracked HTTP and process cleanup. Focused runs passed 72 broad tests, 41 final source/UI tests and the shared phone journey (overlapping coverage). New standings journeys exercised 42 Home/League views across both leagues and seven viewports with pointer, keyboard, focus and geometry assertions.

Ordinary, archive-warmed and combined-read 2 GiB lifecycle scenarios passed with one semantic worker, zero restarts and zero OOM/OOM-kill events. Effective working-set peaks were 1,433,702,400 / 1,421,504,512 / 1,422,692,352 bytes; archive-pressure raw cgroup peaks reached the 2 GiB limit in the latter two scenarios. Guarded recovery/quiescence and its 141-test suite passed. No limit or assertion was relaxed.

Failed disposable fixture/disk preparations, an interrupted browser run caused by a 0700 temporary mount, and an obsolete pre-feature medal assertion were retained as failed evidence. Fresh bounded fixtures, normal temporary-directory permissions and an updated assertion requiring derived provenance resolved them before the final full pass. CI, immutable release and deployed identity/health are separately reported after publication. Authenticated live UI acceptance remains for Scout.

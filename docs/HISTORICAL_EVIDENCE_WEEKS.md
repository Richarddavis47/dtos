# Historical Common-Week Evidence — v1.21.27 / build 2127

## Reconciliation and original reproduction

Starting main matched accepted v1.21.26/build 2126, `a113f8563c0ab7740e5d7e9c6c58519e3a63f2ec`, with no intervening main changes. Scout's new controlled evidence-week reproduction and the previous live acceptance boundaries were reconciled against current source. Existing wording, disclosures and responsive corrections are not redesigned.

The original raw-source fixture reproduced Week 5 transaction admission of Week 3 before production 10 versus Week 4 after production 14: supported +4 and SOUND. `HistoricalFranchiseStateService` independently selected each roster's latest observed week; `HistoricalTransactionIntelligenceService` admitted their delta solely because both totals existed. Entire-roster exchange made those independently selected weeks differ. Incoming historical production was correctly available, but its week was not comparable.

## Corrected evidence contract and deterministic policy

Event-paired reconstruction retains decision-time ownership, Market quotes, settings and roster rules. If both legal lineups are already complete on the same eligible week, that comparison is retained. Otherwise it selects the **latest completed pre-decision week with complete, nonconflicting production for all required eligible players across both rosters**. Normalized positions and supported legal slots remain required. Candidates are considered in descending week order; the sign or decision classification never influences selection.

No common complete legal week produces unavailable lineup evidence, `no_common_supported_historical_week`, and underlying missing-position/coverage reasons. The unavailable comparison has no numeric delta or selected week. A standalone numeric total cannot bypass the transaction-level guard: league/franchise/season, scoring/settings, lineup rules, decision boundary, same eligible week, normalized identity, complete coverage and source references must agree.

The canonical optimal legal lineup engine remains unchanged. Historical league-scored player/week actuals can come from the player's previous franchise; current forecasts are never substituted. Complete actual zeros remain numeric zero; absent production and absent submitted-starter evidence remain unavailable. Market fairness is separately admitted from complete comparable decision-time quotes.

Selected week, source references, before/after totals and unavailable reasons flow through transaction evidence and the FOIS allowlisted handoff. Existing category summaries retain bounded week/reason counts and numeric ranges, not a new per-decision history store. Earlier supported common-week use is explicitly explained. Derived state/transaction method versions advance to prevent stale computed identities.

## Independent source and actual-process acceptance

Run `python -m tools.validation.verify_historical_weeks --output /tmp/week-verification.json`.

The tool always configures its own disposable stores before importing production services. Raw Sleeper-shaped records use the actual canonical season adapter, sparse Market store, historical state/transaction services, FOIS history loader, full generation and actual spawned/compacted worker/publication. No supplied FOIS history, synthetic alternative DOM or pure-helper-only parity claim is used.

Fifteen cases verify the exact Scout scenario; latest complete evidence; latest declining versus earlier improving evidence; no common week; genuine zero; missing normalized positions; missing identity; unchanged eligible player missing latest coverage; partial coverage in every week; REC_FLEX; Superflex; combined flex/Superflex; separate league scoring; a changed decision-week boundary; and conflicting duplicate production. Multiple eligible/future Market observations remain independently governed by the existing decision-time pricing contract.

For Scout's scenario both paths select Week 3, before 10 / after 5, delta −5, DEFENSIBLE. Market remains independently balanced at 500/500. No-common cases are unavailable rather than neutral-zero evidence. Full/spawn comparisons cover all semantic score fields except generation timestamps, plus explicit selected-week distributions, relevant totals, reasons, classifications and confidence/coverage. Workers must be reaped. The previous independent 24-scenario verifier remains a separate regression gate for Market normalization, package coverage, sample independence, two-sided taxonomy and league-specific behavior.

`--observe` records baseline source behavior without claiming corrected acceptance. It is only used against an isolated archive of the prior commit for reproduction/performance comparison; default validation requires every corrected expectation.

## Historical grade preservation

The earlier guard retained assessments lacking `fois-evidence-integrity-1`, but allowed normal refresh of integrity-1 assessments. Because those assessments do not establish comparable evidence weeks, this release advances the evidence contract to `fois-evidence-integrity-2` and extends the same-key guard to earlier versions. Existing payloads, grades, fingerprints, generated times and snapshots remain unchanged. Read-time banners mark earlier versions retained/not revalidated without rewriting them. Corrected current behavioral evidence remains separate.

Isolated integrated full/spawn tests preserve prior integrity-1 rows and snapshots byte-for-byte; the existing verifier separately preserves older unversioned records and ambiguous lineage. New integrity-2 assessments retain the existing normal refresh policy. No scoring weights/model, schema, migration, regeneration command, bulk recomputation, provider backfill or historical maintenance is introduced.

Historical Trading process assessments could be affected if they previously admitted incomparable evidence weeks. No exact production incidence or affected-manager count is inferred. Retained grades have not been corrected or revalidated. Any future regeneration requires separately authorized evidence inventory, isolated deterministic recomputation, comparison and replacement publication preserving original provenance; the earlier [planning-only regeneration procedure](FOIS_FINAL_TRUST_VERIFICATION.md#future-regeneration-plan--not-executed) remains applicable.

## Documentation qualifications and deferred lineage concern

Direct historical-fit score is not an active Recommended ranking term. Supported HIGH historical references can raise overall evidence confidence from MEDIUM to HIGH when Market and lineup evidence are complete; confidence is an active ranking tie-break. Tests cover the actual confidence producer and ranking consumer. No ranking change is made, and history remains soft context rather than a veto or price modifier.

Exact lineage uniqueness is league/draft/selection. On repeated writes, contradictions in season, round or selected player are rejected. Original/selecting-roster identity, lineage ID and selected timestamp are not compared in that duplicate path; first stored metadata remains unchanged. This is narrower than universal contradiction rejection. A controlled test confirms this existing limitation and preservation behavior; production incidence is unverified. Broader contradiction handling and ambiguous retained lineage review are deferred, not corrected through migration or storage repair here.

## Browser and production boundaries

Actual FOIS routes recheck retained banners for both absent and prior integrity versions, supported category findings, Arkham-style no-need wording, disclosure keyboard/focus behavior and page bounds at 320/375/390px, short/realistic portrait heights and desktop. Recent Trade/browser contracts remain release gates.

Read-only production inspection captures baseline summaries and compares sampled grades/provenance after deployment. It does not expose the raw historical evidence required to certify numerical correctness. Without an established authenticated manager browser session, private live pages remain Scout acceptance. Responsive Chromium is not physical iPhone/Safari.

## Scout independent checks

1. Confirm deployed version/build/commit. Distinguish source/fixtures from live numerical acceptance.
2. Re-run the exact Week 3/4 fixture through the raw-source driver: selected weeks 3/3, 10→5, −5 and DEFENSIBLE; compatible Market fairness remains independent.
3. Challenge latest common selection, no-common failure, zero/missing distinctions, incoming cross-franchise production, REC_FLEX/Superflex, decision boundary, scoring context and duplicate observations. Verify full/spawn week, totals, reasons, classification and confidence parity.
4. Run the previous verifier for incompatible prices, partial packages, independent samples, oriented package matches and league isolation. Check no prices, strategy precedence or discovery ranking algorithms changed.
5. Live retained grades must keep original values/provenance and remain NOT REVALIDATED. Specifically recheck Richard/danreilley and TheLandsharks Results; do not infer corrected historical numbers from unchanged grades.
6. Recheck Arkham no-need advice, TheLandsharks category-versus-overall wording, own/opponent disclosures and code wrapping at 320/375/390 and desktop. Prior integrity-1 grades must also display retained status.
7. Sample Recommended/Next Five, Shop/Trade For, Create/Evaluate, Adjust/Cheaper, Calculator/Balance, exact player/pick protections, preview/Keep Original/Adopt, multi-asset reload and explicit navigation. No Sleeper mutation.
8. Keep lineage contradiction review, historical regeneration and physical iPhone/Safari separate. Existing stored history must remain untouched.

## Controlled performance observations

Three sequential raw-source runs per baseline/corrected revision (small fixtures, not live latency): Scout common-week selection p50/worst 12.631/12.714→13.867/16.967 ms; full FOIS computation 34.462/42.910→35.188/47.394 ms; initial spawn wall 423.541/441.694→454.446/654.366 ms including startup. Warm latest-complete spawn p50/worst 47.363/49.193→50.550/54.008 ms. No performance improvement or SLA is claimed.

Both revisions used five historical source-record queries; existing generation-aware record caches are reused. Maximum compact identity projection was 675 bytes, child RSS 37.122→37.192 MB and parent RSS 40.268→40.448 MB. Workers were reaped. No new provider call, permanent cache, database index or whole-history/database scan is introduced; common-week selection adds bounded passes over cached season evidence. Common-week candidate evidence uses the existing bounded season record read.

## Recorded release validation

The canonical validator passed all ten unchanged gates: committed whitespace; working-tree whitespace; staged whitespace; Python compilation; authoritative Ruff; dependency integrity; full unit/regression suite (2,630 discovered tests); route/OpenAPI validation (260 method registrations, no duplicates, 239 OpenAPI paths); tracked canonical HTTP smoke; and process cleanup. Total canonical wall time was 668.042 seconds. The affected pre-validator suite passed 128 tests. Both independent raw-source verifiers passed (15 current common-week scenarios and 24 previous historical evidence-contract scenarios), with actual worker cleanup and retained-record preservation.

Actual-route responsive browser checks include 320/375/390px, short and realistic portrait heights and desktop; these are controlled Chromium fixtures, not authenticated live or physical iPhone/Safari acceptance. Full regression also covers recent Trade/Calculator, navigation, ownership, exact protections, responsive identifiers and local evidence tables.

All three unchanged lifecycle gates passed under a 2,147,483,648-byte cgroup cap:

| Scenario | Effective working-set peak | Raw cgroup peak | Workers | OOM / restarts |
| --- | ---: | ---: | ---: | --- |
| Ordinary | 1,420,566,528 bytes | 1,502,474,240 bytes | 1 | 0 / 0 |
| Archive-warmed | 1,435,250,688 bytes | 2,147,483,648 bytes | 1 | 0 / 0 |
| Combined-read | 1,423,261,696 bytes | 2,147,483,648 bytes | 1 | 0 / 0 |

Archive-warmed and combined-read raw peaks include reclaimable archive pages and reach the cap; effective working sets remain below the unchanged 1.5 GiB gate threshold. No gate or accounting rule was relaxed. Linux recovery/quiescence positive and negative checks and 141 recovery tests passed. An environment restart interrupted the first ordinary lifecycle attempt; its logs were retained and all three gates were rerun to completion with fresh disposable fixtures.

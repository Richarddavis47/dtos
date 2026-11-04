# v1.21.28 / build 2128 — Simple Trade, Supported Discovery

Baseline: v1.21.27 / 2127, `3daa9d47547f2ae0362cd1f75ad6074dc33627aa`. The October 5 vision and October 9 planning handoffs were reconciled with the current implementation and the release request. Their historical storage proposals remain deferred. No standalone Blueprint file was supplied; the detailed current instruction governs this release.

## Reused architecture and boundaries

The four primary hub entries are Build a Trade, Trade For, Shop / Trade Away and Recommended. Existing routes remain unchanged. Calculator stays available from the workspace and generated offers. Ownership-aware dossier/Market/My Team/pick actions retain their existing shared capability contract.

Build and Calculator share exact decimal arithmetic over the prepared canonical asset facts. Build loads the existing fast Market-only workspace; editing makes no additional API/provider requests and does not run discovery, optimal-lineup or FOIS computation. Both totals, individual asset values, favored manager and actual gap update on selection, removal, partner change, preview adoption and reload. Partial totals remain partial; unavailable prices never become zero. Strategy does not reprice assets.

The bar represents outgoing and incoming Market value; captions identify their receiving managers. Green marks the advantaged recipient, red the disadvantaged recipient, gray equal totals. Text, exact totals and the gap provide the same information without color. No probabilities or percentages are claimed. Equality retains the accepted calculator semantics. Controlled 1000/900, 100/20, 400/300, 180/100 and 60/20 examples show that fixed 50/100-point fairness bands describe materially different relative losses on the 0–1000 canonical scale. Richard authorized retaining exact semantics with optional closer-to-even suggestions. No new fairness band was imposed.

One Evaluate action invokes the unchanged bilateral evaluator. Its completed verdict retains the accepted focus/scroll handling. Completed team-specific conclusions and package trade-offs appear immediately; the original evidence and distinct horizons remain expandable. No positive counterparty rationale is invented.

The existing Balance API, generation checks and exact lock store are reused. Balancing sits alongside the assessment, and the current assessment is retained while adjustments load. Every option explains asset changes, old/new totals and gaps and its separate strategic drawback. First click previews; only Adopt changes the current offer. Keep Original retains it. Exact Shop outgoing and Trade For incoming anchors remain enforced. Balanced offers need no sweetener; any genuine nonzero-gap improvement remains optional.

## Targeted discovery and exploration

A fresh valid Shop/Trade For target entry automatically starts the existing bounded search. Shop defaults to all eligible teams and Best Overall. Trade For resolves the actual owner and keeps the target incoming. A target chosen in the workflow starts its search, too. Reload/back-forward does not automatically repeat discovery or discard an adopted proposal. Optional Shop refinements are linked beside the results. Search scope is retained separately from the actual offer counterparty in the same workspace state, so an adopted offer can remain intact while a fresh Shop entry searches all teams; preference, position, partner and protection changes invalidate obsolete results and perform a fresh search under the retained anchor.

The five canonical recommendation labels and recommendation admission stay unchanged. An independently checked exploration admission requires legal ownership/capacity, a resolved existing recommendation label, full Market pricing, complete supported production for both teams, resolved future-capital evidence and medium/high evidence confidence. Missing FOIS history remains soft context. Unsupported or invalid packages do not become viable offers. No acceptance probability is introduced.

Exploration reuses already assessed candidates within the existing search budgets. The request-local list retains at most twelve rows and shows up to three distinct families. Trade For displays these separately after qualifying offers; Recommended exposes them only if no recommendation qualifies. Labels, rationale and drawbacks remain unchanged. No additional evaluations, provider calls or durable writes are introduced. Recommended diversity and Next Five exclusions remain unchanged.

Within the separate exploration list, supported counterparty plausibility precedes the existing rank key. This makes costly but plausible acquisition paths visible ahead of one-sided proposals with weak counterparty support. The actual current-engine fixture produces “Not Worth It” acquisitions with complete evidence and plausible counterparty benefit; those labels are retained. This ordering does not alter qualifying Recommended ranking or recommendation admission.

Intentional ranking change: qualifying Trade For offers use the existing lexicographic separate-dimension rank (recommendation, selected-strategy benefit, counterparty support, confidence and package cost), rather than outgoing Market cost alone. Its first label is “Best supported fit found,” not “Lowest Market cost found.” Distinct package shapes remain represented. Arithmetic price is not a blended strategic score.

## Async, accessibility and preservation

Search, evaluation and Balance requests own an abort controller, offer revision and request generation. Navigation/context changes abort old work, invalidate previews and prevent old responses from adopting results or clearing newer busy state. Balance retains its 45-second timeout; other workspace requests have a 120-second transport timeout with truthful retry feedback. Asset controls pause visibly; context changes/navigation remain responsive. Loading feedback is near the search/Balance action and all cleanup paths recover controls. Explicit target-entry feedback remains visible independently of search completion.

Searchable Build/Calculator asset lists use bounded, keyboard-focusable scroll regions with a nearby Market/Evaluate link, reducing long roster scrolling. The proposal tray stays in document flow. Phone hub entries use a two-column grid; no transparent overlays or pointer pass-through are used. Native disclosures, meaningful button names, focus outlines and text alternatives remain supported. Responsive Chromium is not physical iPhone/Safari or accessibility certification.

No pricing, strategy, capital, legal-lineup, FOIS formula, account authority, historical week contract, storage retention, lineage or persisted-grade code changed. Existing grades remain RETAINED / NOT REVALIDATED. No trades, Sleeper writes, lineup changes, historical regeneration, backfills or migrations were performed.

## Validation evidence

Deterministic tests use actual current routes, authenticated fixture accounts, canonical fixture sources and existing engines. These establish controlled behavior, not universal live acceptance. New functional tests cover complete versus invalid exploration, intent filters, correct costly labels, bounded candidate reuse, strategy-first ranking and scale/tolerance honesty. Actual-page browser journeys cover live totals before Evaluate, both-team summaries, verdict visibility, pointer hit-testing, Balance preview/Keep Original/Adopt, reload, automatic Shop/Trade For, refinements and Next Five at 320/375/390 and desktop with short and realistic heights. Existing regression tests continue covering exact acquired picks, ownership, protections, generations, missing evidence, strategy, league isolation and navigation races.

Detailed measurements and final release-gate results are appended after validation. Local reproducible evidence is in `.validation/trade-simplification/`; no synthetic result is described as authenticated live production or physical Safari acceptance.

## Scout independent handoff

Record live version/build/commit, league, exact assets, strategy, result counts, expected versus actual and timing boundaries. Challenge all unsupported conclusions.

1. Build: select two actual teams, add/remove players and exact acquired picks. Before Evaluate verify individual prices, totals, favored receiving manager, exact gap and bar captions. Missing prices must remain unavailable/partial. Equal totals require no sweetener; closer-to-even is optional.
2. Evaluate: one action, verdict visible without upward backtracking, grounded benefits/costs for both teams, immediate major drawback, expandable independent Market/lineup/capital/package/confidence evidence. Supported overpay remains visibly an overpay.
3. Balance: verify correct direction and actual owned assets; exact original/current pick identity and locks; preview does not adopt, Keep Original preserves, explicit Adopt persists on reload. Edit invalidates old results/status. No stale response overwrites newer intent.
4. Shop: owned player or acquired pick → Shop starts all-team Best Overall search. Refine afterward, select a partner optionally, protect exact assets. New search must retain the outgoing anchor and exclude protected assets.
5. Trade For: opponent dossier → actual owner/target → automatic search. Inspect recommended and supported costly/unfavorable options separately. Edit/re-evaluate; invalid capacity/ownership/locks/missing evidence must remain excluded. Free agents must have no impossible Trade For action.
6. Recommended: prominent Discover, distinct top families and partners, Next Five excludes shown families. Empty states are truthful; exploration appears only when genuinely supported. Do not infer broad diversity or universal speed from one batch.
7. Cross-workflow: generated offer → Calculator → advanced evaluation preserves assets/locks; multi-asset reload, explicit new target precedence, both leagues' scoring/ownership/values/strategy and FOIS boundaries remain correct.
8. Phone: 320/375/390, short and realistic portrait heights and desktop. Pointer-hit primary actions, loading feedback, focus/disclosures, long picks/technical evidence and page width. Distinguish responsive Chromium from physical iPhone/Safari.

Signed-in live Trade testing and physical iPhone/Safari remain Scout/Richard acceptance work if no authorized manager browser session is available. Read-only production health/identity/log checks do not establish numerical or authenticated journey acceptance.

### Controlled quality equivalence

The baseline checkout and this release used identical prepared source facts, strategy and a fixed eligible pick-quote retrieval timestamp, with `PYTHONHASHSEED=0`. Calculator output matched exactly, including its generation. Completed evaluation matched exactly after excluding presentation HTML. Qualifying Shop, Draft Capital Shop, Recommended and Next Five rows **and their variants** matched exactly after recursively excluding presentation HTML. They returned five qualifying results each; evaluation counts remained 162, 156, 18 and 140 respectively. Trade For ordering and the separately admitted exploration feed are the documented intentional changes. This does not establish equivalent outcomes for every production league or package.

The initial unfrozen benchmark was superseded because current retrieval timestamps legitimately change evidence identities and tie-breaks. Intermediate validation runs were superseded while correcting shared-layout and legacy UI-contract failures. Only the final complete validator result is release evidence; no interrupted run is called green.

### Measurement boundaries

Service measurements use three sequential calls per operation over the seven-team canonical DiscoveryRepair fixture, two legal starter slots (QB/WR), prepared source prices/projections and no remote providers. Source/cache state persists between samples. Values are milliseconds (p50 / worst observed), not production SLAs or cold-provider timings:

| Operation | Baseline | Release |
| --- | ---: | ---: |
| Build workspace readiness | 22.95 / 39.17 | 5.25 / 12.81 |
| Canonical calculator service | 3.72 / 4.09 | 3.39 / 4.26 |
| Evaluate | 84.70 / 90.39 | 54.76 / 65.34 |
| Balance | 211.94 / 313.17 | 80.54 / 83.16 |
| Shop first batch | 941.23 / 949.60 | 768.49 / 1013.05 |
| Shop Draft Capital refinement | 897.05 / 1142.92 | 664.07 / 690.48 |
| Trade For first batch | 267.07 / 336.13 | 242.39 / 423.72 |
| Recommended first batch | 74.10 / 80.95 | 151.57 / 223.41 |
| Next Five | 790.50 / 861.10 | 861.36 / 1031.51 |

Discovery timing varies; the small fixture's Recommended and Next Five samples were slower, and some worst observations increased. These measurements do not prove universal performance improvement. Evaluation counts, provider requests, search budgets and qualifying results remained unchanged in the equivalence sample. Build avoids full preparation and makes zero edit-time API requests. Established performance/resource gates and Scout's controlled live timing recheck remain necessary.

Browser intervals include automation, scrolling, request/render and observation overhead. They are recorded separately from service processing. The core phone Build journey has thirteen logical steps from opening Trade through explicit adoption and reload (twelve on desktop, which needs no side-tab switch); diagnostic strategy and exact-pick edits are excluded from that action count. Recorded scroll events include programmatic focus and diagnostic edits and are not human touch gestures or a minimum scroll estimate. Preview/adoption are client state changes, not Sleeper transactions.

The final actual-page run passed nine new tests in 62.652 seconds. Seven viewport samples (320×483/568, 375×483/667, 390×483/844, 1280×900) produced these browser-visible intervals in milliseconds (p50 / worst), including automation and concurrent validation overhead:

| Browser operation | Release sample |
| --- | ---: |
| Open Trade → Build context ready | 428.1 / 492.4 |
| Add incoming player, including pointer/scroll | 101.6 / 132.1 |
| Evaluate → completed assessment | 189.8 / 207.6 |
| Balance → preview options | 236.9 / 374.1 |
| Preview click | 50.7 / 56.8 |
| Explicit adoption | 115.8 / 119.7 |
| Shop route → first offer | 1487.8 / 1535.5 |
| Shop refinement → terminal control recovery | 1052.8 / 1174.0 |
| Trade For route → first offer | 925.4 / 967.3 |
| Discover → terminal control recovery | 396.6 / 429.6 |
| Next Five → terminal control recovery | 735.6 / 866.3 |

Across those runs, the extended Build trace recorded 14–21 page scroll events and 5–7 picker-region scroll events. The actual pointer checks passed, primary verdict fit above phone navigation, and document width remained bounded. Keyboard entry/disclosures, exact protections and preview state receive both this journey and existing regression coverage. No full accessibility certification, signed-in live acceptance, cold/warm production benchmark or physical-phone acceptance is inferred.

### Final canonical validation

The complete 2,639-case regression and all ten canonical gates passed in the production-equivalent Python/Chromium container under the unchanged 2 GiB / 2 CPU limits. Validator duration: 694.842 seconds. Route/OpenAPI validation found 260 method registrations, zero duplicates and 239 OpenAPI paths. Canonical HTTP and tracked-process cleanup passed.

| Canonical gate | Result |
| --- | --- |
| Committed whitespace | PASS |
| Working-tree whitespace | PASS |
| Staged whitespace | PASS |
| Python compilation | PASS |
| Authoritative Ruff | PASS |
| Dependency integrity | PASS |
| Full unit/regression suite | PASS |
| Route/OpenAPI | PASS |
| Tracked canonical HTTP | PASS |
| Process cleanup | PASS |

Additional focused evidence includes 97 functional tests, 37 focused browser/evidence tests, 15 shared-workspace contracts, 10 phone/horizon presentation contracts and the nine new functional/actual-page tests. These sets overlap and are not summed as independent coverage. Initial failures were corrected; assertions for legal ownership, exact locks, explanation identity, visible independent horizons and primary-control hit targets were preserved or strengthened. No gate or timeout was relaxed.

### Lifecycle and resource validation

The ordinary, archive-warmed and combined-read lifecycle gates passed under the unchanged 2 GiB memory/swap and 2 CPU contract. Each reported one expected semantic worker, zero container restarts, zero OOM/OOM-kill events in the completed gate run, compatible artifact reuse, generation replacement and cleanup. Fixtures contained 12,322 assets; ordinary had 30,726 historical records, and archive/combined scenarios had 461,166. All records were newly generated disposable test evidence, not production history.

| Scenario | Result | Peak working set (MiB) | Raw cgroup peak (MiB) | Workers | OOM events |
| --- | --- | ---: | ---: | ---: | ---: |
| ordinary | PASS | 1357.46 | 1436.54 | 1 | 0 |
| archive-warmed | PASS | 1370.00 | 2048.00 | 1 | 0 |
| combined-read | PASS | 1376.76 | 2048.00 | 1 | 0 |

Working-set accounting is the established gate accounting, not a new exemption. Raw archive usage reached the cap with reclaimable file cache. Two earlier fixture-preparation attempts were superseded: insufficient disk replacement headroom, then an OOM while writing a large fixture to tmpfs. The final disk-backed runs had adequate headroom after retained local test-source copies were relocated reversibly; no resource threshold, fixture size or admission rule changed. No application history/cache was repaired or removed.

Guarded Linux recovery/quiescence positive and negative checks passed, followed by all 141 recovery/projection/storage-contract tests in 15.185 seconds. The test used `DTOS_DISPOSABLE_RECOVERY_TEST=1` and the unchanged 2 GiB / 2 CPU container limits. It did not execute production storage maintenance.

# v1.21.12 / build 2112 — Trade discovery performance

## Scope and measurement

This release preserves the v1.21.11 recommendation intelligence and optimizes
repeated exact computation. It does not change Market normalization, freshness,
strategy pricing, counterparty gates, legal-lineup semantics, search budgets,
family exclusion, locks, near misses, repair or adoption. Free-agent Trade For
behavior remains a separate Main Chat workstream.

Measurements run in disposable Python 3.12 containers limited to two CPUs and
2 GiB, over frozen synthetic evidence. Pipeline wall time includes response JSON
serialization; authentication, real upstream latency and browser/network delivery
are outside this benchmark. These are controlled fixture results, not measured
production timings or a production SLA. Profiling overhead is reported separately.

The first result-producing publication uses 12 teams, 30 players, 12 exact picks,
nine starting slots and 13 projection weeks. Three cold/session runs compare the
original v1.21.11 source against this release. A future-horizon filter also forces
the unchanged 180-evaluation budget, retaining truthful near misses.

A second publication uses the current public read-only Day Traders shape:
10 franchises, up to 32 players including six taxi players, 26 active roster slots,
11 starting slots (QB, RB, RB, WR, WR, WR, TE, FLEX, FLEX, FLEX, SUPER_FLEX),
15 bench slots and four draft rounds. Prices and projections are synthetic and
frozen. Three years of exact picks retain original franchise and current owner.
Unsupported third-round evidence is deliberately unavailable. Separate fixtures
cover a complete positional lineup and missing required positional evidence.

Reproduce with `python -m tools.validation.trade_discovery_performance --fixture
<fixture-directory> --output <artifact-directory> --prepare --repeat 3`. Prepare
once, then reuse that publication for both source trees. `--profile` saves cProfile
function counts/timings; `--budget` exercises budget exhaustion. `--reference`
compares every factual/business response against an earlier JSON artifact.

## Root causes and corrections

1. Post-trade exact lineup solving ran for both franchises, both optimal/reserve
   views and each supported week on every package. Pre-trade optimal baselines
   were already reused correctly and remain unchanged. The original 18-evaluation
   Recommended profile made 949 exact solver calls; lineage/projections were valid.
   Its 12.01-second profiled wall time included 10.19 seconds inside lineup solving.
2. Expanded construction repeatedly filtered incoming combinations inside every
   outgoing combination, recalculated package sums/IDs and sorted top-eight and
   nearest-three lists for every pair. One expanded target visited 55,881 pairs
   but made about 112,000 list sorts and about 705,000 match checks. Precompute the
   same valued combinations and filter once, then update small top-k lists only
   when a key can enter them. Every pair, tie ordering, count, diversity shortlist
   and proposal identity remains equivalent to the frozen original implementation.
3. Avoid allocating LineupEntry objects for losing dynamic-programming transitions.
   This retains every legal assignment, score and canonical tie break. Randomized
   reference comparisons include missing/zero/negative projections, eligibility,
   repeated slots, complete and partial assignments.

## Reuse and boundaries

`SearchLineupMemo`, exposed through the existing unified intelligence API, caches
only frozen exact mathematical lineup results. Keys combine account/session,
league/franchise, the existing full canonical search/evidence boundary and exact
player/slot inputs. Projection values, labels, eligibility, scoring/publication,
ownership and roster changes invalidate relevant reuse. Week-specific known-bye
eligibility participates; two weeks with identical math can reuse the result while
week IDs, source provenance and confidence remain in the caller's evidence.

Distinct-week testing found the initial 8 MiB cap churned below one full search working set. The final cap accommodates that measured working set within the unchanged 2 GiB resource envelope. The locked LRU retains at most 32 MiB conservatively accounted bytes, 8,192 entries,
and a 180-second TTL. Oversized or disabled caches retain nothing. Expired entries
are rejected on read and swept at the next request. No new worker, durable write,
provider refresh, result-universe cache or per-user database is introduced.
`search_evidence.reuse` exposes hits, misses, retained bytes/entries, caps and TTL.
Temporary construction combinations use the unchanged bounded asset pools and are
released with the construction call.

Next Five reuses identical mathematical work within the matching session/evidence
scope; new packages still get full strategy, counterparty and package-specific
assessment. It continues to apply previous-family exclusions. Candidate universes
and complete recommendation responses are not retained. A new strategy recomputes
judgment while retaining identical global prices and eligible math.

Prepared canonical Market facts, ownership, scoring, needs/FOIS context and
counterparty profiles were already assembled per request, not fetched per candidate.
The pinned projection reader still reads each of 13 weeks only once per request.
No request-time provider access occurs in the prepared benchmark. In the cold
Day Traders-shaped profile, canonical fact assembly occurred twice (workspace and
league model), not 180 times; counterparty evidence context once; team evaluation
10 times. SQLite work was small: 3,868 statements took 0.029 profiled seconds;
projection decoding took about 0.20 seconds. No query/schema/index migration or
additional concurrency is justified by those measurements.

Explanation construction remains intact. In the cold 180-evaluation profile it
used about 0.40 seconds, rather than dominating latency; deferring it is outside
the smallest demonstrated fix. Reconciliation, ranking, diversity and diagnostics
also remain intact. Inclusive profile times overlap and must not be added together.

## Quality and phone contracts

All 18 responses in the original result-producing fixture match exactly after
removing only timing/reuse telemetry. This includes package identities/order,
recommendation labels, Market values, projections, strategy and counterparty
conclusions, explanations, diversity, near misses and missing evidence. The budget
fixture also matches the original response exactly. Frozen-construction tests
compare all proposal/diagnostic fields across randomized ties, all search phases,
player/pick targets and return preferences; they retain the same >50,000 pairs.

Focused tests cover warm search, Next Five family exclusion, generation changes,
strategy changes, exact locks, unavailable/nonfinite versus zero projections,
account/session separation, byte/entry/TTL bounds and concurrent immutable reads.
The existing phone loading state and revision guard already reject a superseded
response. Responsive Chromium tests at 375/390 verify useful pending text,
aria-busy, disabled controls, page bounds and newer-strategy results winning.
No fake progress percentages or new UI flow is added. Physical iPhone/Safari is
not tested here. Existing technical-token wrapping and readable local table scrolling
remain covered by the accepted browser suites.

## Measured results

### Result-producing 12-team publication

Three runs per workflow. Seconds are p50 / worst; old and new frozen business responses match exactly. The table below records the initial optimization pass; the final-cap reference replay also matches all 18 responses.

| Workflow | v1.21.11 | Optimized |
|---|---:|---:|
| Recommended cold | 5.944 / 5.967 | 1.027 / 1.030 |
| Recommended warm | 5.907 / 6.223 | 0.650 / 0.673 |
| Next Five | 6.024 / 6.922 | 0.925 / 0.964 |
| Shop | 17.554 / 28.383 | 1.925 / 1.962 |
| Trade For | 19.607 / 19.914 | 1.809 / 1.813 |
| Make It Cheaper | 2.295 / 2.375 | 0.395 / 0.434 |

### Budget exhaustion

With the unchanged 180-evaluation budget, v1.21.11 took 93.814 seconds for Recommended and 81.491 seconds for Next Five (one original run). Three optimized runs measured Recommended p50/worst 7.361/7.685 seconds and Next Five 6.335/7.691 seconds, with exactly matching near misses and unavailable evidence.

### Day Traders-shaped observations

The complete 11-starter publication produced the same five Recommended results, one additional Next Five result after exclusions, five Shop results, three Trade For results and three cheaper variants. One original-source sequence measured 149.424 / 121.119 / 138.346 / 24.364 / 40.576 / 2.567 seconds respectively (cold Recommended, warm Recommended, Next Five, Shop, Trade For, cheaper). All six frozen business responses exactly match the optimized sequence.

Distinct-week evidence additionally reproduced a 154.541-second original cold Recommended search. The final memo retains about 3,885 unique exact math results for that cold request; a warm repeat has zero solver misses. The final cache cap addresses measured churn rather than removing candidates.

Under concurrent validation load, three final distinct-week cold samples measured 30.014, 47.335 and 26.218 seconds. Warm samples were about 4–6 seconds. These loaded samples remain visible in the report; the isolated sequence below runs without other benchmark workloads (its first cold request overlapped the tail of the final combined-read gate).

The final-cap memory run reached 185,970,688 bytes process RSS, about 2.23 MB input data, 13.82 MB for the largest complete response object, and 33,553,075 conservatively accounted cache bytes within the 33,554,432-byte cap. No worker was created. These object sizes do not replace lifecycle peak/RSS gates.



### Identical complete Day Traders-shaped publication

One original full workflow sequence versus three final-cap sequences over the same frozen repeated-week publication. All six original business responses match; seconds are original / final p50 / final worst.

| Workflow | Original | Final p50 | Final worst |
|---|---:|---:|---:|
| Recommended cold | 149.424 | 5.677 | 5.876 |
| Recommended warm | 121.119 | 2.495 | 2.495 |
| Next Five | 138.346 | 5.683 | 5.718 |
| Shop | 24.364 | 1.597 | 1.633 |
| Trade For | 40.576 | 2.516 | 2.605 |
| Make It Cheaper | 2.567 | 0.347 | 0.391 |
### Distinct-week final sequence

All 13 weeks have different projections. Three final-cap runs; seconds are p50 / worst. The original cold Recommended response (154.541 seconds) matches exactly. Other rows are measured final timings, not before/after comparisons against a different projection publication.

| Workflow | Final seconds |
|---|---:|
| Recommended cold | 18.087 / 18.163 |
| Recommended warm | 2.549 / 2.583 |
| Next Five | 10.789 / 11.908 |
| Shop | 3.734 / 4.480 |
| Trade For | 7.483 / 8.274 |
| Make It Cheaper | 0.370 / 0.451 |

All three full response sequences match the earlier final-cap sequence exactly. Cold Recommended retains the same 138 full evaluations and five credible results. Next Five retains the same 180 evaluations, one new credible family and truthful near misses; it is a harder search after excluding the original families. Warm Recommended has 7,176 hits and zero misses. Next Five has 7,603 hits and 1,757 misses.

A separate same-exclusions comparison over the repeated-week publication measured warm Next Five p50/worst 5.825/5.827 seconds versus clearing reuse 8.386/8.729 seconds, with exactly identical responses. No result-universe/session storage is needed.

## Release validation

The canonical validator passed all ten unchanged gates: committed/working/staged whitespace, compilation, authoritative Ruff 0.16.9, dependency integrity, full unittest regression, route/OpenAPI, tracked canonical HTTP and process cleanup. Full regression covered 2,486 tests; final focused coverage additionally executes the 240 prior-optimizer randomized assignments through unittest. Recent Trade regression plus new performance coverage passed 94 tests, followed by 11 final focused tests.

Route/API checks: 257 method registrations, 236 OpenAPI paths, no duplicates. Canonical HTTP: 114 requests. Recovery/quiescence: passed plus 141 focused storage/recovery tests. Final ordinary/archive-warmed/combined-read lifecycle peaks: 1,407,438,848 / 1,419,169,792 / 1,402,486,784 bytes, each with one worker, successful cleanup and no resource errors under the unchanged 2 GiB cap.

Production remains subject to fully green CI and exact immutable merged/tagged deployment identity; final release identifiers are reported in the task handoff.

## Scout acceptance

On LIVE PRODUCTION v1.21.12, record time-to-result, result counts and package diversity
for Recommended, Next Five, a safe repeat, Shop Asset and Trade For. Confirm prior
families do not repeat, Market prices and exact protections stay stable, and Make
It Cheaper/preview/adoption remain healthy. Compare quality with recent live behavior.
Check meaningful loading at 375/390 in RESPONSIVE CHROMIUM, and label any PHYSICAL
IPHONE/SAFARI test separately. Continue tracking free-agent Trade For separately.
Do not submit trades, change lineups or mutate Sleeper.

Authenticated production manager access is unavailable from this workspace;
existing read-only inspection returned 401. No new access bridge is created.
Public health and immutable deployment identity are checked after release; exact
live timing and manager acceptance remain Scout's independent checks.

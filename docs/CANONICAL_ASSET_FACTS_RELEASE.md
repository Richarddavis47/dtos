# Canonical Asset Facts — v1.21.9 / build 2109

## Current-code reconciliation

The authoritative baseline is v1.21.8, `cabb73cd05af32ac0666ac40b9dbdbac552deec2`.
Current main was fetched and matched it. The v1.21.4 scope defect remained:
`IntelligenceOrchestrator.player_report` selected Market facts from the active
Front Office's portfolio, which only contained that roster's players. Dossier
Live Data used a global player lookup. Market and Trade used canonical cached
provider selection. Selecting Richard's Front Office for an opposing player
could therefore hide a globally supported price in the headline.

On unchanged current code, deterministic McBride (Sleeper 10225) and Allen
(4984) fixtures both returned headline `None`, Live Data 500 and Trade 500.
These prices establish the scope contradiction, not permanent/live prices.
Scout's 695/931 observations remain separate live evidence.

A second current boundary risk was provider namespace caching: roster Market
could reuse an older raw quote after a published provider snapshot changed.
Published provider rows now bypass this process-local provider cache. Retained
provider rows in the published snapshot remain governed by the existing quote
eligibility policy; no warehouse-only observation becomes a current price.

## Boundary and consumer trace

`cached_market_results` remains the authoritative normalization and source
selection implementation. `cached_market_facts` wraps those results in a
`PlayerMarketFact`: player ID, normalized value, source-generation identity,
generation timestamp when supplied, separate source/retrieval times, per-source
clocks, freshness, supported sources, evidence confidence, availability/reason,
calibration state, agreement, warning and retained-provider fallback.

The per-player source-generation fingerprint excludes league ownership, manager
strategy and roster fit. It includes the source rows, normalization references,
selection method and selected evidence state. This distinguishes source changes
and freshness transitions even in older snapshots without a supplied generation.
Facts serialize to JSON-native durable/API payloads.

| Consumer | Current boundary and correction |
| --- | --- |
| Market directory/detail/API | ValuationUniverse → durable Asset Market read model; canonical fact retained with each selected price. |
| Dossier headline | Global canonical fact; portfolio no longer gates Market availability. |
| Dossier independent evidence / Live Data | Owned-player profile Market fields use that fact; route pins the same fact for Live Data. Raw provider values remain separately labelled. |
| Player-intelligence API | Same global fact and selected price, with inspectable raw provider evidence. |
| Trade Center / Create / Recommended / Shop / Trade For | Shared Trade workspace pools use canonical facts; proposal/search presentation preserves fact provenance. Strategy/evaluation only operate on separate context. |
| My Team / Team HQ | Shared roster/intelligence context; published portfolio provider evidence cannot fall back to an older namespace quote. Compact player cards use prepared projection views, not prices inferred from fit. |
| Commissioner | League-aware opportunity/ownership context and descriptive Sleeper metadata; no independent player-price calculation. |
| Matchups / shared player summary | Pinned prepared Sleeper week/scoring projection views; shared summaries receive display/availability together. |
| Exact acquired pick | Existing pick adapter/ledger remains separate; year, round, original franchise, current owner, range, confidence and established exact slot are preserved. |

Global Market identity does not encode ownership. Market/dossier ownership uses
the same synchronized league teams; Trade pools retain the actual source roster.
Opposing players remain owned by their franchise. Free agents remain unrostered,
not tradeable assets fabricated in another roster's pool.

## Provider and freshness findings

FantasyCalc uses exact Sleeper IDs and the explicitly requested 12-team/2QB/PPR
feed. DynastyProcess uses conflict-rejecting exact provider-ID crosswalks and its
2QB feed. Quote eligibility rejects unresolved identity, invalid/zero-confidence,
historical-only, explicitly expired and incompatible-format evidence. Canonical
selection deduplicates provider families, excludes conflicting mirrors and never
averages unproven formats. FantasyCalc is the existing primary reference when
secondary format compatibility is unproven; a supported DynastyProcess quote can
stand alone when FantasyCalc has no record. No provider is universally required.

Normalization is unchanged: existing provider scales/reliability, 70% native
range plus 30% percentile when the population supports it, or linear normalization
for small populations. Pre-filter normalization references remain authoritative.
Raw FantasyCalc/DynastyProcess units are not DTOS 0–1000 prices. No player-price
tuning, new averaging or strategy repricing was introduced.

FantasyCalc does not supply a source timestamp; retrieval is explicitly displayed
without claiming source freshness. DynastyProcess source date is separate from
retrieval. Freshness/confidence use the existing source-time policy. Stale usable
quotes remain usable; explicitly stale-beyond-policy quotes remain unavailable.
Failed refreshes retaining eligible published rows disclose last-valid evidence.
No accepted maximum age or fallback policy was changed.

Market can serve its last valid immutable artifact while replacement warms.
That artifact retains its own source fact/as-of; it does not borrow newer dossier
or Trade provenance. Shared evidence disclosure distinguishes source generations
from the Market read-model generation. Different generations remain explainable,
not silently asserted equal. Cold absence is explicitly unavailable/warming.

Unavailable reasons cover no supported evidence, unresolved identity, incompatible
format, stale beyond policy, invalid evidence, historical-only evidence and cold
warming. Missing evidence never becomes zero. Evidence confidence and provider
support are distinct from strategy/recommendation/manager acceptance confidence.

## Projection correction

The current Live Data availability reason was `None` when numeric projection
was available, and the page stringified it. The route now renders availability
from the exact same selected-week prepared view as the numeric Sleeper panel.
The player-context API also supplies positive text for available evidence.
No projection calculation, scoring, horizon or Projection Intelligence redesign
was introduced. Available numeric zero is preserved; absent projection is not zero.

## Validation and limitations

The deterministic contract suite covers opposing McBride/Allen, an owned player,
a free agent, last-valid/warming, true absence, stale usable evidence, incompatible
providers, supported secondary evidence, source clocks, strategy changes,
ownership moves, exact acquired picks, refreshed provider cache and selected-week
projection presentation. Real HTTP Market/player/Trade boundaries compare identity,
price, generation, availability and freshness. Retained artifact provenance is
verified independently of current data.

Responsive Chromium at 375px and 390px checks value and unavailable-reason
readability, collapsed evidence, expanded long generation disclosure, no overflow,
and headline/Live Data generation agreement. This is not physical iPhone/Safari.

The final unchanged canonical validator passed all 10 gates in 297.466 seconds.
All 2,473 regression tests passed, including canonical facts, recent Trade
regressions and browser contracts. Route validation passed 257 method registrations,
236 OpenAPI paths and no duplicates; tracked HTTP and process cleanup passed.
Authoritative Ruff, compilation, dependency integrity and all whitespace gates passed.
The isolated browser was Chromium 153.0.8010.12; the earlier focused browser run
also passed with system Chromium 151.0.7922.173.

Ordinary, archive-warmed and combined-read Linux lifecycle gates passed with
2 GiB memory/no swap, two CPUs, one semantic worker and zero OOM events. Effective
memory peaks were 1,425,543,168, 1,429,069,824 and 1,423,360,000 bytes respectively.
The recovery/quiescence gate and its 141 regression tests passed. The combined-read
fixture retained 12,322 assets and 461,166 historical records. No fixture scale or
resource assertion was reduced.

Release commit, PR/CI and deployment evidence are recorded in the release PR and
final task report. Initial failed evidence is retained in local ignored validation
artifacts. No gate is weakened. The first host-wide regression run found two stale assertions
(positive projection text and new Market-layer provenance), a JSON snapshot
serialization defect from tuple-valued facts, and ambient memory-admission
failures while Docker builds/lifecycle work shared the host cgroup. Facts now
serialize to native lists; assertions explicitly verify the extended contract.
Canonical validation is rerun in a dedicated 2 GiB cgroup with the unchanged
validator and gates, rather than weakening admission or mocking release limits.
An intermediate isolated run also exposed a fixture-only Sleeper URL override
that omitted the normal `/v1` path expected by two onboarding mocks. Removing that
override restored all 16 onboarding tests and the complete canonical run. The
container used the workspace's Git 2.52.0 runtime for the unchanged committed
whitespace command; Debian Git 2.39 rejects its supported option combination.

Public production checks can run without an account session. Current manager
pages require sign-in; the existing operations credential returned 401 during
pre-release inspection. No new access bridge is created. Scout owns independent
authenticated live cross-page acceptance.

## Performance evidence

The correction makes no provider HTTP calls. A dossier now pins its canonical fact
for headline and Live Data. Trade still resolves one canonical batch per workspace;
Market resolves one batch per generation. Existing bounded recommendation/search
budgets and repair logic are unchanged. Local fixture timings are not a production
latency promise. Scout's approximately 88-second Next Five observation remains a
separate workstream; no causal link to that latency is established here.

## Scout handoff

Test the deployed v1.21.9 / build 2109 release and record the displayed version,
build and deployment commit. Distinguish LIVE PRODUCTION, RESPONSIVE CHROMIUM,
and PHYSICAL IPHONE/SAFARI in every report.

1. Trey McBride: compare Market, dossier headline, independent/Live Data detail,
   and Trade. Compare price, availability, freshness/as-of and actual ownership.
2. Josh Allen: repeat the same checks. Values may change; do not require 695/931.
3. Repeat for one Richard-owned player, one opposing player and a priced free agent.
4. Change strategy: the same source-generation Market price must remain identical.
5. A numeric Sleeper projection must never coexist with “Current projections: None”.
6. Observe warming/stale disclosure naturally; retained values must identify their
   source/as-of rather than pretend they are newly retrieved evidence.
7. Check readability at 375px and 390px RESPONSIVE CHROMIUM widths.
8. Recheck Recommended, Next Five, Shop, Trade For and Make It Cheaper, including
   exact locks, preview/adoption, near misses and repair diagnostics.
9. Record approximately 88-second Next Five latency separately, along with any
   other cross-page contradiction and the source generations involved.

Do not submit trades, change lineups or mutate Sleeper for this acceptance.

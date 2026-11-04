# DTOS v1.21.30 / build 2130 — Canonical Projection Freshness

Starting main and production: v1.21.29 / 2129,
`83113653399d7c6bde77c555d4dfa18981d2a3dc`; no intervening main changes.
Scout's v2129 preview and Shop corrections are retained.

## Source contract and correction

Sleeper remains the sole canonical player-projection source. The existing
publisher applies the selected league scoring to Sleeper projected statistics;
DTOS derives optimal legal lineups and trade impact separately. Missing player
evidence stays unavailable. No projection model, recommendation threshold,
ranking algorithm, price, historical record or retained grade is changed.

The publisher supplies `projection_snapshot_id`, with a pinned weekly manifest
for horizon publications. Trade previously read a nonexistent `generation`
field and substituted `current`, masking actual publication changes. Trade now
uses the publisher's immutable identity from the same pinned handle used for
lineup reconstruction. Provenance includes league, season/week, scoring profile,
source fingerprint, contract versions and horizon references. Retrieval and
publication timestamps are not replacement identities. Reusing identical
semantic evidence is stable; materially changed publication changes identity.
Missing or foreign identity is explicitly unavailable, never `current`.

The workspace returns the same small source descriptor so reload can compare
retained context with the current league publication. No new request, provider
call, projection snapshot or unbounded cache is introduced. Manual evaluation
and searches reject publication changes during their computation using the
existing `canonical_evidence_changed` response and bounded retry behavior.

## Client freshness and retained context

One explicit collection adapter compares source generations from `results`,
`exploratory_results`, `near_misses`, `comparisons`, Shop `markets[].returns`
and direct `evaluation`. It compares Market, projection and historical source
keys independently, not evaluation IDs, package digests or retrieval times.
Foreign-league assessments cannot update the active league's freshness state.
An empty search contains no source evidence and does not imply staleness.
The browser learns source changes through existing workspace loads and assessed
responses; there is no background polling or claim that an unseen publication
can be detected before one of those supported interactions.

Older assessments keep their recommendation, qualification, drawback and
original provenance. Known changed sources produce retained/stale qualification
and a keyboard-accessible **Reevaluate Trade** action using the existing service.
Reload always marks retained context not revalidated. Preview/Keep Original
preserves exact assets and compatible locks; explicit adoption preserves the
preview's qualified explanation. Balance loading/results/errors retain the
completed assessment separately. A fresh supported Evaluate establishes a new
current assessment. Asset/strategy/league/target changes and obsolete in-flight
responses continue using the accepted intent/binding/revision safeguards.

## Evidence boundaries

`tests/test_trade_projection_freshness.py` uses an actual disposable canonical
publisher, legal-lineup preparation and Trade evaluator. Equal compatible
prices and a publication changing incoming QB production 8→25 reproduce
**−2 / NOT WORTH IT → +15 / SMASH ACCEPT**. These are controlled fixture values,
not production player assessments. Reused evidence/different offers do not
change the source generation; different scoring and league contexts do.
Missing required eligible-slot production fails unavailable, never zero.

`tests/test_trade_projection_freshness_browser.py` executes actual components
and JS with intercepted transport carrying real publisher/evaluator outputs.
Collection placement is controlled to isolate exploratory-only and other
response paths; it is not proof that production discovery returns those offers.
A separate genuine unequal-price negative offer exercises enabled Balance,
without forcing Balance on an exactly equal package or changing fairness rules.
Responsive Chromium covers 320×483/568, 375×483/667, 390×483/844 and desktop
1280×900. Pointer hit-testing, focus, warnings/drawbacks and overflow are checked.
This is not physical iPhone/Safari or authenticated production acceptance.

## Scout independent acceptance

Verify deployed Settings version/build/commit first. Distinguish source fixtures,
authenticated live behavior, responsive Chromium and physical Safari.
Run publication-change scenarios only against disposable fixtures; do not
publish fixture projections into production or mutate Sleeper.

1. Run the original actual-publication fixture. Record both source generations,
   legal-lineup deltas and recommendation labels. Confirm Market totals unchanged.
2. Reuse the same publication for the same and different offers. Generation
   remains equal despite different evaluation IDs. Retrieval-only refresh does
   not invent another generation. Repeat with two league scoring configurations.
3. Exercise exploratory-only, qualifying, near-miss and Shop-return response
   collections. Changed projection evidence qualifies the older assessment;
   legitimate empty searches and different offer IDs alone do not.
4. Preview an offer, change the disposable publication, reload, Keep Original;
   repeat with Adopt. Exact assets/target/locks remain, prior qualification and
   drawback remain, and obsolete evidence is not presented as current.
5. Run Balance on a genuinely unequal package: old assessment stays readable
   during loading/completion/error. Reevaluate establishes current supported
   evidence without automatically changing or adopting the offer.
6. Publish during evaluation/search; obsolete results fail the existing source
   guard. Change strategy/target or navigate during pending requests; older
   responses cannot replace newer intent.
7. Live sample Trade For alternatives, new Shop all-team scope and same-asset
   refinements, live Market totals/bar, Evaluate, Balance, protections,
   multi-asset reload, Recommended/Next Five, free-agent restrictions, strategy
   price invariance, league isolation and retained FOIS disclosures.
8. At 320/375/390 and desktop, short/portrait heights: read stale warning and
   drawback, keyboard-focus/click reevaluation and preview/adoption, inspect
   evidence codes, no whole-page overflow or sticky obstruction.

No affected live trade has been established. Unchanged live retained grades do
not prove numerical historical correctness. No regeneration, migration,
historical backfill, permanent per-trade evidence or Sleeper mutation occurs.

## Controlled cost observation

Twenty-five sequential disposable-fixture evaluations per version, with the
same prepared workspace: baseline/corrected median 4.80/5.61 ms; worst observed
20.50/8.66 ms. Identity extraction averaged 1.44 microseconds over 10,000 calls.
These are local server-function costs with concurrent validation activity, not
browser latency or a production SLA. Source descriptors use in-memory handles;
no extra historical/database/provider reads or persistent derived cache is added.
The original source-publication reproduction was also executed against the
baseline implementation: both sides of the changed publication reported
`current`; the corrected implementation reported distinct publisher identities.

## Resource and validation evidence

Focused verification: 9 new publication/rendered-browser tests passed, plus
34 affected preview, Shop, horizon and capital/strategy regressions. Recovery
positive/negative quiescence checks and 141 retained-storage/projection tests
passed. Lifecycle gates used their unchanged 2 GiB memory/swap and two-CPU
contract, with one expected semantic worker, clean shutdown and zero OOM events.

| Lifecycle | Effective working-set peak | Outcome |
|---|---:|---|
| Ordinary | 1,410,158,592 bytes | Pass |
| Archive-warmed | 1,451,692,032 bytes | Pass |
| Combined-read | 1,451,003,904 bytes | Pass |

The established gate separates effective working set from reclaimable file
cache: raw cgroup peaks can reach the 2 GiB cap during fixture generation.
This is not a claim that total raw cgroup memory stayed below 1.46 GB.

An initial overlapping local full-regression/large-fixture run exhausted
temporary disk space, producing cache-admission/database/browser errors
(2,656 tests, 104 errors), and combined fixture generation exited before its
gate report. Only the new incomplete disposable fixture was removed. The
combined gate and recovery were rerun sequentially and passed; release requires
a separate clean full canonical rerun, which passed all ten gates in 751.134 s.
The complete 2,656-case suite passed (739.739 s). Route validation checked
260 method registrations and 239 OpenAPI paths with no duplicates; canonical
tracked HTTP and final process cleanup passed. No assertion or resource cap was relaxed.

| Canonical gate | Result | Seconds |
|---|---|---:|
| Committed whitespace | Pass | 0.006 |
| Working-tree whitespace | Pass | 0.013 |
| Staged whitespace | Pass | 0.004 |
| Python compilation | Pass | 1.700 |
| Ruff | Pass | 0.103 |
| Dependency integrity | Pass | 0.951 |
| Unit and regression tests | Pass — 2,656 cases | 739.739 |
| Route and OpenAPI | Pass | 1.512 |
| Tracked canonical HTTP smoke | Pass | 7.014 |
| Process cleanup | Pass | 0.092 |

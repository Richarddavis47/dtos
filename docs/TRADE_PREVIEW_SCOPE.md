# DTOS v1.21.29 / build 2129 — Preview Context, Explicit Shop Scope

Baseline: v1.21.28 / 2128, `056d2666379a1a7a4653eecfba2ac932bcd247aa`.
Current main matched that commit when this correction began.

## Cause and correction

The workspace serialized six string assessment fields. It omitted the outer
exploratory qualification, confidence, limitations, structured dimensions and
provenance. The restored fallback renderer also omitted the major drawback.
Balance retained assessments only if a server HTML wrapper was present, so the
restored structured assessment was replaced by pending text.

The temporary, account/session/league-bound draft now retains bounded structured
assessment context, using the existing evaluator's fields. It stores no rendered
HTML, full search feed or new backend history. The current offer assessment is
separate from preview/search feedback and remains readable during Balance,
including empty, failed and timed-out requests. Keep Original preserves it;
Adopt changes only the selected offer, retaining its qualification and costs.
Ownership and exact protections are checked before preview/adoption.

Restoration does **not** revalidate strategic evidence. The UI explicitly marks
restored context **not revalidated**, retains original evidence identity and
shows relevant package, strategy, ownership and Market changes. Fresh evaluation
is required for a current assessment. Editing assets/partner/strategy invalidates
the old assessment; canonical evidence-change responses and changed generation
identities in successful search results qualify retained context as stale.
Missing old metadata is not reconstructed or invented. The existing safeguard
for expired Market-generation Balance previews still requires a fresh Balance
before preview/adoption of those numeric adjustments.

## Shop navigation contract

A new explicit outgoing asset resets incompatible partner/preference scope to
**All eligible teams / Best Overall Return**, retaining compatible exact locks.
The existing bounded discovery starts automatically. Same-asset compatible
resume/reload/history preserves intentionally chosen partner, preference and
position without duplicate automatic search. A fresh navigation may explicitly
specify an eligible `partner_roster_id` and supported `shop_preference`; these
override defaults. Reload/history uses the saved controls rather than replaying
old query parameters. Owner identity remains server/authorized-workspace based.
Picking a different Shop anchor in the workspace also resets old hidden scope.
Build My Own saves the new empty proposal without replacing the prior Shop
history snapshot or cached document, so browser Back can resume its intentional
refinements. A cached-page restoration qualifies assessment context as retained,
not revalidated, and does not start another automatic search.

## Boundaries and evidence

The changes are client presentation/state only. No changes to Market arithmetic,
fairness bands, discovery budgets/ranking, strategy, legal lineups, FOIS scoring,
historical persistence, schema or retained grades. There are no added backend
requests for assessment restoration. Restored context is a prior explanation,
never an acceptance probability or a new recommendation.

`tests/test_trade_preview_scope_browser.py` isolates the UI contract with
controlled structured API evidence. It reproduces the Hampton + exact 2028 R4
own pick → Burrow construction at 672/658 and NOT WORTH IT; this does not prove
the live league returns that package today. The authenticated actual route/API
engine journey in `tests/test_trade_simple_browser.py` also previews, reloads and
adopts a real engine-produced NOT WORTH IT exploratory offer without patching
its recommendation. Responsive Chromium covers 320×483/568, 375×483/667,
390×483/844 and 1280×900 with real pointer hit-testing and keyboard focus.
Network-backed browser Back/Forward is exercised separately from a controlled
cached-document lifecycle test. Route interception prevents genuine browser
back-forward caching in that test; its persisted pagehide/pageshow events are
explicitly simulated, not physical-device or live cached-browser acceptance.

## Scout independent live handoff

Verify deployed Settings version/build/commit first. Record league, strategy,
exact assets, original/revised Market values, qualification, drawback and source
context. Distinguish authenticated live testing from controlled source fixtures;
responsive Chromium is not physical iPhone/Safari acceptance.

1. Day Traders → REBUILD → Trade For Joe Burrow. Open a supported NOT WORTH IT
   exploratory offer; use Hampton + exact 2028-R4-1 if still returned (672/658 in
   the original live sample). Preview → reload: label, exploratory qualification,
   major drawback and supported evidence should remain; restoration must say
   not revalidated. Adopt: exact preview package, target, locks and strategy stay.
2. Start Balance. Prior completed assessment and drawback remain in a separate
   section; nearby Balance status reports loading. Success/empty/error/timeout
   must preserve that assessment. Preview → Keep Original preserves it; adoption
   replaces context with the explicitly selected alternative's assessment.
3. Change strategy or package: the incompatible completed assessment disappears.
   Fresh Advanced evaluation provides current evidence. A changed source must
   not leave a restored explanation claiming fresh validation.
4. Shop Nix, refine to Runaway McBride / Draft Capital. Reload or resume the
   same asset: retain scope, no duplicate automatic search. Build My Own →
   explicitly Shop acquired 2027-R4-3: All eligible teams / Best Overall, new
   exact outgoing anchor, compatible locks, automatic bounded search.
5. New explicit supported partner/preference navigation wins restored defaults.
   Change those controls and reload a URL containing older defaults: preserve
   the current controls, not the obsolete URL scope. Check browser back/forward.
6. Sample live totals, Evaluate, Balance, Keep Original/Adopt, exact same-round
   picks/protections, Next Five diversity, supported Trade For alternatives,
   Make It Cheaper, free-agent restrictions, multi-asset reload, league isolation,
   strategy price invariance and FOIS RETAINED / NOT REVALIDATED banners.
7. At 320/375/390 and desktop, short and portrait heights: inspect full drawback,
   disclosures, source identifiers, visible focus, actual button hit targets,
   nearby loading and no whole-page horizontal overflow or tray obstruction.

Production numerical or authenticated Trade acceptance remains Scout's check
when no signed-in browser is available; public health/identity and bounded
authorized read-only inspection do not establish those journeys.

## Controlled performance observation

Five sequential local Chromium samples with identical prepared API fixtures:
preview p50 49→45 ms, reload 120→201 ms, adoption 71→90 ms, Balance 61→60 ms.
Worst observed respectively 76→92, 188→238, 89→218 and 80→145 ms. These include
browser/automation/fixture transport overhead and concurrent validation load;
they are not production server timings or a universal latency promise. Both
versions made exactly ten API POSTs (five discovery, five Balance). Maximum
sample preview draft grew 781→1,530 bytes; it contains structured context, not
HTML or a persisted generated-offer feed. Backend intelligence is unchanged.

The initial full regression exposed an ownership-warning replacement and a
follow-on desktop fixture error. The warning was preserved and the existing
assertions retained. Final validation passed on the corrected source.

## Release validation

Focused preview/scope/navigation/browser contracts: **23 tests passed**. Full
regression: **2,647 cases passed**, including the new eight-method rendered
preview/scope module and existing Trade, Market, FOIS and historical contracts.
The canonical validator passed all ten unchanged gates in **721.934 seconds**:
committed whitespace, working-tree whitespace, staged whitespace, Python
compilation, Ruff, dependency integrity, full unit/regression, route/OpenAPI,
tracked HTTP smoke and process cleanup. Route checks covered 260 method
registrations, no duplicates and 239 OpenAPI paths; canonical HTTP passed.

Ordinary, archive-warmed and combined-read lifecycle gates passed under the
unchanged 2 GiB cgroup contract, with one expected semantic worker, no OOM events
and successful cleanup. Effective memory peaks were respectively 1,396.46,
1,381.73 and 1,356.05 MiB. Warmed raw memory reached 2 GiB because of reclaimable
file cache; the established working-set gates were not relaxed. Recovery and
quiescence positive/negative checks and all 141 recovery tests passed.

CI and deployment identity are reported separately with the final PR/release.
These source and controlled-browser results do not establish authenticated
production Trade acceptance or numerical historical-grade correctness.

# My Team evidence and session intent — v1.21.34 / build 2134

## Scope and starting point

This release starts from v1.21.33 / 2133, commit
`d4c29e8c4c1ffe222ebcf2210fe348d8eba54d5e` (PR #222).
The implementation prompt and supplied October 9 decisions govern. The complete
Codex audit was available locally as `.validation/my-team-audit/REPORT.txt`.
Scout's summarized reproductions were supplied in the implementation prompt;
the complete independent My Team report was requested but was not available at
implementation time. No additional Scout findings have been invented.

## Existing architecture reused

Sleeper ingestion prepares league-specific identities, slots, statuses, roster
and traded-pick facts. Canonical projection publication, Market consensus,
legal-lineup calculation and the existing intelligence orchestrator prepare the
view. `build_team_headquarters` connects those existing calculations to the
My Team route. Prepared standings are reused, not recalculated from weekly
cumulative scores. Player and exact-pick dossiers and Trade Shop routes remain
the existing implementations. No request-time provider call is added.

The page shows identity, selected goal, inventory counts, roster/depth/capital
shortcuts, supported starting contributions, reserve risks and record/PF standing
before advanced intelligence. One Roster action opens every owned player;
IR and taxi assignments remain visible. Advanced grades, horizons, submitted
starters, activity, history and unsupported forecasts remain available on demand.
Key players are identified by supported canonical Market value, explicitly
separate from weekly production. This is not an intrinsic-tier model.

## Audit reconciliation

| Original finding | Disposition and causal correction |
|---|---|
| F1 P2: A → B Trade builder → fresh A loses strategy; My Team does not consume it | Corrected. Bounded account-session/league/franchise intent is separate from disposable proposals; My Team reads and exposes the same selection. |
| F2 P2: partial reserve projections receive complete depth coverage | Corrected. A complete grade requires every eligible reserve to have supported projection evidence. Partial known subtotal and actual covered/expected counts remain qualified. |
| F3 P2: count-only needs/depth/surplus compatibility | Count-only surplus admission removed. My Team now shows legal starting/flex demand and actual supported reserve coverage. Validated player-removal/expendability scoring remains deferred; the old compatibility need heuristic is not relabeled as roster-quality evidence. |
| F4 P2: positional quality and generic recommendations lack meaningful support | Existing lineup contributions and backup gaps are exposed with limitations and actions. Intrinsic positional quality, overall dynasty utility and automatic competitive-window classification remain unavailable where their approved aggregate is absent. |
| F5 P2: static picks have no exact actions/connected quotes | Corrected. Exact original/current-owner identity, prepared canonical quote/range/confidence, dossier and owned Shop links are connected. Missing prices/ranges remain unavailable. |
| F6 P2: roster buried below empty technical grades; status/key-player evidence disconnected | Corrected. Early section shortcuts, factual summary and positional coverage precede advanced disclosures; source statuses and canonical Market leaders are connected. |
| F7 P2: League Standing uses unavailable overall-strength rank | Corrected. My Team consumes the accepted record/PF standings order and its provenance/qualification safeguards. |
| F8 P3: dossier return points to Transactions; roster disclosure closes | Corrected for explicit My Team navigation. Canonical dossiers accept a validated same-league `from_team`; return links reopen the corresponding inventory context. Disclosure state uses bounded tab-session storage. |
| F9 P3: Arkham 320px has 4px document overflow | Scoped wrapping/min-width corrections applied; verified through actual DOM geometry, not a presumed single-selector cause. Shared portraits unchanged. |
| F10 conditional P2: missing Max PF becomes zero | Corrected at ingestion with the existing nullable standing-points normalizer; renderer displays unavailable. No production instance of a missing source value was asserted. |

Scout themes: strategy and depth reproduce the confirmed defects above. Pick
actions, standings and explanations are connected. Comparison ranks now state
the actual complete-evidence cohort, not the total league population. Coverage
is evidence support, not an outcome probability. Rollover is tested through the
actual canonical publisher: compatible published weeks are pinned; an old week
cannot supply current-week points. The unavailable full Scout report limits
claims about its exact additional reproduction steps.

## Strategy lifecycle and isolation

`dtos_strategy` is a bounded browser **session** cookie: no expiry or Max-Age,
at most 64 goal contexts and 3,800 encoded characters. Its namespace derives
from the authenticated account and existing session, and each row identifies
league plus franchise. It contains only an allowed selected goal, never assets,
protections, owners, counterparties or assessments. My Team and Trade use the
same source. Explicit neutral selection does not revive a migrated old goal.
Fresh navigation, reload and another tab reuse the cookie; a different login
session cannot consume it. Browser-session end is its lifetime boundary; this
does not claim durable cross-device preferences.

Temporary proposals keep the existing authorization binding and ownership
generation. Entering another league may clear an old proposal, but cannot erase
its separate goal. Same-league protections retain existing exact identities.
Other-league packages/protections cannot be restored under a different binding.
Storage failure or capacity limits receive an explicit message; goals are not
silently evicted to make room. Disclosure storage is bounded to 64 small
per-binding tab entries and has no roster data.

## Evidence admission and meaning

Starting contribution uses the existing optimal legal lineup when complete,
otherwise explicitly identified submitted starters. The largest contribution
is not a cross-position quality grade: position and slot demand differ. Reserve
evidence excludes IR/taxi, uses actual eligible owned players and separates
supported zero from unknown. Complete projection coverage does not guarantee
availability, high-quality depth or expendability. Absence exposure is explained
without an injury probability.

Projection generation, league, season, week and scoring context must be compatible.
The current published manifest can provide the selected week; otherwise old
points are withheld and the original source context remains available. Canonical
player values are unchanged; display formatting is separate. Market prices are
strategy-invariant. Picks receive no weekly projections.

Missing overall/dynasty aggregates, intrinsic tiers, liquidity, flexibility,
competitive-window inputs and probability models remain unavailable. Historical
prices are not replaced by current Market quotes; holdings are not manager
preferences. Retained FOIS grades remain NOT REVALIDATED and are not current
roster-strength evidence. No historical grades are regenerated.

| Affected category | Evidence boundary and disposition |
|---|---|
| Submitted/optimal current lineup | Reuses compatible published Sleeper player points and the existing legal optimizer; incompatible week/season/scoring and missing players stay unavailable. |
| Reserve depth | Recoverable admission defect corrected. Eligible covered/expected counts and known subtotal survive; incomplete evidence cannot receive a complete grade. |
| Positional quality/needs/surplus | Legal demand, contributions and reserve coverage are exposed. Intrinsic quality and validated removal-cost/expendability models are not published; counts do not supply them. |
| Market asset strength/key players | Existing prepared canonical prices are reused. Missing prices are not zero, and Market leaders are not weekly-production leaders. |
| Current production quality | Existing admitted production evidence is retained; current prices and overlapping projection horizons are not substitutes for missing production history. |
| Draft capital/range/liquidity | Exact inventory, ownership and compatible prepared quotes are connected. Range requires supported original-franchise draft-order evidence. Aggregate utility and liquidity remain unsupported. |
| Overall dynasty/window/future forecasts | Required approved aggregate inputs/models are absent; selected user strategy still overrides inferred direction. No replacement scalar or probability is invented. |
| Record/standing/Max PF/status | Existing source facts and accepted standings are connected. Missing record/Max PF/status stay unavailable; reconstructed standing retains separate provenance. |
| FOIS/history | Existing league-specific supported evidence is reused. Retained grades remain NOT REVALIDATED; missing history is not an automatic trade veto or a current roster-strength measure. |

## Storage and performance boundaries

No new permanent application data, database, migration, projection archive,
roster snapshot, historical standing series or paid infrastructure is added.
The only new retained intent is the bounded browser-session goal cookie, because
Sleeper does not supply a user's DTOS goal. It need not survive browser-session
end or application restart through a server database. Existing canonical stores
and bounded caches are reused. One bulk projection-view preparation serves the
roster; there are no per-player provider requests. Position summaries use the
already prepared optimizer output, not another projection/valuation engine.

## Validation and evidence boundaries

Focused tests cover partial/zero/missing depth, legal Superflex/IR/taxi exclusion,
actual publication rollover, incompatible season/scoring, explicit strategy and
Market invariance, nullable records/Max PF and account/league/franchise scope.
Rendered tests use real account/league middleware, product routers, A → B → A
fresh navigation, reload, a fresh tab, proposal cleanup, dossier returns, exact
acquired-pick Shop anchors, keyboard focus and DOM portrait/text geometry.

Responsive layouts include 320×432, 320×844, 375×667, 390×844 and desktop.
Source-backed local journeys separately use the captured Day Traders and Arkham
rosters and scoring through the actual canonical publisher. These are controlled
authenticated local fixtures, not authenticated production acceptance or
physical iPhone/Safari tests. Source captures were a bounded observation window,
not an atomic live snapshot. Missing Market/history in those fixtures is not
proof of a provider outage. Raw Sleeper parity is claimed only for previously
compared corresponding source values; no new universal parity claim is made.

Focused baseline modules: 138 passed under a 2 GiB container (9.36s). New
backend fixtures: 13 passed. The final authenticated rendered journey passed
(99.82s) across five viewports, two accounts and three synthetic leagues,
including explicit Back/Forward restoration; a
separate captured-source journey passed 10 views across both real league
configurations with no browser errors, horizontal overflow or portrait overlap.

Controlled pure HQ before/after observations (ms): Day cold 78.59 → 76.60,
Arkham cold 115.06 → 86.50; warm medians 0.308 → 0.397 and 0.298 → 0.354.
A new selected goal, which correctly requires a separate view calculation,
measured 78.35/87.17ms. These small samples are not a universal speed claim.
Local route medians were 10.72/10.45ms over 15 My Team requests per league,
versus audit 4.91/5.07ms over eight requests; the new route also prepares bulk
player projection views and actions. Dossier median 15.63ms (10), Shop HTML
4.42ms (10), builder HTML 2.06ms (10); workspace/search completion is excluded.
Browser click-to-networkidle median 749.75ms (10), including the browser's
roughly 500ms idle boundary. No production SLA is inferred.

The unchanged canonical release validator passed all ten gates together in
875.77s: committed/working/staged whitespace, compilation, Ruff, dependency
integrity, full unit/regression discovery (2,710 tests, 847.55s), route/OpenAPI
validation (261 registrations, zero duplicates, 239 paths), tracked HTTP smoke
and process cleanup. The documented disposable HTTP fixture passed 176 requests,
startup and graceful teardown. Release publication and production acceptance
identities will be reported only after those operations complete.

The ordinary, archive-warmed and combined-read application gates passed with
`memory.max=2,147,483,648`, no container restart and provider synchronization
disabled. Raw / effective cgroup peaks in bytes were respectively
1,502,195,712 / 1,426,419,712; 2,147,483,648 / 1,413,361,664; and
2,071,396,352 / 1,418,584,064. The raw archive peak reached the cap; effective
working set and raw file-cache-inclusive peaks are distinct measurements.
Initial local fixture preparations stopped on filesystem/headroom admission.
They were rerun after verified relocation of this task's disposable inputs;
result logs were preserved and neither admission nor memory limits changed.
Linux recovery/quiescence positive and negative checks and 141 retained-storage,
projection, import and maintenance tests passed under the same 2 GiB limit.

The first complete regression run found three issues: a prepared pick used
`year` rather than the renderer's assumed `season`; an existing parent-page
fixture gave the route and intelligence layer different projection contexts;
and a compatibility wording fixture inferred surplus from eight receivers.
The renderer now accepts the existing identity contracts and withholds unknown
identity actions. The projection fixture supplies one canonical context without
changing its numerical assertions. The wording test retains its positive
assertions over an explicitly admitted boundary, with a new unmocked regression
proving that quantity alone cannot establish complementary surplus. All 36
affected checks passed after correction. Failed logs are retained; no release
gate or source-admission rule was weakened.

## Scout independent live handoff

1. Verify deployed version/build/commit before testing. Day Traders is
   `1313066632158924800`; Arkham is `1319750579458686976`.
2. In Day Traders Trade builder select REBUILD. Open Arkham builder, select WIN
   NOW, then freshly navigate back to Day Traders builder. Expect REBUILD and
   no Arkham assets/protections. Repeat reload, Back/Forward, fresh tab and
   temporary proposal cleanup. Confirm My Team displays the same goal.
3. My Team: verify all owned IDs and Starter/Bench/IR/Taxi assignments against
   Sleeper. Use Roster shortcut, keyboard-open a player, then its My Team return.
   Expect the inventory still open. Compare source statuses without inferring
   missing injury evidence.
4. Verify starting contribution versus reserve evidence separately. For two
   strong QBs with an unknown QB3, the backup gap must remain explicit. Compare
   partial, complete and genuine-zero evidence; no count-only surplus claim.
5. Day Traders acquired 2027 Round 4, original rosters 3 and 7: verify separate
   original identity/current holder, dossier return and direct Shop anchor.
   Arkham acquired 2029 Round 1, originals 1 and 8: repeat independently.
6. Compare My Team record/PF standing with Home/League, preserving source
   cumulative PF/PA and current-position versus final-seed distinction.
7. Challenge controlled roster/status/Market/projection/pick generation changes
   and week rollover. An incompatible week must not show old points as current.
   Compare complete-evidence rank cohort wording with actual available teams.
8. Test all phone widths, short/tall views and desktop for overflow, portrait
   overlap, readable exact pick identities, accessible actions and focus.
9. Sample live Market, Calculator Balance, Shop/Trade For, protected assets,
   Preview/Keep Original/Adopt, Recommended/Next Five, Matchups, standings and
   retained FOIS disclosures. No actual trade or lineup mutation is needed.

Report expected versus actual, exact league/franchise/source context, steps,
counts/values, timings with boundaries, confirmed failures and unverified cases.
Distinguish repository, controlled fixture, raw source, authenticated live and
responsive Chromium evidence. Independent live acceptance remains Scout's work.

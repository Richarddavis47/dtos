# My Team status, session intent and contextual returns

Baseline: v1.21.34 / build 2134, `cfc6a3e9af54a9de311e4c465c00a56c0bbb7f2f`.
Release: v1.21.35 / build 2135. Current main matched the accepted pin.

## Corrections and evidence boundaries

Roster groups copied player dictionaries before `roster_overview` attached source
availability. Enrichment now runs before grouping, so core and other-position
cards share the same supported status. Existing injury-before-status precedence
is preserved, including an injury designation over a generic Active field.
Missing source status stays unavailable. The dossier separately identifies
reported source status rather than conflating no injury designation with Active.

Trade draft persistence wrote the tab-local selector into the shared cookie on
all edits. It now reads authoritative intent without writing it. Only explicit
strategy changes and the existing validated, one-time migration write shared
strategy. Focus, visible-document return, history restoration and ordinary
persistence/payload preparation reconcile the latest goal. No polling is added.
The current package/locks stay local; stale assessments retain prior context and
major drawback with a reevaluation action. Older pending requests are invalidated
through the existing cancellation/revision rules. Account/session/league/franchise
scoping and bounded browser-session lifetime remain unchanged.

The existing canonical dossier URL/`from_team` return contract is consolidated in
`contextual_player_url`; no navigation framework is introduced. Submitted,
optimal, horizon and bye-context links pass the validated current-league franchise,
relevant My Team section and supported player-projection week. The server admits
only known current-league teams and allowlisted return sections. The section
fragment reopens advanced evidence after bounded disclosure restoration. My Team
has no independent week selector; a dossier week does not mutate the active league
week. Existing primary roster and exact-pick returns remain.

The controlled TE fixture used `rec=5`, `rec=1` scoring, TE bonus coefficient .5,
with no explicit bonus statistic. Existing canonical league scoring produces 7.5,
but raw source-order replay only adds supplied stat fields and produced 5.00.
Available evidence does not prove Sleeper's displayed bonus synthesis in this
missing-field case. Exact replay is now unavailable/qualified; My Team and the
dossier display the canonical league-scored value with an explicit unverified
replay explanation. Canonical calculations, raw source stats, scoring settings
and Market values are unchanged. Explicit bonus fields retain the original
non-double-counted replay; missing evidence and supported zero remain distinct.
This is a controlled publication/display finding, not proven live incidence or
new raw Sleeper numerical parity. No player-projection model is introduced.

## Validation

Pinned-baseline rendered routes reproduced both P2 failures (eight failing
observations across authenticated controlled account/league journeys). A focused
status regression also reproduced the copy-order failure. Corrected route fixtures
cover QB Questionable, RB Active, WR IR, K Out, unknown status and conflicting
fields. Captured Day Traders/Arkham source facts were separately rendered through
actual middleware/routes at 320/375/390px, tall portrait and desktop; source
captures are a prior observation window, not current authenticated production.

TE publication tests cover missing/explicit bonus, different premiums, no premium,
non-TE, genuine zero, missing stats, stable reuse and material publication changes.
Actual My Team, dossier and Matchups routes share the canonical values. Rendered
journeys cover both strategy collision directions, partner and asset edits,
reload, account/league isolation, submitted/optimal/bye returns and phone geometry.
A separate retained-assessment browser test covers source context/drawback retention,
reevaluation, Balance, Preview and Adopt without cookie overwrites.

The unchanged canonical validator passed all ten gates in 944.53s, including
2,715 regression tests (915.60s), 261 method registrations with no duplicates,
239 OpenAPI paths, tracked HTTP startup/smoke/teardown and process cleanup.
Lifecycle and CI must pass before merge; deployment identity is reported only
after actual verification. Failed local fixture/test logs are retained; no gate is weakened.

## Storage and performance

No new permanent database, projection history, roster store, scoring engine,
tab-state store, polling system or paid infrastructure. Existing shared canonical
services and bounded session intent/disclosure state are reused. Status enrichment
moves before copying instead of adding another provider request. Source replay
qualification is a constant-time gate over existing evidence. Ordinary draft saves
no longer serialize/write a strategy cookie; reconciliation reads the same bounded
intent. No real Sleeper transaction, trade, roster or lineup change is needed.

## Scout independent live handoff

1. Verify version/build/commit first. Day Traders `1313066632158924800`, Arkham
   `1319750579458686976`: compare full roster status, injury precedence, unknown
   cases and same-page availability/dossier evidence against corresponding source.
2. Day Trade tab REBUILD → My Team second tab WIN NOW → old Trade partner-only
   edit → My Team reload: expect WIN NOW. Reverse it. Repeat asset/pick/protection
   edits, preview/adoption, proposal cleanup, reload, Back/Forward and fresh A→B→A.
   Expect no foreign package/lock/target transfer and no unrelated cookie write.
3. Keep a completed assessment, change goal in another tab, return: prior drawback
   and evidence stay visible with stale/not-revalidated qualification and a clear
   reevaluation action. Check pending old responses cannot become current.
4. Submitted, optimal/horizon and bye-context players: open dossier, verify selected
   week where supported, return to the correct My Team section/franchise. Repeat
   primary full-roster and exact-pick return/Shop anchors.
5. Controlled TE missing-bonus and explicit-bonus fixtures: compare underlying
   canonical values and display qualifications across My Team/dossier/Matchups.
   Do not call a fixture result a live Sleeper discrepancy without matching source.
6. 320/375/390px, short/tall portrait and desktop: readable known/unknown status,
   no portrait/name overlap or document overflow, visible stale warnings/actions,
   keyboard links/disclosures/focus. Responsive Chromium is not physical Safari.
7. Sample accepted depth, exact picks/Shop, standings, Market invariance, Calculator
   Balance, preview/Keep Original/Adopt, Shop/Trade For, explicit target switching,
   FOIS NOT REVALIDATED and historical evidence-week/freshness behavior.

Report expected/actual, exact league/franchise/week/source generation, steps,
values, timing boundaries, confirmed failures and unverified cases. Distinguish
repository, controlled fixtures, raw source, authenticated live and responsive
Chromium evidence. Independent live acceptance remains Scout's work.

Controlled warmed HQ medians over 30 calls (ms), baseline → correction: Day Traders: 0.177 → 0.165; Arkham: 0.152 → 0.143. Both versions share the prepared cache; first-observation timings are not comparable cold-start measurements. All 58 captured roster statuses (31 Day / 27 Arkham) survived grouping versus zero in the pinned pipeline. No production latency or raw source freshness claim follows from this fixture.

Ordinary, archive-warmed and combined-read application gates passed at
`memory.max=2,147,483,648`, with no restarts or summary errors. Raw/effective
cgroup peaks in bytes: ordinary 1479979008/1414967296; archive-warmed 2147483648/1421639680; combined-read 2147483648/1412263936. Archive and combined-read raw peaks reached the cap; raw file-cache-inclusive and effective peaks are distinct. Linux recovery/quiescence positive/negative checks and 141 tests passed. Initial archive fixture preparation stopped at the existing disk-headroom guard before the application gate; a disposable local container reused the installed Python/dependencies through read-only mounts to avoid duplicating the large VFS image. Full fixture sizes and every gate/admission/memory limit remained unchanged. Failed evidence was preserved; standard CI containers independently rerun all scenarios.

The missing-bonus TE actual-route HTML additionally passed 30 responsive render checks across five viewport configurations; the replay qualification fits the roster cards. This component render check supplements authenticated local journeys and does not establish authenticated live or physical Safari acceptance. No successful screenshots or DOM files were archived.

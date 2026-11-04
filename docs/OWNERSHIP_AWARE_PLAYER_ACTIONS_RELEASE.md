# Ownership-aware player actions · v1.21.14 / build 2114

## Reconciliation and reproduction

Current v1.21.12 dossier rendering scanned teams for an owner, defaulted to roster
ID 0, and chose Shop only when the player belonged to the active roster. Every
other case generated Trade For in both the headline and recommendation. A valid
unrostered fixture player had canonical Market 192, two Trade For links carrying
owner 0, and an HTTP 200 targeted entry page. Generation subsequently rejected the
missing owned asset. This reproduces the Slayton class without player-specific
logic or a permanent assertion about live prices.

Market rows already carried retained ownership, but rendered a missing owner as
Unrostered. Team HQ and shared summary cards link to dossiers rather than generating
transaction actions. Trade workspace pools already contained owned assets only,
and manual evaluation rejected a free agent as a missing league trade asset.
Pick dossier actions are separate and unchanged.

## Ownership and actions

`PlayerOwnershipIndex` prepares one request-scoped map from the existing accepted
league roster snapshot. It fetches nothing, changes no freshness policy, and has
no persistent cache. Complete current evidence distinguishes owned-by-me,
owned-by-other, free-agent and unknown. Missing roster lists, league roster-count
mismatch, unresolved player identity and conflicting membership are unknown rather
than free agents. A valid empty roster list is distinct from absent evidence.

Supported capabilities are View Player, Shop Asset for my player, and Trade For
for another manager's player when the active league franchise resolves. Free
agents show Free Agent / Unrostered and the absence of a trading counterparty.
Unknown evidence shows Ownership unavailable with a reason. Neither gets an
invented replacement CTA or empty action container. The shared presentation
renders dossier and selected Market actions; list/card labels and supporting
Market/player APIs use the same model. Live inspection no longer defaults
incomplete evidence to free agency.

Targeted GET links validate capabilities before opening the editor. Unsupported
players receive an explained HTTP 422 page with a Market link; generation returns
`player_action_unavailable`. A supplied owner is replaced with the actual current
owner for a valid target. Manual editing remains available and a free-agent
proposal is invalid; uncertain ownership also rejects evaluation. The prepared
workspace reuses its map across candidate validation rather than rebuilding it
per candidate. Exact picks retain their existing ownership/identity checks.

Current ownership overlays a retained price artifact independently. Market render
keys include the league ownership digest, so drops/acquisitions update labels and
capabilities without requiring a fresh price generation. Catalogue identity loss
also changes the capability generation; unresolved IDs reject direct entry. Canonical facts,
provider normalization, Market freshness/generation, strategy prices and
projections are unchanged. No schema, upstream access, worker or infrastructure
change is introduced.

## Final presentation correction

v1.21.13 shipped the ownership/action correction. A post-deploy probe caught the
optional ownership wrapping rule in an unused theme migration file. An added
unbroken franchise-name fixture reproduced page widths 1,427px (dossier) and
1,254px (Market) at phone sizes. v1.21.14 moves that rule into the rendered shared
theme and applies the dedicated label class to Market cards, action status and
Live Data ownership. Complete names remain inspectable. The rule does not apply
to structured table cells or change canonical data/actions. Phone and desktop
long-name cases now join the existing acceptance coverage.

## Validation

Deterministic coverage includes free-agent dossier and Market cards/detail/API,
my/opponent-owned players, actual-owner deep links, early API rejection, incomplete
and conflicting ownership, other→free→other/my transitions against a retained
price artifact, exact Market fact invariance, manual invalidity and untouched
pick entry behavior. Existing canonical fixtures cover McBride/Allen across
Market/dossier/Trade, projection availability and exact acquired pick identity.
Responsive Chromium covers 320/375/390 and desktop 1440: readable labels/actions,
keyboard focus, no empty action containers and no page-level horizontal overflow.
This does not represent physical iPhone/Safari testing.

Focused ownership/canonical/browser coverage passed 158 tests; final service,
manual-ownership and recent Trade coverage passed 117 tests. Final cache/identity,
browser and service coverage passed 33 tests. The ten-team, 300-player ownership
map plus all card capability lookups measured 0.392 ms p50 and 0.725 ms worst
across 100 controlled runs. Prepared fixture HTTP boundaries (five runs each)
measured p50/worst milliseconds: Market list 1.32/30.11, dossier
3.27/26.33, valid Trade For entry 1.04/1.52, free-agent rejection 1.00/1.21.
These are isolated fixture timings, not live production claims. Ownership
resolution adds zero upstream calls, database queries, persistent cache or workers.

The canonical release validator and unchanged Linux lifecycle/resource gates are
required before release. Final gate counts and production identity are reported
with the release handoff. Existing recent Trade discovery, performance reuse,
stale-intent protection, exact locks, cheaper repair, preview/adoption/reload and
technical identifier/evidence-table coverage remain required.

## Scout live acceptance

Test LIVE PRODUCTION v1.21.14 / build 2114. For Darius Slayton or another current
free agent, compare Market and dossier: canonical value remains available, league
status agrees and Trade For is absent. A safe direct Trade For path must explain
unavailability without inventing an owner or opening an empty editor. Do not
submit trades or mutate Sleeper.

For McBride or another opponent-owned player, verify actual owner and working
Trade For. For Bijan or another Richard-owned player, verify My Team, Shop and
absence of misleading Trade For. Compare canonical values/generation/freshness
across Market/dossier/Trade and verify projection availability remains truthful.
At 375/390 (also 320 where possible), inspect ownership/actions, technical
identifiers and locally scrolling readable evidence tables. Smoke Recommended
latency/result quality, Next Five, Shop, Trade For, Make It Cheaper, exact
protections and preview/adoption/reload.

Label LIVE PRODUCTION, RESPONSIVE CHROMIUM and PHYSICAL IPHONE/SAFARI distinctly.
Continue recording separately: cold Recommended around 24 seconds, Next Five
loading feedback below the viewport and incomplete physical Safari coverage.
No waiver/acquisition engine or unrelated performance change belongs to this release.

Post-deploy logs also showed a pre-existing Team Strength week-alignment rejection
(current fantasy week differs from prepared projection week); the same log was
observed on v1.21.12 before this work. Keep it separate for Main Chat.

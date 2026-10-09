# Phone-first front office — v1.21.20 / build 2120

## Audit and scope

The accepted baseline is v1.21.19, `7ab3852fd46b9e026c8c96b0bf073ada3205659a`.
DTOS already had a shared server-rendered theme and five-destination navigation.
The audit found navy rather than charcoal surfaces, duplicate palette definitions,
inconsistent disabled controls, gold/silver/bronze treatment on DTOS/FOIS ranks,
a dense Home overview, inline protection labels, unformatted derived Trade point
summaries, Balance options far below their action and Next Five feedback at the
bottom of the asset workspace.

The correction consolidates that existing system; it does not introduce a second
theme, UI framework or intelligence engine. Routes, identity/CSRF/ownership checks,
proposal restoration and explicit navigation precedence are unchanged.

## Shared presentation boundary

`src/ui/theme.py` owns palette, compatible legacy aliases, typography/spacing,
controls, cards, badge disclosures, focus, disabled/loading/error and modal
surfaces. Charcoal layers are `#141617`, `#1d2021`, `#262a2b`, `#303536`.
Green remains the interactive accent; canonical Market values retain blue,
and success/warning/error colors retain their meanings. Normal primary,
secondary and muted text on the elevated surface meet 4.5:1 contrast.

The existing `player_summary` supplies consistent QB/RB/WR/TE chips to My Team,
Market and player lists. The same chips appear in Trade asset selection.
Specialized technical-token wrapping and structured evidence-table sizing are
preserved. No global aggressive word-breaking rule is added to tables.

Home keeps the official record separate from DTOS strength, shows at most two
existing supported Attention items and discloses secondary assessment/activity.
Empty Attention remains inspectable under coverage rather than occupying the
first screen. Home's cached body includes the viewer roster and championship
identity; current Attention stays outside that cache.

## Factual badges

`src/ui/badges.py` admits official rank medals only when all current ranks are
unique integers reported by Sleeper. `settings.rank` is retained verbatim, never
derived from wins, points, playoff placement or DTOS rankings. Otherwise Current
Records remains explicitly unranked. Preseason/DTOS/FOIS ranks use neutral styling.

The trophy uses the active league's immediately preceding completed season,
the existing read-only season-cache sections and existing championship reconciler.
Missing, unresolved, inconsistent or wrong-season results omit the trophy. It is
not inferred from current standings. Home, League and Team HQ explain the season
and winners-bracket basis through native keyboard/touch disclosures.

You is tied to authenticated membership in that exact league/roster. Position
chips are identity labels. Protection disclosures show the actual exact player/
pick/required target/Shop anchor and explain the active constraint; no automatic
relaxation is added.

Movement (`↑2`/`↓1`) and completed streak (`W3`/`L2`) presentation contracts are
separate and require an explicit comparison period/result sequence. Current
prepared evidence does not admit historical standings movement or ordered
completed streaks, so these are intentionally omitted on live pages. No historical
reconstruction or guessed arrows are introduced.

Championship presentation reads at most two compact cached sections for a page,
not once per franchise/card. No provider calls, new SQL queries, cache, worker,
schema change or historical-storage mutation is introduced.

## Trade interaction corrections

Calculator Balance uses the unchanged engine. Results move next to Balance and
name the owned assets added/removed on each side, including exact acquired picks.
The separate DTOS assessment, drawback and counterparty context remain visible;
arithmetic improvement is not presented as guaranteed trade quality. Preview
does not mutate the offer; only Adopt does. New offer edits invalidate old status
and previews under the existing revision/request guards.

Protection labels stack above their fields. Derived Trade summary/horizon points
use a two-decimal presentation formatter (`5.4318000000001` → `5.43`), without
changing underlying evaluations, canonical prices, raw Sleeper values or exact
weekly technical evidence. The formatter is scoped to the Trade presentation
adapter, not all evidence.

Next Five shows an immediate live status beside the tapped button, with an honest
spinner and disabled controls. Feedback belongs to the offer revision/request;
new strategy/offer intent clears it and old requests cannot restore it. There are
no fake percentages or search-budget changes.

## Visual evidence and validation

Before/after captures use sanitized authenticated real-router fixtures, not live
customer accounts. Home, My Team, Trade, Calculator, League, Matchups, Market,
player dossier and FOIS were captured at 320/375/390 and 1280px, with both full-page
and viewport images. Representative 375px captures are retained below.

| Surface | v1.21.19 before | v1.21.20 after |
| --- | --- | --- |
| Home | [Before](visual/v1.21.20/home-before.png) | [After](visual/v1.21.20/home-after.png) |
| My Team | [Before](visual/v1.21.20/team-before.png) | [After](visual/v1.21.20/team-after.png) |
| Calculator | [Before](visual/v1.21.20/calculator-before.png) | [After](visual/v1.21.20/calculator-after.png) |
| Market | [Before](visual/v1.21.20/market-before.png) | [After](visual/v1.21.20/market-after.png) |

[Concrete balancing options](visual/v1.21.20/balancing-options.png) and [nearby Next Five feedback](visual/v1.21.20/next-five-loading.png) are also captured with the phone navigation overlay.

Focused tests cover real-router account/league isolation, shared theme/navigation/
touch targets, contrast and keyboard focus, evidence-gated badges, readable
protection controls, concrete balancing changes, Preview/Keep Original/Adopt,
exact locks, nearby Next Five feedback and stale-status cleanup. Existing Market,
projection, technical-table/token, Trade/navigation and resource gates remain
required. Responsive Chromium is not physical iPhone/Safari testing.

## Scout live handoff

On LIVE PRODUCTION v1.21.20/build 2120:

1. Compare Home, My Team, Trade, League, Market, Matchups, dossier and FOIS. Check
   charcoal/green controls, consistent hierarchy/spacing, position chips and You.
2. On League verify medals only for actual reported official standings; DTOS/
   preseason/FOIS ranks must be visually distinct. If a trophy is present, tap it
   and confirm the prior completed championship season/basis in that league.
   Missing movement/streak history must not create arrows or streak claims.
3. Build an unequal priced calculator offer and Balance. Options should be beside
   the action, name actual owned player/exact-pick changes and preserve the original
   until explicit Adopt. Check Preview/Keep Original/Adopt, exact player/acquired-
   pick locks and Shop/Trade For anchors. Edit afterward: old status/options clear.
4. Open protection controls: labels above inputs, full exact identities inspectable.
   Advanced derived point summaries should be readable, not floating-point tails.
   Market totals and strategy price invariance must remain unchanged.
5. Recommended → Next Five: immediate nearby Searching feedback, truthful disabled
   state and current results; no old completion feedback after changing intent.
6. Sample Recommended/Next Five, Shop, Trade For, Cheaper, explicit target switching,
   multi-asset reload, free-agent actions, Advanced Analysis and cross-page prices.
7. At 320/375/390px verify usable actions, feedback, focus, badge explanations,
   contained table scrolling, full technical identifiers and no page overflow or
   sticky element covering focused results. Also sample desktop.

Report expected versus actual. Distinguish LIVE PRODUCTION, RESPONSIVE CHROMIUM
and actual PHYSICAL IPHONE/SAFARI. Physical-device testing is not claimed here;
authenticated live interaction remains Scout acceptance if no session is available.
No real trades, lineup changes or Sleeper mutations.

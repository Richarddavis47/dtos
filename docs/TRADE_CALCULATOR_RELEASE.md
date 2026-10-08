# Trade Calculator & Smart Offer Editor — v1.21.17 / build 2117

## Existing capability and reused architecture

Reconciled clean main at c42f1a1a7e555b21fc98ab4dcc4848c27615a950 (v1.21.16).
Create Trade already had searchable owned players/picks, bilateral assessment,
exact protections, previews/adoption, session persistence and explicit-navigation
precedence. Recommended, Shop, Trade For and repair already used that workspace.
The missing pieces were a discoverable fast calculator, prominent immediate
Market verdict and a bounded arithmetic-balancing operation.

Calculator is a mode of the same component and browser state, not a parallel
editor or valuation system. `build_trade_workspace(market_only=True)` uses the
same canonical Market facts, normalized asset-pool adapters and exact pick
valuation while skipping FOIS and strategic preparation. The ordinary workspace
path remains unchanged. Requested balancing reuses those pinned facts when
building the normal contextual workspace and bilateral assessment. Advanced
analysis is an explicit call to the existing evaluator.

## Market arithmetic and evidence

`services/trade_calculator.py` reuses Decimal-based `market_balance`. The receiving
team is favored: sending 850 and receiving 730 favors the counterparty by 120
canonical Market points. Side A is the active manager; Side B is the counterparty.
Equal totals are approximately balanced. There is no invented tolerance,
fairness percentage, probability, package-price discount or strategy repricing.
The small client calculation performs exact decimal addition over the prepared
canonical numbers, so ordinary edits require no requests.

Missing prices remain unavailable. Each package keeps its missing identities,
known subtotal and full/partial/unavailable status. A partial offer has no
definitive verdict or forced balancing. Player generation, freshness, provider
coverage/confidence and retrieval/as-of evidence remain inspectable. Picks keep
year, round, original franchise, current owner, projected range and confidence.
No pick gets fabricated weekly points.

## Owned balancing, quality and exact constraints

At most 512 cheap constructions and eight bilateral assessments produce up to
four options. Additions go to the lower contributing package; swaps, removals
and bounded two-asset additions must strictly reduce the absolute canonical gap.
Candidates use only the selected teams' owned, priced, distinct assets. Players
and exact acquired picks are considered, with shortlist slots reserved for
available construction types. This is a bounded balancing operation, not another
full discovery search or a promise that an option exists.

Current ownership and exact pick legality are checked through the existing
validator. Exact outgoing player/pick protections, exclusions, incoming targets
and Shop anchors remain enforced. Conflicts name exact identities and offer an
explicit optional action; nothing is relaxed automatically. Unknown/free-agent
assets cannot create fake counterparties. Moved assets retained in a hypothetical
draft are labeled invalid and cannot be balanced.

The existing optimal-legal-lineup, capacity, strategy and counterparty assessment
is separate from the Market arithmetic. Poor stuffing and unresolved capacity
are retained as assessed near misses rather than promoted. An arithmetic
improvement with a strategic/counterparty drawback carries a caution; it is not
presented as a guaranteed attractive deal. Evidence unavailable for these
questions stays unavailable. Overlapping production horizons remain reconciled
by the existing evaluator, not summed by the calculator.

## Preview, integration and navigation

Balance Offer returns previews. Original/current offer stays unchanged until
Adopt. Preview shows asset changes, original/new totals, gap, reason and drawback.
Keep Original preserves it. A small bounded assessment summary accompanies a
restored preview; full candidate universes and explanation HTML are not persisted.

Workspace links and generated-card entry open the calculator with exact package
identities and compatible constraints. Advanced analysis receives the same
package. Existing binding-keyed session/history drafts, account/league/franchise
validation, CSRF, explicit target precedence and stale-response guards remain.
A changed Market fingerprint or a canonical publication during balancing rejects
mixed-generation output. No new cache, workers, schema/index or provider calls
are introduced. Existing bounded account/session/league/generation lineup reuse
has its original 32 MiB/8,192-entry/180-second limits.

## Controlled performance and phone checks

Five local runs with 12 teams, 384 players, 36 exact acquired picks and four
prepared projection weeks (synthetic, read-only, not a live SLA):

| Operation | p50 | Worst |
|---|---:|---:|
| Calculator asset readiness | 32 ms | 57 ms |
| Server canonical recalculation | 34 ms | 36 ms |
| Owned balancing | 222 ms | 318 ms |
| Existing advanced evaluation | 89 ms | 121 ms |
| Browser fixture readiness | 78 ms | 167 ms |
| Browser asset edit/recalculation | 1.4 ms | 2.3 ms |

Browser edits issued zero POSTs. Balancing assessed eight of 217 constructions,
read four projection weeks, created zero workers and retained zero candidate
results. The measured lineup memo retained 78,215 bytes. These measurements use
local fixtures; authenticated production timing is a separate Scout check.

Responsive Chromium covers 320/375/390px and desktop: prominent totals/verdict,
balance/advanced controls, stacked packages, full long pick identity, no page
horizontal overflow, named controls and native progressive disclosure. The
calculator omits the floating proposal tray so it cannot cover these results.
Physical iPhone/Safari was not tested.

## Validation and release acceptance

Focused tests cover canonical equality/favored direction, Decimal precision,
strategy invariance, missing pricing, owned additions/swaps, exact same-round
acquired picks and protections, anchors, quality/stuffing/capacity, generation
publication, authenticated/CSRF/franchise rejection, advanced integration,
preview/adoption/reload, explicit workflow switching and pending requests.
Existing navigation/account/league isolation, ownership, canonical facts,
discovery/performance, Cheaper, horizon/capital and responsive evidence-table
coverage remain required. Product browser CI includes the new suites.

The canonical release validator, full regression, authoritative Ruff,
compilation, committed/staged/worktree whitespace checks, route/API/startup,
canonical HTTP/browser and cleanup must pass. Ordinary, archive-warmed and
combined-read lifecycle plus recovery/quiescence run with unchanged 2 GiB limits.
The initial broad host run hit five existing Market memory-admission guards;
these must pass in the isolated authoritative 2 GiB environment before release.
No validation is bypassed. Gate/CI/deployment outcomes are reported with the
release rather than assumed in this document.

## Scout independent LIVE handoff

Test the deployed version/commit. Record expected versus actual and latency.

1. Open Trade Calculator; compare a simple 1-for-1. Verify which manager receives
   more Market value, individual prices, both totals and numerical gap.
2. Add/remove several players and exact acquired picks; distinguish two owned
   picks with the same year/round and different original franchises.
3. Preview a player addition and exact-pick addition; verify owned assets,
   correct gap direction, original/new totals and separate major drawback.
4. Keep Original, preview again, Adopt, reload; verify only adoption changes
   the current package. Protect a player and one acquired pick; verify the other
   same-round pick remains eligible and no lock is automatically relaxed.
5. Change strategy; Market prices/verdict must remain identical. Review a useful
   strategic overpay: it must remain a Market overpay.
6. Open a generated/adopted trade in Calculator, then Advanced DTOS analysis;
   verify exact assets, owner, locks and required targets survive.
7. Sample missing-price and invalid/moved/free-agent ownership cases: no zero,
   fake partner, definitive partial verdict or forced balancing.
8. Test preview/reload, new explicit target selection and navigation with pending
   work. Old offers must not replace newer intent; genuine identity errors stay
   blocked. Do not cross account boundaries or submit real trades.
9. Check 320/375/390 responsive Chromium: totals/verdict, balancing and protection
   controls, long pick identity, readable disclosures, no page overflow or overlay.
10. Smoke Recommended/Next Five diversity, Shop/Trade For, Make It Cheaper, exact
    protections, explicit target navigation, free-agent actions and canonical
    Market/dossier/Trade price consistency.

Distinguish LIVE PRODUCTION, RESPONSIVE CHROMIUM and PHYSICAL IPHONE/SAFARI.
Authenticated live calculator acceptance may be unavailable to Codex; Scout
independently performs it without another access mechanism. Keep existing cold
Recommended latency, Next Five feedback position and incomplete physical-device
coverage separate. No unrelated Product Integrity workstream is included.

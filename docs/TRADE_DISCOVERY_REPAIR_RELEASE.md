# Trade discovery + repair reliability — v1.21.7 / build 2107

## Current-main reconciliation and findings

The work starts from authoritative main `6042843c35c85856c7bf3f7509cdd66b5008873f`
(v1.21.6). Main was fetched again during implementation and has no intervening
changes. The v1.21.4 capital veto is already fixed; it is not reimplemented here.
Strategy still cannot change a canonical price or turn a pick into weekly points.

| Workflow | Remaining cause in current code | Classification and correction |
| --- | --- | --- |
| Recommended | Six theses, three packages per thesis; filters applied after the small search. Position opportunities miss consolidation and capital constructions. | Search-bound/over-filtering: progressive bounded expansion, actual package families and post-evaluation diversity. |
| Shop player / draft capital | Only one nearest construction per six shapes; missing supported returns or projections can also legitimately prevent results. | Search-bound plus genuine evidence/no-trade cases: wider bounded packages, optional partner, anchor preserved. |
| Trade For | One nearest package per shape can miss credible ways to acquire the same target. | Search-bound: more candidates and varied package shapes, actual owner and target fixed. |
| Adjust / alternatives | The base generator was called without a target and therefore generated zero base constructions; local additions/replacements were the only paths. Ambiguous singular pick commands could lock every pick. | Bug: generate around exact original targets; exact selected locks; evaluated cheaper/younger packages. |
| Counterparty | Missing history was already soft context. Missing direction could leave a capital trade unresolved even with a concrete benefit; depth gains were not consistently recognized. | Evidence/over-filtering: supported production, capital or coverage stories with disclosed costs and unconfirmed intent; no invented tendencies. |
| Future / Sell High | Enabled tags lacked the evidence to qualify. | Draft Capital uses observed priced net capital, not long-term utility. Sell High is disabled and returns an unsupported-requirement explanation before evaluation. |

The retained two-team capital fixture already returned Recommended, Shop,
Trade For, adjustments and alternatives on unchanged main. Thus Scout's sampled
empty results do not establish one universal defect. Live-like deterministic
fixtures reproduce the relevant search, lock, missing-direction/history,
missing-projection and bad-counterparty classes without league-specific code.
Public read-only production context was inspected privately. Scout's exact
submitted packages and authenticated generation responses were unavailable for
an exact production replay; no claim is made that every Dan failure had one cause.

## Search and evidence contract

Search phases retain bounded type/position-diverse pools of 12, 18 and 24 assets,
and 1, 4 and 8 Market-nearest constructions per shape. Expanded phases add
1-for-2 and 3-for-1 shapes. Price proximity proposes candidates; the shared
bilateral evaluator decides their quality. Full evaluation budgets are 180 for
Recommended, 240 for targeted search, and 160 for repair/alternatives. A request
pins its canonical projection generation, caches week reads, deduplicates exact
packages and rejects a changed evidence boundary.

Recommended expands only if it lacks five diverse eligible ideas after strategy,
category and session filters. Fewer than five are shown when that is all that
qualifies. Families use primary target, primary outgoing asset and counterparty;
secondary variants remain in detail. Show Next 5 excludes prior families only
in the page session, with a validated 256-family bound; it is not a quota.

Ordering uses distinct recommendation, strategy-conditioned unique-week
production/priced capital, plausibility, confidence, package quality and Market
fairness evidence. Horizons are not added together. Shop's position preference
constrains returned package content; its supported lineup contribution is still
separate. Age is descriptive and is not a longevity or future-production model.

Ownership, duplicate assets, pick identity, capacity and explicit locks remain
hard constraints. Missing required Market/lineup/capital/active-strategy evidence
remains unavailable. Material production gains can justify disclosed reserve
costs; supported depth gains can be optional. Both sides retain benefit and cost
assessment. Severe Market losses and materially losing weak-signal trades remain
out. Unknown counterparty direction may permit an observed meaningful production
or capital story at bounded Market terms; direction is disclosed as unconfirmed.
Missing history reduces confidence to Medium rather than vetoing the trade.
No acceptance probability or guarantee is produced.

Funnel diagnostics include eligible partners, pools, generated/pruned, evaluated,
hard invalid, missing evidence, counterparty limited, strategically rejected,
filtered, eligible, ranked and displayed. Technical details are expandable.
Near misses contain actual evaluated proposals and rule blockers; target context
is never presented as an established acquisition path. Conflicting locks name
exact identities and offer an optional constraint relaxation. No lock is relaxed
automatically.

## Acceptance and validation

`tests/test_trade_discovery_repair.py` covers the requested A–Q acceptance classes:
diverse first/next pages, fewer than five, Shop player/pick across all teams and
optional partner, actual Trade For owner and varied shapes, cheaper preview,
protected player and one exact pick with other picks usable, younger return,
missing history, bad counterparty, unsupported goal, actual near miss and
impossible locks. Further tests cover progressive expansion, unknown direction,
exact acquired-pick fields and unique supported weeks. Existing capital fixtures
retain all six package families, three strategies, five labels, materiality and
missing-evidence semantics.

Browser contracts use responsive Chromium at 390px and desktop widths. They
verify the original remains unchanged until explicit adoption, Keep Original,
editable handoff, navigation/context isolation and phone readability. This is
not physical iPhone or Safari testing.

Final release-gate results are recorded after execution below. No merge or
deployment is part of this candidate-preparation task.

## Scout acceptance handoff

**What changed:** broader bounded package search, diverse recommendation pages,
exact repair constraints, preview/adopt/keep-original, explicit search outcomes,
actual evaluated near misses and clearer bilateral costs/history limitations.

**What should now work / exact live checks:**

1. Day Traders → Recommended: choose each strategy; expect ranked varied credible
   ideas when supported, fewer than five when appropriate. Show Next 5 should
   exclude prior top-level families; related variants belong inside detail.
2. Shop a currently owned player, then an exact acquired pick: leave partner
   optional, then select one. Every returned package must retain that exact
   outgoing asset; additional players/picks may appear.
3. Shop goals: test Draft Capital and Position Need against an appropriate owned
   asset. Unsupported requirements must be explained; disabled Sell High must
   not run an expensive empty search. Youth uses supported ages/capital only.
4. Trade For an actually owned target: every result must keep the target and
   its real owner. Inspect differing package shapes when credible; no offer is
   required for an impossible target or unsupported evidence.
5. Open a current offer → Make It Cheaper: outgoing canonical Market cost must
   actually decrease, with the required target/Shop anchor and locks retained.
   Preview must preserve original; Keep Original must preserve it; Adopt must
   be the action that changes it.
6. Keep a specific player; protect one exact pick: selected IDs must never be
   outgoing. Other picks remain usable. Try an impossible Shop lock; expect an
   exact conflict and optional relaxation, never automatic relaxation.
7. Younger Return: age must move younger where supported; Trade For's target
   remains fixed. Test Add Pick, Get Player Back, position controls and alternate
   construction against the current proposal rather than a fresh unrelated offer.
8. Sample Dan: missing manager history alone must show a limitation rather than
   veto. Inspect Market, optimal lineup, capital, coverage and supported direction
   separately. Bad bilateral terms still fail; no likely-acceptance claim appears.
9. If empty: expand evaluated near misses and technical details. Distinguish
   required missing evidence, unsupported goal, specific constraints and no
   credible result within the budget. Generic target context is not an offer.
10. Recheck the v1.21.6 player↔pick examples across all strategies. Prices and exact
    year/round/original franchise/current owner/range/confidence must stay intact.

**Intentionally unchanged:** canonical valuation, pick projections (none), legal
constraints, league mutation/submission, independent calculator, storage and
sparse-history work. No broad Trade Center or website redesign.

**Known limits:** finite search is not exhaustive and promises neither five nor
50 trades; unknown projections/prices still block; unknown manager intent is not
inferred; age and priced capital are not long-term utility forecasts; exact live
Scout packages still need independent production acceptance after an authorized
release.

**Phone items:** visible label/package/strategy, why it helps, major drawback,
counterparty summary and primary preview/adopt action. Ensure long pick identity,
expanded technical evidence and preview controls do not overflow or block actions.

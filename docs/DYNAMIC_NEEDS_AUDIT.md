# Dynamic roster diagnostics — baseline and implementation contract

Baseline: v1.21.48/build 2148, 76a0883f5e14285fb2234742b9dfa4ae95b5a720. Remote main and live readiness reconciled October 15, 2026. Supplied product definitions and accepted source contracts apply; separate private Blueprint/concept files unavailable locally are not claimed inspected.

## Baseline evidence before implementation

| Producer / consumer | Actual definition / input | Disposition |
|---|---|---|
| Decision Engine depth_analyzer | Fixed totals QB3/RB7/WR9/TE4; submitted starter targets 1/2/3/1; 55 coverage +35 starter +10 base −20 injury exposure | Replace count scoring with supported legal-lineup diagnostics; retain counts as facts only |
| My Team / Team HQ roster_evidence | Pinned Sleeper projections, actual versus optimal lineup, reserve coverage; surplus explicitly unavailable | Preserve correct boundaries; connect real removal/replacement evidence |
| Front Office _needs / _surpluses | Position depth score <55; surplus deliberately empty | Remove legacy count-derived need assumption; only admitted diagnostic surplus may participate |
| League Intelligence _need / _surplus | Weighted room score, contender/future/floor; liquidity ≥55, composite surplus ≥62; pick count ≥average+2 | Current canonical room scores are unavailable, so the legacy player formula is not established live universal surplus. Remove incompatible duplicate definitions and count-only pick surplus |
| Recommended discovery | Supported incoming player improves eligible actual optimal slot; bounded candidates; final bilateral evaluator | Preserve; add contextual diagnostics only, no hard uncertainty veto |
| Trade / Adjust / Trade For / Shop | Canonical ownership, Market, legal multi-week pre/post lineup, reserve coverage, package shape and capacity | Preserve gates and package-level math; expose shared contextual pre/post diagnostics and donor replacement cost |
| Home opportunities | Projection of existing completed discovery; no automatic search | Keep fast read path; consume package-specific diagnostics from evaluation only |
| Intelligence caches | Snapshot generation and view strategy; roster identity can depend on preparation | Add semantic roster/status/lineup fingerprint; no retrieval-clock-only invalidation |

## Narrow shared architecture

Extend the existing intelligence layer with a disposable, bounded diagnostic read model over one admitted league/week projection publication. Use the existing optimal legal-lineup solver and bounded lineup memo. No Market input changes player production or need/surplus facts.

Each position reports current optimal participation, supported reserve coverage, remove-one lineup loss, effect on a separately optimized disjoint reserve lineup, and add-one opportunity from actual peer reference assets. Reference assets are observed league context, not assumed available offers. No synthetic player or projection is created. Strict removal invariance plus a supported benefit to another roster establishes conditional current-week expendability; being a starter or a useful reserve remains strength rather than surplus. Missing projections/status/slot support withhold dependent conclusions. No forced positional label or numerical confidence model.

Use league-relative observed starter/replacement distributions rather than fixed player-count targets. Explicit strategy changes interpretation, not projections, Market or lineup arithmetic. A rebuilding production gap is not advice to buy an aging starter. Longer-term utility/availability remains unavailable unless supported separately.

Package diagnostics apply all players at once and disclose capacity/forced-cut evidence from the existing evaluator. They must not sum remove-one effects or individual positional add-one maxima. Existing multi-week production/package gates remain authoritative; the new current-week view cannot certify future resilience or change Market fairness.

## Expected change and risk

Replace count-led need context with explainable supported needs, strength and conditional surplus. Shop/Trade For/Recommended/Adjust share the same bilateral evidence; uncertainty alone is not a partner veto. No new Home panel. Risk is extra lineup solving, bounded by existing memo plus byte/entry-capped diagnostic results; measure cold/warm and candidate-search costs before release. No permanent diagnostic archive, schema migration, backfill, paid service, new valuation/projection model or FOIS regeneration.

Controlled failing baseline and final edge/consumer/browser/performance results are retained in .validation/dynamic-needs. The former universal-surplus hypothesis must be distinguished from this baseline's actual missing/legacy diagnostics.

## Implemented contract — v1.21.49 / build 2149

The fixed count-depth score is removed rather than relabeled. `TeamDecision.diagnostics`, My Team/Team HQ positional evidence, League/Front Office contexts and bilateral Trade evaluations share `roster_diagnostics`. No numeric need/confidence scale is invented. Market, legal-lineup, multi-week production, package quality, exact ownership, capacity and FOIS gates remain separate.

- Starter improvement: an actual peer reference can improve the legal assignment or cover an unsupported required slot. Reference is closest to the observed peer starter median, never a synthetic player or assumed offer.
- Quality/depth need: supported legal replacements project below observed peer reserve context. Resilience need: removing a current starter leaves unsupported legal slots. Flex/Superflex replacement can cross positions; a missing same-position bench player alone is not a need.
- Strength: supported starters compare favorably with observed league reference; no sale is implied.
- Conditional expendable depth: removing that exact asset preserves both the optimal lineup and a newly optimized disjoint reserve assignment, and the asset improves an observed recipient lineup. Candidate scenarios cannot be summed or applied independently to a package.
- Uncertain: missing/incompatible projection, season/week/scoring, uncertain status or unavailable source coverage prevents a dependable conclusion. Genuine zero stays supported. IR/taxi/known out/bye restrictions are not usable depth; submitted Sleeper assignments remain separate.
- Strategy is interpreted through explicit selection, then a generation-matched canonical default. REBUILD current-production gaps do not become instructions to buy aging starters. Long-term quality/contract trajectories are not invented.

All outgoing and incoming players move together for package diagnostics. Current post-package starters and reserves are reassigned; existing full multi-week pre/post and forced-cut assessment stays authoritative. A package requiring unresolved cuts is partial, not an executable complete roster. Received picks remain capital, never projected production.

Canonical package pre/post projection totals are reused directly from the admitted horizon evaluator. Availability-qualified depth has separate fields and labels; if its eligible-player view differs, diagnostic comparison is partial rather than relabeling or changing the canonical projection. A controlled known-Out/source-projection discrepancy reproduces this boundary.

Shop/Recommended retain existing qualification and primary ranking; supported need fit is a contextual tie-break, with no unknown-label veto. Counterparty replacement context is disclosed, not an acceptance prediction. Home reads completed discovery/evaluation output without a new diagnostic panel or automatic diagnostic search.

Cache uses the existing bounded lineup memo plus a disposable 12-entry/2 MiB/180-second result store. Identity includes semantic league/ownership, status/eligibility, slots, projection and scoring inputs; retrieval clocks and prices do not alter diagnostic math. Strategy interpretation is view-local. Diagnostic expansion beyond 2,048 eligible league players or 14 starting slots is explicitly unavailable rather than unbounded; these are resource safeguards, not roster targets or surplus calibration. No new permanent file/database/schema or provider polling.

## Evidence and limits

The before-change producer test returned RB depth **100** for eight unprojected RBs. The corrected contract withholds that grade. Intermediate integration failures exposed legacy numeric-depth assumptions; those callers now consume admitted diagnostics or unavailable states rather than substitute zero.

Two public league-settings GETs on October 15 produced `tests/fixtures/dynamic_league_settings.json`. Day Traders has a dedicated TE and three FLEX slots; Arkham has WRRB_FLEX/REC_FLEX and no dedicated TE. Both have Superflex. Tests publish controlled Sleeper-shaped statistics under these actual scoring/lineup settings; this is not authenticated live roster/projection parity.

Controlled ten-roster/180-player measurements: cold diagnostic roughly 445 ms Day / 592 ms Arkham, warm median below 1 ms. Explicit genuine small-fixture discovery roughly 660 ms; Home warm median roughly 3.4 ms. Two hundred settled reads and 100 diagnostic calls preserved nine files / 575,334 bytes. These are local OS-warm observations, not a production SLA. Final detailed tests, resource gates and deployment evidence are reported in the release task report.

## Scout independent acceptance

1. Replay eight unprojected RBs and the ten-team RB-heavy uniform league: no count grade or universal surplus. Missing evidence stays uncertain, not weakness/zero.
2. Three elite Superflex QBs remain strength with meaningful reserve protection. Two usable QBs without a legal replacement show resilience risk; QB/RB/WR/TE legal substitutions must be respected.
3. Remove an equal starter/only backup: promoting the backup must not count it twice. Compare exact remove-one effects and new disjoint reserves. For packages move all players together, retain cut/capacity qualifications and never sum individual scenarios.
4. Test top-heavy poor reserves, interchangeable TEs, elite TE/weak reserve, shallow/deep benches, injured/out/bye/IR/taxi, unknown projection, genuine zero and missing Market evidence. Separate current weekly utility from long-term quality.
5. Explicit WIN NOW/REBUILD/RETOOL changes interpretation while Market/projection/lineup math remains invariant. REBUILD production gaps cannot prescribe aging starters. Change scoring, ownership, availability, slot count, peer concentration and source publication; cache/view identity must change. Retrieval-only churn must not.
6. My Team and opponent Team HQ must match Trade facts for the same admitted source/strategy. Shop, Trade For, Recommended and Adjust retain exact assets, protections, bilateral benefit and capacity/Market gates. Supported need fit does not mean willingness; uncertainty does not exclude partners. Home reason is from the same package evaluation with no new render-time discovery.
7. Independently inspect authenticated Day/Arkham data and authority. Matching local roster IDs cannot cross leagues/accounts. Canonical price/projection parity, Home News, history and FOIS RETAINED / NOT REVALIDATED remain regression contracts.
8. At 320/375/390, short/tall portrait and desktop: human-readable primary conclusions, expandable calculations, keyboard focus and no document overflow. No new Home panel. Separate fixture/source tests, Codex-hosted Chromium, independent signed-in production and physical iPhone/Safari.

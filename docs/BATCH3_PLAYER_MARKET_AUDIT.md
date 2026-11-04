# Batch 3 — Player / Market intelligence audit and implementation ledger

Baseline: v1.16.1 / 1601, `055763b1527d73d0e1902fa87912d33553703a39`.
Candidate: v1.17.0 (minor intelligence release, following v1.16.0's numbering).
Status: implementation in progress; no release or production proof claimed.

## Verified pre-change pipeline

| Boundary | Current input / formula | Proven problem / required migration |
| --- | --- | --- |
| Asset Intelligence `players/value_models.py` | Dynasty: 30% positional age, 20% NFL-team proxy, 50% neutral baseline, league adjustment; bounded 25–72 on 0–100 scale. Redraft: 45% team, 35% designation, 20% neutral. | Production/usage/contract/projection absence is asserted statically. Canonical production must reach this shared boundary before calibration. League adjustment is embedded in what other consumers call intrinsic/global. |
| Player Value Projection `engine.py` | Active franchise player reports; historical adjustment; intrinsic displayed as 90% history-adjusted signal + 10% weekly points ×35. Calibrated value separately omits that forward adjustment. | Missing weekly projection is coerced to zero and reduces displayed intrinsic. Multiple meanings of intrinsic/calibrated values. |
| Player Value Projection rank | Counts better calibrated values among same-position active-roster reports; assigns that count to BOTH overall and dynasty rank. | Roster positional comparison is not global overall or global positional rank. Missing projection also receives a fabricated weekly rank. |
| Production registry | Legacy player dictionaries `recent_points`, `fantasy_points_history`, averages. | Does not consume retained global game facts; `or` discards valid zero averages. |
| `services/global_evidence.py` | Bounded read-only selected-season, league-scored production, usage, schedule, availability, explicit knowledge boundary. | Available API facade but not yet shared input for bulk intelligence. Repeated per-player storage reads are not an acceptable universe preparation design. |
| ValuationUniverse | Global relevant catalog merged with roster enrichment; intrinsic from raw legacy override or Asset Intelligence; calibration-state multiplier; contender/rebuilder formulas separate from dossier. | Needs one canonical player assessment and explicit global versus format-adjusted scope; owner/team fit must not affect global truth. |
| Market Intelligence | Provider normalization and consensus, then gap versus report's 0–100 score. | Audit scale mismatch against normalized 0–1000 consensus; do not retune weights to hide it. |
| `valuation/calibration.py` | Market weight confidence/100 clamped 35–75%; tiers explicit value boundaries, not equal rank buckets. | Preserve until systematic calibration establishes a reason to change; document participation and missing evidence. |
| Intelligence context cache | League/roster, Brain, projection, market and scoped intelligence generations. | Global production publication is not yet a dependency. New prepared evidence must invalidate coherently, not use request-time raw scans. |

## Implementation order

1. Pure canonical evidence-to-production/usage adapters, explicit season and sample
   boundaries, no storage/provider work in the adapter.
2. Bounded shared preparation, semantic generation identity and current versus
   historical contexts. Reuse global facts; derive league scoring without storing
   private per-league global copies.
3. Shared player model and explicit rank universe, deterministic tie/unscorable
   behavior; migrate dossier/Market/Team HQ/Trade adapters coherently.
4. Provider scale/format/availability audit, controlled calibration and sensitivity
   evidence. No name-specific or Day Traders-specific adjustments.
5. Compact methodology-aware history/trend/reason contracts, historical no-hindsight
   tests, real-source panel and storage/performance proof.
6. One final policy-required comprehensive sequence and production acceptance.

## Preserved boundaries

- Batch 1 mechanics, Batch 2 global evidence/scoring/identity and bounded storage.
- Admitted Market replacement warming and atomic publication; unadmitted replacement
  may continue serving complete last-valid state.
- Contracts/routes/snaps remain unconnected unless an approved source proves them.
- No inferred historical publication dates, no current evidence in historical process.
- No FOIS/pick redesign or Batches 4–7; no Current Visual/DINS/Mirror.
- No weight changes yet; no live player values or ranks have been measured in this audit.

## Focused implementation evidence (not release acceptance)

- Canonical production adapter: distinct current/previous seasons, observed game
  order, incomplete scoring not zero/partial-window average, finite numbers,
  sample-aware production trend. No provider/SQL work in the consumer adapter.
- Global production stream: explicit relevant-player IDs, at most two seasons,
  128-ID query chunks in one read transaction. Published-only, dual temporal
  boundaries and corrected revisions match the existing canonical read contract.
  A 500-player fixture covers chunking without per-player database connections.
- Background Sleeper sync prepares compact production windows before valuation;
  dossier value profiles consume the prepared state. Semantic production identity
  participates in the Intelligence context cache key. No global raw fact copy is
  stored per league. Broader shared model/consumer migration is still pending.
- Legacy average compatibility now preserves an actual zero season average.
- Market gap scale defect corrected using existing `normalize_internal`: legacy
  0–100 report scores are converted before comparison with normalized 0–1000
  consensus. This is a unit correction, not a weighting change.
- Dossier Market consensus no longer passes through the default 0–100 clamp:
  the immutable assessment contract declares its scale explicitly (default 100,
  provider consensus 1000); the displayed scale is disclosed. A focused 812-point
  case proves preservation without changing other assessment scales.
- ValuationUniverse and Brain carry the same prepared production context; the
  current-production layer cannot prefer a stale legacy player dictionary value.
  Brain coverage no longer infers historical facts from an intrinsic number or
  projection facts from a modeled future value. Actual zero projections qualify
  as evidence; absence does not.
- Asset Intelligence receives pinned production/projection in its context rather
  than claiming those feeds are globally absent. Canonical evidence is disclosed
  separately from the still-legacy numeric proxy. Completing valuation calibration
  is required before release; this is not represented as a finished player model.
- Existing Brain/valuation integration suite: 31 passed after evidence plumbing.
  Focused prepared-evidence + Asset Intelligence suite: 12 passed after the latest
  context extension. Lint is green. No comprehensive gate, commit, push or deploy.
- Focused production/stream/facade/player-value tests: 35 passed. Market tests:
  16 passed. Further source-boundary tests continue; comprehensive gates not run.

Remaining: shared valuation/profile migration (including obsolete report text),
global/league rank scopes and all consumers, provider/format reconciliation,
methodology calibration and outlier explanations, version-aware value/rank/tier
history, real-source panel, performance/storage and full production acceptance.

## Rank and Market reconciliation — current focused findings

- The rank primitive now declares its comparison scope, value basis, population,
  scored population, position and deterministic semantic generation. Equal values
  use canonical identity as a stable ordinal tie break. Missing evidence receives
  no rank; real zero remains ranked. Dossier legacy ranks are explicitly labelled
  roster positional comparisons; overall rank now compares the entire roster.
- The prepared Brain carries separate intrinsic, Market and league-adjusted rank
  records. Ownership changes and roster-provided value overrides do not affect
  catalog-based intrinsic rank. Superflex adjustment is separate from intrinsic.
- **Important unresolved production boundary:** `relevant_players/service.py`
  filters both catalog and provider rows using league ownership/history plus the
  top 150 remaining free agents. Thus the prepared production universe is NOT the
  complete global player universe. Filtered ranks are explicitly labelled
  `league_universe`, never `global`. Global reference preparation must occur
  before this filter, retaining bounded comparison results rather than another
  whole live catalog. This also affects provider percentile normalization:
  recomputing percentiles after league filtering can change identical public
  player prices between leagues. A pre-filter shared normalization/reference
  boundary remains required before release.
- Missing weekly projections previously subtracted 10% from dossier intrinsic.
  Available-component weight normalization now omits missing components while
  retaining the existing relative weights. Actual zero retains its full weight.
  Contender/rebuilder blends use the same rule. This fixes missingness, but does
  not resolve the remaining distinction between dossier and universe formulas.
- Unsupported provider normalization previously supplied numeric zero. Such raw
  quotes now remain disclosed but cannot participate in consensus or its range,
  cannot be recorded as normalized history, and cannot make Market look available.
  The consensus boundary additionally rejects explicit unsupported normalization
  even if a caller marks the quote available.
- Current formulas confirm a calibration limitation: canonical production and
  usage have zero numeric impact in the legacy intrinsic model; age/team proxies
  therefore dominate its limited spread. Calibration may weight Market up to 75%.
  Changing provider weights alone would hide, not correct, the weak intrinsic
  evidence model. No player-specific override or new arbitrary weight was added.

Focused results in this continuation: valuation/rank/player integration 46 passed;
prepared-rank tests 5 plus primitive-rank tests 5 passed; Market and projection
missingness/player-profile tests 39 passed. Ruff passed for the changed boundaries.
These are focused proofs, NOT complete Batch 3 or release acceptance. No live
Daniels result, full calibration panel, release, deployment, or restart claimed.

### Pre-filter normalization correction

Sleeper background synchronization now prepares scalar normalization references
before relevance filtering. Existing provider rows retain their own scalar,
normalization version, population size and deterministic reference identity—not
another full population. Cached consensus, universe provider disclosure and Market
quotes reuse matching references; confidence/freshness still use current evidence.
Raw-value/version changes cannot reuse a stale reference. Two different league
subsets reproduce the same full-population result. Repeated unchanged preparation
is identical. This resolves the identified percentile-filter issue for newly
prepared snapshots; full global rank/model preparation remains unfinished.

Zero provider confidence no longer becomes the default 70. The consensus also
rejects zero-confidence participation rather than granting a minimum weight and
45 confidence from self-agreement/coverage alone. Raw observations remain upstream.
The valuation/normalization/universe focused set passes 40 tests after correction.

Running calibration tests independently exposed existing package import cycles
through Trade/Front Office `intelligence.league_scope` imports. Deferring those
two helper imports until their evaluation functions run resolves initialization
order without changing helper logic or authorization. Fresh-process checks cover
both public import orders. The initial focused failures are retained here; they
were corrected, not bypassed with a test-order change.

Latest prepared-rank set: 6 passed, including retired players with a legacy numeric
override remaining unranked in active intrinsic rankings.

### Pre-filter global rank preparation

The global comparison boundary is now implemented using streaming evaluations
before relevance filtering. Only rank inputs/results are retained; after filtering,
non-member results are discarded while full-universe rank identity/population is
preserved. Brain input identity includes the global rank generation. Dossier labels
global intrinsic, global Market, league-adjusted and roster comparisons separately;
missing global preparation is unavailable, never promoted from a roster rank.

These remain ranks of the disclosed existing methodology, not a claim that its
pending intrinsic calibration is complete. The old filtering-only finding above
describes the defect motivating this boundary, not the current implementation.
Focused rank/reference/UI guard set: 21 passed. A synthetic 2,000-player preparation
took 0.590 seconds and produced 2,067,512 compact serialized bytes BEFORE member
pruning. This is a cheap scale check, not Linux/production memory acceptance.

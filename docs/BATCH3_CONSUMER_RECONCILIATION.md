# Batch 3 — Market and consumer reconciliation ledger

Status: CLOSED — bounded active Player/Market semantic consumer audit. This is not release or production acceptance. No Batch 4.

## Field-level active-consumer contracts (final audit in progress)

These rows classify the inspected runtime paths, not hypothetical replacement APIs.
An unavailable scalar has no implied numeric unit and must not acquire one from
another evidence dimension. Earlier pending notes below are retained audit history;
the closure record at the end supersedes them.

| Active field / consumer | Source semantic | Unit | Scope | Generation | Availability | Consumer meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Player dossier `market_consensus`; main player `consensus`; Market API | Admitted external normalized quotes | 0–1000 Market price | Canonical player, provider format | Current published Market snapshot | None without admitted quote; actual zero retained | Acquisition price, not intrinsic quality |
| Player `dtos_dynasty`, contender, rebuilder, fit | Unsupported long-term scalar | None | Player / selected context | Pinned intelligence context | Unavailable | No alternative number is substituted |
| Player production windows | Prepared canonical production | League-scored PPG / stated raw stats | Player, league, season/window | Prepared production generation | Missing preparation remains unavailable | Observed performance, not dynasty value |
| Dossier global Market ranks | Pre-filter prepared rank universe | Ordinal | Explicit global Market universe | Matching Market generation + rank methodology | Stale/unprepared reference excluded | Market rank, not roster rank |
| Dossier weekly rank | Canonical weekly projection | Ordinal | Same-position roster, stated week | Pinned projection snapshot | Missing projection unranked | Roster weekly comparison only |
| Market directory `result_position` | Filter/sort result order | List position | Current filtered result | Market read model | Present only for returned rows | Navigation order, not dynasty rank |
| Brain/Market agreement | Multiple comparable provider observations | Agreement index 0–100 | Provider comparison for asset | Current evidence publication | Zero/one observation unavailable; real zero supported | Agreement, not outcome probability |
| Team HQ foundation fields | Existing canonical team-card dimensions | Dimension-specific score/grade | League / franchise | Canonical card generation | No independent neutral fallback | Same assessment, not competing formulas |
| Home podium | Canonical team-card rank | Ordinal | League team assessment | Home generation / canonical directory | Missing rank produces no podium | Not standings or FOIS rank |
| Market evidence `impact` for price/quote/gap | Directional recommendation contribution | Contribution, not a price measurement | Evidence presentation | Current report | Zero contribution; missing observation separately unavailable | Price magnitude alone confers no recommendation |
| Data-platform raw trend | Same-provider raw observations only | Provider raw unit / percentage | One provider/category/player | Source timestamps | Mixed providers or fewer than two observations unavailable | Not canonical consensus movement |

### Additional final-audit corrections

- Player value adapter no longer trusts unchecked cached Brain global ranks; it
  shares the prepared-rank admission check with Brain.
- Removed raw `recent_points` / `season_average` fallback from active Player
  values because it lacks the canonical league/scoring/season boundary.
- The main `/players` Live Data panel and `/api/data/consensus/market` now reuse
  canonical Market normalization/consensus, not raw-value averaging. Current
  quote absence cannot resurrect a warehouse price. Provider raw rows remain
  source evidence, not consensus-scale values.
- Market's separate consumer consensus now requires multiple admitted providers
  for agreement/dispersion. Duplicate single-provider quotes do not establish it.
- Removed arbitrary price-minus-50 / quote-minus-500 recommendation impacts.
  Missing intrinsic gap is unavailable, not an observed zero gap.
- Home no longer promotes enumeration into missing team ranks; it labels the
  canonical team assessment independently from standings and FOIS.

Focused validation this audit: 20 dossier/rank/production tests; 13 consensus
tests; 13 active-roster/Home tests; 2 player/API normalization/replay tests;
6 independence/raw-trend tests. Counts overlap and are not a total regression
count. Comprehensive gates have not run.

### Ledger closure still pending

Complete classification of remaining provider-network/generic API evidence
admission and history consumers, including format/lineage and methodology
boundaries. Then verify the full consumer ledger against actual call sites.
The final 57-player consensus panel has not run; the rejected research panel is
not relabeled as accepted output. Release gates remain deferred.

## Market sources

### Provider-network/history classification from active code

| Feed | Classification | Independent family | Current price use | Historical use / exclusions |
| --- | --- | --- | --- | --- |
| FantasyCalc | External observed-market reference | fantasycalc_observed_market | Published current quote; actual source format retained | Historical-only rows excluded from current network/Brain evidence |
| DynastyProcess | External FantasyPros-derived representation | fantasypros_derived_market | Normalized external reference; exact PPR/team-count equivalence remains unproven | Not a second independent source alongside FantasyPros |
| FantasyPros | Upstream of DynastyProcess; presently credential/license-disabled | fantasypros_derived_market | No new integration enabled | Matching mirror is one vote; conflicting mirror is excluded pending resolution |
| Sleeper trade / league-local demand | League-private transaction facts and derivations | sleeper_league_observed | Not an independent global player-price quote | Context/process evidence, not external Market consensus |
| DTOS historical/intrinsic/pick values | Internal model output | dtos_intrinsic | Excluded from external consensus | Internal historical conclusions remain separate from historical external prices |
| nflverse | Performance evidence | nflverse_open_performance | Not a Market price | Production/statistical evidence only |
| KTC, MFL, Fleaflicker | Disabled/unconnected interfaces | Registry families only | No admitted current quotes | Registry presence is not evidence availability |
| Legacy raw/mixed Market snapshots | Insufficient comparison provenance | Not an additional source | Never current-price fallback | Retained, but no trend without comparable boundaries |

Network format fields now come from quote metadata rather than fabricated
12-team/Superflex/PPR defaults. Missing source publication time remains unknown;
ingestion/knowledge time is not substituted for it. Zero confidence remains zero.
Historical-only rows and internal/league-local families do not enter current
external-price consensus. Duplicate same-provider rows are one observation;
conflicting copies are excluded. Single-family disagreement is unavailable.
Provider dispersion is not labelled a statistical confidence interval.

New in-memory Market-history observations carry value concept, scale, format
and normalization method. Trend evaluation rejects unspecified/mixed boundaries,
conflicting equal timestamps and future observations, and sorts valid times.
Old history is not deleted or assigned invented metadata. This does not yet
complete the later structured trend-reason/methodology-transition release work.

Focused results: 12 provider-network tests passed; 22 consensus/history tests
passed; 9 boundary tests and 6 network/Brain tests passed (overlapping suites).
An import-cycle failure introduced while sharing registry lineage was corrected
by resolving that registry at evaluation time; the focused rerun passed.

**Remaining closure issue:** exact quote-format admission across the current
consensus adapters must be reconciled. The actual DynastyProcess payload declares
2QB, but does not establish FantasyCalc's explicit 12-team/PPR1 dimensions. It
must not be described as exact-format corroboration. Ledger and final panel are
still not accepted; no production rankings or release artifacts were published.

| Source | Identity | Format | Timing | Independence / limits |
| --- | --- | --- | --- | --- |
| FantasyCalc | Explicit Sleeper ID | Requested dynasty, 2QB, 12 teams, PPR1 | Retrieval known; source publication timestamp unavailable | Observed-trade external reference; not DTOS intrinsic |
| DynastyProcess | FantasyPros → Sleeper exact crosswalk; conflicting mappings excluded | Explicit value_2qb; exact PPR/team-count equivalence is not established by this CSV | scrape_date retained for freshness, retrieval retained for knowledge boundary | FantasyPros-derived reference; no extra independent vote for its upstream source |
| KTC / other disabled sources | Not admitted | Unconnected | Unavailable | No fabricated quote or synthetic consensus contribution |
| DTOS / DTOS Pick | Internal model | Internal | Internal | Explicitly excluded from external Market consensus |

Public DynastyProcess inspection: dataset scrape_date 2026-09-04 versus retrieval
2026-09-09. Source freshness must not be reset by retrieval. Historical observation
timestamps must not be replaced with the earlier source date. Normalization now
uses the separate date without changing the returned observation boundary.

Consensus corrections: repeated identical provider observations count once;
conflicting observations from the same provider are excluded (no last-row-wins);
zero-confidence/invalid/unsupported observations cannot corroborate; full-precision
weights determine the result, rounded weights are display only. The Market adapter
reports missing providers after actual admission, not before confidence exclusion.
Format compatibility and shared-lineage admission still require end-to-end proof.

## Consumer inventory / migration contract

| Consumer | Explicit concepts needed | Located legacy dependency / required change |
| --- | --- | --- |
| Player Dossier | Intrinsic evidence profile, Market price/rank, weekly projection, production and confidence | asset_intelligence/players/value_models.py still manufactures age/team-based dynasty score; player_value_projection/engine.py consumes it. Replace the labelled scalar, not its input with Market. |
| Market | Canonical Market price, provider evidence, intrinsic profile, clearly scoped ranks | valuation/universe.py still sets intrinsic_dtos_value from legacy raw fields/evaluator. market routes already accept missing values; profile exposure and unavailable intrinsic rank needed. |
| My Team / Team HQ | Selected-league roster, scoring-specific lineup evidence, Market holdings, profile/support | Shared intelligence orchestrator/report consumers require migration together; do not inject a new number into an old field. |
| Brain | Typed independent evidence axes and generation | valuation_intelligence/engine.py reads intrinsic layer and builds rank references; remove unsupported scalar coverage without substituting zero. |
| Competitive Window | League/franchise-specific projection, roster strength and supported horizon | competitive_window engine requires a separate dependency trace before any numeric migration. It must not equate historical-quality tier with contender status. |
| Trade Center | Market Balance from Market price; bilateral context from explicit league/team evidence | trade_intelligence/market/trade_market.py contains legacy fallback from absent Market to blended/internal score; prove active call paths and remove semantic substitution. Preserve canonical Market Balance when Market evidence exists. |
| Trends / intelligence memory | Separate Market/quality/rank concepts with methodology and as-of boundaries | intelligence_memory/pipeline.py uses league_adjusted OR intrinsic; valuation/automation.py assumes numeric intrinsic. Both need explicit missingness/version migration. |

The inventory above records the original dependencies; implementation updates below
supersede its original findings. It is not a completion checklist.
Legacy intrinsic scalars must not silently survive as accepted evidence. Pick
models require separate scope review; changing player availability is not authority
to erase an independently supported pick calculation.

## Acceptance still required

- Two-provider source-backed panel with format/freshness disclosures and identity coverage.
- Historical as-of admission and bounded repeated-sync proof through real storage paths.
- Complete consumer migration, including absent-value arithmetic and no fallback relabeling.
- Methodology-version trend boundaries and no timestamp-only movement.
- Real league/player acceptance and required final release gates.

The 319-supported / 79-missing projection snapshot remains preserved.

## Final-audit corrections (ledger still open)

- Market directory order is explicitly `result_position` / `filtered_results`,
  not a dynasty/global rank; result order no longer receives podium treatment.
- Prepared global ranks require matching rank methodology and Market source
  generation before Brain overlays them on the league-filtered universe.
- Agreement requires a comparison: zero/one observations produce unavailable,
  not 35/70. Missing agreement is excluded from averages and comparison lists;
  genuine zero agreement remains supported. Market/API/Brain preserve null.
- Market detail no longer labels all layers with a blanket 0–10000 unit.
  Market price, league-scored PPG, evidence support and longevity are distinct;
  an unestablished scale remains absent.
- Team HQ secondary grades now present the existing canonical team card,
  including generation/league identity. Removed independent youth/depth/pick/
  flexibility formulas and the missing-age neutral-50 fallback. No new grading
  model was introduced.

Focused proof: 25 valuation-intelligence tests and 18 scalar/rank/Market tests
passed. Active roster/Team HQ run: 17 passed, one obsolete generic-rank assertion
failed (expected rank 1 where overall evidence is unavailable); corrected to
require unavailable, with focused recheck recorded separately. This is not
comprehensive release validation or ledger closure.

Focused recheck: 2/2 passed (objective Team HQ model and canonical secondary
grade identity). Changed-file Ruff and whitespace checks passed. No release or
production mutation occurred.

## Valuation / Brain boundary migration

The valuation universe no longer republishes cached `dtos_value`/`dynasty_value`
or age/team proxy scalars as player intrinsic value. Player intrinsic,
league-adjusted, contender, rebuilder and future scalar layers remain unavailable.
The existing pick model remains separate and unchanged. Raw metadata fantasy
points cannot fill canonical current-season production. Missing age is no longer
a neutral numeric age score. Unsupported liquidity remains unavailable rather
than being inferred from intrinsic or price magnitude.

Prepared reference-production quality, observed usage, sample confidence,
longevity context and evidence generation are exposed separately as an intrinsic
evidence profile and passed unchanged into the valuation Brain record. The
profile publishes no intrinsic scalar or tier. The checkpoint writer now keeps
league-adjusted and intrinsic fields separate, including legitimate zero.

## Active connected-chain integration

The former age/team dynasty score, synthetic two-year score, player-value
Market/projection blend, price-to-dynasty roster adapter, and generic team grade
have been retired from the active chain. Player portfolio/future/asset-health
adapters propagate unavailable. Trade season-utility/fit impacts also propagate
unavailable instead of substituting an acquisition price. Package Market Balance
still uses the distinct acquisition-price contract.

`evaluate_roster` now calls the existing generation-bound grading model.
Team HQ and the canonical window share that result. Actual and optimal starters,
legal backup depth, Market holdings, production and longevity remain distinct.
The old dynasty field stays unavailable; Market holdings have their own field.
Caches and crawl views include a method/evidence-generation boundary. See
`BATCH3_ROSTER_ASSESSMENT_BOUNDARY.md` for trace and focused proofs.

The ledger is **still open** pending remaining active-consumer/static audit,
legacy test-contract migration, final Market panel, trend/version and release
acceptance. This is not a claim of zero remaining substitutions throughout DTOS.

## Trade acquisition-price boundary migration (in progress)

- Package balance and guardrails consume explicit acquisition prices only. True
  zero remains zero; missing prices cannot fall back to dynasty, weekly or fit scores.
- Player TradeAsset intrinsic value is unavailable. Its acquisition price comes
  from admitted external Market consensus; the existing independent pick model is
  retained separately.
- Generated/adjusted packages exclude unpriced candidates, without removing them
  from owned-asset pools. A selected unpriced asset produces a typed
  `market_evidence_unavailable` response, not a fabricated balance or engine crash.
- Intrinsic-dependent future benefit and expected benefit stay unavailable. Shared
  recommendation and league-summary consumers preserve that missingness rather
  than interpreting it as negative/neutral benefit.
- Priced workflow fixtures now supply explicit external quotes; package-shape tests
  supply explicit acquisition values instead of relying on retired fallback behavior.

The integrated recommendation presentation now preserves unavailable intrinsic,
contender and rebuilder scalars; weekly projection deltas require evidence for
every participating player and never coerce a missing projection to zero. The
acquisition-price delta retains its distinct label and supported pick-price basis.

Legacy redraft/team-fit player scalars are now unavailable through the active
Trade adapter. Other player/league opportunity formulas and their presentation
still require the ledger's semantic audit. No comprehensive release gate is authorized by
these focused changes alone, and no intrinsic rankings are ready for publication.

## Exact provider-format decision (2026-09-09)

See [provider-format audit](BATCH3_PROVIDER_FORMAT_AUDIT.md) for the exact feeds,
authoritative sources, six-part semantics and explicit unknowns. The current
FantasyCalc/DynastyProcess relationship is INCOMPATIBLE / UNKNOWN for combined
consensus. Numeric rescaling is not an approved format transformation. The core
consensus now requires an explicit shared compatibility contract before combining
independent sources; the active provider-network path also retains them separately.
Single-source confidence is not reduced merely by the absence of another source.
Ledger remained OPEN at that checkpoint pending API/presentation propagation and final consumer sweep.

## Bounded final sweep — closure record

The final sweep traced routes/components/services and the active Player projection,
Valuation Universe, Market, Brain, roster/team, Competitive Window, Trade adapters
and diagnostic serializers. Searches included legacy dynasty/player scalars,
generic ranks, list enumeration, missing-price/projection fallbacks, provider
agreement and historical adapters. No new valuation architecture was introduced.

| Additional active boundary | Source semantic | Unit | Scope | Generation | Availability | Meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Projection audit rank maps | Canonical Market price | Ordinal | League Market player universe; excludes picks | Current supplied Market snapshot; deterministic rank methodology | Missing price unranked; actual zero ranked | Audit comparison, not global dynasty rank |
| Crawl team rank | Canonical team-card assessment | Ordinal | Selected league | Supplied canonical cards | Missing rank retained | Explicit Team Assessment, not standings inferred from enumeration |
| Commissioner team ordering | Canonical card order | List order | Selected league | Same active cards | Unranked teams stably ordered without fabricated rank | Navigation order only |
| Historical Trade adapter | Historical as-of acquisition evidence | Historical Market units | Event/franchise | Existing historical state boundary | Missing price stays missing | Package price only; not dynasty/redraft/team fit |
| Market/API evidence state | Admitted source price | Provider-specific normalized 0–1000 representation | Exact source format | Published observation/method | Separate quotes retained when combined price unavailable | Single provider / proven consensus / unavailable |
| Brain agreement | Admitted compatible comparison | 0–100 index | Compatible independent families | Provider-network generation | No raw-quote fallback | Evidence agreement, not confidence in outcome |
| Calibration diagnostics | Compatible evidence availability | Count/status | Current evidence universe | Current provider network | No agreement inferred from healthy-feed count | Diagnostic only |

Concrete sweep defects corrected: retired directory rank access; missing prices
ranked as zero; unavailable team ranks sorted/enumerated as conclusions; historical
Market price copied into unrelated scalar slots. Fully priced historical package
behavior remains unchanged; missing acquisition evidence returns UNAVAILABLE.

Guarded unavailable player-scalar paths (including legacy league opportunities)
remain unavailable, not substituted. Pick-specific model outputs and retained
historical checkpoint fields remain explicitly separate; this audit does not
redesign Pick Intelligence or historical grades. Provider normalization constants
are DTOS representation parameters, not asserted provider maxima or proof of
cross-provider compatibility. Final panel outliers remain a separate acceptance gate.

Focused proof: active/rank suite ran 33 tests, with two obsolete pre-format-decision
expectations failing. Those expectations were corrected explicitly; all five
consumer-boundary tests passed on rerun, reusing the 28 unchanged passing tests.
Historical/diagnostic adapter suite: 17 passed. No comprehensive gates run.

**Consumer ledger CLOSED for the audited active candidate contract.** Remaining
work is the requested actual-player panel review, planned trend/change-methodology
work and release/production acceptance—not speculative semantic re-auditing.

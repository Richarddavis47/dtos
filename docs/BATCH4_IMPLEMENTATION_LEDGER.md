# Batch 4 implementation ledger — in progress

Baseline: immutable v1.17.2 / build 1702. Candidate branch:
`codex/v1.18.0-fois-pick-intelligence`. No release or production change yet.

## Audited active boundaries

| Boundary | Existing source | Finding / disposition |
| --- | --- | --- |
| Canonical postseason | `src/core/history_context/playoffs.py` | Supplies qualification, semifinal participants and championship participants independently of final placement; preserves missing dependencies. Season-specific completion and multi-week contracts still require audit. |
| FOIS history adapter | `src/core/fois/history.py` | Corrected canonical semifinal field mismatch and qualification lost when placement is unavailable. Integer/string roster identities normalized. |
| Results scoring | `src/core/fois/results.py` | Uses completed seasons; playoff qualification now reaches this active path. Missing postseason boolean coverage and unsupported cycle defaults require further review. |
| Executive scoring | `src/core/fois/engine.py` | Corrected overlapping strongest/weakest categories: one category or ties cannot support contradictory comparative labels. Remaining metric semantics still under audit. |
| Category weights | `src/core/fois/configuration.py` | Existing Results 30%, Trading/Asset Management 25%, Roster 20%, Drafting 15%, Waivers 10%; unchanged. |
| Score aggregation | `src/core/fois/scoring.py` | Available metric weights renormalized; neutral evidence 50 maps to executive 70. Coverage/confidence separate. Justification and all category inputs remain to be reviewed before acceptance. |
| GM attribution | `src/core/fois/service.py` | Seasons allow missing ownership; drafts/waivers currently unfiltered by historical owner. Must resolve attribution, unknown evidence and leave/rejoin before acceptance. |
| Draft/waiver facts | `src/core/fois/history.py` | Canonical selections attributed to roster, but limited decision evidence. Preserve explicit unavailable process/outcome rather than fabricate. Transaction-type and ownership filtering require audit. |
| Pick report | `src/core/asset_intelligence/picks/pick_value.py` | Legacy round table, time discount and neutral Market placeholder found. Trace active consumers before replacing; no claim these are canonical Market prices. |

## Focused proof so far

- 31 tests passed across FOIS Results, canonical postseason facts and GM intelligence.
- Includes bye recipients with no final placement, canonical semifinal identities,
  string champion identity, and disjoint strength/weakness reporting.
- Initial new-test accessor typo corrected before the passing run.
- No comprehensive release gate or production validation run for this candidate.

## Remaining dependency order

1. Complete canonical history/GM tenure and postseason completeness audit.
2. Results, trading, draft, waiver and historical roster evidence integration.
3. Scoring/confidence/generation coherence, method transition and bounded storage.
4. Pick identity, ownership, range, exact-slot lineage and portfolio integration.
5. Real source-backed all-GM and pick panels in two authorized leagues.
6. Focused storage/performance/coherence proof, then frozen authoritative gates.
7. Immutable release, deployment, bounded production preparation, acceptance,
   stable-input restart and cleanup.

Batch 4 is not complete. Batch 5 is not started. Current Visual, DINS and
External Visual Mirror remain retired. User reference files are preserved.

## Attribution follow-up

The active FOIS service now requires identified ownership for Results, Trading,
Drafting and Waivers; unknown history is retained but excluded from GM scoring.
Historical roster metrics require their own identified manager. Canonical
conflicting season-owner observations remain unknown instead of last-row-wins.
Draft/waiver facts preserve owner and event timestamp separately. Exclusion
counts are disclosed in score warnings.

32 focused tests pass, including active-service attribution and tenure tests.
Three existing tests required explicit fixture ownership: their previous
unattributed records no longer legitimately produce GM scores. No thresholds
were changed. Precise intra-season ownership intervals and returning-manager
tenure boundaries remain open; seasonal ownership is not timestamp proof.

## Pick consumer trace — open

- `trade_intelligence/market/trade_market.py::_pick_asset` incorrectly promotes
  normalized deterministic option value into Market/trade acquisition price;
  it also supplies a fixed redraft number and fixed liquidity score.
- `valuation/universe.py::_pick` publishes the deterministic round model as
  intrinsic/utility/future layers with heuristic multipliers and an internal
  provider row. This is not independent external Market evidence.
- `asset_intelligence/picks/pick_value.py` retains a neutral 50 Market placeholder.
- `asset_intelligence/portfolio.py` and `team_intelligence/engine.py` aggregate
  these option scores into portfolio/future-capital assessments.
- `routes/draft.py` displays the option score; downstream truthfulness must be
  corrected with the shared contract, not merely renamed independently.
- Historical reconstruction also contains a fixed pick contribution requiring
  no-hindsight review before migration.

No pick-price source correction is claimed yet. The complete consumer trace,
external quote contract and missing-value propagation must precede acceptance.

### Pick-price correction checkpoint

The active `_pick_asset` now returns unavailable Market/acquisition price instead
of normalized internal round/range score. `market_pick_value` no longer returns
a neutral 50 placeholder. Existing acquisition-price admission rejects a mixed
player/pick package with missing pick evidence using the explicit unavailable
contract. Original franchise, owner, range and exact-slot fields are unchanged.
10 focused price-contract tests pass, including the actual pick adapter.

Ingestion audit: `data_platform/provider_activation.py` retains FantasyCalc
quotes by Sleeper player ID and DynastyProcess quotes by FantasyPros-to-Sleeper
player crosswalk. Neither path constructs year/round/format pick observations.
This proves no supported pick quote reaches this adapter; it does not prove
the public providers have no pick datasets. External source coverage and all
remaining pick consumer migrations are still open. Internal utility/redraft
fields remain separately pending audit and are not accepted as validated values.

### Semantic quote integration checkpoint

- Public ingestion now retains separate concept-aware pick observations for FC
  and both DP variants, excluding them from player-ID maps. Refreshed snapshots
  replace prior provider pick arrays rather than append observations.
- Selector requires explicit requested provider-format identity; established
  exact slot precedes supported range, then generic. Generic is never relabeled.
- Historical, stale/future, invalid/conflicting or incompatible evidence is
  excluded. Retrieval/source times remain distinct. Raw provider units retained.
- 23 focused provider/identity/selection/Trade-price tests pass.
- Active price normalization and downstream integration remain unfinished:
  player and pick package prices need the same compatible normalization context,
  not pick-only percentiles or a player-score conversion. Real panels pending.

### Retained production reconciliation — 2026-09-13

Read-only Render Web Shell inspection compared both canonical cache ledgers
against fresh Sleeper league/rosters/traded-picks responses. No cache, database,
configuration or production source was changed. No SSH key or temporary file
was created. One shell diagnostic initially failed with a line-break syntax
error; the corrected read-only command completed for both leagues.

| League | Retained/source picks | Missing/extra/duplicate | Owner differences | Draft rounds retained/source |
| --- | --- | --- | --- | --- |
| Day Traders (1313066632158924800) | 120/120 | 0/0/0 | 0 | 4/4 |
| Super Flexxxin (1313063672284721152) | 90/90 | 0/0/0 | 0 | 3/3 |

Both retained league IDs match. Both sources and caches specify six playoff
teams and week 14 playoff start; this does not prove different playoff formats.
No invalid owner IDs were found. Comparison covers every year/round/original
franchise/current owner in the retained future universe, not just samples.

Classification: deployed caches have no `pick_quotes` collection. Their ledger
rows contain identity/owner fields only. Candidate external-price differences
are EXPECTED METHODOLOGY/SCHEMA DIFFERENCES, not evidence of incorrect ownership.
No production external-price parity is claimed. The ledger itself has no
ownership-chain field; historical transaction-chain reconciliation remains open.
The Picks page renders `traded_picks`, including 2026 records, not the complete
future ledger: historical UI rows are not extra future assets.

Live account switching reached Super Flexxxin with its correct franchise.
Subsequent Picks-page browser commands timed out; complete round-trip UI
context proof remains open. This is not a passing browser gate.

Concrete adapter correction: Trade no longer derives EARLY/MID/LATE from a
simple points/win-rate ranking. Unprepared range stays UNKNOWN and an
unestablished exact slot is removed. Prepared evidence is not recomputed from
the current owner's strength. 14 focused range/Trade-price tests passed.

Still open: historical ownership chains, full UI isolation round trip,
range/confidence/portfolio/history methodology, remaining legacy pick consumers,
FOIS category completeness and real all-manager diagnostic panels. No release
gates, commit, release or deployment performed. Batch 5 NOT STARTED.

### Historical lineage and FOIS evidence correction

- Historical pick dossier globally deduplicated its owner chain, erasing a
  return trade (A -> B -> A). It now preserves sequential owners, includes the
  first observed transfer's outgoing owner, excludes failed transfers, and
  discloses missing transitions. Current snapshot ownership does not rewrite
  historical events. Only completed exercise events establish slot status.
- 12 focused historical graph/lineage tests passed, including rerun after the
  completed-exercise guard.
- Browser recovered: Super Flexxxin Picks showed its own franchise and three
  rounds; switching back restored Day Traders/Chase Bank and fourth-round
  picks, without the other franchise. Navigation deadlines were exceeded on
  Picks, but a subsequent bounded state read succeeded. Cause is not proven;
  no product responsiveness fix is justified by this observation alone. Full
  Market/settings parity is not claimed.
- FOIS trade activity no longer earns a decision-quality score. Unknown
  strategically-productive evidence is excluded from quality denominator,
  remains missing and reduces coverage. Supported false remains genuine zero.
- 26 FOIS focused tests passed after correcting the new test's field names and
  adding explicit seasonal-owner evidence to the existing leaderboard fixture.
  That fixture had previously exercised excluded, unattributable results.
- Real historical lineage panels, range/confidence/portfolio completion and
  source-backed all-manager FOIS output panels remain open. No comprehensive
  release gate or production mutation occurred.
# Batch 4 storage acceptance constraint

Permanent growth remains a release blocker. No paid capacity increase is
authorized. FOIS grading must reference canonical decision/evidence identities,
not persist duplicate trade/draft/waiver/roster/provider payloads per decision.
Pick history must retain only meaningful range/confidence/ownership/provenance
changes, with semantic deduplication and explicit historical boundaries.

Focused repository proof: 100 unchanged-evidence saves with changing observation
timestamps produce no extra score, history, semantic-state or evidence-link rows,
no page-count increase and no database/WAL/SHM byte growth. Nine storage tests
pass including existing state deduplication and league-scoped worker publication.
This is local evidence, not a production backfill/storage acceptance claim.

Before production publication/backfill: measure disk headroom and projected
bounded writes, including temporary/WAL overlap. Final acceptance must record
storage before/after, FOIS size, Pick Intelligence size, backfill growth,
unchanged-replay growth and remaining free disk. Do not publish while these
measurements or growth admission are unresolved. Meaningful history growth must
be distinguished from repeated unchanged observation growth.

# Batch 2 — canonical data foundation (candidate work in progress)

Baseline: v1.15.1 / 1501, a4046f808a86865640cfad1549bf99d02b130e1a.
Candidate branch: codex/v1.16.0-canonical-data-foundation.
No production mutation, release, or Batch 3 work has occurred.

## Existing boundaries to extend

| Concern | Existing boundary | Audit finding / action |
|---|---|---|
| Player IDs | data_platform.normalization.PlayerIdentityResolver | Remove name-only and cross-namespace joins; reject ambiguous IDs; retain PFR crosswalk |
| League history | history_context.CanonicalHistoryStore / SleeperSeasonCache | Preserve provider-backed facts; no HistoricalStore recreation |
| Event normalization | historical_intelligence.HistoricalIntelligenceService | Preserve normalized playoff coverage and FAAB/settings fields |
| Playoffs | CanonicalHistoryStore._season_records | Existing result retained only first/second; canonical reducer now preserves supported placements and semifinal dependencies |
| As-of franchise | historical_franchise_state.HistoricalFranchiseStateService | Existing reconstruction to audit, not replace |
| Market checkpoints | intelligence_memory.IntelligenceCheckpointStore | Preserve sparse global observations and FOIS scoped reuse |
| Production provider | historical_memory.providers.NflverseProvider | Existing streamed adapter; column compatibility and active global persistence still to audit |
| League scoring | historical_memory.scoring.calculate_fantasy_points | Reuse; explicitly disclose unsupported components |
| Consumer production | player_value_projection.CachedProductionProvider | Legacy player-field dependency; canonical consumer bridge still pending |
| Evidence status | DataEnvelope / historical EvidenceAvailability / freshness | Extend existing concepts; distinguish observation kind from availability and freshness |
| Storage | v1.15.1 FOIS/projection semantic codecs | Preserve; measure actual new growth before production backfill |

## Focused evidence so far

- 14 data-normalization tests pass, including namespace collision, ambiguous IDs,
  name-only rejection, changed team/name/status, and PFR mapping.
- 3 playoff reducer tests pass: six-team bye participation, semifinal lineage,
  placement separation, missing/conflicting/incomplete championship.
- 12 existing historical-intelligence tests pass alongside those 3 playoff tests.
- Whitespace passed before the later playoff integration; final gate still pending.
- Initial pytest invocation was unavailable in the existing virtual environment;
  repository unittest execution succeeded. No dependency was installed.

These are focused proofs only, not release acceptance.

Additional focused evidence:
- 46 existing HistoricalStore-migration/franchise-state tests pass with the
  canonical playoff adapter integration.
- 3 stat-normalization tests pass; the current 2025 public CSV header was checked
  using a streamed first-line read (not a full dataset download).
- 13 provider/player API tests pass after replacing the false projection-provider
  message with availability from the active league's pinned canonical snapshot.
  A foreign-league snapshot cannot supply its value or generation to this path.
- Focused Ruff passed for the initial identity, playoff, and stat modules;
  final complete lint/validation remains pending.

No production backfill, storage mutation, push, PR, release, or deployment yet.

Latest batched focused run: 94/94 tests passed (7.168 seconds), covering all
modified identity, provider, playoff, historical adapter and API boundaries.
Draft ingestion now retains draft ID; selection keys distinguish two drafts in
one season and preserve the source roster's franchise. FAAB/bid facts survive
canonical event normalization. Consolation cannot supply the league champion.

## Source review (2026-09-08; approval/connection not implied)

- Sleeper bracket contract: https://docs.sleeper.com/#getting-the-playoff-bracket
  Winner dependencies use `{w: match_id}`; placement matches are not seeds.
- nflverse weekly stats: https://nflreadr.nflverse.com/reference/load_player_stats.html
  Current dictionary differs from some existing adapter column names; verify before ingestion.
- Snaps: https://nflreadr.nflverse.com/reference/load_snap_counts.html
  PFR-origin game-level data from 2012; dataset-specific reuse review pending.
- Contracts: https://nflreadr.nflverse.com/reference/load_contracts.html
  OTC-origin historical/active contracts; upstream permitted-use review pending.
- Cadence/availability: https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html
  Do not equate downloadable historical data with current injury availability.

## Remaining dependency order

1. Finish identity provenance and consumer compatibility audit.
2. Historical chain/tenure/draft/transaction/settings reconciliation and coverage.
3. Existing as-of reconstruction fidelity and no-hindsight validation.
4. Dataset-specific licensing, normalized global production/context ingestion,
   source cadence, missing-evidence states, and bounded persistence.
5. Canonical consumer evidence bridge and contradiction inventory.
6. Focused idempotency, storage, isolation, and real-source proof.
7. One authoritative final validation sequence on frozen candidate.
8. PR/release/deployment, admitted bounded production backfill, multi-league proof,
   stable restart, cleanup, full Batch 2 report, then stop.

Retired Current Visual, DINS and External Visual Mirror stay retired. User-owned
images and blueprints remain untouched. No paid infrastructure is authorized.

## Global foundation continuation (not release acceptance)

The user explicitly prioritized the global layer before further consumer work.
New modules under the existing data_platform boundary:

- `global_evidence`: normalized scalar allowlists per evidence family, compressed
  content-addressed states, compact temporal revision references, no league/account
  fields, bounded atomic batches, read-only queries, existing storage maintenance
  fence, SQLite size admission and pre-write free-space admission.
- `global_production`: verified GSIS-to-canonical mapping and source game-time
  requirements; bounded normalized nflverse batches; existing scoring engine on
  read with no durable per-league production copy.
- `evidence_availability`: shared freshness-policy reuse and explicit cached,
  stale, unavailable, not-connected, not-applicable and insufficient-sample states.

Candidate storage budget is 256 MiB plus a 128 MiB disk reserve (not the separate
500 MiB runtime memory reserve). This is an application admission budget, not an
infrastructure change. Production sizing/admission remains pending.

Focused proofs: 8 global-storage tests and 1 global-production test pass. They
cover 500 repeated consumers with identical database bytes, A-B-A temporal
transitions without duplicate payloads, as-of correction selection, unknown
publication time, rollback, disk admission, independent-process reopen and two
league scoring profiles sharing the same evidence fingerprint. Three availability
tests pass; a literal-comparison lint finding was corrected and Ruff passed.

These modules are not yet wired into production synchronization or consumers.
Do not claim integration or live coverage from unit fixtures. Remaining work:
source-specific adapters/permissions, bounded resumable sync and source health,
production path/configuration integration, actual source-backed reconciliation,
storage measurements, and all final release gates.

Source permission review found current Sports Reference data-use restrictions
that need resolution before connecting PFR-origin snap data. Keep that proposed
adapter NOT CONNECTED; do not scrape or assume the downloader's code license
settles upstream rights. References:
https://www.sports-reference.com/data_use.html
https://github.com/nflverse/nflreadpy/blob/main/README.md
Contract-source permitted-use review is still pending. These optional gaps do not
authorize paid access and do not block the independent canonical foundation work.

Follow-up foundation work:
- Global state/revision separation preserves A-B-A changes while reusing payloads.
- Read-only service facade does not create a missing database and cannot publish.
- Central configuration adds DTOS_GLOBAL_EVIDENCE_FILE, respecting durable root
  and cache-path defaults without changing any production environment setting.
- Global production scoring is derived per supplied league settings via the
  existing scoring engine; no scored league copy is stored.
- Latest combined focused run before the configuration-override test: 13/13 pass;
  Ruff passed. Comprehensive gates have NOT been run.
- Public nflverse schedule CSV header verified from the documented nfldata
  dataset; schedule ingestion and actual game-time mapping are still pending.

Next: finish resumable approved-source ingestion and source-level freshness/
coverage bookkeeping; connect it to the background-only runtime boundary. Then
perform the original real-league historical and source-backed acceptance proofs.
No overall Batch 2 completion is implied by the foundation unit tests.

## Background-source ingestion progress (2026-09-08)

- Atomic ingestion checkpoints now share the transaction with each bounded batch.
  Interrupted sources resume from committed evidence; completed unchanged revisions
  skip normalization/publication. Truncated pinned sources fail closed.
- Temporary source snapshots are decoded-byte/disk admitted, content-hashed, and
  removed on success or failure. No raw feed is retained permanently.
- nflverse production ingestion pins source hash, GSIS crosswalk fingerprint,
  game-time mapping and normalization version. Unknown publication time remains
  unknown; modern backfill does not become historical decision-time knowledge.
- Schedule ingestion uses documented Eastern kickoff times with IANA DST rules.
  The first Windows test exposed missing timezone data; `tzdata` was added to
  requirements and the ignored environment. Focused tests then passed.
- Exact-ID DynastyProcess enrichment rejects conflicts in both directions. No
  display-name joins; changing a display name does not invalidate evidence joins.

Public-source local proof (not production backfill): 2025 schedule had 285 games,
zero missing kickoff times. The first Sleeper-only GSIS mapping produced 5,773
production states from 19,422 rows, with 13,649 unresolved rows. Schedule plus
production database was 6,533,120 bytes; total duration 5.187 seconds. Temporary
source/database files were removed. This exposed a real catalog mapping gap.

After exact-ID crosswalk enrichment, 6,309 of 6,321 QB/RB/WR/TE rows resolve;
12 remain unresolved. Other positions: 12,199 resolved / 902 unresolved rows.
These counts describe identity coverage, NOT complete support for defensive or
kicker scoring. Unresolved offensive identities: Tyler Conklin, Jeshaun Jones,
Quentin Skinner, Dalen Cambre, Drake Dabney. Do not fabricate mappings.
Crosswalk: 12,492 rows, 7,398 resolved catalog players, 4 ambiguous players,
11 ambiguous GSIS IDs. Conflicts deliberately remain unresolved.

Source fingerprints:
- Schedule: fa49d8cf74dec2506ab3a3a5f20c3a17c60617e252500df492c28c1e1553d554
- 2025 production: e5e0615b3d96a3eaebfaee91e55afb4a4e7fe0caf057454177bcd7d6ad4bcfc2
- Crosswalk: a02b7dc2364a8b8de2bd3c91147b1dce46033f627a382161c409b29c5e7defd2

References:
- https://nflreadr.nflverse.com/articles/dictionary_schedules.html
- https://nflreadr.nflverse.com/reference/load_ff_playerids.html
- https://github.com/dynastyprocess/data

Focused ingestion/snapshot/schedule/production checks: 8 passed. Subsequent
crosswalk + production checks: 4 passed. Ruff passed for the new source modules.
No comprehensive validation, commit, release or production mutation yet.
Runtime scheduling/admission, source coverage receipts, remaining evidence
families, real-league proofs and the final acceptance chain are still pending.

Further progress:
- One-shot public-source worker and background coordinator now exist. Worker
  input is only protocol/season/database/temporary-directory. Credentials and
  league/account state are excluded. Parent owns temporary cleanup after timeout.
- Existing lifecycle coordination and memory admission are reused; startup and
  Market-critical work defer ingestion. Periodic current-NFL-season ingestion is
  one global task after startup, coordinated with other intelligence-heavy work.
- Normalizer imports no longer eagerly load the unrelated legacy JSON warehouse;
  the existing data_platform singleton remains lazy-compatible for its consumers.
- Focused worker/background/execution/memory-lifecycle checks: 21 passed.
  Production runtime acceptance and real worker memory measurements remain pending.

Sleeper-only Day Traders read-only chain/bracket/roster proof discovered all six
seasons by previous_league_id (no Historical Memory fill):

| Season | League ID | Richard roster | Source postseason placement |
| --- | --- | --- | --- |
| 2026 | 1313066632158924800 | 1 | Unresolved/in-season; not a final qualification claim |
| 2025 | 1180090396074209280 | 1 | Champion (1st) |
| 2024 | 1048396014442389504 | 1 | 3rd; semifinal participant |
| 2023 | 916477632584318976 | 1 | 3rd; semifinal participant |
| 2022 | 784434742798966784 | 1 | 6th; playoff participant |
| 2021 | 714297384074555392 | 1 | Not in winners bracket; final consolation placement not yet queried |

All six source roster lists contain ten franchises. 2026 source bracket has
unresolved future participants/results, so its partial semifinal list is NOT
treated as a complete Final Four. Reducer now reports that incompleteness,
preserves first-round-bye IDs, and rejects conflicting match IDs independent of
row order. Seven focused playoff/history checks passed. Full transaction/draft/
waiver/standings/tenure/as-of reconciliation and second-league proof remain open.

### Subsequent real-source proofs (local, read-only production)

Isolated 2025 worker: 18,508 production states + 285 schedule states, 914
unresolved production rows across all positions; 20,369,408 database bytes;
9.672 seconds; sampled/final worker RSS 86,671,360 bytes. Worker and temporary
source/cache teardown completed. This is not a Linux cgroup acceptance claim.

Day Traders completed-season source coverage (all ten franchises each season;
18 matchup buckets, 19 transaction buckets including zero; no duplicate IDs):

| Season | Transactions | Trades | Draft selections | Traded picks | Normalized bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2021 | 352 | 32 | 250 (two drafts) | 36 | 375868 |
| 2022 | 541 | 97 | 30 | 65 | 370047 |
| 2023 | 320 | 39 | 30 | 77 | 288698 |
| 2024 | 342 | 41 | 30 | 78 | 313069 |
| 2025 | 317 | 22 | 30 | 71 | 302312 |

Each required source section returned available. This proves endpoint coverage,
not automatic correctness of every downstream conclusion. Standings fractional
points and unavailable matchup result handling were corrected with focused
regressions. Partial weekly endpoint failures now remain partial in cache status.
Source league/season identity is validated before accepting payloads.

Real as-of example: transaction 1292323930639454208 at
2025-11-07T00:49:04.583000Z. Richard's before/after state correctly removes
player 11586 and adds PICK-2026-R4-ORIG2. Reconstruction provider calls = 0.
No market evidence was supplied: market coverage correctly remained 0 rather
than substituting current values. Temporary provider cache was removed.

Second authorized league aggregate proof: membership uniquely verified, ten
current franchises, five-season terminated chain; latest historical season has
ten franchises, 319 transactions, 30 draft selections, its own scoring and
roster rules. No private league identifiers or player/transaction payloads are
included in this report. This is source-proof progress, not production acceptance.

### Focused continuation: read and temporal boundaries

- Player intelligence exposes a bounded canonical-evidence read using the selected
  league's season/scoring. Wrong league context returns 503 before exposing a
  player report. Missing scoring is unavailable, not calculated zero. A later
  source-refresh receipt is excluded from a historical as-of response; eligible
  underlying facts retain their independent knowledge boundary.
- Background ingestion cancellation now signals the worker coordinator; within
  its one-second polling interval it kills/reaps the worker and removes its
  temporary directory instead of waiting the full source deadline.
- Unpaired Sleeper matchup rows preserve player points without fabricating a
  game between bye/unpaired teams. Both documented bracket dependency forms are
  supported, resolving only explicit source outcomes.
- Historical franchise reconstruction now excludes same-week final totals at
  intraweek/event boundaries. Event-only boundaries use the source event week;
  timestamp-only boundaries without a proven week leave weekly results unknown.
  Missing points are not coerced to zero and unknown players cannot enter an
  optimal lineup as zero-point evidence. Method identity advances to
  `reverse-event-reconstruction-2`; this is factual/no-hindsight plumbing, not
  FOIS scoring-model tuning.

Focused results: canonical player API/normalization 17 passed; worker execution
4 passed; historical reconstruction/reconciliation/playoffs 25 passed;
transaction intelligence plus franchise reconstruction 28 passed after normal
application initialization. A direct isolated import of the transaction test
encountered the existing eager package circular-import chain; retain that failed
invocation rather than describing it as a test pass. No release gate was run.

Batch 2 remains incomplete. Source-family coverage, full reconciliation/tenure
proofs, production storage admission/backfill and final release acceptance remain
required. No commit, push, release, deployment or production mutation occurred.

Ownership source proof: six Day Traders seasons, 60 franchise-season owner
observations, 50 exact prior-season/roster-slot continuation links, zero chain
gaps, zero observed owner changes. Richard is observed in all six seasons.
No exact takeover timestamps were inferred and no durable writes occurred.
The canonical ownership reconciler preserves co-owners and explicitly reports
season-observed continuity, not undocumented intra-season tenure. Three focused
regressions cover changed/returning owners, missing links/same-name separation,
and invalid chains. CanonicalHistoryStore exposes this as a background-only
reconciliation read; FOIS tenure/grade migration remains a later consumer task.

Real unchanged-replay proof with source-check receipts: 20,377,600 bytes before
and after, zero growth, zero production rows re-examined, zero new states.
First preparation 14.516 seconds, replay 1.844 seconds. Both workers were reaped;
the parent temporary directory removed the database and storage-lock file.

Explicit backfill tooling now defaults to read-only dry-run admission and requires
explicit seasons plus `--apply` for execution. Seasons execute sequentially and
stop on the first incomplete/deferred result; no automatic retry or source
substitution. Its 24 MiB/season planning estimate is based on the measured
19.43 MiB season, not a guarantee. The new global database ceiling was set to
256 MiB to accommodate a roughly ten-season global corpus (about 194 MiB at the
measured shape) without per-league copies. This changes no existing database
budget, Render disk size/tier, or runtime reserve. Actual production admission
must still pass before mutation; meaningful corrections can exhaust the ceiling
and then fail closed rather than delete irreplaceable evidence.
Backfill/storage focused tests: 13 passed. Production backfill is not yet run.

Read-only production capacity check (2026-09-08, existing Render Web Shell):
2,077,073,408 total bytes; 621,338,624 used; 1,438,957,568 available (31% used).
Inodes: 281 used of 131,072; 130,791 free. Largest allocated database sizes:
projections 227,028,992 bytes; FOIS 82,075,648 bytes; intelligence 10,002,432
bytes. Previously classified retired validation/visual directories remain
present and untouched. No deletion is needed for planned admission. No SSH key,
credential transfer, application/database mutation, or infrastructure change
occurred. The temporary browser shell tab was closed after the measurements.
These numbers prove current capacity only, not successful future backfill.

### All-franchise regular/postseason reconciliation

Sleeper-only reconstruction compared all ten franchises in each completed season.
Regular-season wins/losses/ties matched source roster totals in all 50 cases.
Points-for matched in 49/50 cases: 2021 roster 6 reports 1,537.78 in the roster
standing, versus 1,537.68 summed from source weekly matchups. The 0.10 source
disagreement remains explicit; neither source was rewritten or forced to agree.
No incomplete paired results, duplicate transaction IDs or duplicate
draft-ID/selection-number pairs were found in those five seasons.
All five winners brackets reconciled qualification, byes, semifinal participants,
championships and placements without missing-dependency reasons.

| Season | Complete transactions | Failed attempts retained separately |
| --- | ---: | ---: |
| 2021 | 285 | 67 |
| 2022 | 500 | 41 |
| 2023 | 296 | 24 |
| 2024 | 307 | 35 |
| 2025 | 312 | 5 |

Real completed waiver 1296347791647346688 (2025-11-18T03:18:27.808000Z)
adds player 10232 and drops 6271; before/after reconstruction matches exactly,
with zero provider calls during reconstruction. Failed waiver
1298506804233240576 remains an attempted claim, not an ownership move. The
reconstructor now explicitly ignores failed/pending adds/drops.
Real free-agent event 1310384278512599040 adds 4381 and drops 11579; source and
derived differences match. Draft selection 1180090396074209281:30 adds 12505
at the event boundary, but the source selection timestamp is unavailable.
No exact draft selection time or historical market value was fabricated.

Actual Day Traders scoring inspection identified the Sleeper `fum_lost` alias,
TE reception bonus, and two-point components. The global derivation now handles
those explicit aliases; missing long-touchdown bonus counts remain missing.
Published `passing_40`/`receiving_40` count big plays, not 40-yard touchdowns,
and must NOT be substituted. Production normalization v2 also retains published
per-game target/air-yard shares. Seasonal shares remain unavailable without a
valid aggregation denominator. Twelve focused ingestion/production/usage/worker
tests passed. The prior real replay size/timing proof describes normalization v1;
deduplication mechanics remain proven, but v2 final payload-size acceptance is
still pending. Exact full Day Traders fantasy-score reproduction must disclose
unsupported bonus/defensive components rather than claim complete scoring.

### Feed publication and real scoring continuation

The normalization-v2 real worker completed in 11.797 seconds with 87,289,856
bytes final worker RSS and a 20,377,600-byte database. The diagnostic database
was removed after closing its reader; an earlier diagnostic-only cleanup attempt
failed because its SQLite connection had not been explicitly closed. No product
database or production file was involved. All 20,377,601 temporary file bytes
(database plus lock) were removed and absence verified.

Using the same real source game (`2025_17_BAL_GB`, Sleeper player 10217), the two
authorized leagues produce **known-component** totals of -1.68 and -0.58. Their
actual scoring rules differ (including completions and interceptions). Both
results remain **incomplete**, with `fantasy_points=null`: unsupported bonus and
other required components are not silently treated as zero. This proves scoped
derivation of shared facts, not full-score equivalence. No private league ID or
payload is retained in this report.

Ingestion review found that previously only individual batches were atomic.
The candidate now stages new revisions invisibly and promotes them in the same
transaction as the completed feed cursor. Readers retain the prior complete
evidence during an interrupted refresh. Resume publishes all staged revisions;
replacement of an abandoned source removes only never-published staging records.
Published historical revisions remain intact. Read bounds now fail explicitly
rather than silently truncating evidence. Seventeen focused ingestion/storage/
source-receipt tests passed, including interruption, resume, prior-generation
visibility, atomic promotion, historical boundaries and abandoned-input cleanup.
The earlier real database-size proof predates this additional revision metadata;
final storage acceptance must measure the completed candidate.

Second authorized league, 2025 source-only reconciliation: 10/10 franchise
W/L/T records and 10/10 points totals matched. No matchup gaps, duplicate
transactions or duplicate draft selections. Thirty draft selections; 319
transactions (292 complete, 27 failed), including 19 trades, 236 free-agent
events and 64 waiver attempts. Winners-bracket dependencies resolved without
reason codes. Only aggregate private-league evidence is retained here.

The reconciliation helper now reports an unavailable derived record when the
regular-season boundary is missing, rather than comparing a fictitious 0–0
record with authoritative standings. The ingestion coordinator also holds a
nonblocking cross-process OS lock shared by CLI/background callers. Its single
one-byte lock file is intentionally retained to keep inode identity stable;
ownership is kernel-managed, not an expiring credential or growing log.
Eight focused locking/worker-cleanup/reconciliation tests passed.

Global reuse fixture: 500 independently scoped league scoring reads reuse one
source fingerprint with zero database-byte changes. A focused combined run of
23 read/isolation/ingestion/locking/reconciliation tests passed.

Schedule/bye source proof (2026): 272 regular-season games, zero missing kickoffs;
Buffalo has 17 games and derived bye week 7. Its first source game is at Houston,
2026-09-13 17:00 UTC. Source download 2,175,934 bytes; isolated schedule database
364,544 bytes; temporary cleanup verified. A bye is derived only from a complete
32-team 17/18-week schedule shape, never from an arbitrary missing game. A changed
NFL format is explicitly unavailable rather than guessed. This is independent of
league count and contains no terminal season. Season-indexed reads now select
the requested period before applying the result bound. No per-league schedule
copy or request-time provider query is introduced.

Additional source-header verification supports first-down and sacks-suffered
components. Normalization v3 retains those exact fields, preserving null versus
zero. Long-touchdown bonuses remain unsupported, not substituted by big-play
counts. Canonical production now distinguishes **raw evidence availability**
from **scoring completeness**: present source statistics are cached even when
the full fantasy total/PPG cannot be computed. A partial total is not promoted
to a complete score and does not erase available production evidence.

Further as-of review found an unsafe existing text-ID ordering fallback for
untimed events. The candidate no longer invents that chronology: same-draft
selection order uses numeric source pick order, otherwise unknown ordering
excludes affected assets from supported ownership and reports partial coverage.
A drafting roster is not assumed to be a traded pick's original roster. Missing
original-pick identity remains a coverage gap. Seventeen focused franchise tests
pass. The first new fixture invocation failed because it modified already-cached
source rows without advancing its fixture generation; after correctly advancing
that generation the intended missing-timestamp case passed. Preserve that failed
invocation. Prior real reconstruction proofs precede this additional boundary
correction and need affected focused revalidation, not a full-suite rerun.

Source follow-up resolved an important portion of that chronology: Sleeper's
completed draft has real start/last-pick timestamps. They are now retained as
selection **bounds**, including when reading an existing cache with matching
draft metadata. Exact selection `occurred_at` stays null. The affected real
trade, waiver and free-agent examples again have complete ownership coverage
and unchanged source-backed player differences. Selection 30 again adds 12505;
its broader state remains partial for overlapping events/original-pick identity.
All four reconstructions use zero provider calls; temporary caches were removed.

Completed normalization-v3 plus atomic-publication/index metadata proof:
23,052,288 bytes before and after unchanged replay (zero growth); 19,422 source
rows, 914 unresolved identities, zero missing game times. First run 13.516 s;
replay 1.672 s with zero new states and zero production rows re-examined.
Observed peak child RSS 86,966,272 bytes. Both workers reaped; temporary database,
source staging and lock files removed. The measured season is about 21.99 MiB,
within the unchanged 24 MiB/season planning estimate. A later bounded focused
selection passed 133 tests in 10.919 s; this is not the full release gate.

The canonical player facade also exposes scoped schedule/bye evidence. A current
catalog team cannot enter an explicit historical as-of response: historical team
selection uses an eligible selected-season game, or stays unavailable. No current
team, projection, price or prior-season production is silently substituted.

First canonical release attempt (run 5aa16a089fd545caa7d07945ea2f01f1):
whitespace, compilation, Ruff and dependency gates passed. Regression ran 1,507
tests in 571.509 seconds and failed one player-dossier assertion requiring the
obsolete text "No supported production-stat provider is configured". The Batch 2
source capability intentionally replaces that false claim with scoped canonical
evidence availability. Only that obsolete expectation is corrected; source and
thresholds are unchanged. Routes/HTTP/cleanup gates were not reached by that
attempt. Compilation also reported an inaccessible pre-existing ignored legacy
validation-worktree directory; no user-owned or legacy directory was removed.

After the fixture-only assertion correction, the focused player/API/provider
selection passed 16/16. Canonical run `3eef14fdd4ea4919a514a842ff959cb0` passed
all 10 gates in 715.967 seconds. Full regression passed (1,507 tests in the
unchanged test inventory), routes: 252 registrations, zero duplicates, 234
OpenAPI paths. Tracked HTTP validation passed in 114.540 seconds; process cleanup
passed. The earlier failed trace is preserved in ignored validation evidence.
Linux/browser CI, production backfill/reconciliation, restart and final cleanup
remain required; this is not a completed Batch 2 acceptance report.

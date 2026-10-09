# FOIS Evidence Integrity & Trust — v1.21.25 / build 2125

## Evidence and scope

Starting main matches v1.21.24/build 2124, commit `48047d204395b4d12ea638c32ecebb2fd0585c16`. Source and controlled cases reproduce the reported evidence-admission defects; they do not establish that a particular live manager grade is incorrect. The Codex audit artifacts and findings supplied from Scout are the evidence basis. Separate Scout FOIS audit and Product Blueprint files were requested but not available locally at implementation time. This release follows the explicit authoritative requirements supplied in this workstream and preserves scoring weights/model 5.1.

## Historical lineup

Spawn compaction previously omitted `normalized_players`, although the canonical historical identity store needs those fields for eligibility. It now retains the minimum complete identity projection (including supported birth dates used by historical age coverage), including players absent from current rosters. Historical player/week joins remain league-scoped and use player identity before franchise ownership. Prior-counterparty production can therefore support acquired players. Duplicate observations must agree. Future/intraweek actuals remain excluded.

The existing exact legal-lineup optimizer replaces the historical greedy loop. REC_FLEX, WRRB_FLEX, Superflex and supported aliases use canonical eligibility. Missing positions, unsupported slots, missing eligible-player weekly points or incomplete legal assignments produce unavailable impact, never supported zero. Complete evidenced zero is retained. Numerical source fixtures exercise full versus actual spawned computation and before/after admission; they are not live historical acceptance.

Controlled baseline replay reproduces full input at 22→14 points (DEFENSIBLE) versus compact input at unsupported 0→0 (SOUND); corrected source gives supported 22→14 and DEFENSIBLE in both paths. This is source verification, not live grade acceptance.

## Historical Market

Asset states retain provider membership, context, normalization version, value concept, scale, format, methodology, quote timestamp and checkpoint identity. The sparse-store adapter requires explicit producer comparison semantics; matching legacy context/version strings cannot establish units. Legacy observations remain stored, but cannot establish fairness without that identity. Exact asset identity stays separate from price units: the known canonical producer’s asset-specific pick/year/range fields do not make an otherwise compatible player/pick package incomparable. Provider format, normalization, scale and methodology remain comparison boundaries. Complete nonnegative finite prices on both sides must share the complete comparison identity and canonical Market concept. Same context alone is insufficient. Historical lookups retain at-or-before eligibility; exact picks need their own historical quote. Missing/partial/incompatible evidence withholds fairness and price-based behavioral support. No current price, generic pick estimate or raw-scale substitution is introduced. The older process-grade price-subset fallback is removed.

## Behavioral and Trade contracts

Independent transaction identity determines sample count. Asset counts remain separately inspectable; correlated acquisitions cannot inflate decision confidence. Price tendencies require complete comparable historical packages. Non-price transaction facts remain usable. A 64-entry LRU bounds generation-aware, league/franchise/manager-aware behavioral reuse.

The shared two-sided package vocabulary covers one-for-one, both orientations of one-for-two, multi-asset, player-plus-pick and pick-heavy. Trade matches that vocabulary using both sides rather than only received count; `mixed` is not blanket package support. Pre-integrity behavioral generations are not admitted as new historical-fit evidence. Historical fit remains soft context/tie-break evidence, with references and no acceptance percentage, price adjustment or strategy override.

## Manager-facing trust

Front Offices describes youth/veteran/pick holdings as current roster composition, not demonstrated acquisition preferences. Completed trade counts and observed periods replace selective/aggressive labels. Compatibility is explicitly uncalibrated and nonprobabilistic; acceptance probability remains unavailable even with bilateral trade history. Unsupported controlled-franchise switching is replaced by a link to authorized league Executive Profiles.

Poor records describe poor-results periods; explicit rebuilding evidence is required for rebuilding intent. Existing outcome-duration measurements remain separately described. Empty Results is unavailable rather than `None/100` or a claim that weakness was ruled out. Category-specific supported strengths remain visible without requiring an overall grade.

Own/opponent Executive Profiles expose supported behavioral dimensions, independent sample counts, coverage, confidence, asset counts and evidence references through native keyboard/tap disclosures. Long evidence tokens wrap in scoped evidence elements, preserving full selectable strings and specialized table behavior.

## Historical preservation boundary

**Existing pre-integrity assessment payloads, fingerprints, generated times and snapshots are not replaced by corrected evaluator output.** Startup, league hydration and background sync normally compute and publish FOIS. Repository publication now refuses to replace an existing pre-integrity score key; these assessments remain visibly marked **Retained / not revalidated**. Corrected current behavioral summaries can be prepared separately in memory without changing stored grades. New assessments use evidence-integrity contract `fois-evidence-integrity-1`; ordinary later refreshes of those new assessments remain supported.

There is no release-triggered bulk score regeneration, backfill, history migration or maintenance command. Existing normal retention/safety policy remains unchanged. Stored Trading grades could include previously unsupported lineup/Market evidence; Results could describe a losing period as rebuilding. These grades have not been corrected or newly validated. A later authorized regeneration must inventory affected records, preview differences and preserve provenance before publishing replacements.

## Exact lineage boundary

Future draft selections use additive `exact_pick_lineage` storage with league, draft, season, round and exact selection identity. Selecting roster and explicitly known original roster are separate fields; selecting roster does not establish original ownership. Missing exact selection identity fails closed. Repeated identical selections deduplicate; conflicting evidence is rejected.

Legacy `pick_lineage` is not scanned, migrated, merged or reinterpreted by this new writer. Existing ambiguous records remain as they were and need separately authorized review. Exact lineage is compact permanent intelligence, not a new historical snapshot system.

## Validation and production boundaries

Integrated evidence fixtures, actual route/browser checks at 320/375/390 and desktop (short and realistic portrait heights), account/league isolation, Trade regression, canonical release validation and unchanged 2 GiB lifecycle gates are required. Final results are recorded in the release report. Responsive Chromium is not physical iPhone/Safari.

Authenticated live manager/evaluation acceptance is not inferred from fixtures. Public production version/readiness can be verified; without an existing authorized authenticated session, private historical correctness remains an independent Scout check.

## Scout independent acceptance

1. Verify release build/commit and distinguish source fixtures from live history.
2. Confirm retained grades are labeled not revalidated and were not silently regenerated.
3. Inspect own/opponent behavioral disclosures: independent transactions, price coverage, references, confidence and limitations.
4. Front Offices: holdings labeled composition, no acceptance forecast or misleading franchise switch; current needs remain useful context.
5. Empty Results unavailable; losing history does not establish intentional rebuild; activity wording states counts/observed period.
6. At 320/375/390 and desktop, open long-code supporting evidence with pointer and keyboard; verify full text, focus, dismissal and bounded layout. Preserve leaderboard name/score spacing.
7. Source fixtures: full/spawned eligibility parity; incoming-player prior-franchise production; true zero versus missing; REC_FLEX/Superflex; partial coverage; historical Market scale/version/concept/time compatibility; independent behavioral samples.
8. Trade: package fit uses both orientations and references, remains soft, respects explicit strategy and cannot change canonical prices. Missing history does not veto a credible offer.
9. Sample Recommended/Next Five, Shop/Trade For, Create/Adjust/Cheaper, Calculator/Balance, Preview/Keep Original/Adopt, exact player/acquired-pick locks, ownership and navigation.
10. Source/storage fixtures: new exact selections are separated by league/draft/selection; legacy ambiguous records remain untouched. No production maintenance or Sleeper writes.

Record expected versus actual. Label live production, controlled source fixtures, responsive Chromium and physical iPhone/Safari separately.

## Recorded release validation

Final source: 78 affected focused tests passed; the 2,612-case full regression suite passed through the canonical validator. All ten gates passed: committed, working-tree and staged whitespace; compilation; Ruff; dependency integrity; full regression; routes/OpenAPI (260 registrations, no duplicates, 239 paths); canonical HTTP smoke; process cleanup. Retained-grade disclosures also passed 21 actual-route responsive/desktop views.

Unchanged 2 GiB Linux lifecycle gates passed with one compute worker: ordinary effective peak 1.310 GiB, archive-warmed 1.338 GiB, combined-read 1.321 GiB. Archive page cache reached the raw cgroup cap under the existing working-set accounting; no OOM or OOM-kill occurred. Recovery/quiescence positive/negative checks and 141 recovery/storage tests passed. Test containers and live local servers were cleaned up.

Controlled performance (15 sequential runs, not live latency): 500-trade cold aggregation p50 2.924→6.518 ms, worst 3.201→7.230 ms; warm bounded-cache p50 0.071→0.099 ms, worst 0.123→0.161 ms. Correct exact 32-player/11-slot historical lineup p50 0.082→4.964 ms, worst 0.167→17.115 ms. These costs replace cheaper incomplete/greedy work. A 16,000-identity synthetic catalog now retains a 1,662,737-byte compact input (previously 43 bytes with all identities omitted); compaction p50 6.377 ms, worst 18.935 ms. Cache generations are bounded at 64 entries after 100 builds. Prepared-profile route samples remained near 14 ms median with the same ten SELECTs; existing query/legacy cold-search optimization is outside this release.

GitHub CI, immutable publication, deployment identity and public readiness are reported after release. Authenticated historical numerical acceptance remains unverified here and belongs to independent Scout testing; retained grades are not claimed corrected.

The first lifecycle CI attempt and one justified retry failed before testing because Docker Hub returned HTTP 429. CI now pulls the official Python mirror pinned to the same Linux amd64 manifest digest (`97983fa8cc88343512862c62307159a82261c3528dc025f79e5a3f7af43e50b4`), verified against Docker Hub. Image contents, lifecycle commands, resource limits and assertions are unchanged; the Dockerfile default remains the existing Python tag.

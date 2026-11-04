# Phone Matchups & Standings — v1.21.31 / build 2131

## Authority and reconciliation

Starting main and read-only production both exactly match v1.21.30/build 2130,
`18701cf28d42668bbaf9ed5a94c5a86cd2b97aca`. No intervening main changes were found.
The current implementation instruction governs this scope. Richard clarified that
the detailed instruction incorporates the October 10 Scout planning handoff and
supersedes its earlier wait instruction. Blueprint v0.5’s older release checkpoints
are historical. The October 10 planning handoff was subsequently supplied and reconciled verbatim;
its original wait instruction is explicitly superseded. Standalone Blueprint and
reference screenshots were not present in the execution workspace; no pixel
comparison is claimed.

## Implementation and source contracts

- Reuses `services.matchup_season`, the canonical ProjectionService, prepared team
  strength, Matchup Desk, existing player dossiers, badges and primary navigation.
  No new valuation/projection/odds engine, backend endpoint or persistent store.
- Matchups default to the selected league’s supported current week. Previous/next,
  explicit selection and current-week return use normal URLs; navigation does not
  mutate the league week. Past scores never borrow current pregame projections.
- Compact two-column cards retain both team identities, avatar/initial fallback,
  actual scores, complete submitted-lineup projections, actual/projected leader,
  state and visible incomplete-coverage warning. The main card is a native link
  with no nested controls; secondary evidence is outside that link.
- A league-matched authenticated membership orders its matchup first and supplies
  “You”. Other matchups use stable identity order. Unknown opponents and no published
  own matchup remain explicit; playoff byes still require source bracket evidence.
- Detail aligns source starters by configured slots. Bench is visible; current-week
  IR/taxi uses the already retained roster assignments and adds current inventory
  missing from the weekly player list with unavailable weekly scores. Historical
  and future views retain weekly non-starters without inventing dated IR/taxi labels.
- Known player identities use the existing dossier, including opponent non-starters.
  `week` and validated `matchup` parameters provide a local return link. Unknown
  identities do not create broken dossier links. This is navigation, not impersonation.
- Official total comes from Sleeper matchup `custom_points` when supplied, otherwise
  `points`, never from summing the displayed inventory. Bench/IR/taxi do not enter it.
  Multi-week playoff component scores and complete round evidence remain disclosed.
- Player projections use the pinned compatible canonical Sleeper week publication.
  Underlying unrounded values and provider-owned display formatting are retained.
  Submitted totals sum only their source starters; incomplete evidence is unavailable
  with a known subtotal disclosed. Zero requires source evidence. Optimal legal-lineup
  totals are separately labeled **DTOS-derived**, expandable and never replace starters.
- Current source snapshot, actual scores, player projections and any eventual remaining
  estimate are distinct. No current actual + full projected contribution is summed.
  No unbounded polling, per-player provider calls or new per-week storage is introduced.

## Probability investigation

Sleeper’s retained matchup response contains roster/player actual points and submitted
identities, not a calibrated win probability. The existing pregame/live desks explicitly
withhold odds and players-remaining estimates. Current projections lack an approved
uncertainty distribution and supported remaining-game model. This release therefore
shows no numerical win probability. A projected-points share would not satisfy the
contract. A future probability feature needs validated uncertainty, game/remaining
status, calibration, source provenance and product approval; it is not a new player
projection model and is outside this release.

## Standings

One renderer powers prominent Home standings immediately after the franchise summary
and complete League standings. It shows franchise, record, PF, PA, “You”, supported
rank/medals, preceding-league-season champion trophy and completed-game streaks.
Source missing PF/PA no longer default to zero in synchronization; an existing scoring
parser preserves source precision and supported zero. Team-directory and HQ score
consumers also preserve unavailable PF/PA rather than crashing or displaying zero;
this is a narrow consequence of the source correction, not a team-intelligence change. Display formatting does not
change values. Official ranks require a complete unique Sleeper-reported rank set;
records/PF are never sorted into an invented official rank.

A playoff-position boundary requires complete official ranks, a valid qualification
count, explicitly zero divisions and standard playoff type. Division/wildcard/custom
or missing rules withhold the boundary with a reason. Current position is not clinching.
No rank movement is displayed without comparable official historical rank observations.
W/L streaks use only consecutive completed regular-season pairs with both official
scores and reset across unavailable evidence. Medal, champion and streak explanations
use existing accessible disclosures. Standings remain distinct from DTOS strength,
dynasty value, contender and FOIS rankings. Missing authoritative ranks are a source
limitation, not repaired with a synthetic ordering.

## Evidence and validation

Focused fixture/browser checks exercise current/previous/next/direct week selection,
full-card pointer/Enter activation, focus, own matchup order, league isolation, source
scores, zero/missing/partial projections, actual canonical publication, two scoring
contexts, submitted/optimal separation, flex/Superflex/REC_FLEX slot labels, full
inventory and dossier return, standings record/PF/PA, supported ranks/simple boundary,
division/missing-rule withholding, champion/medal/streak semantics and source changes.

Actual rendered router journeys run in Chromium at 320×483/844, 375×432/812,
390×677/844 and 1280×757. They require actual DOM hit-testing, keyboard activation,
visible focus, 44px primary card/player/return targets, keyboard-expanded lineup/source
disclosures (including full generation identifiers) and
no document overflow. Existing authenticated account/league A→B→A browser tests
remain release gates. This is responsive Chromium, not physical iPhone/Safari or
accessibility certification. Browser fixture source inputs are controlled, not live
manager/player acceptance.

Controlled warm before/after measurements use the same small fixture and baseline
source modules. Prepared overview/detail and week-selection costs (25 samples),
Home/League in-process HTTP (25), and idle 390×844 Chromium navigation to
DOMContentLoaded (five warm samples) are separate measurement boundaries.

| Operation | Prepared p50 before→after (ms) | Prepared worst before→after (ms) | Browser p50 before→after (ms) | Browser worst before→after (ms) |
|---|---:|---:|---:|---:|
| Overview | 0.143→0.112 | 0.221→0.214 | 36.507→37.380 | 82.739→61.629 |
| Week Switch | 1.036→1.155 | 1.641→1.874 | 35.791→36.400 | 40.169→49.933 |
| Detail | 0.121→0.187 | 0.436→0.304 | 32.810→38.434 | 39.821→78.924 |
| Home | 2.160→1.869 | 8.030→2.236 | 28.655→31.617 | 38.999→39.244 |
| League | 1.897→1.869 | 6.114→2.695 | 29.749→34.435 | 31.812→46.012 |

Dossier browser navigation p50 52.292→83.623 ms; worst 59.240→86.074 ms.
Warm authenticated league activation plus Home (10 isolated HTTP samples)
p50 7.659→7.979 ms, worst 16.743→9.102 ms. The unchanged actual canonical
horizon publisher on identical source evidence (10 samples per batch) measured
p50 4.279→3.341 ms, worst 6.318→5.255 ms; this is variation, not a new publisher.
An earlier run competing with regression observed a 705 ms detail-navigation
outlier; the idle recheck is retained separately and does not erase that observation.
No universal speedup or production internet SLA is claimed. Detail exposes more
roster content and dossier return loads the shared stylesheet. Navigation adds no
provider calls or database writes. Unchanged 2 GiB lifecycle gates validate the
production-shaped memory/worker workload separately.

The first full run exposed two inspection compatibility failures: missing starter
selectors and projection display semantics. Those were restored without changing
assertions. Additional expanded-source testing caught 320px generation-ID overflow;
the source disclosure now uses the existing wrapping evidence style and the expanded
state is part of the permanent browser journey. A subsequent source-consumer review found that the old team-directory formatter
could crash on unavailable PF, while HQ defaulted unavailable PF/PA to zero. Both
presentation consumers now preserve unavailable, with genuine-zero regression proof.
The final affected 52-test focus run passed.
The final canonical validator passed all ten gates in 733.910 s. Full regression
contains 2,671 discovered cases and passed in 723.031 s. Route/OpenAPI validation
reported 260 method registrations, no duplicates and 239 OpenAPI paths; tracked
HTTP and process cleanup passed. Documentation/architecture validation, authoritative
Ruff, compilation and final whitespace checks passed.

| Canonical gate | Result | Seconds |
|---|---|---:|
| Committed whitespace | PASS | 0.005 |
| Working-tree whitespace | PASS | 0.012 |
| Staged whitespace | PASS | 0.004 |
| Python compilation | PASS | 1.307 |
| Ruff | PASS | 0.107 |
| Dependency integrity | PASS | 1.016 |
| Full regression | PASS | 723.031 |
| Route/OpenAPI | PASS | 1.422 |
| Tracked canonical HTTP | PASS | 6.917 |
| Process cleanup | PASS | 0.089 |

All lifecycle runs preserve memory/swap limits of 2 GiB and one expected semantic
worker. Ordinary uses 12,322 assets/30,726 history records; archive-warmed and
combined-read use 12,322/461,166. No provider synchronization or production storage
maintenance occurs. Effective peaks and raw cgroup peaks are reported separately:

| Lifecycle | Effective peak (GiB) | Raw peak (GiB) | Result |
|---|---:|---:|---|
| Ordinary | 1.313 | 1.388 | PASS |
| Archive-warmed | 1.348 | 2.000 | PASS |
| Combined-read | 1.347 | 2.000 | PASS |

Archive/combined file-cache pressure reaches the raw cap; this is not concealed
as process-memory headroom. All three report zero OOM/OOM-kill events, zero
restarts and no gate errors. Linux maintenance/quiescence positive/negative checks
and all 141 recovery/storage/projection tests passed (14.909 s for the tests) inside
the unchanged 2 GiB disposable container. Existing ambiguous retained records are
not migrated, repaired or deleted. CI and actual deployment must still pass before
completion; production fixture/source results are not authenticated UI acceptance.

## Preservation and limitations

Trade algorithms, prices, projections, protections, preview/Keep Original/Adopt,
Shop/Trade For, freshness and strategy contracts are unchanged. FOIS historical
grades remain RETAINED / NOT REVALIDATED; no regeneration, migration, backfill,
lineup change, trade or Sleeper mutation occurs. Existing historical records remain.
A bounded pre-release read-only production/source check matched four Day Traders
Week 5 franchises across two matchups: official actual scores and submitted identities
matched raw Sleeper exactly. All ten raw roster settings lacked official rank; the
league reports six playoff teams, zero divisions and standard playoff type, but that
does not establish rank. A separate corresponding Sleeper projection feed check returned 3,117 accepted raw
rows; all 38 available sampled starter values matched production canonical values
exactly before rounding. The live inspection does not expose the retained raw
publication fingerprint, so this establishes contemporaneous sample equality,
not independent proof of identical raw source generations or every cross-page value.
These source observations are separate from canonical publication fixtures. Signed-in live UI acceptance belongs to Scout where
no existing authenticated browser is available. Historical/future IR/taxi assignments,
unsupported official rank/division qualification, calibrated odds and remaining-game
estimates are withheld, not fabricated.

## Scout independent handoff

Source/fixture reproduction: `python -m unittest tests.test_matchups_phone
tests.test_matchups_phone_browser tests.test_matchup_evidence_contract
tests.test_live_inspection`. These execute actual publishers, routers, Chromium and
canonical display reconciliation; they are not evidence of every live historical
score. The October 10 read-only source sample is Day Traders
`1313066632158924800`, 2026 Week 5: matchup 1 (rosters 4/10), matchup 2
(rosters 2/8). Select the authenticated franchise’s actual current matchup for
own-first acceptance rather than assuming this sample is Richard’s matchup.


1. Verify deployed v1.21.31/build 2131 and exact merge commit in Settings/readiness.
2. In Day Traders and Arkham, Home → Matchups: current week, own matchup first,
   side-by-side teams, official score and labeled submitted projection. Select past,
   current and future weeks; unavailable dated projections must stay unavailable.
3. Activate the entire card by pointer and keyboard. Compare starters in configured
   slots, scroll through visible bench and current IR/taxi. Official total must exclude
   non-starters. Check Superflex/REC_FLEX/custom slots and empty/unknown identities.
4. Open an opponent bench/IR/taxi player dossier; return through the matchup link
   and browser Back. Matchup/week must persist and player projection context match.
5. Home and League: compare record/PF/PA with raw Sleeper, “You”, rank availability,
   champion season/league basis, medals and W/L streak disclosures. Missing official
   ranks must not become list-order ranks. A withheld playoff cutoff is expected where
   ranking/division/tiebreak evidence is unavailable; no clinched label is implied.
6. Compare underlying player values for the same player/league/week/source generation
   across Matchups, dossier, My Team and Trade. Verify raw Sleeper source independently
   before claiming numerical parity. Optimal totals must be marked DTOS-derived.
7. Verify no unsupported win % or remaining estimate, and no actual/projection double
   counting. Refresh through existing normal infrastructure only; no player mutation.
8. Test 320/375/390 with short and portrait heights, plus desktop: no document overflow,
   readable aligned rows/PF/PA, visible focus, unobscured pointer targets and disclosures.
9. Recheck Trade live Market, Evaluate, Balance, previews/adoption, exact locks, automatic
   Shop/Trade For, Recommended/Next Five, projection freshness, selected strategy and
   FOIS retained-grade badges. No historical grade should be silently regenerated.
10. Report exact live identity/date, league/week/matchup, scores and projections, source
    provenance, result counts, timing boundaries, actual failures and unverified cases.
    Distinguish fixture/source checks, authenticated production, responsive Chromium
    and physical iPhone/Safari. Do not claim complete acceptance from unchanged grades.

# Batch 3 — Intrinsic methodology calibration checkpoint

## Supported-horizon profile and projection-zero correction

This supersedes the earlier claim that all 398 Market-covered players had real
numeric forecasts. Fresh field-presence inspection finds 319 projections and 79
empty projection-stat records. Mixon's 0.00 was generated from an empty stats
object, not a supported zero expectation. His Out designation is independent;
it must not transform missing source evidence into zero. No inferred causality.

Parser 2.1 returns missing for empty/unscorable stats; explicit numeric zero is
preserved. The canonical publication path also rejects older cached empty zeros.
Projection semantic policy advances to 3 so old published snapshots cannot be
accepted unchanged under the corrected contract. Focused existing projection
tests pass; this change invalidates relevant later release acceptance evidence.

Forward context distinguishes projected, supported_numeric_zero,
zero_with_unavailable_status (association, not provider-causality proof),
no_projection, provider_missing_player, not_applicable and boundary_mismatch.
Weekly zero never implies zero dynasty utility. Metadata freshness remains a
retrieval-bound observation, not a claim of independently verified role persistence.

Architecture decision for this candidate: expose an intrinsic evidence profile
beside independent external price, rather than claim the unvalidated historical
scalar is a standalone dynasty price. Profile axes: historical production quality
(excluding age), latest observed usage, current opportunity, current availability,
one-week expectation, position-specific longevity context and historical support.
No precise multi-year forecast is required in principle; the outstanding work is
validating how these heterogeneous horizons inform decisions, not inventing future
stats. A numeric utility/tier is unavailable until that mapping is defensible.

The regenerated 57-player panel retains rejected candidate scalar research for
traceability, clearly labels it rejected, and appends the current evidence profiles.
Love retains positive weekly evidence with missing historical quality. Kittle's
designation is not a recovery estimate. No per-player override is implemented.
Cross-engine migration and Market reconciliation remain required before release.

## Forward evidence audit — horizon remains an acceptance blocker

Current public Sleeper metadata and the existing canonical weekly provider were
queried once for the 398-player Market-covered set. All 398 had numeric weekly
projections, including explicit zero. The source's NFL state selected 2026 week 1;
the audit did not hardcode the season/week. Output is local diagnostic evidence.

The new pure forward-context boundary validates player, generation, observation,
expiry, season/week and reference scoring. It rejects nonfinite values, does not
backdate current status, does not zero-fill missing projections, and does not
convert depth order or questionable designations into arbitrary multipliers.
This boundary is not yet integrated into production consumers.

Source examples: Jonnu Smith depth 2 / 3.51 projected reference points; Mixon team
missing / Out / explicit 0; Kittle Questionable / 10.08; Love 13.25 despite missing
historical NFL evidence in the retained audit. These observations explain why
demonstrated historical quality must not be labelled forward expected value.
They do not prove long-horizon intrinsic utility or trading recommendations.

The active canonical service supplies weekly projections only. Legacy seasonal
fields found in calibration.py are disconnected noncanonical weekly extrapolations
and are explicitly excluded. No supported season/career forecast has been admitted.
Accordingly forward_dynasty_utility remains unavailable rather than annualizing
one week or inventing recovery/role persistence. A horizon-explicit supported
expectation/methodology is still required to finish the requested numeric layer.
The 57-player panel now includes the actual current-context decomposition. No
quality score was silently reclassified as an accepted dynasty utility.

## Tier and forward-role checkpoint (candidate 3)

Candidate intrinsic bands now have an independent API accepting only intrinsic
value. Market price, provider availability, league and confidence cannot alter
the band. Missing intrinsic evidence is Unavailable, not the lowest tier.
Proposed boundaries are 750/650/500/350/200 on the retained 0–1000 scale, labelled
quality bands rather than franchise/starter/league-fit promises. These are
diagnostic boundaries, not yet accepted empirical decision cliffs. Continuous
values remain unchanged across a band boundary; no tier-based boost is applied.
Market's existing tier policy has not been renamed or reused as intrinsic tiering.

Offline sensitivity over all 1,327 retained source-backed players passes sample
independence: equal production/usage across seasons with seven versus seventeen
games retains identical quality and tier while confidence changes. Production
perturbation of ten percent changes values by at most 33/1000; one year of age
changes values by at most 11/1000. These are local sensitivity checks, not a
forecast-accuracy claim. The old audit rounded age; replay differences of up to
one point are disclosed and must not be claimed as cross-version exact equality.

Supporting usage now reflects the most recent observed season rather than an
average of former roles. It remains bounded at ten percent before omission
renormalization. Missing latest usage cannot be filled from a former season.
This changes the methodology version to candidate 3; the maximum observed change
versus candidate 2 is 38 points (including at most one point of age rounding).
Multi-year production, confidence and position-specific longevity are unchanged.
This does not claim that last season's usage is today's verified depth-chart role.

Forward evidence audit: the prepared consumer projection is a league-scored weekly
Sleeper expectation. It is legitimate for short-term lineup/league utility and
team-window fit, but is not a standardized multi-year NFL projection. Feeding it
unchanged into global intrinsic quality would mix scoring formats and horizons.
Do not annualize one week, multiply it into a speculative career score, or backdate
it. A supported, fixed-scoring, horizon-explicit projection/role adapter is still
required before a numeric forward component can enter the global methodology.
Age and newest observed usage already affect the assessment; they are not prospect
priors. Rookies without NFL performance still have unavailable production-based
intrinsic evidence and may independently have meaningful Market/projection evidence.

Candidate 3 distribution (historical cohort, not published active-player ranks):

| Position | Count | Range | Median | Proposed top-band count |
| --- | ---: | ---: | ---: | ---: |
| QB | 159 | 51–722 | 391 | 0 |
| RB | 344 | 15–791 | 283.5 | 4 |
| WR | 541 | 22–801 | 298 | 4 |
| TE | 283 | 53–789 | 306 | 2 |

The absence of a QB in the highest proposed band is a calibration review item,
not authorization to inflate QB quality or insert Superflex into intrinsic value.
True cross-position replacement/format utility, Market disagreements, current-role
eligibility, outlier classification and downstream promotion remain incomplete.
Do not declare the proposed bands stable or publish diagnostic rankings yet.

## Multi-year correction checkpoint (candidate 2)

The following section supersedes candidate 1's shrinkage and one-season findings
below. This remains a diagnostic model, not promoted production behavior.

- Quality no longer shrinks toward 40 because a player has fewer games. Equal
  measured quality produces equal intrinsic value; sample depth affects confidence.
- Four recent observed seasons use separate recency curves: QB 1/.8/.6/.4;
  RB 1/.55/.25/.10; WR 1/.7/.45/.25; TE 1/.8/.55/.35. These remain explicit
  candidate assumptions requiring stability/cohort validation, not fitted facts.
- Season blending caps game-count influence at eight games. A short season cannot
  erase previous productive seasons; absent seasons are omitted, never zero-filled.
- Up to eight compact summaries establish career depth; only four recent observed
  seasons influence quality. Missing recent seasons reduce confidence and disclose
  that older quality does not prove current health/role. No injury is inferred.
- A seven-game and seven-year player with identical observed quality have the same
  intrinsic value, different confidence. Rookies without scored evidence remain
  unavailable, not negative or invented prospects.
- The existing 0–1000 scale and production transform constants are unchanged.
  Removing confidence shrinkage alone materially resolves compression. No constants
  were tuned to Daniels or another player.

Read-only 2022–2025 audit: 981 scored players (127 QB, 258 RB, 398 WR, 198 TE).
Ranges: QB 64–722, RB 15–790, WR 22–800, TE 78–793. This is a historical scored
cohort and includes players who may not be current active assets. It must not be
published as today's global dynasty leaderboard. Diagnostic evidence is retained
only in ignored local validation material; no rankings were published.

Remaining calibration: current-active cohort eligibility, position-aware tier
boundaries, role/usage trajectory, supported forward-looking evidence, sensitivity
to alternative windows and Market disagreement classification. Multi-year canonical
consumer integration is not yet complete. Do not declare Batch 3 done.

Canonical preparation now supports eight bounded seasons in one read transaction,
with compact regular-season reference summaries. It preserves the narrower existing
two-season reader contract, admits only published facts known at the requested
boundary, excludes unknown/postseason classifications from the reference model,
and performs no provider calls or durable writes. A revised historical fact changes
the generation; an unchanged later read does not. Current/previous league-scored
windows remain separate. Focused model/preparation/stream coverage: 28 tests pass.
This is preparation plumbing, not promotion of the candidate numeric model.

Expanded source audit: seven completed seasons (2019–2025), 1,327 scored players,
120 unresolved/ambiguous source rows retained as gaps. Compact public-source
summaries are saved only in ignored `.validation` for subsequent offline cohort
analysis; no raw per-league duplication or public ranking publication occurs.
Sleeper's `active` flag alone is not a proven current-roster eligibility rule:
1,320 historical scored players retain that flag. Do not silently label this
historical cohort the current dynasty universe. Current team/status and evidence
recency require separate availability/eligibility treatment, not a production
quality penalty or fabricated rookie values.

Tier incompatibility is confirmed in `valuation/calibration.py`: without Market
evidence, the existing classifier cannot grant Elite/Cornerstone at any numeric
value and requires 850 even for Core Starter. That is an evidence-price coupling,
not a reason to inflate intrinsic values. Intrinsic tiers require their own
methodology-bound contract; confidence and Market availability must be disclosed
separately. No legacy tier policy has been silently changed in this checkpoint.

## Prior candidate evidence (preserved)

Status: candidate research and focused proof, **not promoted to production**.
No player-specific overrides; no Batch 4 work. Current numerical consumer model
has not been replaced by this candidate yet.

## Actual shape

| Concept | Candidate role / preserved separation |
| --- | --- |
| Market price | Normalized external price benchmark. Zero weight inside intrinsic quality. A market-anchored negotiated price is not renamed intrinsic value. |
| Production | Primary intrinsic performance input, scored under fixed PPR/4-point passing reference rules, not the active league's scoring. |
| Usage | Smaller supporting role signal from the same sample; not an independent confidence vote. RB carries + targets; WR/TE targets. QB comparable usage remains unavailable. |
| Age/lifecycle | Position-specific longevity adjustment. RB curve declines faster than QB/WR/TE. Young age alone cannot create an intrinsic score. |
| Projection | Excluded from this dynasty-quality candidate; belongs to short-term assessment and league-scored lineup utility. Existing consumer migration remains required. |
| Format/scarcity | Excluded from global intrinsic quality. Superflex QB demand, league size and replacement supply belong to league utility. Broader utility calibration remains pending. |
| Team fit | Roster need, competitive window and owner context are not global model inputs. |
| Confidence | Sample support and known metadata; explicitly not outcome probability. A small sample has lower conviction and disclosed shrinkage. |
| Missing evidence | No scored NFL sample yields unavailable intrinsic quality. A rookie can still have Market evidence without invented NFL production. |

Candidate numerical components are production 75%, supporting usage 10%, lifecycle
15%, with unavailable components omitted. Production uses a smooth saturating
transform and a six-effective-game shrinkage prior. These are transparent initial
assumptions, **not empirically fitted or accepted coefficients**. The output and
every component reconcile; the model contains no player identity, Market price,
league, account or owner parameter.

## Canonical preparation

The existing bounded fact stream now derives a fixed reference-scored summary
alongside league-scored summaries. No second SQL read or durable raw-fact copy is
introduced. Reference generation excludes league scoring; league generation still
changes correctly with scoring. Wrong-league access is rejected. The adapter version
advances to v2 so existing generation caches cannot mistake this for the old shape.
Previous-season evidence remains explicitly previous-season; it never fills a
missing current-season actual.

## Read-only source audit, September 9, 2026

Sources: [Sleeper public player catalog](https://api.sleeper.app/v1/players/nfl),
[existing DynastyProcess ID crosswalk](https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv),
[nflverse 2025 weekly statistics](https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2025.csv).
nflverse attribution: CC-BY-4.0. Only regular-season rows were considered.

The first audit used Sleeper's GSIS fields alone and left 4,870/6,037 rows
unresolved. It is retained as incomplete evidence, not used for calibration.
Using the repository's exact-ID crosswalk resolved all requested panel players;
12 rows remained unresolved/ambiguous and were excluded without name matching.
Crosswalk-level ambiguity: 11 GSIS IDs and four Sleeper player IDs. Those counts
are not a claim that all 12 excluded rows were ambiguous.

The scored cohort contains 601 players: 81 QB, 148 RB, 239 WR, 133 TE.
This is a matched prior-season statistical cohort, **not an accepted active-global
dynasty ranking**. Current birth dates/metadata are used for today's assessment,
not represented as historical knowledge-at-the-time.

| Position | Candidate range | Median |
| --- | ---: | ---: |
| QB | 326–619 | 457 |
| RB | 214–679 | 392.5 |
| WR | 227–691 | 408 |
| TE | 268–709 | 414 |

Daniels's candidate assessment: 527/1000, QB22, overall 119 in this cohort;
seven games, 16.04 reference PPG, age 25.73, confidence 39. Contributions:
401.5475 production + 125 lifecycle. QB comparable usage is omitted. This is
neither a manual override nor a finished production rank.

Other candidate panel values: Hurts 588, Burrow 535, Henry 546, Jefferson 572,
Chase 665, Bowers 639, Kelce 569, Jeanty 615, Hampton 580. They are diagnostic
outputs, not endorsed final valuations or expected test targets.

## Why this candidate is not promoted

- The entire scored cohort peaks at 709; blindly retaining existing 790-point
  elite tier boundaries would suppress every elite label. Distribution and tiers
  must be calibrated together, not patched for a named player.
- The current two-season production adapter supplies one completed season in the
  preseason. Multi-year stability and injury-shortened season behavior need a
  broader evidence assessment before describing this as complete dynasty quality.
- A common reference performance score is not yet full positional replacement
  utility, league-size demand, short-term projections, or team-specific fit.
- Existing consumers still use competing numerical formulas. Their migration and
  methodology-aware trends must follow acceptance of the shared model.

Focused proof: 12 name-free model tests cover broad position/age/production grids,
rookie/veteran missingness, real zero, production dominance, bounded usage influence,
smooth birthdays, position curves, small-sample confidence, temporal/reference
rejection, contribution reconciliation and fresh-process determinism. A separate
canonical-store test proves differing league scoring leaves reference results
unchanged without additional global records. No comprehensive gate was run.

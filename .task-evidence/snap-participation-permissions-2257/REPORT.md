# Snap participation — permission review held

Status: **HELD before implementation**. No application change, ingestion, release,
deployment, production sync, league entry or Trade search was performed.

## Verified baseline

Fresh public readiness and GitHub main checks on November 15, 2026 agree:

- v1.22.42 / build 2257.
- Commit `66a54635df075b2a120606ae3e6e3e5a96bd7b21`.
- Application tree `129b9423d529d3a5fea70603474f22088a662389`.
- No existing snap feature branch or related open feature PR was found.
- `v1.22.43` had no Git tag at observation time. It is not reserved by this review.

See `CAPTURE_RECEIPTS.json` for exact fresh-check times, commands, exit statuses
and source filenames. Source document captures are public documentation, not
authenticated owner observations. The readiness request is a public live check.

## Specific unresolved permission boundary

The prior source-specific audit at
`docs/BATCH2_CANONICAL_DATA_FOUNDATION.md:116` explicitly leaves PFR-origin snaps
NOT CONNECTED until the Sports Reference data-use question is resolved.
This review found no evidence resolving that question:

1. The nflverse-data repository publishes a CC BY 4.0 license. This is a data
   repository license, not merely the downloader's code license.
2. nflreadpy says the majority of nflverse data (all except FTN as of July 2025)
   is broadly CC BY 4.0. That affirmative statement is preserved in full.
3. nflreadr and nflverse say: “NFL data accessed by this package belong to their
   respective owners, and are governed by their terms of use.”
4. The snap loader expressly identifies Pro Football Reference as the source.
5. Sports Reference's current data-use page says users should not create websites
   or tools based on data scraped from its sites without permission. It also
   explicitly acknowledges that facts can be reused in accordance with copyright
   law. Both statements are preserved; this review does not declare all reuse
   prohibited or make a legal determination about DTOS.
6. Public nflverse-data issue 106 asks specifically whether CC BY covers snap
   counts and third-party restrictions. At this review it is closed with zero
   comments. Closure is not an affirmative permission grant or a refusal.

The unresolved fact is whether the broad nflverse license suffices for this
PFR-origin dataset's automatic retention and customer display in DTOS despite
the upstream terms. Technical accessibility, attribution alone, and an existing
approval for different nflverse statistics do not resolve this specific prior
review finding. No new approval requirement is inferred for all other sources.

**Smallest next action:** obtain source-specific clarification from nflverse or
Sports Reference covering DTOS's periodic acquisition from nflverse releases,
normalized game-level retention, and attributed customer display, or an authorized
rights determination resolving the conflicting documentation. No purchase,
credential change, provider contact, or acceptance of new terms was made here.
Resume implementation against the then-current production baseline when this
source-specific question is resolved.

## Verified source shape and lifecycle (source inspection only)

- Published schema includes game ID, PFR game/player IDs, season, week, game type,
  historical team/opponent, and separate offensive, defensive and special-teams
  counts and percentages. It does not establish routes or route participation.
- Fresh GitHub asset metadata matches the supplied 2026 CSV research size
  (1,147,455 bytes) and SHA256
  `ba54197d9e1e9a5473153f984f4880e736020c9e20565d1df246bf1e62714866`.
  The actual CSV was not downloaded or parsed in this task. The supplied row
  count and Bijan example were not independently reverified.
- Existing exact-ID resolver recognizes PFR, but crosswalk enrichment currently
  supplies GSIS only. No name joins were added.
- Existing global worker runs in its admitted isolated subprocess and shared
  evidence store. Snap ingestion is not connected.
- Existing scheduler starts after a 30-second delay and requires a source season
  and startup completion. After a run, it waits six hours, except a `deferred`
  result selects a 30-second delay. Failures currently use the six-hour interval.
  These are existing global-worker settings, **not a maintained snap feed**.
- nflverse documents upstream PFR updates at 00:00, 06:00, 12:00 and 18:00 UTC
  during the season, dependent on PFR availability. This is not a real-time feed.

## Completion and limitations

No feature tests, memory measurements, successive-revision tests, rendered snap
controls, canonical release suites or publisher workflow were run. With no
implementation, those cannot establish a pass. Existing application bytes,
thresholds, reserves, fantasy scores, projections, saved state and account
boundaries are unchanged. There is no claim of live snap coverage, live parity,
physical-device acceptance or customer recovery.

The source captures and checksums are the deliverable for this held review.
Earlier research observations remain observations; they are not new measurements.

## Sanitized Scout handoff

1. Verify `SHA256SUMS` against these downloadable files.
2. Confirm the source-specific conflict above, including nflverse's affirmative
   data-license statements and Sports Reference's fact-reuse caveat; do not treat
   the issue's closed status as permission.
3. Confirm production remains build 2257 at the cited commit using public
   readiness, without entering a cold league or initiating work.
4. Do not expect snaps in the dossier or describe an automatically maintained snap
   feed as delivered. No such code was shipped.
5. Once the permission question is resolved, the implementation still needs the
   exact-ID ambiguity controls, bounded automatic refresh/corrections/recovery,
   temporal and cache-generation tests, resource measurements and all mandatory
   release gates requested by the owner. No release gate is waived by this audit.

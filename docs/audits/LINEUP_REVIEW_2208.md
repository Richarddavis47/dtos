# Build 2208: prepared lineup review and actionability

## Contracts and implementation

The weekly source starter array remains the submitted lineup, in exact source
slot order, including explicit `0` empty slots. The analytical optimum remains
the existing independently prepared highest-projected legal lineup. No solver
mathematics, projection, trade verdict or valuation policy changes.

An explicit empty submitted slot leaves the full submitted-lineup projection unavailable; its player projection remains missing. A separate, labeled named-starter subtotal supports only the review comparison when every nonempty starter has compatible scoring evidence. The empty slot has no player contribution. A truncated starter array, unresolved
player or missing player projection does not become zero. All configured slots
must be accounted for before the submitted total can support a comparison.

`src.core.intelligence.lineup_review` is a pure consumer, not another optimizer. It checks
an already prepared optimum against the actual current source assignments.
It reuses NFL game facts from Team Strength's existing bounded background
schedule read; no schedule read, provider request or solver is added on ordinary
navigation. The new compact schedule map is held once per existing bounded
league profile, not persisted as a separate analytical warehouse.

A positive alert requires: current active NFL week; a supported manual-lineup
league (no best ball or enabled automatic-substitution policy); complete
comparable totals and a positive displayed gain; exact compatible weekly
projection rows; current owned/non-IR/non-taxi players; source/current starter
agreement; verified names and eligible assignments; and recorded future kickoffs
for every player being moved. NFL team, fantasy eligibility and participation are rechecked against the current exact-ID catalog; a transition cannot reuse a former team’s game lock. Only regular-season game facts may establish fantasy Week 1–18 locks. A nonzero current-week player score also suppresses a proposed move when it contradicts a future recorded kickoff; genuine zero does not prove that a game is unstarted. Unknown participation, missing game times, started
games or stale/missing acquisition times fail closed. Unchanged locked starters
may remain in the same slot. Repeated identical slots are matched to unchanged
starters before assigning the remaining prepared entries.

Roster retrieval and projection preparation must both be at most 15 minutes
old. This is a conservative alert-admission limit, not a new projection freshness
claim or provider polling schedule. A failed projection refresh retains valid
numbers but suppresses an actionable alert. Read-time lock revalidation uses the
request clock. An open browser retracts the imperative suggestion at the earliest
affected kickoff or evidence-age deadline, and on returning to the tab, using
one local timer and no network activity. A monotonic navigation-age deadline also prevents a slow customer wall clock from extending the verified window; counting response transfer conservatively shortens it. Sleeper remains authoritative at actual
submission; DTOS does not submit, reserve or change a lineup.

We intentionally do not solve a second, lock-constrained lineup on navigation.
If the prepared unconstrained optimum cannot be legally applied, a different
improvement might exist; DTOS shows the supported comparison as informational
instead of endorsing an unverified change. No improvement yields no positive
alert. Missing evidence yields an explanation, never a fabricated gain.

## Presentation

Current Matchups shows the controlled manager's review before matchup cards.
My Team shows a positive, independently qualified review directly after the
accepted early outlook; unsupported states do not add repetitive My Team cards.
The full submitted roster remains separate. Optimal disclosures resolve exact
canonical IDs to names and position labels in Matchups and Team Strength.
Unknown/conflicting identities use “Player name not verified”; IDs remain in
internal data and contextual links. No name-based athlete substitution.

Matchup rows now apply the existing shared player/week/season/scoring/source
conflict check, as well as weekly parent identity admission. Prepared optimal
entries are also checked against the selected leaf before presentation. Current
head and future leaf snapshot identities follow the existing ProjectionService
contract; they are not incorrectly treated as identical IDs. Independent valid
future/current comparisons remain independent.

Bye, current Out/inactive and unassigned-NFL-team notes reuse existing prepared
facts. Numeric zero remains numeric. ADP-only records are described as records
without usable scoring statistics, not proof that every Sleeper interface lacks
projections. No hard-coded classification for a named player.

## Live evidence limits and needs discrepancy

The connected browser requires app reauthentication. The prior configured
inspection credential returned 401; no authentication bypass or account mutation
is permitted. Source evidence from build 2207 is a read-only provider observation
at 2026-10-28 ~17:52 UTC, not the original production publication.

That replay had 7/10 complete supported optimal lineups and 0/10 complete needs
assessments. Needs requires supported replacement-pool evidence and qualified
availability; a complete supported starting lineup alone is insufficient. Scout's
reported 3/10 live count has no matching publication/time attached in this task.
The difference cannot be attributed to a software defect or claimed to be
resolved without matching source generations and preparation state. No count is
forced to equal the lineup population. The previous 182.03 production total is
not substituted with the later replay's 185.4278.

The retained source observation for Hurts, Marks, Collins, Hill and Restrepo
contains ADP-only Week 8 rows at the inspected canonical projection endpoint.
The schedule supports HOU Week 8 bye context for Marks/Collins; Hurts was listed
IR/inactive; Hill's player record had no NFL team; Restrepo was active with TEN
Week 9 bye. These are timestamped observations, not permanent classifications or
a claim about every Sleeper endpoint. The new presentation derives reasons from
the currently admitted facts, not those names.

## Verification and release boundary

Synthetic publication -> preparation -> HTTP -> rendered Chromium controls cover
empty/source lineups, +0/positive/missing values, lock and freshness suppression,
FLEX/Superflex, source conflicts, current/future separation, exact names, expiry,
keyboard/pointer/emulated touch and account/league context. Existing complete
security tests remain required. Controlled Chromium is not a live signed-in
Day Traders walkthrough or physical iPhone/Safari acceptance.

Release requires the exact final source tree to pass the full canonical
validator (all ten gates), hosted Product/security/tooling and existing enforced
resource/lifecycle controls. Failed, incomplete and skipped attempts must remain
in the independent handoff. Passing synthetic resource gates is not a broad
production-capacity clearance; prior raw fixture-preparation peaks remain
qualified separately. No production accounts, rankings, lineups, trades or
retained FOIS grades are changed during acceptance.

Official Sleeper lock reference reviewed:
https://support.sleeper.com/en/articles/3473234-why-was-someone-able-to-drop-their-starter-after-they-have-played
A starter's slot remains locked after kickoff, including the off-roster case;
a new player needs an eligible open slot before their own kickoff. The review
therefore rejects source/ownership mismatches rather than reconstructing a
hypothetical action across an off-roster locked starter.


A focused evidence disclosure expiring originally returned focus to the document
body. Expiry now moves only that hidden control's focus to the existing visible
Review in Sleeper link and exposes a status announcement; focus already on a
visible action remains there. The unchanged complete Product list reached 505
cases before its previous 16-minute deadline, with no assertion-failure output.
Its bounded test budget is 20 minutes (22-minute job), preserving all assertions,
coverage, 2 GiB controls and the independent 500 ms liveness requirements.


The full Product run completed 539 tests and caught an introduced empty-slot
availability regression: the existing full submitted projection must stay
unavailable with an empty slot. That contract and its existing assertion are
preserved. `lineup_review_baseline` is a separate known-contribution subtotal;
it supports filling explicitly empty slots but cannot fill an unknown player's
projection. The alert and team card label this subtotal rather than claiming a
complete submitted-lineup projection.

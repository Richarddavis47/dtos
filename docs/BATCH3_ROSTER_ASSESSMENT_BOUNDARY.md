# Connected roster assessment migration

## Current trace and intended questions

| Boundary | Current inputs | Intended question | Migration requirement |
| --- | --- | --- | --- |
| Player Dossier value models | Age, NFL team, format, injury designation; canonical facts disclosed separately | What evidence supports this player's demonstrated quality and current opportunity? | Remove age/team-derived dynasty and synthetic two-year scalar; expose evidence dimensions, with availability. |
| Player value/projection adapter | Legacy dynasty plus Market calibration; weekly points converted to value | What is the external acquisition price, and what is the supported weekly expectation? | Keep price and weekly units distinct; no contender/rebuild scalar derived by mixing them. |
| Roster cards / position rooms | Calibrated trade price relabeled dynasty; proxy floor/ceiling; weighted card grades | What is the room's production, legal-lineup contribution, depth and evidence coverage? | Aggregate each concept independently; unsupported overall grade stays unavailable. |
| Team Intelligence | Starting-lineup dynasty, contender/rebuild totals, room grades, picks | How competitive is the franchise under its league rules? | Stop aggregating the ambiguous player scalar into every horizon. Preserve pick evidence as a distinct dimension. |
| Competitive Window | Current/overall/future/depth/youth/capital/risk strength indices | Is one supported team-level contender/retool/rebuild conclusion possible? | Missing required dimensions cannot become zero, rebuilding, or an alternate scalar. |
| Team HQ / unified recommendation | Shared TeamAssessment plus remaining legacy cards | What is the canonical assessment for this league/franchise/generation? | Consume one complete assessment, with explicitly labeled dimensions and one overall conclusion. |

The orchestrator already replaces unified recommendation window/outlook from
`roster.assessment`. This shared publication point must be preserved; generating
another independent headline assessment would reintroduce the contradiction.

## Implemented foundation

`RosterEvidence` is pinned to league, franchise, evidence generation and projection
generation. It reads only canonical same-week points. Actual starter identities
and their projected total are separate from the optimal legal projected lineup.
It reuses the existing optimizer and never changes submitted slots. Partial legal
lineups or missing eligible-player projections cannot be advertised as a complete
optimal projection. Market/legacy metadata cannot fill missing points.

TeamAssessment now carries this evidence. Roster metrics expose separately named
actual and optimal projection totals. Existing weekly floor/ceiling evidence remains
separate; it is never inferred from a strength score.

CompetitiveWindow accepts explicit missing required inputs and returns Unavailable,
zero confidence, and absent championship/playoff/rebuild scores—not a rebuild label.
Existing supported-input classification formulas are unchanged.

## Active integration

The existing `roster_grading.py` boundary is now invoked by the active
`evaluate_roster` path. The old player-score/room/team arithmetic has been removed.
One pinned context supplies every franchise's grading inputs. Team cards carry
league and generation, and TeamAssessment rejects a mismatched card.

The active player value adapter no longer calibrates dynasty value against Market,
converts weekly points into a dynasty score, invents a two-year outlook, or fills
missing lineup comparisons with zero. The original age/team/format scalar has
also been retired at its source. Missing player portfolio utility propagates into
the old future/asset-health adapters as unavailable.

Market asset strength and production quality have named fields. The historical
`dynasty` field remains unavailable; it does not secretly contain Market strength.
Team HQ displays the explicit dimensions and canonical actual/optimal evidence,
not competing legacy diagnostic grades. Its unified recommendation still uses
the same TeamAssessment. Current lineup can be strong while longevity is weak;
neither becomes a manufactured overall contender/rebuild grade.

The existing legal optimizer selects optimal starters and a separate useful
backup lineup. Actual submitted starters remain untouched. The independent
canonical pick model is retained as Future Capital.

Cache changes:
- assessment cache namespace includes the grading-method boundary;
- TeamAssessment validates card league/franchise/generation;
- crawl schema is 2.0 and its response cache includes evidence generation;
- unsupported cached intrinsic/global-adjusted ranks are not republished by the
  player view adapter.

Active-path tests exercise the real orchestrator and Team HQ/dossier builders:
contrasting asset/lineup, age/lineup and depth/starter rosters; missing/partial
evidence; franchise and league switching (overlapping IDs); generation change and
unchanged replay; unavailable overall/window instead of competing A/F headlines;
and rejection of an old-generation card.

## Remaining release blockers

This integration is not full Batch 3 acceptance. Final representative Market
panel, trend/methodology boundaries, remaining legacy-consumer review, route-wide
focused regression migration, real production/storage evidence and comprehensive
release gates remain open. Do not declare the consumer ledger clean merely
because the active roster grading path is now integrated.

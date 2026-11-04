# Team HQ assessment provenance and correction — v1.13.7

## Before-state evidence

Authenticated secondary Team HQ repeatedly showed A / Elite Contender alongside
Rebuilding, floor/ceiling 0/100 and F50/F48 recommendation outlook. Real B-A-B
switching restored correct franchise, rosters, picks and Market ownership. That
isolation evidence remains valid. No leak was established.

The original failing page did not expose its internal cache key or generation.
Those exact historical identifiers cannot honestly be reconstructed from HTML.
Observed synchronization boundary was 2026-09-06 18:28 UTC. An attempted read-only
projection-audit navigation was blocked by the browser client, not an HTTP product
failure; no credential was extracted and no transport bypass attempted.

## Source mapping

All fields start with request-selected `require_data`, selected league ID and roster
ID, then `IntelligenceOrchestrator.analyze`. The same result supplies both paths;
there is no independent Team HQ database query for assessments.

| Conclusion | Previous source | Inputs / fallback | Corrected consumer |
|---|---|---|---|
| Header overall grade | Team Intelligence percentile grade | Valuation, starters, depth, picks, youth relative to league | Same canonical TeamIntelligenceCard |
| Header competitive window | build_competitive_window | Current/future/overall percentiles, depth, risk, confidence | Same contract, shared by assessment/recommendation/roster |
| Rebuilding identity | roster `_identity` | Legacy current score below55 | Shared canonical window, not another classifier |
| F current recommendation | Decision Engine current_outlook | 35%record/35%points/30%maxPF; preseason neutral50, strict absolute letter scale | Shared current-contending relative grade; old result diagnostic explicitly labeled |
| F future recommendation | Decision Engine future_outlook | 55%age-based player proxy /45%pick proxy | Shared Team Intelligence future percentile; old coverage diagnostic explicitly labeled |
| Weekly floor/ceiling | active PlayerCard averages | Missing bounds converted to0, scaled to0–100 | Complete starter sums from pinned canonical projection; absent/partial/wrong-week remains null |
| Position room letters | active absolute room score | Different from league-relative header scale | Canonical league-relative position grades |
| Projected lineup ranking | legacy proxy league-card sums | Not actual Sleeper weekly forecast | Not presented as weekly projected rank |

The old current/future and position formulas are retained as separate diagnostic
dimensions or internal compatibility inputs, not silently relabeled canonical.
The Team Intelligence percentile/competitive-window formulas themselves are unchanged.
No confidence claim is added merely because multiple consumers now agree.

## Proven causes versus uncertainty

Proven: competing absolute/relative engines; preseason neutral baseline graded F;
missing projection bounds coerced to zero; publication-week check using general
league week; cache omitted projection and Brain generations. Cross-process/route
selection is not assumed wrong. Exact runtime presence of valid projection bounds
at the old failure was not retained; missing bounds may be legitimate. The fix
must preserve unknown rather than invent an uncertainty interval.

## One boundary

`RosterReport.assessment` and `IntelligenceResult.team_assessment` are the same
immutable TeamAssessment. It includes league, roster, opaque generation, canonical
TeamIntelligenceCard, projection snapshot/week/as-of, covered/expected starters,
points/bounds and limitations. Team HQ and unified recommendation consume it.

The cache remains `snapshot:<context.snapshot_key>:<stage>` with bounded TTL. Its
identity now also contains already-published league source generations, Brain
semantic generation, and projection snapshot ID. No request-thread provider call,
database query, archive read or whole-dataset digest is added. The projection
snapshot is read once under its existing lock and retained by reference through
the assessment; publication during computation cannot mix rows from two snapshots.
An existing in-flight old generation may finish coherently; the next lookup uses
the new key. Wrong-league snapshots fail closed. Per-league state is never copied
from the global fallback merely because an unrelated league lacks evidence.

Current roster-strength percentiles are not actual weekly points. Missing or partial
starter evidence cannot become a full lineup total. Real canonical zeros remain
zeros. Missing uncertainty bounds are not inferred from point estimates.

## Validation

Focused regression covers snapshot pinning, projection/Brain invalidation, effective
preseason week, unavailable bounds, genuine zero, B-A-B equivalence, foreign snapshot
rejection and shared assessment identity. Existing trade/roster/window/isolation and
browser suites remain required. Full canonical/Linux/production gates must pass
before release completion. DINS/Current Visual/Mirror remain retired.

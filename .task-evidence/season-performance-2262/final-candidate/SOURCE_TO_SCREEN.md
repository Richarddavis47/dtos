# Season results: source to screen

| Evidence family | Shared path and behavior | Boundary |
|---|---|---|
| Official record and standing | Existing Team Headquarters/standings source logic, retained unchanged; record now links to season details | Source cumulative records are not reconstructed from sampled weeks; unresolved standings remain unresolved |
| Team scoring | Prepared Sleeper league matchup rows → season_performance → My Team / Home | League/season/scoring/calendar/methodology must match; native custom score overrides precede base points |
| Comparative scoring | Same observed weeks across the full configured unique franchise cohort | Missing peer coverage withholds the league average; no unfair rank or inferred overall strength |
| Recent team weeks | Existing completion calendar, plus existing prepared playoff participant resolver | Missing expected weeks are explicit; bye placeholders are not played-team observations; unknown bracket context withholds recent scoring |
| Retained/corrected results | Existing publication lifecycle and semantic generation → stateless read, existing Home cache generation | Failed refresh retains qualified last-valid rows; a correction requires a genuine new publication, never current-player reconstruction |
| Current roster outlook | Existing qualified projection/needs/capital evidence, unchanged | Actual season scoring never supplies a projection, contender/rebuilder label, Trade score or manager intent |

The feature closes a presentation gap: native season team scores already existed on Matchups but were not consolidated beside the franchise outlook. No new upstream acquisition or provider fallback is added. Genuine missing/incompatible scores remain missing. This task has no authenticated owner-publication capture; supplied live context from prior tasks is not replayed as current evidence. Deterministic literal-source controls are fixtures, not proof of actual league totals.

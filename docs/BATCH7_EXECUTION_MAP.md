# Batch 7 execution map

Baseline: v1.20.0 / build 2000. Scope: season operations and final integrated acceptance.

Authority: Richard's Batch 7 specification and Product & Intelligence Blueprint
v0.5, with later settled Batch 1–6 contracts taking precedence over historical
blueprint implementation status. Current Visual, DINS and Mirror remain retired.
The original blueprint files and unrelated local acceptance artifacts are preserved.

## Existing implementation — preserve

| Area | Active implementation | Batch 7 disposition |
| --- | --- | --- |
| League calendar | `src/core/intelligence/season_calendar.py` | Verify lifecycle boundaries and settings isolation |
| Full-season matchups | `services/matchup_season.py` | Verify completion, bracket lock and historical reads |
| Projection/weekly lineup and horizons | `src/core/intelligence/team_strength.py` and Batch 5 tests | Reuse accepted intelligence; test transitions, not recalibration |
| Global source refresh | `src/core/data_platform/scheduler.py`, `dtos_app.py` background tasks | Audit bounded scheduling, failure recovery and unchanged replay |
| Historical season eligibility | `src/core/historical_memory/season_state.py` | Keep provider eligibility distinct from fantasy league lifecycle |
| Reports, Desk, attention/events | Existing Batch 6 services and tests | Verify shared temporal context and no false reread movement |
| Trade, FOIS, Picks | Accepted Batches 3–6 canonical paths | Integrated acceptance; change only concrete defects |

## Dependency order

1. Focused transition matrix: preseason, pre-week, active/completed week, bye,
   regular-season completion, playoff qualification/rounds, completed season and
   next-season isolation. Establish concrete gaps before implementation.
2. Refresh/recovery audit: existing background flights, explicit sync, failure,
   atomic publication, restart compatibility, no request-path bulk work.
3. Storage accounting: current measurements, bounded expected writes, replay,
   attribution of any material growth. No paid capacity increase or canonical deletion.
4. Integrated two-league acceptance across manager and advanced surfaces,
   including mobile, keyboard/accessibility and exact A→B→A context restoration.
5. Freeze only after focused proof is coherent; authoritative release gates,
   immutable release/deployment, production acceptance, controlled restart and cleanup.

## Status at initial inspection

- **Implemented:** intelligence foundations and manager surfaces listed above.
- **Partial / needs proof:** lifecycle coverage, adaptive refresh behavior,
  transition event semantics, recovery and storage accounting.
- **Not implemented:** the Batch 7 transition acceptance matrix and final
  integrated Batch 7 acceptance evidence. No new product feature is presumed missing.
- **Acceptance only:** cross-surface parity, responsive/accessibility audit,
  release/deployment/restart and repository synchronization.
- **Blocked:** no product decision currently established as blocking. Any genuinely
  unresolved behavior will be reported separately, without blocking independent work.

Detailed production, infrastructure and security evidence remains local/private.
This document contains only public-safe implementation planning. No comprehensive
gate or Batch 7 completion is claimed by this initial map.

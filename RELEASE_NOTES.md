# DTOS v0.9.3 — Commissioner Desk

DTOS v0.9.3 replaces the homepage with the Commissioner Desk: a daily executive briefing and the central integration hub for the Front Office Operating System.

## Highlights

- Added Active League and Active Front Office selectors with persistent local context.
- Organized the homepage around “What changed?”, “What matters?”, and “What should I do?”.
- Added visit-window transaction events with meaningful empty states and explicit historical-data limitations.
- Added deterministic league headlines that expose their supporting evidence.
- Added personalized Front Office status, record, standings rank, roster grade, and draft-capital grade.
- Added prioritized recommendations with confidence scores, reasoning, supporting metrics, and future-engine hooks.
- Added league intelligence, expandable standings, transactions, matchups, leaders, and health snapshots.
- Added league-personality extension points without hardcoding a specific league.
- Added reusable typed models, business services, and server-rendered components.

## Metadata

- Application: DTOS
- Version: 0.9.3
- Build: 903
- Codename: Commissioner Desk

## Data boundaries

- One Sleeper league is available in this release, but the active-league architecture accepts a collection.
- Browser-local context persistence does not introduce authentication or user accounts.
- Standings movement, injury changes, matchup result timing, and league records require future historical snapshots.
- Competitive Window and advanced Player, Trade, GM, Draft, and predictive intelligence remain future engines.
- Recommendations use objective foundation data and do not assert player value, trade availability, or championship probability.

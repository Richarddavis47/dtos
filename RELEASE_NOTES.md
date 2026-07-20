# DTOS v0.9.2 — Team Headquarters

DTOS v0.9.2 turns every franchise detail page into a modular Front Office Headquarters while preserving the league directory and all existing application routes.

## Highlights

- Added a Front Office header with team identity, avatar, record, league rank, update time, and a stable Competitive Window placeholder.
- Added an Asset Snapshot covering roster size, owned picks, first-round picks, roster and starter ages, youth, and veteran counts.
- Added deterministic Front Office Summary sections for assessment, strengths, weaknesses, and short- and long-term outlooks.
- Added explainable grades for QB, RB, WR, TE, Youth, Depth, Draft Capital, Flexibility, and Overall Team Grade.
- Organized rosters into position rooms with age, NFL team, lineup designation, and bye-week availability.
- Organized every owned draft pick by year with acquired-pick provenance.
- Added current performance, a newest-first team transaction timeline, future-intelligence placeholders, and quick actions.
- Separated calculation, summary, data-view modeling, and presentation responsibilities.
- Added `DTOS_PHILOSOPHY.md` and targeted Team Headquarters tests.

## Metadata

- Application: DTOS
- Version: 0.9.2
- Build: 902
- Codename: Team Headquarters

## Data boundaries

- Foundation grades measure observable roster construction and draft assets; they are not player-value estimates or championship forecasts.
- Current streak and player bye weeks display as unavailable when Sleeper does not supply them.
- Competitive Window, Contender Score, Rebuild Score, and advanced intelligence remain stable placeholders for future engines.

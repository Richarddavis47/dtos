# Changelog

Notable DTOS changes are recorded here from the repository's Git history.

## v0.9.4 - 2026-07-20

- Added a centralized, reusable Decision Engine with typed context, profile, evaluation, team-window, and recommendation contracts.
- Separated Current Championship Outlook from Future Outlook and added independent Depth and Asset Health evaluations.
- Added deterministic positional depth analysis, five competitive-window classifications, and contextual recommendation categories.
- Standardized recommendation priority, confidence, metrics, collapsed reasoning, and future explanation hooks across DTOS.
- Connected Commissioner Desk and Team Headquarters intelligence surfaces to the shared engine without redesigning either page.
- Replaced the ambiguous overall team grade with a clearly scoped Roster Construction grade.
- Added Decision Philosophy documentation and focused engine contract tests.
- Updated application metadata to DTOS v0.9.4, build 904, codename Decision Engine v1.

## v0.9.3 - 2026-07-20

- Replaced the homepage with the Commissioner Desk executive briefing organized around what changed, what matters, and what to do.
- Added extensible Active League and Active Front Office models, selectors, URL state, and browser-local persistence.
- Added deterministic daily briefings, evidence-backed league headlines, personalized Front Office summaries, explainable prioritized recommendations, league intelligence, and expandable league snapshots.
- Added reusable Commissioner models, services, and presentation components with future intelligence hooks.
- Removed the hardcoded league identity from shared application chrome and added league-personality extension points.
- Added `docs/CommissionerDesk.md`, expanded the README, and added targeted Commissioner Desk tests.
- Updated application metadata to DTOS v0.9.3, build 903, codename Commissioner Desk.

## v0.9.2 - 2026-07-20

- Rebuilt every franchise detail page as a responsive Team Headquarters with front-office identity, assets, performance, roster rooms, draft capital, recent activity, future outlook, and quick actions.
- Added deterministic, explainable roster-construction grades for core positions, youth, depth, draft capital, flexibility, and the overall team.
- Added objective Front Office Summaries that disclose missing data and avoid speculative player-value or competitive claims.
- Added reusable Team Headquarters calculation and view-model services plus targeted unit tests.
- Added `DTOS_PHILOSOPHY.md` to establish evidence-first, transparent, deterministic standards for future intelligence systems.
- Updated application metadata to DTOS v0.9.2, build 902, codename Team Headquarters.

## v0.9.1 - 2026-07-20

- Rebuilt the Transactions page as a responsive Front Office dashboard with activity summaries.
- Added cached filtering by team, owner, transaction type, player, draft-pick involvement, date range, and search text.
- Added sortable transaction columns, configurable pagination, team links, player transaction pages, position badges, asset movement details, and preserved raw Sleeper payload access.
- Added transaction-only Sleeper synchronization with preserved filter state, last-successful-refresh reporting, and graceful failure handling.
- Added a dedicated transaction business-logic service and targeted unit tests.
- Updated application metadata to DTOS v0.9.1, build 901, codename Transactions Center.

## v0.9.0 - 2026-07-20

- Completed the Settings migration into `routes/settings.py`.
- Moved health, API, and synchronization endpoints into `routes/api.py` so `dtos_app.py` remains focused on application setup and router registration.
- Centralized application name, version, build number, and release codename in `app_metadata.py`.
- Added DTOS version, build, Git branch, and latest commit information to the Settings page.
- Cleaned and reorganized `dtos_app.py` without changing existing endpoint behavior.
- Made the default cache location portable across Linux and Windows.

## v0.8.9 - 2026-07-20

- Moved the Draft Picks page from `dtos_app.py` into a dependency-injected router in `routes/draft.py`.
- Registered the Draft router with the FastAPI application while preserving the existing `/picks` endpoint behavior.

## v0.8.8 - 2026-07-20

- Moved transaction history rendering from `dtos_app.py` into `routes/transactions.py`.
- Registered the Transactions router through the shared application dependencies.
- Refreshed the repository's packaged DTOS archive.

## v0.8.7 - 2026-07-20

- Moved the Front Office HQ dashboard from `dtos_app.py` into `routes/hq.py`.
- Registered the HQ router through the shared application dependencies.

## v0.8.6 - 2026-07-19

- Moved team list and team detail routes from `dtos_app.py` into `routes/teams.py`.
- Registered the Teams router through the shared application dependencies.
- Added a packaged v0.8.5 archive to the repository at that point in history.

## v0.8.5 - 2026-07-19

- Moved matchup list and matchup detail routes from `dtos_app.py` into `routes/matchups.py`.
- Registered the Matchups router through the shared application dependencies.
- Added a packaged DTOS archive to the repository.

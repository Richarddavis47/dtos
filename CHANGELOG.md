# Changelog

Notable DTOS changes are recorded here from the repository's Git history.

## v0.9.0 - 2026-07-20

- Completed the Settings migration into `routes/settings.py`.
- Moved health, API, and synchronization endpoints into `routes/api.py` so `dtos_app.py` remains focused on application setup and router registration.
- Centralized application name, version, build number, and release codename in `app_metadata.py`.
- Added DTOS version, build, Git branch, and latest commit information to the Settings page.
- Cleaned and reorganized `dtos_app.py` without changing existing endpoint behavior.

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

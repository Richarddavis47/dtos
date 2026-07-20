# DTOS v0.9.0 — Front Office Foundation

DTOS v0.9.0 completes the current modular-router foundation while preserving existing application behavior.

## Highlights

- Completed the League Settings migration into `routes/settings.py`.
- Added a Front Office information card to Settings with version, build, Git branch, and latest commit details when available.
- Moved health, status, league-data, and manual-sync endpoints into `routes/api.py`.
- Centralized release metadata in `app_metadata.py`:
  - Application: DTOS
  - Version: 0.9.0
  - Build: 900
  - Codename: Front Office Foundation
- Simplified `dtos_app.py` to application lifecycle setup, shared rendering/data helpers, and router registration.

## Compatibility

- Existing URLs and response behavior are preserved.
- Git metadata is optional; Settings displays `Unavailable` when branch or commit information cannot be detected.

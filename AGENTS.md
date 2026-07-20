# DTOS Repository Guidelines

## Application architecture

- DTOS is a FastAPI application.
- Preserve all existing functionality unless explicitly asked to change it.
- Use modular routers in `routes/`.
- Keep `dtos_app.py` focused on application setup, shared dependencies, and router registration.
- Never overwrite working modules from memory. Inspect and modify the repository's current files.
- Inspect the repository before making changes.

## Git and release workflow

- Work from the current `main` branch.
- Create one feature branch per release.
- Prefer small, focused releases.
- Update version strings consistently wherever the current version appears.
- Before committing, run Python syntax checks on changed Python files and run `git diff --check`.
- Commit the focused changes, push the feature branch, and open a pull request to `main`.
- Do not merge a pull request unless explicitly authorized.

## Handoff

- Report all changed files.
- Report the checks run and their results.
- Report any known limitations.

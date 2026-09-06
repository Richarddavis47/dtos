# Release Process

1. Follow AGENTS.md and the explicitly authorized release scope. Preserve failed evidence.
2. Run focused tests while diagnosing; batch corrections before final validation.
3. Run the canonical `.venv/Scripts/python.exe -m tools.validation.validate_release`,
   full regression, lint, compilation, dependencies, whitespace, routes/OpenAPI and smoke.
4. Require ordinary, archive-warmed and combined-read Linux **application** lifecycle
   checks: cold construction, non-semantic reuse, one material replacement, compatible
   restart, provider-free requests, memory admission, responsiveness and cleanup.
5. Run lightweight browser product journeys with `requirements-validation.txt`:
   desktop/mobile navigation, authenticated A→B→A context, two accounts, Trade workflows,
   numerical contracts and accessibility. Do not create successful screenshot archives.
6. Review ancestry and diff; merge only green required PR checks. Release and deploy
   the exact merge commit; do not rewrite immutable prior releases.
7. Verify real authenticated production journeys and account/league/franchise isolation,
   full smoke, semantic inspection, stable-boundary restart and post-restart smoke.
8. Confirm storage/privacy, temporary-resource cleanup and clean synchronized main.

Current Visual, Live Visual, DINS and External Visual Mirror are retired. They are not
release gates and have no publication steps. Their historical failed evidence remains
accurate; old published release artifacts remain immutable. Shared product checks were
retained, not waived. Application memory and responsiveness contracts are unchanged.

See [validation architecture](VALIDATION_ARCHITECTURE.md). Version/build identity is
centralized in `app_metadata.py`. Stop for genuine unsafe or out-of-scope failures;
never weaken a gate or label an unexecuted check as passed.

# DTOS Repository Instructions

## Application architecture

- DTOS is a FastAPI application.
- Preserve all existing functionality unless the release request explicitly changes it.
- Use modular routers in `routes/`.
- Keep `dtos_app.py` focused on application setup, shared dependencies, shared helpers that cannot yet be moved, and router registration.
- Update application metadata and version strings consistently through the centralized metadata module.
- Prefer small, focused releases.

## Standard autonomous release workflow

When a release prompt authorizes end-to-end completion, perform the full workflow without pausing between routine steps:

1. Start from a clean, current `main` branch.
2. Pull the latest `origin/main`.
3. Create one feature branch for the requested version.
4. Inspect the repository and existing roadmap before coding.
5. Implement the complete requested release while preserving existing functionality.
6. Install required dependencies in the ignored `.venv` when needed.
7. Run all applicable validation:
   - Compile all Python files.
   - Run `git diff --check`.
   - Run an application startup test.
   - Check route registration, including missing and duplicate routes.
   - Run HTTP smoke tests for all major existing routes.
   - Run targeted tests for new or changed functionality.
8. Fix every discovered issue and repeat validation until everything passes.
9. Update application metadata, version, build number, `CHANGELOG.md`, and `RELEASE_NOTES.md`.
10. Review the final diff for accidental changes, dead code, duplicate routes, hardcoded version strings, and regressions.
11. Commit the focused release and push its feature branch.
12. Open a pull request targeting `main`.
13. Mark the pull request ready for review after validation passes.
14. Squash-merge the pull request when all checks pass and the release prompt authorizes end-to-end completion.
15. Switch the local repository back to `main` and pull the merged changes.
16. Confirm that `HEAD` matches `origin/main`, the working tree is clean, the correct application version is reported, and the merged application starts successfully.
17. Stop the local test server before finishing.
18. Report:
    - Release version.
    - Feature branch.
    - Pull request.
    - Merge commit.
    - Changed files.
    - Features implemented.
    - Checks completed.
    - Issues found and fixed.
    - Any known limitations.

## Autonomy and safety rules

- For routine patch and minor releases, complete the full process without waiting for approval when the prompt says "build end to end."
- Do not stop merely because a dependency is missing; install it safely in the ignored virtual environment.
- Do not leave an unmerged pull request when end-to-end completion is authorized and all merge conditions pass.
- Do not push directly to `main` unless explicitly instructed.
- Stop only for destructive changes, authentication failure, unavailable required credentials, ambiguous product requirements that materially affect behavior, or a problem that cannot be safely resolved.
- Never hide failed checks or claim a test passed when it was not run.
- Preserve `DTOS_CACHE_FILE` and all other environment overrides.
- Maintain Windows compatibility.
- Never overwrite working code from memory; inspect the repository first.
- Do not merge unless the prompt explicitly authorizes the merge or end-to-end completion.

## Expected release request

Use this one-line request format:

> Build DTOS vX.Y.Z end to end according to the roadmap and AGENTS.md.

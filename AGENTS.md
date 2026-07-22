# DTOS Repository Instructions

## Application architecture

- DTOS is a FastAPI application.
- Preserve all existing functionality unless the release request explicitly changes it.
- Use modular routers in `routes/`.
- Keep `dtos_app.py` focused on application setup, shared dependencies, shared helpers that cannot yet be moved, and router registration.
- Update application metadata and version strings consistently through the centralized metadata module.
- Prefer small, focused releases.

## Standard autonomous release workflow

For every DTOS feature or release, perform the full workflow without pausing between routine steps:

1. Start from a clean, current `main` branch.
2. Pull the latest `origin/main`.
3. Create one feature branch for the requested version.
4. Inspect the repository and existing roadmap before coding.
5. Implement the complete requested release while preserving existing functionality.
6. Install required dependencies in the ignored `.venv` when needed.
7. Run all applicable validation:
   - Run the canonical `.\.venv\Scripts\python.exe -m tools.validation.validate_release` entry point for a complete release.
   - Compile all Python files.
   - Run `git diff --check`.
   - Run an application startup test.
   - Check route registration, including missing and duplicate routes.
   - Run HTTP smoke tests for all major existing routes.
   - Run targeted tests for new or changed functionality.
   - Do not substitute an ad hoc command list for the canonical release validator.
8. Fix every discovered issue and repeat validation until everything passes.
9. Update application metadata, version, build number, `CHANGELOG.md`, and `RELEASE_NOTES.md`.
10. Review the final diff for accidental changes, dead code, duplicate routes, hardcoded version strings, and regressions.
11. Commit the focused release and push its feature branch.
12. Open a pull request targeting `main`.
13. Mark the pull request ready for review after validation passes.
14. Confirm there are no merge conflicts with current `main`, then squash-merge the pull request when every required validation gate passes.
15. Delete the merged feature branch locally and remotely.
16. Create and push the release version tag, and publish release notes when appropriate.
17. Switch the local repository back to `main` and pull the merged changes.
18. Confirm that `HEAD` matches `origin/main`, the working tree is clean, the correct application version is reported, and the merged application starts successfully.
19. Stop the local test server before finishing.
20. Continue to the next approved milestone or prepare the backlog without waiting for another approval.
21. Report:
    - Release version.
    - Feature branch.
    - Pull request.
    - Merge commit.
    - Changed files.
    - Features implemented.
    - Checks completed.
    - Issues found and fixed.
    - Any known limitations.

## Required release gates

Automatic merge is authorized only after all of these pass:

- All unit and targeted tests.
- All linting and DTOS quality checks.
- Python compilation and any other applicable build step.
- Application startup.
- Route registration and HTTP smoke tests, with no duplicate routes.
- All release-specific validation.
- A conflict check against current `main`.

If any gate fails, stop immediately, do not merge, report exactly what failed, and wait for instructions. Never skip, bypass, hide, or misrepresent a validation result.

## Autonomy and safety rules

- Complete the full feature-branch, validation, pull-request, squash-merge, branch-cleanup, tag, documentation, and synchronization process without waiting for merge approval whenever every required gate passes.
- Do not stop merely because a dependency is missing; install it safely in the ignored virtual environment.
- Do not leave a validated release pull request unmerged.
- Do not push directly to `main` unless explicitly instructed.
- Explicit approval is always required for force pushes, published-history rewrites, destructive database or data migrations, credential or authentication changes, intentional deletion of user data, or bypassing validation.
- Otherwise stop only for a failed validation gate, an unsafe merge conflict, unavailable credentials, materially ambiguous product requirements, or an unexpected issue that could compromise DTOS stability or integrity.
- Never hide failed checks or claim a test passed when it was not run.
- Preserve `DTOS_CACHE_FILE` and all other environment overrides.
- Maintain Windows compatibility.
- Never overwrite working code from memory; inspect the repository first.
- A passing release is standing authorization to merge; no additional approval is required.

## Expected release request

Use this one-line request format:

> Build DTOS vX.Y.Z end to end according to the roadmap and AGENTS.md.

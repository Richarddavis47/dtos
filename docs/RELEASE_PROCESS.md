# Release Process

`AGENTS.md` is authoritative. In summary:

1. Start from clean synchronized `main` and create one release branch.
2. Inspect contracts and roadmap, implement a focused release, update metadata and documentation.
3. Run `.\.venv\Scripts\python.exe -m tools.validation.validate_release` from the repository root.
4. Stop on any failed gate. Never bypass or misreport validation.
5. Review the diff and conflict state, commit, push, open a ready pull request, and squash-merge after all gates pass.
6. Delete the feature branch, tag the merge commit, publish release notes, return to `main`, pull, and repeat startup/smoke validation.
7. Confirm clean synchronized state and no remaining validation process.

Version metadata lives only in `app_metadata.py`. Build numbers use the numeric release tuple (`1.0.0` → `1000`). Release artifacts are the Git tree, annotated tag, GitHub release notes, changelog, validation report, and production-readiness checklist.

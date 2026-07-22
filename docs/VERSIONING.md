# Versioning Policy

DTOS follows Semantic Versioning.

- Patch releases fix defects without intentionally changing public behavior.
- Minor releases add backward-compatible functionality or provider capabilities.
- Major releases may change frozen contracts only with migration documentation and explicit authorization.

The public compatibility surface includes documented HTTP methods, paths, accepted inputs, response meanings, environment variables, orchestrator entry points, provider contracts, and persisted cache interpretation. Additive JSON fields are compatible. Deprecations are documented in release notes and retained for at least one minor release when practical.

`VERSION`, `BUILD_NUMBER`, and `RELEASE_CODENAME` are centralized in `app_metadata.py`. Git tags use `vX.Y.Z` and point to the squash merge on `main`.

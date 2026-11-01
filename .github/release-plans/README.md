# Guarded Actions release publication

This tooling branch changes no application files relative to the recorded production baseline. The existing canonical workflow is already dispatchable on main, so GitHub can execute its explicitly selected tooling-branch revision without a preliminary main merge or Render deployment.

The owner-authorized `audit`, `prepare`, and `publish` operations use the job-scoped `GITHUB_TOKEN` with `contents: write`, as the established v1.21.91 publisher did. The old hard-coded publisher is not invoked. There is no PAT, credential relay, new secret or deployment hook.

`audit` verifies the pinned source, twelve hosted jobs, original artifact digests, all canonical payload hashes, test counts, ten gates, lifecycle outcomes, sanitized recovery evidence and attachment manifest. `prepare` performs the same verification and uploads only those files to the existing unpublished draft, then downloads every attachment to verify its bytes. It creates no tag and never merges a PR.

Only after successful preparation may the existing approved application PR be merged normally by the authorized maintainer. `publish` requires that exact PR to be merged at current main, with a tree identical to the validated source. It rechecks evidence, updates the existing draft to the actual merge commit, creates or verifies its annotated tag without overwriting anything, then publishes and verifies immutability and attachment readback. It observes the normal Render rollout through bounded public read-only smoke checks.

The publisher rejects a different actor, event, repository, source branch, publisher ref, advanced publisher ref, changed application tree, failed/missing checks, corrupt artifacts, unexpected assets or wrong tag. Publication is serialized and cannot cancel another publication. Normal PR and manual validation retain their existing behavior.

The build 2221 plan and its recovery archive are frozen release evidence, not application state or a source-data warehouse. The archive hash is independently verified in the existing Scout handoff. Original failed/canceled Actions attempts are retained; no application regression rerun is needed solely to replace the failed Cloud upload credential.

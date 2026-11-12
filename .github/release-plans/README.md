# Build 2248 guarded publication

This tooling-only branch is based on production build2247 and must never be merged into main. It reuses the established Actions `GITHUB_TOKEN` with job-scoped `contents: write`; no inspection credential, personal token or external upload relay is involved.

The version-specific plan is usable only with `finalized: true`, exact source-bound successful local and hosted records, original artifact API digests, complete recovery and prior-attempt manifests, an existing draft and an unused tag. The application canonical validation steps are unchanged. The publisher independently verifies required jobs on the exact candidate, all internal manifests, source tree, tests and resource controls before preparation.

`prepare` uploads only to the draft and verifies attachment readback. It produces a preparation certificate bound to this controller revision and evidence. Main is merged only after every mandatory gate and preparation succeeds. The same frozen controller's `publish` operation requires that successful preparation run, approved PR state and exact merged source tree before creating/verifying the tag and publishing the immutable record. No application changes may be introduced by this tooling branch.

The recovery archive is stored as ordered, checksummed parts under the established four-part/256MiB cap. Prior failures and cancellations remain distinct from final passing evidence. Release attachment hashes and deployment/source identity are checked separately.

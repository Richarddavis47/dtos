# Team Assessment Coverage — validation in progress

Baseline: `dd3366d7b3d5e713c8004ec5e34b72ac9a27a94f` (production v1.22.11/build2226).
Original candidate: `cd400cf84ce6f80405848d43b95e7fece975c42b`.
Current candidate: `28b60c46c80d9394c3f16d83cd6eeb2b66ca231d`.
Current source tree: `5a28b6548e4bc7d0b0bebc16a427ad00173a9f39`.

`candidate.patch` and `original-canonical.log` are the original, unchanged artifacts. Their hashes and the two UID0/mode0755 bytecode directories are recorded in `source-and-original-failure.json`.

`candidate-28b60c4.patch` is the complete current patch against the same baseline; `candidate-28b60c4.json` explains each revision. Original earlier patches are retained alongside it. The current changes handle absent metadata, restore the existing compact phone presentation, and require canonical lineup admission before showing retained weekly points. No analytical model or threshold was changed.

The original whole-tree compilation was blocked by root-owned ignored bytecode. No chmod/chown or broad permission changes were performed. Tests now run in `/workspace/team-assessment-candidate`, a clean exact checkout, as UID/GID1000 inside a real2GiB/no-swap/twoCPU/network-none container. The runtime is Python3.14.3 from immutable image `sha256:2c9de92bf8e05a79587f6edba94052cf614c984a5cb81a62613871388cd6533e`.

Current focused result: **69 tests passed**. This includes complete/partial/missing rendered comparisons, unchanged phone roster visibility checks, and missing-scoring rejection. The full canonical entry point `python -m tools.validation.validate_release` is running; **no complete regression or ten-gate pass is claimed yet**.

Preserved attempts: `cd400cf-interrupted.zip` records the legacy-wording failure; `interrupted-ca76bf4.zip` records absent-metadata and mobile-layout failures, plus the subsequent focused qualification failures. Interrupted runs are not completion evidence. The source-replay numerical fixture is presentation-only and does not establish live Granite verification.

No merge, tag, GitHub release or production deployment is authorized or performed. Only candidate/evidence branches have been pushed.

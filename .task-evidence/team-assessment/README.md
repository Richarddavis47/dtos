# Team Assessment Coverage — final validation running

Baseline: `dd3366d7b3d5e713c8004ec5e34b72ac9a27a94f` (v1.22.11/build 2226).
Original candidate: `cd400cf84ce6f80405848d43b95e7fece975c42b`.
Current candidate: `a332afe8fc545320c9a74134ab56f87c66b91af4`.
Current tree: `6b8ea104ce38338270d33ffb9ae225e6018395b6`.

`candidate.patch` and `original-canonical.log` are unchanged original artifacts. `candidate-a332afe.patch` is the complete updated patch against the same baseline, with exact-tree application proof. `candidate-a332afe.json` explains revisions and previous failures.

Original compilation failed in root-owned ignored bytecode directories. No permission changes or elevated testing were used. The clean exact checkout runs as UID/GID 1000, Python 3.14.3, enforced 2 GiB/no swap/two CPUs/network disabled. `run-clean.py` and `invocation-focused-a332afe.json` specify the runtime and commands.

**71 final focused checks passed. Full canonical validation is running; no final pass is claimed yet.** Application edits remain limited to Home/My Team presentation. Test changes update old wording assertions and collect unreachable browser-fixture objects without bypassing actual memory admission.

`failed-06f56ba.zip` preserves the previous completed full run: 4,071 tests, four failed viewport subtests and three errors (evidence-directory failure and two real capacity-deferred Trade browser timeouts). The per-test observer missed subtest callbacks; original unittest console totals are authoritative. Earlier interrupted archives remain separate. A deferred operation does not count as completion.

No merge, tag, GitHub release or deployment is authorized or performed. Production is unchanged. Fixture results do not establish live Granite acceptance or physical Safari behavior.

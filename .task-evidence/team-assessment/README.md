# Team Assessment Coverage — validation complete, not released

**PASS: 4,071 full regression tests, all ten canonical gates, and 71 focused checks.**

Baseline: `dd3366d7b3d5e713c8004ec5e34b72ac9a27a94f` (v1.22.11/build 2226).
Original candidate: `cd400cf84ce6f80405848d43b95e7fece975c42b`.
Validated final candidate: `a332afe8fc545320c9a74134ab56f87c66b91af4`.
Validated source tree: `6b8ea104ce38338270d33ffb9ae225e6018395b6`.

## Downloadable review evidence

- `candidate.patch`: complete original candidate patch against baseline.
- `candidate-a332afe.patch`: complete final patch against the same baseline.
- `patch-application-proof-a332afe.json`: applying final patch reproduces the exact source tree using an isolated temporary Git index.
- `original-canonical.log`: unchanged original compilation failure log.
- `canonical-a332afe.log`: final complete ten-gate summary.
- `focused-a332afe.log`: final 71 focused tests, including complete/partial/missing rendered states and real Trade browser journey.
- `validation-a332afe.zip`: complete final canonical logs, 559 original manifest payloads with checksums, test-event stream, browser evidence, container measurements, invocation and methodology.
- `FINAL_VALIDATION.json`: exact identity, counts, memory and final results.
- `ATTEMPTS.json`: failed and interrupted attempts; no interrupted run counts as completion.
- `failed-06f56ba.zip`: prior full run with four failed viewport subtests and three errors. Original unittest console totals are authoritative; observer does not capture subtest callbacks.
- Earlier interrupted archives and original patches remain unchanged alongside these deliverables.
- `SHA256SUMS`: checksums of all top-level deliverables except itself.

## What changed and why

Application changes remain limited to Home/My Team presentation and a shared pure formatter. The weekly analytical optimal-lineup comparison replaces generic unavailable wording when compatible evidence exists. It states week, supported points, slot coverage and comparable/full-league population, preserving provisional qualification. Partial/missing evidence stays qualified; existing valid overall ranks remain supported. No composite grade is added, and submitted Sleeper lineups remain separate.

Validation uncovered stale text expectations, absent optional fixture metadata and a phone layout regression; those were corrected. Missing scoring still withholds numerical evidence, and the existing detailed qualification remains visible. The obsolete projection-coverage assertion now checks the new honest comparable-team denominator. Its evidence directory is created before assertions to avoid masking failures. Two old Trade browser timeouts reflected real memory deferral during a long shared test process. Test setup now collects unreachable earlier fixture objects and trims only unused allocator pages, including between viewport cases. Production admission and Trade code are unchanged; the actual journey must still execute successfully.

## Execution and preservation

Original compilation was blocked by UID/GID 0, mode 0755 ignored directories:
`/workspace/dtos/.validation/canonical-release/__pycache__` and
`/workspace/dtos/.validation/canonical-release/observer/__pycache__`.
No chmod/chown, broad permission changes or elevated tests were used.

Validation ran from clean `/workspace/team-assessment-candidate`, as UID/GID 1000, Python 3.14.3, Chromium 156, enforced 2 GiB/no swap, two CPUs and network disabled. Runtime image:
`sha256:2c9de92bf8e05a79587f6edba94052cf614c984a5cb81a62613871388cd6533e`.
`invocation.json` and `run-clean.py` record exact Docker command and mounts.
Canonical command: `python -m tools.validation.validate_release` (unchanged canonical validator).
Focused command is recorded in `invocation-focused-a332afe.json`.
Full canonical duration: 2,354.377 seconds. Kernel cgroup peak: 2,020,847,616 bytes; no OOM/max events. Final cgroup usage: 176,160,768 bytes. Route validation: 282 method registrations, 247 OpenAPI paths, no duplicates. Tracked HTTP smoke and process cleanup passed.

No grading engine, Trade calculations/qualification, scoring, optimal-lineup selection, submitted lineups, saved preferences or resource-admission policies changed. No merge, tag, GitHub release or production deployment occurred. No version increment was made. Production deployment requires separate authorization.

## Scout/Main Chat handoff

Verify SHA256SUMS, archive integrity, exact candidate/tree and all 559 canonical manifest entries. Review original and final patches and preserved failure logs. Confirm final console says 4,071 tests/OK and canonical summary says ten gates passed. Review complete/partial/missing and valid-overall-rank preservation tests plus four-width browser evidence. These are disposable fixture results, not live Granite recovery or physical iPhone/Safari acceptance. No hosted workflow rerun or live production mutation was performed for this validation-only assignment.

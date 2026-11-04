# Team assessment evidence consistency — ready for release review

**PASS: 64 focused tests, 4,065 full regression tests, all ten canonical gates. No merge, tag, release or deployment.**

Reviewed base: `a332afe8fc545320c9a74134ab56f87c66b91af4`, tree `6b8ea104ce38338270d33ffb9ae225e6018395b6`.
Production baseline: `dd3366d7b3d5e713c8004ec5e34b72ac9a27a94f`, v1.22.11/build 2226; not modified.
Validated candidate: `89ecf568e572255da75de83feee85bc5d8ab066f`.
Validated tree: `ae32e0aa79119450bfe36904536579c9d9f870f9`.

## Correction

The reviewed formatter combined saved horizon points/coverage and stored qualifications with a rank from a separately recalculated current assessment. Availability could change without changing that saved horizon. The formatter also failed to reapply source-age and failed-refresh qualification.

Home and My Team now select an existing identity-keyed diagnostic publication through `prepared_diagnostics`. The existing reader validates current eligibility, scoring and source identity and requalifies the cached result using current freshness/refresh evidence. No solver, hydration, synchronization or provider request is added. Points, selected-slot count, rank (strictly greater unrounded totals), supported population and full-league population all come from that single diagnostic. The saved profile and a separately graded card no longer supply comparison numbers. A cache miss withholds rank and explains the need for matching current evidence.

The lead and expanded My Team comparison share the same selected diagnostic. The compact lead retains its provisional label; the existing disclosure explains the effective reason. Home includes the effective qualification in the directory text, which is part of its body-cache identity, so aging and refresh failures cannot leave a cached current label in place. Home can read prepared weekly diagnostics without constructing an optional full Headquarters assessment when that cache is missing.

Overall grades remain unset. Existing valid overall ranks remain on the original path. Grading, scoring, Trade evaluation/qualification, submitted Sleeper lineups, preferences and memory admission are unchanged.

## Tests and original attempts

New rendered-page transition coverage on both surfaces includes a coherent fresh control; a saved profile followed by an availability change; source aging without a numerical publication change; failed refresh of retained evidence; and missing prepared diagnostics. Tests assert admitted points/rank agreement or withheld rank, retain qualification reasons and verify the saved profile is unchanged. Unit controls cover zero, missing and incompatible evidence. Nine older formatter/mock test methods were consolidated into three tests including a stateful real rendered-route integration control; counts are test methods, not transition counts.

- `focused-070842b.log`: 22 tests, one failure (Home had diagnostics but no optional HQ cache).
- `focused-343014c.log`: 31 tests, one error (fixture lacked projection context).
- `focused-4333a32.log`: 64 tests, two failures (missing-cache expectation and phone spacing).
- `focused-1727345.log`: 64 tests, five failures (four obsolete expanded-text assertions and phone pending-message spacing).
- `focused-89ecf56.log`: **64 tests, OK**. Pending summaries were shortened without removing the detailed explanation; assertions now check the coherent comparable-team wording.
- `original-bytecode-failure.log`: unchanged original earlier compilation failure. Previous complete and interrupted task evidence remains separately in `../team-assessment/`.

## Exact execution and independent review

Clean writable checkout: `/workspace/team-assessment-candidate`; UID/GID 1000, Python 3.14.3, Chromium 156, two CPUs, enforced 2 GiB/no swap, network disabled. No permission changes or elevated test execution. Runtime/commands are recorded in `invocation.json`, `invocation-focused.json`, and `run-clean.py`. Full command: `python -m tools.validation.validate_release` using the unchanged canonical validator.

Read [the complete ten-gate log](canonical.log), [exact results](result-summary.json), [patch against reviewed base](reviewed-base.patch), [complete patch against production baseline](production-base.patch), and [patch application proof](patch-proof.json).

[Canonical evidence archive](canonical-evidence.zip) contains all original canonical logs, measurements, trace, browser captures and 559 verified manifest entries. [Readable regression console](regression-console/README.md) provides the original console split at line boundaries; concatenation exactly reproduces the original log. No failure text was removed. `SHA256SUMS` covers every published file except itself.

Final cgroup limit: 2,147,483,648 bytes. Kernel peak: 1,999,650,816 bytes; zero OOM/max events. Final cgroup usage: 176,398,336 bytes. Process cleanup passed. Fixture/browser acceptance is not live Granite recovery or physical iPhone/Safari acceptance. No hosted workflow results are claimed for this validation-only task.

Scout/Main Chat: verify manifest and archive checksums, candidate/tree, readable console final 4,065/OK and ten gate results; review the rendered current/availability/aging/refresh transitions. Release review only; deployment needs separate authorization.

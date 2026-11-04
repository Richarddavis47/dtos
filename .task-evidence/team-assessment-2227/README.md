# Team Assessment Coverage — released and deployed

**v1.22.12 / build 2227**, merged PR[#316](https://github.com/Richarddavis47/dtos/pull/316). [Immutable release](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.12).

Production commit: `40226bb497a5b5c30047cc5f98e49c4008c67992`.
Validated candidate: `40cea1690943cca2ba1b99b50612c5ae6b5c68ac`.
Validated/merged tree: `de2827e28dea58e7174c938ba4b38930e0892bea`.
Reviewed starting candidate: `89ecf568e572255da75de83feee85bc5d8ab066f`, tree `ae32e0aa79119450bfe36904536579c9d9f870f9`.
Production baseline: `dd3366d7b3d5e713c8004ec5e34b72ac9a27a94f`, build 2226.

## Customer correction

Home and My Team use one admitted league/week/generation diagnostic for projected points, legal slot coverage, comparison rank, population and effective qualification. No saved-profile/new-rank mixing. Source aging and failed refreshes are requalified using existing rules; missing comparisons withhold unsupported values.

A matching incomplete diagnostic now keeps the facts it supports. The rendered disposable 9/10 case shows **9/10 slots covered; 1 of 2 league teams comparable**, with no complete points total or projected rank. Expanded text explicitly says the comparison is prepared but the legal lineup is incomplete, explains withheld totals/rank and names missing slots only when supplied by the diagnostic. Official standings remain separate. Complete and truly absent controls are retained.

No grading model, scoring, Trade calculation/qualification, submitted lineup, saved preference or admission-policy change. No new solver/provider work on reads. Model-wide overall grades remain unset.

## Review evidence

- [Final Scout checklist and qualifications](SCOUT_FINAL.md)
- [Exact completion/deployment record](COMPLETION.json)
- [Patch against reviewed candidate](candidate-reviewed.patch), [complete patch against production baseline](candidate-production.patch)
- [Complete ten-gate summary](canonical.log), [local result/memory counters](local-verified.json)
- [Full passing original regression console, readable parts](regression-console/README.md)
- [First full failed original console, readable parts](failed-attempt1-console/README.md)
- [Original canonical/recovery evidence ZIP](Assessment-coverage-evidence.zip), [separate prior attempts ZIP](Prior-attempts.zip)
- [Hosted run/job/artifact metadata](hosted-final-records.json), [Actions preparation and attachment digests](preparation-verified.json), [immutable publication verification](publication-verified.json)
- [Independent public readiness/unauthenticated smoke](production-readonly-smoke.json)
- [All file checksums](SHA256SUMS)

Final passing results: **65 focused, 4,066 full local regression tests, all ten local gates; all twelve hosted jobs, 4,066 hosted canonical tests, 595 Product executions; 40 publisher guard tests; five exact-source constrained preflight cases**. Clean writable checkout, UID1000, Python 3.14.3, enforced 2 GiB/no swap/two CPUs/network-none. All 559 local and 563 hosted canonical manifest entries verified. Sixteen immutable attachments verified by native Actions with byte readback. `invocation.json` and `invocation-focused.json` retain exact commands. Canonical command: `python -m tools.validation.validate_release`.

## Failed and qualified evidence

The first local full run executed4,066 tests with one 114.145 ms failure against the unchanged 100 ms literal fixture Home scheduling assertion. This fixture endpoint does not call assessment presentation. Twenty unchanged isolated repetitions measured 4.691–7.613ms; then a fresh full canonical retry passed on the same commit. No assertion, resource limit or application threshold was relaxed. The cause of the single excursion remains unproven. Prior original full/focused failures and interrupted attempts remain separately manifested; they never substitute for a pass.

The initial focused65-test run had one overbroad assertion that also matched an official standing. The corrected assertion targets projected comparison ranks. Routine publisher setup/CLI limitations, Cloud signed redirect transport failures and the early Cloud HTTP 502 readiness observation are retained with precise provenance and signed URLs redacted. The old CLI Projects Classic query was replaced with supported normal GitHub PR metadata/merge APIs, with exact-head/tree checks and normal server protections.

Cloud's artifact transport limitation was not worked around with credentials: the established authorized Actions publisher performed the actual original-byte verification. All mandatory gates and publication passed. Live authenticated franchise acceptance and physical Safari testing remain unverified. No Granite recovery or earlier 503 cause is claimed.

# Roster space on bye-week pickup cards

PR [#362](https://github.com/Richarddavis47/dtos/pull/362). The [source receipt](source.json) and [patch](candidate.patch) bind the change to the verified build 2272 baseline.

DTOS now reports how many active roster places are used alongside the prepared lineup fit. It uses the configured starter and bench limit and the selected team’s source-verified membership. IR and taxi places are separate. Incomplete or older membership evidence can leave active space unknown until a normal refresh.

- Open fixture, 5 of 6 active places used. [Screenshot](screenshots/roster-space-open-390.png)
- Full Superflex fixture, 5 of 5. An IR vacancy and two taxi vacancies add no active place. [Screenshot](screenshots/roster-space-full-390.png)
- Missing Sleeper taxi membership. The pickup fit remains visible and the missing occupancy is explained. [Screenshot](screenshots/roster-space-unknown-390.png)

The prepared Chromium fixture checks contextual Back, league isolation, layout overflow, waiver/lock wording and target-week projections. The focused run also verifies how the source membership flag survives native synchronization and cache restoration. [Original focused console](checks/focused-final-original.log)

[Scout acceptance route](SCOUT_HANDOFF.md) · [SHA256SUMS](SHA256SUMS)

The guarded release is [v1.22.58 / build 2273](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.58). The [Scout handoff](SCOUT_HANDOFF.md) links the release and verification route. See [release records](release/), [publisher logs](checks/publisher/) and [checksums](SHA256SUMS).

# Bye pickup IR safety evidence

This evidence describes the [build 2274 candidate](https://github.com/Richarddavis47/dtos/pull/363). The release is gated on full exact-source local and hosted validation and the guarded publisher.

- Read the [source identity](source.json), [patch](candidate.patch) and [source notes](NOTES.md).
- Open the [original focused console](checks/focused-final-original.log) and [source-bound focused receipt](checks/task-focused-ready.json).
- Compare the [released fixture](prior-attempts/released-last-spot-390.png) with the [corrected last-spot fixture](screenshots/ir-last-spot-390.png). The screenshots are simulated Chromium phone views, not production owner or physical-device results.
- Follow the [Scout acceptance route](SCOUT_HANDOFF.md) and verify the [readable files by checksum](SHA256SUMS).

The original hosted canonical run failed a pre-existing Trade browser journey after admission deferred. Its original output is [preserved separately](prior-attempts/hosted-canonical-44969401958/). The final candidate changes only test browser cleanup alongside the already verified IR feature. The 390px feature screenshots at this checkpoint describe unchanged feature application and fixture bytes from the first candidate. [Recovery and exact gates](NEXT_ACTIONS.md).

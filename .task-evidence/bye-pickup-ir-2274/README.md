# Bye pickup IR safety evidence
 
The [failed first hosted run](prior-attempts/hosted-canonical-44969401958/) and [matched isolation replay](prior-attempts/trade-viewport-isolation-control/) are separate. The first candidate passed its local full suite, but that earlier tree does not establish a pass for the current candidate. See the [recovery record](NEXT_ACTIONS.md).

This evidence describes the [build 2274 candidate](https://github.com/Richarddavis47/dtos/pull/363). Production is running [immutable v1.22.59 / build 2274](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.59).

- Read the [source identity](source.json), [patch](candidate.patch) and [source notes](NOTES.md).
- Open the [original focused console](checks/focused-final-original.log) and [source-bound focused receipt](checks/task-focused-ready.json).
- Compare the [released fixture](prior-attempts/released-last-spot-390.png) with the [corrected last-spot fixture](screenshots/ir-last-spot-390.png). The screenshots are simulated Chromium phone views, not production owner or physical-device results.
- Follow the [Scout acceptance route](SCOUT_HANDOFF.md) and verify the [readable files by checksum](SHA256SUMS).

The production proof is in [release records](release/). See the [original publisher logs](checks/publisher/).

# Build 2284 evidence

The priority pages were rendered on the pinned Chromium 156.0.8078.108 toolchain within 2 GiB, using the same prepared fixtures for the baseline and final candidate. The baselines use the live application tree for v1.22.68/build 2283. The themed baseline Trade Review uses the original production page helper in a disposable harness. No account was signed into production for these screenshots.

Open the before, after and comparisons folders for 320px, 390px and 1280px. The revisions appear only after an explicit button press. Full-page screenshots may show the fixed bar at the captured scroll position. In the actual short viewport, both the primary button and the final action cleared the fixed bottom navigation and passed a hit test, keyboard activation or touch. The 320px League fixture keeps its long franchise names wrapped with the full Points For totals and all controls within their boxes.

- [Burrow decision trace](DECISION_TRACE.md) and [original JSON](burrow-decision-trace.json)
- [Responsive fixture console and exact-source receipt](original-tests/)
- [Scout handoff](SCOUT_HANDOFF.md)
- [Draft PR and full validation status](https://github.com/Richarddavis47/dtos/pull/373)

The full-source gates and guarded publication must pass before this candidate is released.

## Verified production

[DTOS v1.22.69 / build 2284](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.69) is live and ready. The immutable release includes 23 verified attachments, with separate originals for the complete local and hosted tests, Product Browser, prior attempts and checksums. The exact local and hosted canonical runs each passed 4,693 tests and ten gates under 2 GiB with zero OOM kills. All 13 hosted checks and both guarded publisher stages passed. Review the [production receipts](production) and [original test index](original-tests).

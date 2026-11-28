# Release hold for build 2286

The draft PR is open and unmerged. Production was verified ready on **v1.22.70 / build 2285**, commit `db4e7ea43bc3106502132b26841ddf520fe29dae`, tree `9f0734bbf30581f048b522e6e795f2b2d3bbe919`. At the availability check there was no v1.22.71 tag or build 2286 publisher branch. No deployment or signed-in production inspection was performed for the candidate.

Candidate `3f3a19689b70beb01b1b5e9eb8e885917a83a094`, tree `9f5d965fe9b0e513e1d200de0e7e0bb1fcb2cceb`. [PR #375](https://github.com/Richarddavis47/dtos/pull/375) · [Readiness receipt](original-tests/held-production-identity.json)

## Hosted verification

All 13 required checks passed on the candidate. The second hosted canonical attempt passed all ten gates and ran 4,699 tests under the original 2 GiB cap. Kernel peak was 2,051,289,088 bytes, with zero OOM kills. The first canonical attempt is retained separately. Its existing Rebuild workflow saw 400,896,000 bytes of Trade headroom versus the 402,653,184-byte reserve. The matched window records an admission deferral before evaluation. [Passing attempt](https://github.com/Richarddavis47/dtos/actions/runs/46086945006/attempts/2) · [Earlier attempt](https://github.com/Richarddavis47/dtos/actions/runs/46086945006/attempts/1) · [Verified artifact receipts](original-tests/hosted-artifacts-verified.json) · [Original consoles](original-tests/hosted-original-consoles.zip)

The Product Browser workflow logged successful batches of 817, 35 and 235 tests. Tooling and lifecycle checks passed. [Product Browser](https://github.com/Richarddavis47/dtos/actions/runs/46086945049) · [Tooling](https://github.com/Richarddavis47/dtos/actions/runs/46086945009) · [Lifecycle](https://github.com/Richarddavis47/dtos/actions/runs/46086945020)

## Required local run

| Exact-source attempt | Outcome | Measured Trade headroom |
| --- | --- | --- |
| 1, original invocation | Completed all 4,699 tests with three errors and one failure in existing Trade journeys | 391,878,656 bytes on the first Team Need deferral |
| 2, unchanged invocation | Interrupted after an existing Rebuild request returned HTTP 503 | 388,921,344 bytes |
| 3, aligned with hosted optional screenshot settings | Passed Rebuild, then interrupted after the tenth existing source-evidence Evaluate request returned HTTP 503 | 395,628,544 bytes |
| 4, verified byte-identical Python and Chromium on read-only mounts | Interrupted after an existing Rebuild request returned HTTP 503 and the browser assertion timed out | 365,006,848 bytes |

The reserve was 402,653,184 bytes throughout. Attempt 3’s matched sample recorded 289,681,408 file bytes locally and 200,511,488 on hosted, with fewer anonymous bytes locally. This establishes greater local file usage in that sample. The specific allocation causing the difference remains unidentified. The failed request paths did not invoke the new preview. Attempts 2–4 stopped after an observed error. They provide no completed validation receipt. The cap, application reserve, test order and assertions stayed intact. [Original consoles, memory logs and matched windows](original-tests/local-attempts.zip)

## Publisher and recovery

The draft held because the full local gate did not pass. The initial isolated publisher unit preflight reported six setup errors against an unfinished staging plan. After loading the actual hosted run receipts, all five admission and fail-closed tests that needed the run list passed. The finalized transport test and guarded publisher remain incomplete. Completing a publisher plan requires genuine passing local evidence. [Initial preflight](original-tests/publisher-unit-preflight-original.log) · [Five-test follow-up](original-tests/publisher-receipt-controls-original.log)

Resume from the draft’s exact tree on an approved local executor that can complete the canonical run at 2 GiB. Reuse the hosted receipts only while the tree remains identical and the original evidence is valid. Follow the repository’s publisher and production verification after a full local pass. Keep the old attempts separate.

The downloadable archives preserve original file bytes and include checksums. Each canonical attempt’s embedded manifest describes its original native artifact and can also list outputs outside the curated download. [Published file checksums](SHA256SUMS) · [Scout acceptance route](SCOUT_HANDOFF.md)

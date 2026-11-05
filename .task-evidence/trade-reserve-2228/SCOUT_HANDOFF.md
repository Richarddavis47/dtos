# Trade reserve evidence — build 2228 acceptance

Validated candidate: 9d30dd2ede74c065e373841aa8fbaa20fea82f84
Source tree: 0764486d9440d39438a615ef301ddafe3a30a7fd
Production baseline: 40226bb497a5b5c30047cc5f98e49c4008c67992, v1.22.12/build 2227.
PR #317: https://github.com/Richarddavis47/dtos/pull/317
Target: v1.22.13/build 2228. Local canonical validation passed: 4,082 tests, all ten gates, Python 3.14.3, actual 2 GiB/no swap/two CPUs/network none. Hosted canonical publication evidence is reconciled separately before release.

Confirmed source issue: known K/DEF assets with no legal starting slot counted as usable reserve candidates in a Superflex configuration without K/DEF slots. Canonical optimization correctly selected none, but a nonempty candidate population prevented verified empty usable cover from becoming zero. Missing projections for those irrelevant positions could also invalidate reserve coverage. The shared preparation boundary now uses the existing exact fantasy-position/slot rules. Unknown eligibility and required Granite K/DEF evidence remain fail-closed. A new prepared-method identity prevents mixing prior and corrected profiles.

Confirmed presentation loss: same-publication one-QB fixtures retain an owner's 10-point partial reserve subtotal with an unprojected active bench receiver, while the partner independently has supported 10-to-20-point reserve production. The old primary summary collapsed both sides into incomplete-depth wording when later weeks lacked evidence. Primary summaries and existing disclosures now distinguish known partial subtotals, complete weekly effects, genuine zeros, missing player-week evidence, eligible candidate counts and unfilled reserve-cover slots. All week/phase/source/owner/scoring guards remain; no partial subtotal becomes a delta or second starting lineup.

Evidence scope: source-compatible disposable twelve-team fixtures and a genuine fixture-qualified +8 consolidation under Win Now, Retool and Rebuild, with its -1 reserve cost retained. This is not a live qualified Granite offer. The historical 128 assessments/zero recommendations are supplied observations; matched per-package records were unavailable, so their missing-evidence causes cannot be counted or reconstructed. No owner settings, rankings, Custom method, goals, trade package or submitted Sleeper lineup were changed.

Matched before/after: same projection generation and exact starting-lineup impacts in all three cases. Median 10-sample warm evaluation times: complete one-QB 67.25 -> 73.36 ms; partial-bench one-QB 77.06 -> 76.20 ms; Superflex 78.05 -> 76.72 ms. Fresh 2 GiB/no-swap container peaks: 80,199,680 -> 80,240,640 bytes; no OOM events. These small controlled workloads do not predict live search timing, capacity or long-term leak behavior.

Focused original attempts remain separate from successful final evidence. Failed attempts: initial probe import path; a Superflex assertion exposing the eligibility defect; a browser assertion expecting trailing decimal zeros plus consequent missing screenshot-directory output; initial baseline probe expected a new-field name absent in original source. No failed or deferred operation is counted as execution success. Original local final console reports 4,082 tests, all passed; all ten gates passed. Container peak 2,054,938,624 bytes; final cgroup current 201,433,088 bytes; zero OOM/OOM-kill events and process cleanup passed. The five-case metadata-only preflight separately passed with no leftover children or scratch state; it is not a substitute for actual Trade execution. Hosted outcomes are authoritative in the exact-source records verified by the publisher before release.

Scout checklist after validated deployment:
1. Verify deployed version/build/commit, immutable release assets, exact candidate/merged tree and checksums.
2. Without initiating discovery automatically, verify contemporaneous safe resource readiness. Any new live search requires bounded authorized acceptance and safe admission at that moment.
3. Inspect both teams' current-week primary reserve facts and expanded analytical before/after starters and reserves. Confirm exact week/generation/scoring, legal QB/RB/WR/TE/FLEX/K/DEF or league-specific Superflex slots, names and individual sums.
4. Confirm known partial cover is labeled partial with the affected player/phase reason, while a valid partner or other week stays visible. Missing is never zero; verified empty usable cover can be zero. Other weeks retain their own projections.
5. Confirm bilateral verdict, Neutral/Custom values, exact picks, submitted starters and workspace remain intact. No preference mutation or provider refresh is needed to inspect retained evidence.
6. Inspect 320×432, 375×667, 390×844 and desktop keyboard/touch-emulated browser records. Physical iPhone/Safari is not claimed.

This release does not establish live Granite recovery, explain an earlier 503 or guarantee that any manager will accept a trade.

## Verified publication and deployment

PR #317 merged as `6b43bfa183ed9a2023ecb59247c8831da3c4b1dd`, tree `0764486d9440d39438a615ef301ddafe3a30a7fd`, exactly the validated tree. [Immutable v1.22.13 / build 2228 release](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.13) has 16 verified attachments. All twelve required hosted jobs passed, including 4,082 hosted canonical tests/ten gates/563 manifest entries and 611 Product tests. Source-pinned local evidence has 559 manifest entries; the full original console has 28 readable, byte-equivalent parts. Separate publisher guard controls: 40 passed.

Authorized publisher commit: `6b63608a15b6d03836c831efc5f3a20e306d6c1b`. Preparation run 41951492920 and publication run 41951845830 both passed, including source/CRC/manifest checks and attachment byte readback. Legacy hard-coded publish-2191 jobs were intentionally skipped and never dispatched. The frozen recovery archive preserves the original pre-publication validation record; COMPLETION.json and production-readonly-smoke.json give the final result.

Independent public production verification reports v1.22.13/build 2228, exact deployed commit `6b43bfa183ed9a2023ecb59247c8831da3c4b1dd`, ready. Liveness, Welcome and Sign In returned 200; unauthenticated private endpoints returned 401. Welcome has no customer beta/prerelease wording. No production league entry/search or saved-state mutation was performed. Independent private Granite acceptance remains separate and must respect current resource admission.

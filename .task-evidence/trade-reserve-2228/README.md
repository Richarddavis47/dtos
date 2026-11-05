# Trade reserve evidence — build 2228

Status: **HELD pending final hosted canonical validation and guarded publication**. This record does not claim a deployed release.

Production baseline: v1.22.12/build 2227, commit `40226bb497a5b5c30047cc5f98e49c4008c67992`, tree `de2827e28dea58e7174c938ba4b38930e0892bea`. Candidate: `9d30dd2ede74c065e373841aa8fbaa20fea82f84`, tree `0764486d9440d39438a615ef301ddafe3a30a7fd`. [PR #317](https://github.com/Richarddavis47/dtos/pull/317).

The canonical reserve pool now respects the exact configured starting-slot eligibility. Proven slot-ineligible assets cannot hide an established empty usable reserve pool; unknown eligibility and required K/DEF projections remain unresolved. Presentation preserves independent phases, sides and weeks, distinguishes known partial subtotals from complete replacement comparisons, and explains prepared-player gaps. No prices, thresholds, submitted lineups, saved preferences or resource policies were changed.

Local validation: **4,082 tests, all ten canonical gates passed**, exact clean candidate, Python 3.14.3, UID1000, enforced 2 GiB/no swap/two CPUs/network none. Peak cgroup usage 2,054,938,624 bytes; no OOM/OOM-kill; final cgroup 201,433,088 bytes; process cleanup passed. Focused final controls: 77 passed. Browser controls: two passed, all four viewports, keyboard/touch emulation, no overflow or disclosure requests. Metadata-only preflight: five cases passed, no leftover children or scratch; not a substitute for Trade worker execution.

[Complete patch](candidate-production.patch) · [Source identity](source.json) · [Commands and methodology](commands.md) · [Scout handoff](SCOUT_HANDOFF.md) · [Matched fixture comparison](matched-comparison.json) · [Preserved shared source blobs](preservation.json)

[Complete local recovery archive](2228-recovery.zip) contains all 559 verified canonical payload entries, original logs/observer/trace, fixture evidence and manifests. [Prior attempts archive](2228-prior.zip) separately preserves original setup, Superflex and browser assertion failures. Its prior-manifest.json identifies every member; none substitutes for final acceptance. Probe scripts are the corrected harness, while original initial setup failures remain in their original logs.

[Original full regression console](original-local-canonical/unittest-console.log) · [Canonical console](original-local-canonical/canonical.log) · [Ten-gate trace](original-local-canonical/canonical-trace.jsonl) · [Original test observer](original-local-canonical/tests.jsonl) · [Result](original-local-canonical/result.json) · [Verified local result](local-verified.json). The selected original-local-canonical files are readable convenience copies; the full original 559-file population is in the recovery archive.

The following line-boundary parts concatenate byte-for-byte to the original full console, SHA256 `1a82708125f4ffd2942a3bf04f8600917f908e012ec1369341c9ebed45ab873e`. [Part checksums](readable-console/SHA256SUMS).

- [unittest-console-001.log](readable-console/unittest-console-001.log) — 399,884 bytes
- [unittest-console-002.log](readable-console/unittest-console-002.log) — 399,731 bytes
- [unittest-console-003.log](readable-console/unittest-console-003.log) — 399,805 bytes
- [unittest-console-004.log](readable-console/unittest-console-004.log) — 399,896 bytes
- [unittest-console-005.log](readable-console/unittest-console-005.log) — 399,924 bytes
- [unittest-console-006.log](readable-console/unittest-console-006.log) — 399,669 bytes
- [unittest-console-007.log](readable-console/unittest-console-007.log) — 399,897 bytes
- [unittest-console-008.log](readable-console/unittest-console-008.log) — 399,697 bytes
- [unittest-console-009.log](readable-console/unittest-console-009.log) — 398,906 bytes
- [unittest-console-010.log](readable-console/unittest-console-010.log) — 399,943 bytes
- [unittest-console-011.log](readable-console/unittest-console-011.log) — 399,989 bytes
- [unittest-console-012.log](readable-console/unittest-console-012.log) — 399,516 bytes
- [unittest-console-013.log](readable-console/unittest-console-013.log) — 399,560 bytes
- [unittest-console-014.log](readable-console/unittest-console-014.log) — 399,694 bytes
- [unittest-console-015.log](readable-console/unittest-console-015.log) — 399,884 bytes
- [unittest-console-016.log](readable-console/unittest-console-016.log) — 399,471 bytes
- [unittest-console-017.log](readable-console/unittest-console-017.log) — 399,931 bytes
- [unittest-console-018.log](readable-console/unittest-console-018.log) — 399,575 bytes
- [unittest-console-019.log](readable-console/unittest-console-019.log) — 399,983 bytes
- [unittest-console-020.log](readable-console/unittest-console-020.log) — 399,802 bytes
- [unittest-console-021.log](readable-console/unittest-console-021.log) — 399,860 bytes
- [unittest-console-022.log](readable-console/unittest-console-022.log) — 399,740 bytes
- [unittest-console-023.log](readable-console/unittest-console-023.log) — 399,808 bytes
- [unittest-console-024.log](readable-console/unittest-console-024.log) — 399,969 bytes
- [unittest-console-025.log](readable-console/unittest-console-025.log) — 399,682 bytes
- [unittest-console-026.log](readable-console/unittest-console-026.log) — 399,966 bytes
- [unittest-console-027.log](readable-console/unittest-console-027.log) — 399,966 bytes
- [unittest-console-028.log](readable-console/unittest-console-028.log) — 259,621 bytes

## Scope and limitations

The historical Granite 128-assessment/zero-qualified result is supplied evidence. Its matched per-package diagnostics were unavailable; no historical cause count is invented. All new accepted offers and point comparisons are deterministic disposable fixtures, not live qualified Granite trades. No production Trade search, sync, FOIS rebuild, account login or user preference mutation was performed. A public Welcome read returned 200 with no beta/prerelease wording.

Same-projection-generation controls preserve exact starter impacts and three recorded rejection verdicts. A separate genuine +8 fixture consolidation retains its -1 reserve cost and Worth Pursuing verdict under all three strategies. Partial known cover is never zero or a full delta; supported zero is numerical only when proven. Source freshness is qualified using the existing rule. Physical iPhone/Safari and indefinite leak freedom are not claimed.

Checksums: manifest.json inventories all published payloads; SHA256SUMS also includes that manifest. Existing immutable historical evidence is unchanged. Hosted workflow and release verification records are added after their actual completion.

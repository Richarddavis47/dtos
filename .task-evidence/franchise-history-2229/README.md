# Franchise transaction history — build2229 held review

**HELD — PR #318 is draft/unmerged. No tag, release or deployment.** Production remains v1.22.13/build2228, `6b43bfa183ed9a2023ecb59247c8831da3c4b1dd`, verified ready by one public read. [PR #318](https://github.com/Richarddavis47/dtos/pull/318) · [Hold record](HELD.json) · [Production identity](production-held-identity.json).

Candidate `63efcdde1573f9cbf2bc5b2bd02984d3d477064f`, tree `e044d42def632a55f56180adfaf9330d632c0f37`. [Complete patch](candidate-production.patch) · [Source identity](source.json) · [Patch/source verification](source-integrity.json) · [Protected subtree identity](preservation.json) · [Commands and limitations](commands.md) · [Scout checklist](SCOUT_HANDOFF.md).

The existing Franchise History now exposes retained completed transactions and observed draft selections. Source acquisition establishes Complete/Partial/Unknown; calendar age does not. Missing history never becomes no activity. Exact pick originals remain independent of owner/selector. Unknown pick year does not become transaction year. Status, conflicting records, source-generation changes and ambiguous ownership are qualified. Known independent facts survive incomplete identity or raw-cache eviction. Existing Trade Ledger dossier links require supported completion/identity. No prices, scoring, Trade thresholds, saved settings or memory policies changed; FOIS stays RETAINED / NOT REVALIDATED.

| Final exact-source validation | Outcome |
|---|---|
| Focused source/rendered/workflow controls |112passed,197.417s|
| Local full regression |4,107passed, original console OK|
| Local canonical gates |10passed, including startup/route/HTTP/process cleanup|
| Hosted required jobs |11passed,1failed|
| Hosted Product executions |636passed (620+16)|
| Hosted canonical |4,107executed;1error at390×844; gates8–10not run|
| Original artifact integrity |568local payload entries;572failed-host entries verified|
| Dedicated metadata-only2GiB preflight |5cases passed; not restoration or live acceptance|
| Browser history controls |Day/Ark at320×432,375×667,390×844,1280×900; keyboard/touch emulation; no overflow or extra disclosure requests|

[Local verified result](local-verified.json) · [Original canonical console](original-local-canonical/canonical.log) · [Original full successful regression console](original-local-canonical/unittest-console.log) · [Ten-gate trace](original-local-canonical/canonical-trace.jsonl) · [Local result/memory](original-local-canonical/result.json) · [Hosted outcomes](hosted-final-held-records.json). Local container limit2,147,483,648bytes/no swap/two CPUs/network none/UID1000; kernel peak2,007,875,584bytes, final202,018,816bytes, no OOM/OOM-kill. Cleanup observations are not indefinite leak-freedom proof.

The blocking [hosted canonical run](https://github.com/Richarddavis47/dtos/actions/runs/41966683398) failed after a real capacity deferral. At the request: raw cgroup1,915,293,696bytes; usable headroom297,076,736bytes(283.31MiB), below unchanged402,653,184bytes(384MiB) required. Heavy-work conflict was not indicated. The browser fixture then timed out waiting for an offer. No completed search is inferred from that request and no OOM occurred. Client/test-process memory is included in the disposable cgroup; this is not a production-memory sample or a demonstrated history calculation defect. Bounded fixture recovery did not establish portable normal execution. Admission was never bypassed; the candidate remains held.

[Original failed-host ZIP](host-failed-original.zip) (74,233,133bytes; SHA256`d8fa0d53f63f04178f11484f0b99c1f0e8b15e4e12284a8da599e5be08301508`) · [Integrity proof](host-failed-artifact-integrity.json) · [Original failed-host console](original-host-failed-canonical/unittest-console.log) · [Failed-host result](original-host-failed-canonical/result.json) · [Decoded original job log](host-canonical-failure-decoded.log) · [Decoded successful Product job](host-product-success-decoded.log). The unchanged observer does not hook addSubTest: the full console, not absence of observer error events, establishes the hosted error.

[Complete local recovery archive](2229-recovery.zip) contains the full568-entry original local payload population, original source-bound logs and controls. [Prior attempts archive](2229-prior.zip) preserves the complete earlier failed local canonical output plus original incomplete, failed, superseded and withdrawn-attempt logs/manifests. The separately published original failed-host ZIP preserves every original hosted payload. Neither archive is a production release. The frozen local recovery handoff is a source acceptance record; HELD.json and this checklist give the later hosted failure/hold state.

Evidence uses the repository's explicitly partial October12Sleeper captures. The baseline replay retained3league transaction records/40selections for Day Traders (including the separately controlled older FAAB fixture), and0transactions/260selections for Arkham. These are fixture inventories, not current live counts. The chosen Day roster3 has5current retained selections plus1controlled2023FAAB event with qualified continuity; Arkham roster1 has26observed selections, paginated25per page. Both source-season controls remain partial, with acquired weeks1/5; the older controlled event has week1only. Synthetic complete-empty, unknown, owner-change and malformed cases are separately identified. Current live account history completeness is unverified. Missing source weeks, exact manager takeover time, unsupported pick originals/years and selection timestamps remain unknown. No source history or Market grades were reconstructed from current rosters.

[Original baseline console](baseline.log) survives unchanged. Original baseline HTML/report were overwritten by a probe; [baseline-recreated](baseline-recreated/report.json) is explicitly recreated using the exact production baseline tree. The source and canonical evidence distinguish this limitation. All previous immutable evidence folders remain untouched.

Readable console parts below concatenate byte-for-byte to their original logs. Final local full-console SHA256`bf92ca5b645861f81294f029a56002a64e7113edc87a4cf2d0f21216cd4119f9`. [Local part checksums](readable-console/SHA256SUMS) · [Failed-host part checksums](readable-host-failed-console/SHA256SUMS) · [Earlier failed local part checksums](readable-prior-failed-console/SHA256SUMS) · [Product part checksums](readable-product-console/SHA256SUMS).


Successful local regression:

- [unittest-console-001.log](readable-console/unittest-console-001.log) — 399,832bytes
- [unittest-console-002.log](readable-console/unittest-console-002.log) — 399,926bytes
- [unittest-console-003.log](readable-console/unittest-console-003.log) — 399,962bytes
- [unittest-console-004.log](readable-console/unittest-console-004.log) — 399,885bytes
- [unittest-console-005.log](readable-console/unittest-console-005.log) — 399,945bytes
- [unittest-console-006.log](readable-console/unittest-console-006.log) — 399,626bytes
- [unittest-console-007.log](readable-console/unittest-console-007.log) — 399,886bytes
- [unittest-console-008.log](readable-console/unittest-console-008.log) — 398,182bytes
- [unittest-console-009.log](readable-console/unittest-console-009.log) — 399,202bytes
- [unittest-console-010.log](readable-console/unittest-console-010.log) — 399,892bytes
- [unittest-console-011.log](readable-console/unittest-console-011.log) — 399,765bytes
- [unittest-console-012.log](readable-console/unittest-console-012.log) — 399,865bytes
- [unittest-console-013.log](readable-console/unittest-console-013.log) — 399,876bytes
- [unittest-console-014.log](readable-console/unittest-console-014.log) — 399,905bytes
- [unittest-console-015.log](readable-console/unittest-console-015.log) — 399,853bytes
- [unittest-console-016.log](readable-console/unittest-console-016.log) — 399,658bytes
- [unittest-console-017.log](readable-console/unittest-console-017.log) — 399,551bytes
- [unittest-console-018.log](readable-console/unittest-console-018.log) — 399,953bytes
- [unittest-console-019.log](readable-console/unittest-console-019.log) — 399,859bytes
- [unittest-console-020.log](readable-console/unittest-console-020.log) — 399,996bytes
- [unittest-console-021.log](readable-console/unittest-console-021.log) — 399,911bytes
- [unittest-console-022.log](readable-console/unittest-console-022.log) — 397,492bytes
- [unittest-console-023.log](readable-console/unittest-console-023.log) — 399,817bytes
- [unittest-console-024.log](readable-console/unittest-console-024.log) — 399,832bytes
- [unittest-console-025.log](readable-console/unittest-console-025.log) — 399,894bytes
- [unittest-console-026.log](readable-console/unittest-console-026.log) — 399,988bytes
- [unittest-console-027.log](readable-console/unittest-console-027.log) — 399,882bytes
- [unittest-console-028.log](readable-console/unittest-console-028.log) — 278,288bytes

Failed hosted regression:

- [host-failed-console-001.log](readable-host-failed-console/host-failed-console-001.log) — 398,087bytes
- [host-failed-console-002.log](readable-host-failed-console/host-failed-console-002.log) — 399,969bytes
- [host-failed-console-003.log](readable-host-failed-console/host-failed-console-003.log) — 399,826bytes
- [host-failed-console-004.log](readable-host-failed-console/host-failed-console-004.log) — 399,908bytes
- [host-failed-console-005.log](readable-host-failed-console/host-failed-console-005.log) — 399,666bytes
- [host-failed-console-006.log](readable-host-failed-console/host-failed-console-006.log) — 399,880bytes
- [host-failed-console-007.log](readable-host-failed-console/host-failed-console-007.log) — 399,929bytes
- [host-failed-console-008.log](readable-host-failed-console/host-failed-console-008.log) — 399,975bytes
- [host-failed-console-009.log](readable-host-failed-console/host-failed-console-009.log) — 398,160bytes
- [host-failed-console-010.log](readable-host-failed-console/host-failed-console-010.log) — 399,574bytes
- [host-failed-console-011.log](readable-host-failed-console/host-failed-console-011.log) — 399,907bytes
- [host-failed-console-012.log](readable-host-failed-console/host-failed-console-012.log) — 399,738bytes
- [host-failed-console-013.log](readable-host-failed-console/host-failed-console-013.log) — 399,739bytes
- [host-failed-console-014.log](readable-host-failed-console/host-failed-console-014.log) — 399,913bytes
- [host-failed-console-015.log](readable-host-failed-console/host-failed-console-015.log) — 399,813bytes
- [host-failed-console-016.log](readable-host-failed-console/host-failed-console-016.log) — 399,869bytes
- [host-failed-console-017.log](readable-host-failed-console/host-failed-console-017.log) — 399,779bytes
- [host-failed-console-018.log](readable-host-failed-console/host-failed-console-018.log) — 399,840bytes
- [host-failed-console-019.log](readable-host-failed-console/host-failed-console-019.log) — 399,945bytes
- [host-failed-console-020.log](readable-host-failed-console/host-failed-console-020.log) — 399,588bytes
- [host-failed-console-021.log](readable-host-failed-console/host-failed-console-021.log) — 399,437bytes
- [host-failed-console-022.log](readable-host-failed-console/host-failed-console-022.log) — 399,607bytes
- [host-failed-console-023.log](readable-host-failed-console/host-failed-console-023.log) — 399,971bytes
- [host-failed-console-024.log](readable-host-failed-console/host-failed-console-024.log) — 399,910bytes
- [host-failed-console-025.log](readable-host-failed-console/host-failed-console-025.log) — 399,916bytes
- [host-failed-console-026.log](readable-host-failed-console/host-failed-console-026.log) — 399,828bytes
- [host-failed-console-027.log](readable-host-failed-console/host-failed-console-027.log) — 399,936bytes
- [host-failed-console-028.log](readable-host-failed-console/host-failed-console-028.log) — 213,916bytes

Earlier failed local regression:

- [prior-failed-console-001.log](readable-prior-failed-console/prior-failed-console-001.log) — 399,596bytes
- [prior-failed-console-002.log](readable-prior-failed-console/prior-failed-console-002.log) — 399,796bytes
- [prior-failed-console-003.log](readable-prior-failed-console/prior-failed-console-003.log) — 399,907bytes
- [prior-failed-console-004.log](readable-prior-failed-console/prior-failed-console-004.log) — 399,978bytes
- [prior-failed-console-005.log](readable-prior-failed-console/prior-failed-console-005.log) — 398,802bytes
- [prior-failed-console-006.log](readable-prior-failed-console/prior-failed-console-006.log) — 399,710bytes
- [prior-failed-console-007.log](readable-prior-failed-console/prior-failed-console-007.log) — 399,987bytes
- [prior-failed-console-008.log](readable-prior-failed-console/prior-failed-console-008.log) — 399,797bytes
- [prior-failed-console-009.log](readable-prior-failed-console/prior-failed-console-009.log) — 399,858bytes
- [prior-failed-console-010.log](readable-prior-failed-console/prior-failed-console-010.log) — 399,510bytes
- [prior-failed-console-011.log](readable-prior-failed-console/prior-failed-console-011.log) — 399,850bytes
- [prior-failed-console-012.log](readable-prior-failed-console/prior-failed-console-012.log) — 398,580bytes
- [prior-failed-console-013.log](readable-prior-failed-console/prior-failed-console-013.log) — 399,928bytes
- [prior-failed-console-014.log](readable-prior-failed-console/prior-failed-console-014.log) — 399,837bytes
- [prior-failed-console-015.log](readable-prior-failed-console/prior-failed-console-015.log) — 399,902bytes
- [prior-failed-console-016.log](readable-prior-failed-console/prior-failed-console-016.log) — 399,639bytes
- [prior-failed-console-017.log](readable-prior-failed-console/prior-failed-console-017.log) — 399,904bytes
- [prior-failed-console-018.log](readable-prior-failed-console/prior-failed-console-018.log) — 399,769bytes
- [prior-failed-console-019.log](readable-prior-failed-console/prior-failed-console-019.log) — 399,835bytes
- [prior-failed-console-020.log](readable-prior-failed-console/prior-failed-console-020.log) — 399,865bytes
- [prior-failed-console-021.log](readable-prior-failed-console/prior-failed-console-021.log) — 399,842bytes
- [prior-failed-console-022.log](readable-prior-failed-console/prior-failed-console-022.log) — 399,655bytes
- [prior-failed-console-023.log](readable-prior-failed-console/prior-failed-console-023.log) — 399,788bytes
- [prior-failed-console-024.log](readable-prior-failed-console/prior-failed-console-024.log) — 399,824bytes
- [prior-failed-console-025.log](readable-prior-failed-console/prior-failed-console-025.log) — 399,445bytes
- [prior-failed-console-026.log](readable-prior-failed-console/prior-failed-console-026.log) — 399,789bytes
- [prior-failed-console-027.log](readable-prior-failed-console/prior-failed-console-027.log) — 399,813bytes
- [prior-failed-console-028.log](readable-prior-failed-console/prior-failed-console-028.log) — 237,730bytes

Successful hosted Product:

- [product-console-001.log](readable-product-console/product-console-001.log) — 399,858bytes
- [product-console-002.log](readable-product-console/product-console-002.log) — 399,868bytes
- [product-console-003.log](readable-product-console/product-console-003.log) — 399,828bytes
- [product-console-004.log](readable-product-console/product-console-004.log) — 399,895bytes
- [product-console-005.log](readable-product-console/product-console-005.log) — 396,953bytes
- [product-console-006.log](readable-product-console/product-console-006.log) — 399,358bytes
- [product-console-007.log](readable-product-console/product-console-007.log) — 399,865bytes
- [product-console-008.log](readable-product-console/product-console-008.log) — 399,630bytes
- [product-console-009.log](readable-product-console/product-console-009.log) — 44,948bytes

[Checksum manifest](manifest.json) inventories all published payloads; SHA256SUMS also includes that manifest. No secret, temporary signed delivery URL or private production cache export is included. Evidence publication does not deploy the application.

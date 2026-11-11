# Draft capital after a proposed trade — build 2247

Released **v1.22.32/build 2247**: [immutable release](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.32). Prepared offers and the existing two-offer comparison now show supported remaining picks by season/round, own versus acquired firsts, and expandable exact identities. Incomplete inventory retains verified movements with unknown remaining totals; retained offers never borrow today's inventory.

- PR: [#336](https://github.com/Richarddavis47/dtos/pull/336), merged.
- Deployed commit: `55351c8e4062dc7d74ceb7748eab2179d1bfd92a`; validated tree: `1b282fe3e29a76efbbdab08b8dbd42ff9e1d0846`.
- Validated candidate: `d01acbe65f28a509457524a5e481558cf24d4b2a`; baseline: `8c051475524e2fa46dbad05fb94c65bc8b1e5310`.
- Both full local/hosted runs: **4,378 tests/all ten gates**. All 13 required hosted jobs; 875 Product executions; 21 focused controls plus 2 supplemental numerical checks. Source-bound original artifacts/manifests verified.
- Guarded Actions preparation [43084927614](https://github.com/Richarddavis47/dtos/actions/runs/43084927614), publication [43086477527](https://github.com/Richarddavis47/dtos/actions/runs/43086477527). Same frozen publisher94fe23248c1fcca28da039ab7aca41d6c8647f64; all 23 attachments verified by full byte readback.

## Review

[Final report](REPORT.md) · [application evidence](APPLICATION_VALIDATION.md) · [source method](FEATURE_METHOD.md) · [Scout acceptance prompt](SCOUT_HANDOFF.md) · [exact complete patch](candidate.patch) · [source and patch hashes](patch-verified.json) · [handoff manifest](handoff-manifest.json) · [SHA256SUMS](SHA256SUMS).

### Original readable logs

- Local full regression: [222 exact parts](local-console/), [first](local-console/unittest-console-001.log), [last/summary](local-console/unittest-console-222.log), [part checksums](local-console/SHA256SUMS). Concatenate in numeric order for original SHA256 `35bb02f19435e3df871214a6d2996deb67d7d0df48f5dfa02cc7074bdc02fb7c`.
- [Local original ten-gate trace](local-canonical/canonical-trace.jsonl), [original result](local-canonical/result.json), [729-entry original manifest](local-canonical/manifest.json), [verified cleanup](local-container-cleanup.json).
- [Hosted canonical originals/readable console parts](hosted-canonical/), [689-entry verification](host-canonical-verified.json). [Canonical workflow](https://github.com/Richarddavis47/dtos/actions/runs/43066261728).
- [Full875-execution Product decoded original in 92 exact parts](product-console/), [source/transfer receipt](product-log-transfer.json), [counts](product-test-counts.json). This is complete decoded connector text, not a claim of pre-decoding wire bytes; original native job bytes are also attached in the release's product/prior log ZIP.
- [Earlier attempts](PRIOR_ATTEMPTS.md), [extra original failure parts](prior-originals/), [initial publisher HTTP503 original and classification](publisher-attempt1/), [initial publish tag-visibility404 original and verified continuation](publisher-publish-attempt1/). Those failed attempts remain distinct; neither was waived or counted as success.
- [Eight focused phone/desktop captures and source-bound JSON](focused-browser/). `False` is the disposable1-QB/K/DEF fixture; `True` is Superflex. Neither is an owner live screenshot.

### Immutable original attachments

[Complete handoff ZIP](https://github.com/Richarddavis47/dtos/releases/download/v1.22.32/Draft-Capital-Handoff.zip),126,005,127bytes,SHA256 `e5f8c319f306844c518783fe3f1da4a63863e11e5410975f50f73ed5e29a946a` (all 729 local canonical members unchanged); [original hosted canonical ZIP](https://github.com/Richarddavis47/dtos/releases/download/v1.22.32/canonical-original.zip),SHA256 `870d7d23afdbf006b6d6b6bb04154d52ae868d5fac29c5d22bd0cd48ed2f23b1`; [prior attempts](https://github.com/Richarddavis47/dtos/releases/download/v1.22.32/Prior-attempts.zip); [release checksum list](https://github.com/Richarddavis47/dtos/releases/download/v1.22.32/SHA256SUMS); [release manifest](https://github.com/Richarddavis47/dtos/releases/download/v1.22.32/evidence-manifest.json); [validation](https://github.com/Richarddavis47/dtos/releases/download/v1.22.32/VALIDATION.json).

Public production readiness, exact deployed identity, protected-route behavior and static JavaScript parity were independently observed. Owner authenticated live offers and physical iPhone/Safari remain unverified because the supported owner-browser/Render Shell capability is absent. No production search/sync/FOIS rebuild, saved-setting, submitted-lineup or real-transaction mutation was performed. Shipping this feature does not establish Granite entry recovery or an earlier503 cause. The later deployment/publication receipts are separate from the immutable pre-merge handoff ZIP.

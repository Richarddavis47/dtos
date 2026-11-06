# Current-season production coverage — v1.22.18 / build 2233

The shared canonical scoring and display boundaries are corrected. Supported individual NFL observations now survive irrelevant team-defense/zero-weight requirements and supported source fields reach canonical preparation. Market and dossiers show observed weeks, coverage, qualified per-observation averages and missing fields. Genuine applicable gaps still withhold fantasy-point windows and current-production values. Career History roster totals never replace canonical production.

Released through [PR322](https://github.com/Richarddavis47/dtos/pull/322) and the [immutable release](https://github.com/Richarddavis47/dtos/releases/tag/v1.22.18). Candidate `0a9bb07dbda9d8d9f742b55328fdd68a7d234364`; validated tree `7074ce8c9655a640bd8b79c360f20f18fdd4ab2a`; deployed merge `38f23ecc607d38d986af5c1c20ae57fffeb8f827`. [Patch](candidate-production.patch), [tree reconstruction](source-integrity.json), [production smoke](production-readonly-smoke.json), [Render deployment](render-deployed.json), [attachment verification](publication-verified.json), [complete Scout prompt](SCOUT_HANDOFF.md).

## Confirmed causes and source-to-screen flow

Existing NFLverse acquisition → explicit identity/season/week facts → canonical global store → selected-league component scoring → bounded current/prior-season preparation → cache save/restore → existing valuation consumers and Market/dossier rendering. The historical scorer and reference model coefficients are unchanged. The adapter now ignores only disabled or known individual-inapplicable team-defense categories, retains supported public kicking/return/big-play fields and refuses malformed active statistics. A 40-yard play is not a long touchdown. Unknown position and NFL fullback RB-bonus classification stay unknown.

Current-season completed-week filtering uses matching authoritative NFL state. Observed records, not calendar weeks or asserted games played, form the denominator. No zero is inserted for bye/DNP/missing weeks. Component-complete observations do not establish full-season acquisition or final game status. Incomplete windows retain their counts and missing fields; partial subtotals are never complete averages. Current and previous seasons remain distinct.

A failed or partial source check no longer marks old facts newly fresh. Retained values keep their original knowledge boundary and explicit qualification. Existing failed league refreshes are separately labelled, including cached Market HTML. Old caches reuse only already-retained same-generation sample counts; absent scored counts, weeks and field diagnostics stay unknown. Newly normalized fields require the next legitimate admitted publication; no forced production refresh was performed.

## Before/after evidence and limitations

[Matched fixture results](before-after.json) compare the original baseline and corrected boundaries on the same disposable QB record. Standard offensive scoring plus required team-defense fields recovers from unavailable to 18.00 points per observation. The Granite-coefficient fixture's missing categories narrow from 29 to 2, but its fantasy average remains withheld for player st_ff/st_fum_rec. Arkham/Day coefficient fixtures likewise retain missing required fields. These are synthetic values and field-count controls, not current live player totals. Some extra fixture fields are deliberately absent even when the provider has matching columns; the table must not be read as an actual upstream population audit.

Main Chat supplied the authenticated player:4984 observation with separate 2026 roster Weeks 1–8 / 183.82. Codex did not reproduce that private request and does not claim183.82 as a canonical total. Public authoritative league settings for Granite, Arkham and Day Traders and a bounded 256,000-byte existing-provider schema sample were inspected. No private roster was exported. Remaining player special-teams, long-TD, interception-return and unproved missed-kick semantics remain genuine or qualified gaps; no new source/fallback is introduced. This NFL-player source does not establish team-DEF season production. Existing forward K/DEF projections remain independent.

## Final validation

| Evidence | Result |
|---|---|
| New exact-source production controls |28 passed; 8 viewport/scope cases and 24 screenshots|
| Local full regression |4,180 passed; all 10 canonical gates passed|
| Hosted full regression |4,180 passed; all 10 canonical gates passed|
| Required hosted jobs |12 of 12 passed|
| Main Product executions |709 passed|
| Separate publisher security/integrity controls |44 passed|
| Verified canonical manifest payloads |640 local / 644 hosted|

[Original readable logs/index](LOG_INDEX.md), [original Actions Product/prior log index](original-hosted-job-index.json), [local proof](local-verified.json), [hosted proof](host-canonical-verified.json), [hosted runs/artifacts](hosted-final-records.json), [browser controls](browser-final/browser.json). Earlier baseline assertions, fixture/import/API setup errors, hosted cross-version route failure and superseded partial runs remain separately manifested in [prior-originals](prior-originals) and [2233-prior.zip](2233-prior.zip). They are not counted as final-source successes. Supplemental before/after helper import failures are separately preserved and did not change application source.

The readable canonical folders mirror the original console/trace/result files. The complete 640-payload local tree is inside 2233-recovery.zip; the complete 644-payload hosted tree is in canonical-original.zip on the immutable release. Manifest paths resolve after extracting those full originals. Original Actions Product/prior log bytes are separately preserved beside explicitly labelled connector-decoded logs.

Both full runs enforce 2,147,483,648 bytes (2 GiB), no swap, two CPUs and no external network, with no OOM/OOM-kill. Measured local kernel peak: 2046902272 bytes; hosted: 2079088640 bytes. Existing Trade/FOIS/sync/league-entry completion, safe deferral, recovery, cancellation and cleanup proofs pass; the final local five-case preflight leaves no child or scratch state. Deliberately pressured fixture peaks are not ordinary-read demand and cleanup does not prove long-term leak freedom. The hosted canonical run took 4,187.76 seconds, close to the existing 4,200-second harness budget; no time limit was relaxed. Local time was 2,600.35 seconds. These are full-suite timings on different execution hosts, not page-response benchmarks or universal performance claims.

The original 8 GiB scratch prerequisite and all resource reserves remain intact. Scratch cleanup was inventoried and limited to exact redundant published copies, completed duplicate Git checkouts and regenerable ignored bytecode. Source objects and unique original logs remain preserved.

## Preservation and remaining live boundary

No Trade threshold, Neutral/Custom formula, reference valuation coefficient, saved ranking, preference, goal, exact pick, submitted lineup, legal-lineup calculation, historical/FOIS formula or admission policy changed. No new provider, persistent duplicate data store, background acquisition or page-render preparation was added. Existing source method/adapter versions identify the normalized publication and prevent stale semantic reuse.

Production readiness, exact Render deployment and bounded guest/authentication-boundary smoke are live checks. This session lacks an associated owner browser or Render Shell/SSH; private authenticated source-to-screen recovery is unverified and the previous external inspection 401 was not repeated. No production sync, Trade search, FOIS rebuild, cache clear, restart or saved-user-data mutation was initiated.

Phone/browser controls are disposable store/preparation/route fixtures in two isolated league scopes, not live league lineup claims. Public actual scoring configurations are separate tests. Viewports 320×432, 375×667, 390×844 and 1280×900 pass readable internal table width, keyboard focus, touch emulation, no document overflow and no disclosure acquisition. Physical iPhone/Safari and comprehensive screen-reader acceptance remain unverified. Shipping this correction does not establish Granite recovery, full-season acquisition, a qualified Trade recommendation or the cause of an earlier 503.

[Complete Scout acceptance prompt](SCOUT_HANDOFF.md) · [Checksums](SHA256SUMS) · [Manifest](manifest.json).

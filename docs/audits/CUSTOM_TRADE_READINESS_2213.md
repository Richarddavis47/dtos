# Custom Trade readiness — build 2213

## Read-only production evidence

On 2026-10-30 at 01:24–01:45 UTC, the authorized owner session on released build 2212 showed Market ready (991 assets), My DTOS available (699 eligible rows), and both Trade workspace and Calculator Custom ready. Revision 9 contained 628 saved assets and 628 exact personal values, with no compatibility issues. Repeated saved-intent fingerprints matched. No ranking, preference, trade, lineup or historical write was made. The October 29 unavailable view was not reproduced and its cause is not asserted.

The published Market generation was `2026-10-30T01:14:45.161157+00:00`; prepared valuation generation was `2026-10-30T01:13:51.995352+00:00`. Saved baseline source generation was `2026-10-24T05:53:25.581155+00:00`. Current personal generation was `c2a5d7e2503f6d1d3888d7565e3e3653d3d0738a64a3c8721456dec3f858451c`. Older saved baselines do not inherently prevent current compatible values.

| Canonical asset | Resolved identity | Current neutral value |
|---|---|---:|
| player:13602 | Jack Strand, QB | 79 |
| player:13075 | Myles Price, WR | 67 |
| player:3155 | Laquon Treadwell, WR | 15 |
| player:11593 | Brevyn Spann-Ford, TE | 20 |

These are authorized canonical publication observations, not imported public quotes. Each reported available, FantasyCalc coverage, partially calibrated, non-fallback evidence retrieved 2026-10-29T13:08:09.878162+00:00. Provider source-update time and freshness were unknown; do not call them newly updated upstream prices. Canonical neutral normalization is unchanged. Asset-specific fact generation hashes differ by asset as designed; outer publication and valuation generation agree across responses.

Counts describe different contracts: Market lists 991 assets; filtering to priced assets includes 700 (95 QB, 142 RB, 235 WR, 107 TE, 120 picks; one other position). My DTOS additionally applies its existing eligible identity/ownership universe (699); saved ordering retains its original 628-asset cohort. New eligible assets do not silently enter saved ordering. Counts alone are not evidence of a defect.

## Confirmed producer/consumer defect

A disposable real AssetMarket/cache, account store and HTTP pipeline reproduces the following on the exact released engine: changed input marker, unchanged complete durable semantic generation, same immutable reader, Market ready, but My DTOS returns 409 and Trade Custom remains unavailable. Market cache already proves semantic equality and reuses its reader; personal admission still compares the original construction marker. Repeated reads cannot recognize the cache's accepted preparation.

The baseline engine is replayed directly from commit `3c447c4c6f674326a629c7892fdd9fc22c725ce2`, SHA-256 `dc06eb20199dd258d31a808211d8b74a3db698f4bee36c1a93d81836aa15c2f1`; its expected regression failure is retained. This fixture proves an application defect, not the historical owner's exact failure.

## Narrow correction

Keep the original build marker immutable. Maintain one bounded admitted-input marker on the reader. Only the existing cache branch that proves equal durable semantic generation under publication/epoch checks can advance it. The durable contract includes canonical universe, valuations, ownership, provider evidence, database, league and schemas. No changed-price, failed, pending or superseded evidence is certified. No source provenance is relabeled, prices recomputed, slots reconciled or new historical records invented.

Trade optional bootstrap includes its existing safe structured readiness code. Distinguish preparation from asset-price review. Offer an explicit **Reload Custom evidence** action through existing same-page reload and workspace restoration. It does not initiate preparation, polling, discovery, evaluation or writes, nor silently select Custom. Neutral remains available; exact offer and saved intent remain intact.

## Partial availability and safeguards

The build 2204 exact lower/upper rank-slot completion algorithm is unchanged. Unsupported saved assets keep their positions; no compression, zero substitution or guessed slots. Supported-only packages can use proven exact values. A package dependent on an unresolved value remains qualified/withheld. Neutral prices, source/generation checks, trade thresholds, legal lineups, exact picks, historical grades and authorization remain unchanged. Existing partial-value and Trade workflow controls are rerun alongside new end-to-end controls.

Six new controls cover semantic no-op admission and full HTTP equality, failed preparation, changed prices, superseded/foreign scope, ordinary-read heavy-call/write guards, and browser recovery at 320×432, 375×667, 390×844 and 1280×900. Existing suites cover top/middle/bottom missing assets, genuine zero, equal slots, the named four assets, mixed packages, account/league isolation and navigation.

## Measurement and acceptance limits

Local logic runs declare a fixture memory observer because unrelated host tmpfs/cgroup occupancy prevents actual Market admission; the original refusal is preserved. A real isolated 2 GiB Docker attempt failed before application start due to full parent overlay storage. Neither is a resource pass. Mandatory unmodified canonical validation, actual 2 GiB lifecycle, hosted Product/security and cross-version controls must pass on existing hosted CI before release. No resource gates, assertions or limits are weakened.

Owner Work-browser controls are unavailable in this session. Authorized normal HTTPS verifies live backend readiness; disposable Chromium verifies rendered behavior, keyboard/touch, focus, no overflow and exact offer preservation. This is not owner-browser or physical Safari acceptance. No additional provider/solver/FOIS/history/discovery work is permitted on ordinary reads; guarded controls verify zero calls. No new analytical persistence or infrastructure is introduced.

## Scout acceptance

Reproduce the baseline semantic no-op mismatch and corrected same-generation admission, reject real transitions and failures, verify unchanged full saved document and exact personal curve, exercise supported-only versus dependent packages, and inspect explicit recovery at all four sizes. Independently verify deployed source, authorized owner readiness without mutations, private/no-store headers, and canonical/lifecycle artifacts. A currently ready live account does not prove what caused the older unavailable browser view.

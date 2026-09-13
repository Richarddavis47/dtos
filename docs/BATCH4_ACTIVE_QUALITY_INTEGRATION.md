# Batch 4 active FOIS quality integration

Status: active Day Traders preparation proof complete for this correction; Batch 4 is **not release-ready**. Second-league proof is explicitly bounded below. Pick completion remains open.

## Clustering classification

The evidence supports **B (evidence-limited)** plus **C at the diagnostic median summary**, not a forced ranking correction. The corrected individual assessments already distinguish Strong/Sound/Defensible/Questionable/Poor. A median discards the different proportions of those conclusions. No change to individual historical decisions was needed to manufacture separation.

Representative retained Day Traders evidence:

| Decision / franchise | Boundary UTC | Actual process | Supported evidence / limitation |
|---|---|---|---|
| 882828147664642048 / 1 | 2022-10-04 00:59:01.858 | Strong, 90; high confidence | Favorable complete package price, coherent package, supported lineup context; no outcome assessment |
| 787147952350232576 / 3 | 2022-01-13 00:20:05.643 | Poor, 20; low confidence | Premium paid and poor package assessment; lineup context unavailable; this is a bounded process judgment, not later outcome |
| 1222365586357493760 / 1 | 2025-04-27 23:39:35.544 | Defensible, 65; low confidence | Favorable complete package price and coherent package, but missing lineup context does not justify upgrading to Strong |

Thus some Defensible outcomes are a real limit of contemporaneous evidence, not a finding that every manager performed identically. The unchanged distributions remain available alongside active scores.

## Active implementation

The actual `FOISService` preparation, manager attribution, `FOISEngine`, and local `FOISRepository` path now carries bounded category details: process/outcome magnitude distributions, confidence, missing requirements, descriptive dimensions, waiver observation horizons, FAAB availability and historical roster-reference precision. These are aggregated derived facts, not copies of canonical decision payloads.

Trading uses an equal-decision mean of supported process magnitudes. Unsupported decisions contribute no magnitude. A manager needs the existing minimum of three supported trades for a category grade; smaller samples remain visible as insufficient-sample metrics. Package impact is not used as an unverified importance multiplier. Increasing identical sample volume does not change quality; it affects confidence and coverage. Individual magnitudes remain bounded by the existing evaluator scale, and the complete distribution remains visible for outlier interpretation.

The existing executive conversion is retained: `70 + (mean magnitude − 50) × 0.75`, clamped to 0–100. This is a declared policy scale, not a claim that ordinal categories are precise physical measurements. No player/manager-specific coefficients or fitted grade curve were introduced.

Later outcome, recovery and productive-activity indicators are retained separately but excluded from process-category aggregation. Waiver exchange direction does not create a scalar grade, and unknown FAAB does not become zero. The model/category/configuration boundary is now **5.1**, preventing reuse under the previous scoring identity.

## Actual active ten-manager panel

| Manager | Results | Trading Process | Provisional available-category composite |
|---|---:|---:|---:|
| RichardDavis47 | 86.52 / B | 86.12 | 86.34 / B |
| danreilley | 83.16 / B | 86.88 | 84.85 / B |
| davefedex | 72.49 / C− | 80.89 | 76.31 / C |
| garrettadame36 | 78.91 / C+ | 81.25 | 79.97 / C+ |
| Mears30 | 77.51 / C+ | Insufficient sample | Unavailable |
| zkobes | 74.66 / C | 85.00 | 79.36 / C+ |
| OGV | 48.28 / F | 77.73 | 61.67 / D− |
| TheLandsharks | 76.05 / C | Insufficient sample | Unavailable |
| anthonyrangel | 67.10 / D+ | Insufficient sample | Unavailable |
| Markgus13 | 73.84 / C | 85.00 | 78.91 / C+ |

Source: `BATCH4_ACTIVE_QUALITY_PANEL.json`, generated from the verified retained evidence through the active service, not reconstructed from the earlier coverage-only report. Richard's **86.52/B is still Results only**. The new 86.34 composite is explicitly partial/provisional; it does not claim Waiver, Drafting or Roster quality coverage.

All ten retain unavailable Trading Outcome, Drafting Process/Outcome and unsupported Waiver/Roster grades. Their supported scoped observations remain in category details. Nothing was filled from present-day Market data.

## Overall policy and confidence

- Configured weights: Results 30, Trading Process 25, Roster 20, Drafting 15, Waivers 10.
- At least two supported categories are required. Results alone never produces overall FOIS.
- Unavailable categories are excluded, never zero. The existing configured renormalization uses the available weights; Results + Trading therefore become 30/55 and 25/55, not an undisclosed full five-category score.
- This remains provisional while categories are unavailable. Outcomes do not rewrite historical process or enter Trading Process quality.
- Confidence uses supported decision evidence and sample separately from quality. Overall confidence is the available-category weighted confidence, reduced by category completeness and historical coverage under the existing confidence formula. It is not an outcome probability.
- Comparative strengths/weaknesses require different available scores; unavailable categories cannot become weaknesses. These are relative supported-category comparisons, not assertions that a lower B-grade category is objectively poor.

## Super Flexxxin bounded active proof

The same model/service evaluated 13 historical managers from the four public source seasons 2022–2025. Source league IDs and payload checksums are in `BATCH4_SECOND_LEAGUE_ACTIVE_PANEL.json`. Each season retains three draft rounds and its own six-team playoff structure. Seasonal ownership changes separate franchise 2's TigerWouldDoIt/TheLandsharks, franchise 6's HoneyJ/Markgus13, and franchise 10's Marko216/aficzner13. This is seasonal attribution, not invented exact intra-season tenure timing.

Richard's separate Super Flexxxin Results score is 88.50 over four seasons; it does not inherit his Day Traders 86.52. All second-league overall scores remain unavailable because this bounded source check intentionally did not fetch historical decisions. **This proves active Results/seasonal-tenure isolation, not complete second-league decision-quality coverage.** A new production export was neither attempted nor needed for this check. The historical source now identifies one manager as MostDopeFF; no name-based manager override is applied.

The initial public-source request was blocked by local network restrictions. The same bounded read succeeded with the permitted network execution; no credentials, new service or production mutation was involved.

## Tests and remaining work

49 focused engine/service/presentation/storage tests passed, plus a 17-test focused quality/attribution/tenure/replay set after the final detail changes (sets overlap). Older tests expecting one trade or Results alone to establish a composite were updated to the explicit minimum-category/sample contracts. Individual small-sample metrics remain preserved. `git diff --check` passed.

Open: full second-league decision-quality proof, manager-facing presentation of scoped details, Pick range/confidence methodology, bounded range history, portfolio completion and full live league-switch parity. No comprehensive gates, release, deployment, production publication or Batch 5 work occurred.

The authorized local production-equivalent evidence is retained while dependent proofs remain. No new production transfer occurred. Remote cleanup remains accepted. No test server or ongoing replay process was left running.

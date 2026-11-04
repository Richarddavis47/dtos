# Batch 5 structured presentation handoff

This documents existing interfaces. Batch 6 presentation work is not started.
Consumers must preserve availability, unit, scope, league and generation; absence
is never a numeric zero or a negative assessment.

| Concept | Existing canonical interface | Presentation constraint |
| --- | --- | --- |
| Weekly league-scored projection | `ProjectionService.week_snapshot`, player `canonical_projection` | Retain canonical precision; surface-specific Sleeper formatting follows the projection scoring contract. |
| Actual submitted lineup | Team Strength team `actual_submitted_starter_ids` | Never label an optimal future lineup as submitted. |
| Optimal legal lineup | Team Strength team `weekly[week].optimal` | Partial supported subtotal is not a complete team projection. |
| Current / Next-N / ROS / playoff | Team Strength team `horizons` | Retain requested/supported weeks, availability, rank scope and calendar identity. No unsupported-week extrapolation. |
| Depth / bye resilience | Team Strength team weekly reserve and known-bye evidence | Supported non-starting coverage; neither bench Market value nor an injury forecast. |
| Trade recommendation | Shared evaluation `recommendation`, `recommendation_trace` | Workflow origin cannot supply a different judgment. Unavailable stays unavailable. |
| Market fairness | Shared evaluation `market_evidence` / `dimensions.value_fairness` | External acquisition prices only; retain missing/partial evidence. |
| Package quality | Shared evaluation `dimensions.package_quality` | Retain active/counterparty distinctions and supported lineup contributors. |
| Counterparty plausibility | Shared evaluation `dimensions.counterparty_plausibility` | Evidence-backed classification, not an acceptance probability. |
| Multi-horizon trade effect | Shared evaluation `multi_horizon_impact` | Pre-trade optimal versus post-trade optimal; preserve both sides, coverage and generation. Hypothetical only. |
| Strategic fit | Shared evaluation `dimensions.strategic_fit` | Keep horizon, depth, future-capital and unavailable longevity evidence distinct. |
| Why now / reason tags | Recommended result `opportunity.why_now`, `opportunity.reason_tags` | Stable fit is not a newly observed catalyst. Missing timing evidence stays unavailable. |
| Confidence / limitations | Shared dimensions and reason/limitation fields | Evidence support is not quality and not outcome probability. |

Evaluation provenance includes methodology, input generations and a stable
evaluation identity. Team Strength includes league, season, projection generation,
methodology and semantic generation. A methodology transition must not be shown
as an independent player/team improvement. Pick quote concept, ownership and range
remain separate in asset evidence. Display adapters must not reconstruct a grade,
Market discount, recommendation or independent plausibility score.

Generated search constraints and refresh exclusions are request/page-local.
Only an explicit editable proposal crosses a workflow handoff. Search diagnostics
and rejected candidate universes are not durable history. Future presentation work
must not add persistence of canonical source payload copies.

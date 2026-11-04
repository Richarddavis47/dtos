# Player Value & Projection Integration v1

## Purpose

This layer provides factual, explainable player inputs for roster, matchup, and trade decisions. It deliberately keeps DTOS intrinsic value, external market consensus, contender value, rebuilder value, and current-season production separate.

## Contracts

`PlayerValueProfile` combines immutable `ValueMetric`, `Projection`, `ProductionContext`, `LineupValue`, and `PositionalContext` contracts. Every provider-backed field exposes its source, retrieval state, confidence, timestamp, and limitations. Portrait fields are optional and always include an initials fallback.

## Provider lifecycle

Projection and production providers are registry-backed. The supported state sequence is live provider, fresh cache, disclosed internal fallback, then unavailable. The bundled weekly model is always labeled `fallback`; cached production is labeled `cached`; absent production is labeled `unavailable`. Market Intelligence continues to own external provider consensus and disagreement.

## League scoring

Projection providers receive the cached Sleeper scoring configuration. Passing-touchdown, interception, reception, and tight-end premium settings alter the deterministic fallback. Future live providers must supply scoring-compatible projections or clearly document normalization.

## Lineup and positional value

For each Active Front Office, DTOS calculates projected starter status, flex/superflex utility, replacement points, points above replacement, points above the current starter, marginal lineup value, positional supply, scarcity, and dynasty/weekly rank. These fields are contextual rather than universal.

## Integrations

- Player dossiers show value, market posture, weekly outlook, production, positional context, and evidence.
- Roster Intelligence consumes projected impact and unified player values while retaining player count only as depth.
- Matchups aggregate starter projections, floors, ceilings, positional edges, volatility, confidence, and missing data without win probabilities.
- Trade Intelligence separately compares dynasty, market, contender, rebuilder, and weekly projection deltas.
- The unified API exposes the same contracts used by server-rendered pages.

## Limitations

No championship-equity or matchup-probability model exists in v1.2.0. Live projections and complete historical production require future providers. Fallback projections are useful deterministic estimates, but never masquerade as live data.

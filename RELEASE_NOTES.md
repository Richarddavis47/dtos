# DTOS v1.2.0 — Player Value & Projection Integration v1

DTOS now combines independent dynasty, market, current-season, projection, lineup, scarcity, and strategic value inputs without collapsing them into one unexplained score.

## Highlights

- Unified player-value profiles with source, state, confidence, freshness, evidence, and limitations.
- Existing Market Intelligence consensus, range, disagreement, trend, value gap, liquidity, and explicit market posture.
- League-scoring-aware weekly projection contracts with floor, median, ceiling, role, injury adjustment, and disclosed fallback state.
- Recent-production windows when cached statistics exist, plus an explicit unavailable state when they do not.
- Roster-aware projected roles, points above replacement, points above the current starter, and marginal lineup value.
- Positional ranks, tiers, scarcity, league supply, and elite positional advantage.
- Enhanced player dossiers, Roster Intelligence rooms, matchup projections, trade horizon comparisons, unified API output, and separate team ranking dimensions.

## Metadata

- Version: 1.2.0
- Build: 1200
- Codename: Player Value & Projection Integration v1

## Intentional boundaries

- No championship or matchup win probability is introduced.
- The bundled projection provider is explicitly labeled as a deterministic fallback, not a live projection feed.
- Production remains unavailable when no cached history exists; DTOS does not invent recent game statistics.
- External market values remain separate from DTOS internal valuation.

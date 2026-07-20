# DTOS v0.9.5 - Asset Intelligence v1

DTOS v0.9.5 establishes one deterministic and explainable evaluation source for individual players and draft picks.

## Highlights

- Added reusable player, pick, evidence, risk, value, context, and report contracts under `src/core/asset_intelligence/`.
- Added player dossiers with executive summary, snapshot, four independent values, archetypes, strengths, weaknesses, risk, opportunity horizons, and contextual recommendations.
- Added Dynasty Value, Redraft Value, neutral Market Value, and Front Office-specific Team Fit Value.
- Added draft-pick intelligence covering dynasty value, neutral market value, risk, expected range, time horizon, and strategy.
- Added a reusable Evidence Engine; every score and recommendation exposes observed values, source, impact, explanation, confidence, and limitations.
- Updated the Decision Engine to aggregate Asset Intelligence reports instead of maintaining separate player and pick formulas.
- Enhanced existing player and draft-pick pages without a broad UI redesign.
- Added `/api/players` as the canonical rostered-player dossier index, with the same index available through `/api/league?include_players=true`.

## Metadata

- Application: DTOS
- Version: 0.9.5
- Build: 905
- Codename: Asset Intelligence v1

## Intentional boundaries

- Production, usage, coaching, supporting-cast, contract, live projection, and historical market feeds are not currently connected.
- Missing inputs remain neutral and are disclosed; DTOS does not fabricate a value from unavailable data.
- Market Value is intentionally 50/100 with low confidence until a traceable consensus provider exists.
- Archetypes avoid elite or breakout claims that cannot be supported by the cached evidence.
- Asset Intelligence advises; the GM makes the final decision.

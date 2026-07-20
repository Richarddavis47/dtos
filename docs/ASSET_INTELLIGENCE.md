# Asset Intelligence v1

## Purpose

Asset Intelligence answers: **What is this asset, and what is it worth in context?** It is the single evaluation source for players and draft picks. Decision Engine, Commissioner Desk, Team Headquarters, Trade Intelligence, GM Intelligence, Draft Assistant, APIs, and future mobile clients should consume its public reports rather than duplicate formulas.

## Evaluation philosophy

Evaluations are deterministic, contextual, and traceable. Every numeric result includes observed factors, the factor's impact, a plain-language explanation, its source, confidence, and known limitations. An unavailable input receives no hidden estimate. Neutral placeholders are labeled explicitly.

Asset Intelligence advises; the GM decides.

## Four intelligence layers

1. **Football Intelligence** uses available age, position, NFL roster status, injury designation, experience, and bye-week facts. Production, opportunity, usage, coaching, supporting cast, offensive environment, and contract feeds are extension points and remain disclosed when absent.
2. **League Intelligence** carries scoring and roster settings, including an explicit Superflex QB adjustment. Positional scarcity and league trends can be added as evidence providers.
3. **Front Office Intelligence** carries the Active Front Office, roster depth, needs, strategy, and Decision Engine competitive window. Team Fit is therefore contextual rather than universal.
4. **Decision Engine Integration** aggregates individual player and pick reports through portfolio adapters. Team evaluation no longer owns separate asset formulas.

## Four core player values

- **Dynasty Value** measures long-term asset flexibility from position-aware age and current roster-status signals.
- **Redraft Value** measures current-season availability and opportunity signals independently from dynasty value.
- **Market Value** represents market consensus. V1 remains neutral at 50/100 with low confidence because no traceable consensus provider is connected.
- **Team Fit Value** selects the relevant horizon for the Active Front Office window and adjusts for observable position need.

The values are intentionally independent. None is an overall player score.

## Player dossier

`PlayerReport` contains an executive summary, normalized snapshot, four core values, conservative archetypes, strengths, weaknesses, multi-factor risk, current/2-year/long-term opportunity horizons, contextual recommendation, and combined limitations. Supporting Evidence uses collapsed `<details>` regions in the current server-rendered page.

Archetypes are limited to claims supported by cached evidence. Elite, breakout, buy-low, or sell-high labels require future production and market providers.

## Evidence Engine

`Evidence` records `factor`, `observed_value`, numeric `impact`, `explanation`, `source`, and availability. `EvidenceEngine` calculates bounded confidence from evidence coverage and produces deterministic summaries. Confidence describes evidence completeness, not the probability that an action succeeds.

## Draft-pick intelligence

`PickReport` uses a published round baseline and explicit time discount. It exposes Dynasty Value, neutral Market Value, risk, expected range, time horizon, recommendation, and limitations. V1 never assumes an early, middle, or late slot when projected finish is unknown.

## Architecture

```text
src/core/asset_intelligence/
|-- engine.py                 stable facade
|-- models/                   context, evidence, value, dossier, and pick contracts
|-- evidence/                 confidence and evidence summarization
|-- players/                  profile, values, league context, risk, archetypes, evaluator
|-- picks/                    value, risk, and evaluator
`-- portfolio.py              Decision Engine adapters
```

`services/asset_intelligence.py` assembles application context from cached league and Active Front Office data. `components/asset_intelligence.py` renders reports without performing calculations.

## Player discovery API

`GET /api/players` is the canonical player-dossier index. It lists cached rostered players only and returns `player_id`, display fields, owning roster IDs, and the correctly encoded `dossier_url`. Consumers must use that URL rather than constructing `/players/` without an ID.

`GET /api/league?include_players=true` embeds the same lightweight index for clients that need league data and dossier discovery together. The default league response continues to omit the full NFL player database. Both contracts work entirely from cached data when Sleeper is unavailable.

## Extension rules

- Add new facts as focused evidence providers, not template logic.
- Preserve separate Dynasty, Redraft, Market, and Team Fit values.
- Never convert missing data into an undisclosed estimate.
- Keep provider inputs and formula weights visible and tested.
- Maintain stable report contracts so future modules do not require redesign.

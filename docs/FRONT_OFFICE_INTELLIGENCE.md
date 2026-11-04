# Front Office Intelligence v1

## Purpose and philosophy

Front Office Intelligence answers: **How does this Front Office make fantasy-football decisions?** It describes organizations from observable league actions so recommendations can be more realistic without judging managers or inferring personal traits.

The same cached input always produces the same report. Every classification exposes its source evidence. When history is sparse, DTOS uses a labeled neutral default and withholds acceptance probability instead of guessing.

## Architecture

`src/core/front_office_intelligence/` is the shared intelligence layer. Its engine consumes Decision Engine team evaluations and cached Sleeper rosters, transactions, and draft-pick ownership. It produces immutable organization reports, pairwise compatibility reports, negotiation forecasts, and a league relationship graph.

The layers are:

1. `models.py` — stable report, activity, preference, compatibility, forecast, and relationship contracts.
2. `engine.py` — deterministic evidence collection, classification, and league-model orchestration.
3. `services/front_office_intelligence.py` — application view selection.
4. `components/front_office_intelligence.py` — presentation only.
5. `routes/front_offices.py` — `/front-offices` and `/api/front-offices` contracts.

## Behavioral and evidence model

Profiles use completed trade count, waiver/add/drop activity, current roster age composition, owned draft assets, Decision Engine horizons, positional needs, and depth. V1 does not have response-time, counteroffer, draft-result, or offer-rejection history, so it does not assign those behaviors.

Competitive windows map the Decision Engine's independent current and future outlooks to product-facing phases. Organizational philosophies describe observable roster construction and activity. Asset preferences require an explicit threshold; otherwise the report says no strong preference is established.

Compatibility compares each organization's Decision Engine needs with the other's depth surplus, then gives completed bilateral trades a small, capped familiarity signal. Relationship graph edges mean only observed trade history and calculated roster compatibility. They never represent personal relationships.

Acceptance probability remains unavailable until both organizations have at least five observed trades and the pair has at least three completed bilateral trades. When available it is capped conservatively at 65% and is never presented as a prediction or guarantee.

## Integration points

Trade Intelligence delegates partner compatibility and negotiation context to this module while continuing to consume Asset Intelligence for player and pick values. Commissioner Desk, Team Headquarters, Draft Assistant, and future Market Intelligence can consume the same report contracts without duplicating behavior logic.

Future providers can add historical drafts, offer/counter events, seasonal activity normalization, or persistent snapshots behind these contracts. New evidence must remain observable, traceable, neutral, and compatible with cached operation.

## Privacy and fairness boundary

DTOS models fantasy-football actions only. It does not infer personality, character, competence, relationships, private intent, or traits outside the league. Labels such as “good” or “bad” manager are prohibited. Users can inspect every contributing factor, source, limitation, and confidence signal.

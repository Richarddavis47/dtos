# DTOS v0.9.7 - Front Office Intelligence v1

DTOS v0.9.7 introduces a shared, explainable model of how each organization behaves inside its fantasy league. It improves recommendations from observable actions without judging managers or inferring personal characteristics.

## Highlights

- Gives every organization an evidence-backed competitive window, philosophy, activity profile, negotiation style, asset preferences, strengths, constraints, and confidence score.
- Calculates pairwise compatibility from Decision Engine needs and depth, with a small capped signal for completed bilateral trades.
- Uses Asset Intelligence portfolio reports as shared asset context without duplicating valuation formulas.
- Adds conservative negotiation forecasts, alternative structures, fallback targets, and explicit sparse-history limitations.
- Adds an informational relationship graph limited to observed league activity and roster compatibility.
- Makes Trade Intelligence consume this shared layer for partner selection and negotiation context.
- Adds `/front-offices` and `/api/front-offices`, plus Commissioner Desk navigation and Team Headquarters integration.

## Metadata

- Application: DTOS
- Version: 0.9.7
- Build: 907
- Codename: Front Office Intelligence v1

## Intentional boundaries

- Acceptance probability remains unavailable until both organizations and their bilateral history cross documented minimum sample thresholds; even then it is capped at 65%.
- Cached data does not expose response timing, rejected offers, counteroffers, or private negotiation intent, so v1 does not classify those behaviors.
- Relationship edges describe completed trades and calculated compatibility only, never personal relationships.
- DTOS does not infer personality, competence, character, or traits outside observable fantasy-football actions.

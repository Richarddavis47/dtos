# DTOS v0.9.4 - Decision Engine v1

DTOS v0.9.4 introduces the shared intelligence layer that future Front Office modules can extend without duplicating evaluation logic.

## Highlights

- Added contextual team profiles carrying Active Front Office, league settings, strategy, league context, positional rooms, and market-context extension points.
- Evaluates Current Championship Outlook and Future Outlook independently; DTOS no longer presents a single overall team score.
- Added deterministic Depth and Asset Health horizons plus QB, RB, WR, and TE room evaluations.
- Classifies Championship, Playoff, Transition, Rebuild, and Ascension windows with concise explanations.
- Standardized Buy, Sell, Hold, Trade, Compete, Rebuild, Waiver, and Monitor recommendation categories.
- Every recommendation includes priority, bounded confidence, reasoning, supporting metrics, and a future explanation hook.
- Commissioner Desk and Team Headquarters now consume the same engine while preserving their executive layouts.

## Metadata

- Application: DTOS
- Version: 0.9.4
- Build: 904
- Codename: Decision Engine v1

## Intentional boundaries

- V1 uses transparent heuristics and neutral fallbacks; it does not claim predictive accuracy.
- Live projections, dynasty market values, simulations, machine learning, AI chat, and automated trade negotiation are not included.
- The engine advises; the GM retains the final decision.
- Future modules should extend the shared contracts and providers rather than duplicate scoring logic.

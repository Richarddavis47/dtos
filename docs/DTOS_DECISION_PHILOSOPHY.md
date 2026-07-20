# DTOS Decision Philosophy

## Purpose

The Decision Engine is DTOS's shared intelligence layer. Commissioner Desk, Team Headquarters, Trade Center, Player Intelligence, GM Intelligence, League Reports, Draft Assistant, and notifications should consume the same contracts instead of inventing page-specific evaluation logic.

## Context over raw rankings

No player, pick, trade, or roster is evaluated in isolation. An evaluation receives an explicit context: Active Front Office, league identity and settings, team strategy, competitive window, league-relative inputs, positional conditions, and available market conditions. Missing context is disclosed and handled with a neutral fallback rather than fabricated.

## Separate current and future

DTOS does not generate an Overall Team Score. Current Championship Outlook measures observable present-season strength. Future Outlook measures age structure, young assets, and draft flexibility. A team can be strong in one horizon and weak in the other; neither result is allowed to overwrite the other.

Depth and Asset Health are additional independent evaluations. Each horizon exposes its score, confidence, factors, data sources, and limitations.

## Explainable intelligence

Every recommendation includes:

- A title and concise summary.
- A category and High, Medium, or Low priority.
- A confidence score from 0 to 100.
- Reasoning that remains collapsed by default in the interface.
- Supporting metrics a GM can verify.
- A stable hook for future explanation providers.

Confidence describes the completeness and consistency of available evidence. It is not a probability that a recommended action will succeed.

## Simple interface, powerful backend

Pages should remain readable executive briefings. Calculation belongs in modular evaluators, not templates. Presentation components receive stable, typed results and decide only how to display them. New data providers may replace v1 heuristics without requiring a page redesign.

## DTOS advises; the GM decides

Recommendations support human judgment and never replace it. DTOS must expose uncertainty, limitations, and competing horizons so the GM can make the final decision. The system does not negotiate trades, execute roster moves, or present speculation as fact.

## Extension contract

Future work should add or replace focused providers for projections, dynasty market value, positional scarcity, league history, owner tendencies, trend detection, and simulations. Extensions must continue to return the shared evaluation and recommendation models, preserve current/future separation, and include inspectable evidence.

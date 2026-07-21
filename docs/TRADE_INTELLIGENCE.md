# Trade Intelligence v1

## Purpose

Trade Intelligence answers: **What is the best trade available for this Front Office right now?** It is a contextual opportunity and explanation engine, not a universal trade calculator. DTOS proposes evidence-backed options; the GM decides whether to contact a partner or make a roster move.

## Architecture

```text
src/core/trade_intelligence/
|-- engine/       orchestration, generation, evaluation, negotiation, prioritization
|-- analysis/     current, future, balance, depth, value, risk, and efficiency impacts
|-- market/       recipient-context player and pick pools
|-- gm/           partner compatibility and cached-history signals
|-- evidence/     shared traceable trade evidence helpers
`-- models/       proposals, partners, impacts, recommendations, negotiations, dossiers
```

`services/trade_intelligence.py` selects the Active Front Office and builds the presentation-neutral result. `components/trade_intelligence.py` renders the read-only executive view. `routes/trades.py` exposes `/trades` and `/api/trades`.

## Recommendation philosophy

There is no universally good trade. Every opportunity uses the Active Front Office's team window, position needs, roster depth, and strategy; the partner's needs and surpluses; cached asset values; package balance; and available trade history. Current and future value remain separate.

Every recommendation includes priority, confidence, Expected Value, bilateral reasoning, and supporting evidence. Confidence reflects evidence completeness and package balance, not acceptance probability. Acceptance remains explicitly unavailable until a validated GM behavior provider exists.

## Trade generation process

1. Decision Engine evaluates every team and identifies windows, weak rooms, and surplus rooms.
2. Asset Intelligence evaluates every eligible player and pick in the recipient Front Office context.
3. Partner Intelligence ranks complementary needs and adds a small, disclosed cached bilateral-trade familiarity signal.
4. The generator considers bounded shortlists and supports 1-for-1, 2-for-1, 3-for-2, player-plus-pick, pick-package, and multi-asset shapes.
5. A package is retained only when blended Dynasty and Team Fit values are within the documented 0.80–1.25 balance boundary.
6. Duplicate packages are removed and opportunities are ranked deterministically.

The boundary prevents intentionally imbalanced proposals. It does not claim that a manager will accept an offer.

## Evaluation process

Each proposal exposes:

- Current Outlook Impact from Redraft Value.
- Future Outlook Impact from Dynasty Value.
- Roster Balance and Positional Depth against Decision Engine needs.
- Asset Value using package Dynasty Value totals.
- Risk using Asset Intelligence risk reports.
- Opportunity Cost from negative asset-value deltas.
- Market Efficiency from the currently available Market Value provider.
- Championship Outlook as a documented current/fit proxy, never a probability.

The dossier explains why the Active Front Office improves, why the partner receives contextual value, why the package falls inside the realism boundary, and why the current team window makes the opportunity timely.

## Negotiation process

V1 produces a human-controlled opening offer, likely-counter guidance, a value-based walk-away boundary, a fallback package, alternative cached targets, and negotiation notes. It does not send messages, submit trades, predict private intentions, or negotiate automatically.

## Trade types and priority

The engine can classify Championship Push, Rebuild, Value Arbitrage, Age Swap, Pick Acquisition, Depth Upgrade, Elite Consolidation, Roster Balance, Market Exploit, Sell High, and Buy Low opportunities. V1 assigns only classifications supported by current evidence; future market feeds can activate the market-movement types without changing the enum or dossier.

Priorities are Urgent, High, Medium, Low, and Future Watch. Urgent is reserved for future time-sensitive evidence providers and is not fabricated from cached roster data.

## Integration points

- **Decision Engine:** team windows, current/future horizons, position needs, depth, and asset-health context.
- **Asset Intelligence:** every player value, pick value, Team Fit value, risk input, and source evidence.
- **Evidence Engine:** shared observable evidence contracts and confidence inputs.
- **GM Intelligence:** future acceptance, preferences, response patterns, and negotiation complexity.
- **Market Intelligence:** future consensus, movement, buy-low, sell-high, and market-efficiency inputs.
- **Commissioner Desk and Team HQ:** stable links and future embedded opportunity summaries.
- **Draft Assistant, mobile, and notifications:** stable API/dossier contracts.

Extensions must enrich providers rather than copy Decision or Asset Intelligence formulas into Trade Intelligence.

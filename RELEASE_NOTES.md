# DTOS v0.9.6 - Trade Intelligence v1

DTOS v0.9.6 introduces a deterministic Assistant General Manager that identifies and explains contextual trade opportunities without acting like a universal trade calculator.

## Highlights

- Evaluates every potential partner through Decision Engine roster needs, strengths, team windows, and cached bilateral trade history.
- Builds player and pick pools exclusively through Asset Intelligence reports.
- Generates bounded 1-for-1, 2-for-1, 3-for-2, player-plus-pick, pick-package, and multi-asset proposals.
- Keeps Current Outlook and Future Outlook impacts independent.
- Evaluates roster balance, positional depth, asset value, risk, opportunity cost, market efficiency, and a clearly labeled championship-outlook proxy.
- Produces prioritized Trade Dossiers with evidence for why each side benefits, why the package is balanced, and why the timing fits the Active Front Office.
- Adds opening offer, likely counter, walk-away point, fallback, alternative targets, and human-controlled negotiation notes.
- Adds `/trades` and `/api/trades`, plus Team HQ and navigation integration.

## Metadata

- Application: DTOS
- Version: 0.9.6
- Build: 906
- Codename: Trade Intelligence v1

## Intentional boundaries

- Acceptance likelihood remains unavailable until a validated GM behavior model exists.
- Market consensus remains neutral where Asset Intelligence lacks an external provider.
- Championship impact is an explainable current-value proxy, not a probability forecast.
- Cached historical trades provide a small familiarity signal; they do not imply manager intent.
- DTOS does not message managers, submit trades, negotiate automatically, or execute roster moves.

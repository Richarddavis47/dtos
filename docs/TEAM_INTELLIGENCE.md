# DTOS Team Intelligence

DTOS v1.4.5 provides one reusable, league-relative Team Intelligence Card for every franchise. Commissioner Desk, Team Headquarters, Front Office views, League Intelligence, and public crawl APIs consume the same classification contract.

## Methodology

Raw team inputs continue to come from existing DTOS systems:

- canonical 0–1000 player and pick values from Valuation Calibration;
- win-now, rebuild, risk, confidence, and liquidity from Asset Intelligence;
- quality-first position rooms and diminishing bench depth from Roster Intelligence;
- league format, superflex, scarcity, roster requirements, taxi, and IR context already carried by Decision Engine profiles.

Each category is ranked against the selected league. Ties receive identical ranks and percentiles. Letter grades derive from league percentile, not an absolute score threshold.

| Percentile | Grade |
| ---: | --- |
| 90–100 | A+ |
| 80–89 | A |
| 65–79 | A- |
| 50–64 | B+ |
| 40–49 | B |
| 30–39 | C |
| 20–29 | D |
| 0–19 | F |

## Overall weighting

| Category | Weight |
| --- | ---: |
| Current Contending | 22% |
| Dynasty | 14% |
| Starting Lineup | 14% |
| Depth | 9% |
| QB / RB / WR / TE | 7% / 6% / 7% / 5% |
| Draft Capital | 6% |
| Youth | 4% |
| Future Outlook | 3% |
| Roster Flexibility | 2% |
| Asset Liquidity | 1% |

Depth uses only the next five bench assets after starters and applies Roster Intelligence's quality weighting. Additional replacement-level bodies do not receive equal credit.

## Competitive windows

Exactly six mutually exclusive values are public:

- Elite Contender
- Contender
- Playoff Team
- Re-tooling
- Rebuilding
- Full Rebuild

Classification uses current, future, and overall league-relative strength. It does not use a separate page-specific vocabulary.

## Preseason behavior

When no team has completed a game, league tables are labeled `Preseason Projection`. Projected order comes from Team Intelligence rather than arbitrary 0–0 standings order. Current records become descriptive inputs only after games exist.

## Public API

`/api/crawl/teams`, `/api/crawl/front-offices`, and `/api/crawl/snapshot` expose concise cards with `team_intelligence_schema_version: "1.0"`. Each card includes category grade, score, percentile, rank, confidence, current window, and explanation. Detailed internal evidence remains outside list responses to protect response size.

## Limitations

Projected wins, playoff odds, and championship odds are deterministic relative-strength indicators derived from league percentiles. They are estimates, not simulations or guarantees.

- Historical risers and fallers remain unavailable until prior Team Intelligence snapshots are retained.
- Production, contract, and role inputs remain limited by configured providers.
- Championship and playoff odds are relative strength indicators, not simulation probabilities.

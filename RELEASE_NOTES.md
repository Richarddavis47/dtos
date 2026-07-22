# DTOS v1.4.2 — Provider Data Flow Activation

DTOS now carries approved public provider data through transport, normalization, canonical identity, consensus, API, and player-page presentation. Legitimate values are shown with attribution; unsupported fields explain the exact provider limitation.

## Highlights

- FantasyCalc and DynastyProcess public values now refresh into the canonical market cache with visible attribution.
- Sleeper player metadata, depth-chart fields, ownership, transactions, and trending activity reach player pages end to end.
- Provider failures preserve prior data only as a disclosed cached fallback; unsupported sources state the exact limitation.
- Bijan Robinson resolves to Sleeper ID `9509`; FantasyCalc value `10213` remains a value, never an identity.
- Canonical DTOS player identities reconcile Sleeper, FantasyCalc, KeepTradeCut, FantasyPros, Underdog, and Dynasty Daddy identifiers when supplied.
- Normalization covers names, teams, position eligibility, free agents, rookies, values, rankings, ADP, timestamps, confidence, and metadata.
- Invalid values, broken IDs, provider mismatches, and conflicting metadata are blocked before entering consensus.
- Provider reliability tracks success, failure, schema stability, and latency.
- Consensus 2.1 weights confidence, reliability, freshness, agreement, coverage, and missing sources without using a simple average.
- Sleeper trending adds and drops use the documented public API and remain cached for offline operation.
- Player dossiers display normalized identity, consensus, provider values, freshness, confidence, availability, licensing, and unavailable reasons.
- `/api/players/{player_id}/intelligence` exposes the full normalized player contract.
- Settings provides a Provider Activation Dashboard.

## Metadata

- Version: 1.4.2
- Build: 1420
- Codename: Provider Data Flow Activation

## Provider boundaries

- Sleeper league, player, roster, transaction, trade, matchup, metadata, and trending endpoints are active through its official read-only API.
- Cached provider values are normalized and attributed when legitimately supplied to DTOS.
- FantasyCalc remains subject to its attribution, caching, and commercial-use terms.
- Providers without approved public or licensed access remain explicitly disabled; no scraping or fabricated data is introduced.

## Non-goals preserved

No championship probability, Decision Engine change, trade recommendation change, machine learning, or scouting feature was added.

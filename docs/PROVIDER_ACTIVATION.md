# Provider Activation Guide

## Rules

Activate a provider only when DTOS has a documented public API or approved licensed integration. Never scrape an unsupported source, invent a value, or hide a fallback. Every activation must declare licensing, refresh support, attribution, rate limits, normalization, reliability, and failure behavior.

## Active access

Sleeper's official read-only API supplies league settings, players, rosters, picks, transactions, trades, matchups, standings, NFL state, and trending adds/drops. Player metadata is refreshed at most daily; trending data is attributed to Sleeper and follows published API guidance.

Existing cached FantasyCalc-, KeepTradeCut-, Sleeper ADP-, and DynastyProcess-compatible values are accepted only through normalized adapters when legitimately supplied. Cache ingestion is not represented as a live upstream request.

## Configuration-gated access

FantasyCalc usage must comply with attribution, caching, non-substitution, and commercial-use restrictions. FantasyPros and commercial news sources require approved credentials or licensing. Underdog, Dynasty Daddy, KeepTradeCut, and other sources remain disabled where no approved public contract exists.

Configure enablement with `DTOS_PROVIDER_<NORMALIZED_NAME>`. Enabling a provider does not bypass missing credentials, licensing, normalization, or quality gates.

## Adding an adapter

1. Confirm access and licensing.
2. Implement the Data Provider SDK contract.
3. Normalize identity and every field.
4. Add deterministic live, cached, historical, unavailable, schema-change, and rate-limit tests.
5. Document attribution and refresh limits.
6. Verify no provider-specific object reaches an intelligence engine.

## Source coverage inventory — build 2257

| Evidence | Existing connected path | Coverage and limits |
|---|---|---|
| Fantasy projections | Sleeper weekly projection publication, league scoring and exact player/week identity | Numeric zero and negatives are supported. ADP-only rows without scoring statistics are unavailable, not zero. Selected-player evidence does not establish complete catalog coverage. |
| Fantasy results | Retained Sleeper league matchup player/starter scores | Compatible completed observations, live/unconfirmed observations, conflicts and missing coverage remain distinct. No NFLverse scoring fallback. |
| Auxiliary football analysis | Retained nflverse box-score facts | Targets/carries/receptions where supported, separately qualified by source check and observation boundary. Does not supply authoritative fantasy scores. Snaps, routes and future models remain unsupported. |
| Neutral Market | Existing compatible FantasyCalc and DynastyProcess adapters | Provider/format/method compatibility and source clocks still apply. No personal Custom values substituted. Unsupported/licensed feeds are not activated. |
| Franchise history | Sleeper season chain and retained weekly transaction buckets | Existing admitted preparation recovers only gaps, at most19periods and4concurrent requests per season. A failed period waits at least5minutes before another preparation attempt. Existing observed buckets are not refreshed by this recovery. No page-render acquisition or automatic retry loop. |

Player source health is a read-only scoped disclosure; evaluator/Trade eligibility does not consume its labels. It separates configured capability, prepared observation count, original observation/source clocks, freshness and failure. Unknown clocks remain unknown. A complete-season cache’s structural validity is not proof of complete transaction acquisition. A verified source league/season is required before gap recovery; aliases and incompatible archives do not authorize a fetch. Atomic writes retain other source families, transaction identities and historical grade provenance.

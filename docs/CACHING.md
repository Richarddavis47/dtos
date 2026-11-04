# Caching Architecture

DTOS has three distinct cache layers:

1. `DTOS_CACHE_FILE` stores the last normalized Sleeper snapshot for restart and network-failure resilience.
2. `IntelligenceCache` stores snapshot-scoped Decision, Asset, Front Office, Trade, Market, and final results with a configurable TTL.
3. `MarketQuoteCache` stores provider quotes with provider/execution metadata and explicit stale-fallback rules.

Successful Sleeper or transaction refresh invalidates affected intelligence snapshots. Expired entries are recomputed. An exception never overwrites a valid persisted Sleeper cache. Corrupted JSON is logged and treated as unavailable rather than crashing startup.

Health output reports entries, hits, misses, hit rate, invalidations, TTL, provider fallback counts, and market cache age. Cache keys must include every context dimension that can change an answer. Preserve `DTOS_CACHE_FILE`; do not assume a home-directory path or shared filesystem.

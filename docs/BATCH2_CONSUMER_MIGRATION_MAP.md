# Canonical evidence → downstream migration map

Batch 2 establishes source facts, temporal boundaries, identity reconciliation,
shared storage and scoped derivation. It does **not** tune valuation models,
rankings, FOIS grades or trade recommendation weights. Batch 3 is not started.

| Consumer boundary | Current verified input | Canonical evidence available in candidate | Remaining migration |
| --- | --- | --- | --- |
| `player_value_projection/providers.py` — `CachedProductionProvider` | Player dictionaries: `fantasy_points_history`, `recent_points`, season-average fields | Global nflverse game production, source identity, explicit missing data and league-scored reads | Replace legacy dictionary production windows with bounded canonical windows; explicitly select season/denominator. Do not silently score incomplete games. |
| `projection_intelligence/calibration.py` | Legacy recent-points and season-average fields | Shared raw production and derived target/carry usage | Later player-intelligence batch must consume canonical evidence before changing calibration. No coefficients changed in Batch 2. |
| `player_value_projection/engine.py` | Existing projection registry, market reports and historical-evidence dictionaries | Canonical production/usage plus existing scoped Sleeper projection snapshot | Migrate evidence plumbing separately from value/rank calibration; preserve explicit unavailable state. |
| `data_platform/provider_activation.py` / player intelligence API | Sleeper player metadata; existing provider registry | Scoped projection bridge and bounded `canonical_evidence` production/usage facade | Bulk legacy valuation consumers still require explicit migration; no per-universe request-time SQL/provider loop introduced. |
| `historical_intelligence/service.py` | CanonicalHistoryStore over disposable Sleeper cache | Corrected postseason/byes, fractional standings, missing results, draft IDs and FAAB facts | Audit all event-type consumer assumptions; preserve source-season identity and incomplete coverage. No manual GM-score corrections. |
| `historical_franchise_state/service.py` | Reverse canonical transactions from source roster/pick state | Real trade, completed waiver, free-agent and draft boundary examples; failed claims excluded; no provider calls during reconstruction | Future consumer migration must preserve missing exact draft times, season-observed tenure and unavailable historical status/market evidence. |
| `fois/service.py` / historical transaction evaluator | Scoped historical facts and generation-scoped permanent checkpoint evidence | Richer canonical facts and shared NFL evidence, independent of current-value substitution | Batch 4 must reconcile evidence consumption/grades. Retain v1.15.1 semantic deduplication and v1.14.0 checkpoint batching. |
| `brain/service.py`, `intelligence/team_assessment.py`, `team_intelligence/engine.py` | Existing scoped intelligence products | One shared evidence source with league-specific scoring possible | Migrate at the planned downstream boundary; one canonical assessment generation and league identity remain mandatory. |
| `asset_market/engine.py` | Existing Brain/valuation/provider semantic contracts | Global evidence storage is additive, not an alternative current-market fallback | Any future consumption must explicitly include semantic evidence dependencies, not retrieval timestamps. Preserve artifact compatibility/restart rules. |
| `trade_intelligence/evidence_context.py` | Precomputed scoped FOIS/behavior/trend products | Reconciled historical source inputs beneath those products | Preserve Batch 1 Trade Center and zero request-time raw-history scans; later batches consume improved derived products, not bulk provider reads. |

## Evidence availability boundaries

- Production: real 2021–2025 files verified available; 2026 file currently 404.
  No previous-season substitution for current-season production.
- Usage: target/carry counts derive from the same production facts without a
  second stored payload. Snaps/routes and missing team denominators remain absent.
- Schedule: real global game IDs/kickoffs; documented Eastern timezone converted
  with IANA data. Future kickoff can be known today, but a current observation is
  never available before its knowledge boundary.
  A bounded canonical team-schedule derivation is implemented; 2026 Buffalo's
  17-game schedule and week-7 bye were verified against the full current source.
  Existing projection/matchup schedule consumers have not been replaced.
- Contracts, snap/route detail and other proposed feeds require source-specific
  current-coverage/permitted-use proof. A downloader's code license is not a
  substitute for upstream data rights. Unapproved families stay unconnected.
- Sleeper current status/depth metadata are current catalog facts, not proof of
  historical point-in-time injury/role. Historical gaps must remain explicit.

This is an implementation tracking map, **not a completed release report**.
Remaining source-family/canonical facade work and final acceptance are required.

The player intelligence API now includes a bounded `canonical_evidence` facade
with season-scoped scoring, usage and source availability. Older provider text
and bulk downstream consumers still require the explicit migrations above; this
does not claim those consumers already use the new NFL evidence. Historical
franchise weekly-result plumbing has also been corrected to exclude unproven
same-week/future totals at timestamp and event boundaries.

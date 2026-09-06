# Live Product Inspection

## How ChatGPT inspects DTOS

1. Start at `https://dtos.onrender.com/api/inspect/live`.
2. Read the current production identity.
3. Follow collection links to discover teams, matchups, relevant players, picks,
   seasons, FOIS profiles, and public APIs.
4. Use semantic URLs for exact values and human URLs for visual inspection.
5. Use release identity and sanitized validation results for version comparison.
6. Use `/api/audit/projections/current` for full projection calibration.

The root is compact and self-describing. Large collections are paginated. Live
Inspection reads only retained or persisted canonical state and never initiates
provider synchronization, Projection or Brain generation, Asset Market
construction, FOIS calculation, or Historical Memory writes.

## Inspect once, extend forever

The canonical FastAPI application router owns public-surface metadata. Every
public GET route is inspection-enabled by default. A route can be excluded only
through a documented approved classification such as crawler control, internal,
sensitive, administrative, or unsafe. Building a separate manually maintained
Live Inspection URL list is an anti-pattern.

The registry supplies current semantic inspection and dynamically resolves canonical
entities. New public routes appear without a separate hardcoded surface list.
Automated visual capture/publication is retired. Prior published assets remain
historical, not a current-readiness dependency.

## Healthy contract

```json
{
  "status": "available",
  "mode": "semantic_read_only"
}
```

Every release must verify current identity, completeness, critical links,
presentation contracts, and zero side effects from the public root.

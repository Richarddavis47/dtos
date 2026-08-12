# Live Product Inspection

## How ChatGPT inspects DTOS

1. Start at `https://dtos.onrender.com/api/inspect/live`.
2. Read the current production identity.
3. Follow collection links to discover teams, matchups, relevant players, picks,
   seasons, FOIS profiles, and public APIs.
4. Use semantic URLs for exact values and human URLs for visual inspection.
5. Use DINS for immutable release comparison.
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

The registry supplies current Live Inspection and API discovery; existing DINS
page discovery consumes the same application route source and dynamically
resolves canonical entities. New public routes therefore appear without edits to
Live Inspection-specific code. Removed routes disappear while immutable prior
DINS releases remain unchanged.

## Healthy contract

```json
{
  "status": "complete",
  "completeness_percent": 100.0,
  "broken_links": 0,
  "side_effects": 0
}
```

Every release must verify current identity, completeness, critical links,
presentation contracts, and zero side effects from the public root.

# Live Visual Inspection

Live Visual Inspection is the rolling, read-only presentation layer above the
canonical v1.10.10 Live Product Inspection contract. It captures the real public
DTOS page and never reconstructs a special inspection page.

## External-assistant workflow

1. Fetch `/api/inspect/live`.
2. Follow `visual_inspection` or the `matchups` collection.
3. Follow a matchup's semantic URL.
4. Follow `visual.mobile` or `visual.desktop`.
5. Download the anonymous PNG.
6. Inspect the rendered presentation.
7. Cross-check values through `/api/audit/projections/current` when needed.

## Capture contract

- `/api/inspect/live/visual` — rolling visual index.
- `/api/inspect/live/visual/manifest` — current capture inventory.
- `/api/inspect/live/visual/health` — queue, failure, and browser-process health.
- `/api/inspect/live/visual/captures/{surface_id}/{viewport}.png` — public PNG.
- `/api/inspect/live/visual/metadata/{surface_id}/{viewport}` — DOM and identity metadata.

Current matchups are mandatory at 390×844 mobile and 1440×1000 desktop
viewports. Public surfaces inherit eligibility from the canonical route registry;
bounded policy selects core, representative, or demand/background capture rather
than continuously rendering every dynamic entity.

Capture runs after successful canonical startup and after a material matchup
presentation fingerprint changes. Observation timestamps do not cause work.
One background worker serializes browser use, publishes atomically, and retains
the last valid capture on failure. HTTP reads only inspect retained files.

## Permanent release gate

Every release must report both:

- Live Product Inspection: Complete
- Live Visual Inspection: Complete

The production gate requires every current matchup's mobile and desktop PNG,
canonical DOM reconciliation, anonymous HTTP access, and deterministic browser
cleanup before DINS publication.

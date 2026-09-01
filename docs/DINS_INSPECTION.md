# DTOS AI Inspection System (DINS)

## Purpose

DINS provides a stable JSON description of what major DTOS pages render. It is
designed for automated agents, regression tools, accessibility analysis, and
future presentation-contract verification that should not parse raw HTML.

For v1.6.5, browser artifacts also verify the Product Design System contract:
shared headers, primary actions, explainable recommendation panels, meaningful
dynamic page names, absence of internal identifier labels, accessibility findings,
and public artifact URLs. A violation fails the visual release manifest.

DINS is an inspection boundary, not another business-logic layer. It reports
cached facts and page structure; it does not reproduce DTOS calculations.

## Safety contract

Every DINS request is:

- read-only;
- deterministic for the same cached state;
- limited to `STATE["data"]`, cached timestamps, and cached error metadata;
- free of Sleeper synchronization and provider requests;
- free of Intelligence Orchestrator and page-view-model execution;
- free of database writes and application-state changes;
- free of raw HTML.

Inspection endpoints do not use `ensure_fresh`, `sync_sleeper`, or any refresh
route. They remain useful during provider outages because cached data and explicit
availability states are sufficient.

## Schema version

The inspection schema is version `1.0`, independent from the DTOS application
version. Each response contains:

- `application_version`
- `inspection_schema_version`
- `page_name`
- `route`
- `sections`
- `cards`
- `tables`
- `charts`
- `buttons`
- `navigation`
- `links`
- `empty_states`
- `placeholder_actions`
- `warnings`
- `page_metrics`
- `last_updated`

Sections, cards, and charts use an `InspectionElement` contract containing a
stable key, title, component type, structured data, and availability status.
Tables declare stable columns and row objects. Actions distinguish enabled
controls from placeholders. Links declare their relationship to the inspected
page.

`page_metrics` provides section, card, table, chart, button, navigation, link,
empty-state, placeholder, warning, and table-row counts. Counts are derived from
the returned contract rather than maintained separately.

`last_updated` is the cached successful synchronization timestamp. It is `null`
when no successful synchronization is cached, accompanied by an explicit warning.

## Endpoints

### `GET /api/inspect`

Returns the DINS contract and inspection-page catalog as cards and links.

### `GET /api/inspect/pages`

Returns the registered page catalog as a table with page route, inspection route,
and scope.

### `GET /api/inspect/team/{roster_id}`

Describes Team Headquarters, including its header, snapshot, summary, grades,
roster, draft capital, performance, timeline, future outlook, and quick actions.
Cached players and picks are returned as tables. Player links and placeholder
actions are explicit.

### `GET /api/inspect/player/{player_id}`

Describes the Player Dossier and exposes cached identity, ownership, trending,
and provider-value evidence. It does not calculate a new dossier, consensus,
projection, recommendation, or team-fit score.

### `GET /api/inspect/front-office/{roster_id}`

Describes Front Office Intelligence sections and reports cached organization,
roster, draft-capital, and activity inputs. It does not execute Front Office
Intelligence or infer organizational behavior.

### `GET /api/inspect/trades`

Describes Trade Intelligence and lists only cached transactions whose type is
`trade`. It does not generate, value, rank, or negotiate packages.

Unknown team, player, and Front Office identifiers return HTTP 404 with an
explicit cached-state explanation.

## Empty states and warnings

Missing rosters, picks, transactions, provider values, or synchronization
timestamps are represented as structured empty states or warnings. Absence is
never converted into fabricated content. A cached synchronization error is
surfaced as a warning without initiating recovery.

## Extensibility and limitations

## DINS 2.0 visual and release architecture

DTOS v1.6.3 retains the v1 semantic endpoints and adds six coordinated layers:
semantic contracts, rendered visuals, sanitized DOM/accessibility evidence, curated
style/geometry measurements, deterministic interactions, and versioned release
manifests. The FastAPI route registry is the inventory source. Dynamic team, player,
and matchup paths are expanded from cached deterministic representatives; an unknown
parameter type fails release route validation instead of silently disappearing.

Artifacts live below `static/inspection/v{version}-b{build}-s{schema}` and are exposed
through `/inspection-artifacts/...`. The web service only reads these files.
Release manifests use runtime deployment metadata from `/api/status`, including
the deployed commit, source branch, and deployment timestamp. Public captures must
set `DTOS_PUBLIC_URL` (or pass `--public-url` to the capture command); localhost
transport URLs are never accepted as publication identity and fail closed when
no public origin is configured. Run the
bounded capture worker after deployment:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m tools.inspection.capture --base-url https://dtos.onrender.com
```

The worker sends `X-DTOS-Inspection: deterministic`, uses cached application state,
blocks synchronization in that request context, disables motion, waits for network
idle and document readiness, normalizes ordering through the site map, and closes
Chromium in `finally`. It records network failures without cookies, headers, query
values, environment variables, source, stack traces, or filesystem paths.

Desktop is 1440x1200, tablet is 1024x1366, and mobile is 390x844. Each produces a
viewport screenshot, full-page screenshot, structured page contract, sanitized DOM,
and accessibility report. Current and previous bundles are retained; older metadata
may remain after images are pruned. Missing or stale bundles make inspection health
pending rather than falsely ready. Browser crashes and timeouts produce partial
manifests and fail validation.

Accessibility findings are grouped as critical, serious, moderate, and minor. New
critical findings fail the capture outcome; moderate/minor findings remain visible.
Image comparisons ignore low-level channel differences within a configurable
anti-alias tolerance and report changed-pixel percentages rather than assuming every
intentional change is a regression.

### AI Auditor Quick Start

- Discovery: `https://dtos.onrender.com/api/inspect/site-map`
- Readiness: `https://dtos.onrender.com/api/inspect/health`
- Current release: `https://dtos.onrender.com/api/inspect/releases/current`
- Visual index: `https://dtos.onrender.com/api/inspect/visual/pages`
- Team semantic contract: `https://dtos.onrender.com/api/inspect/team/1`
- Team visual contract: `https://dtos.onrender.com/api/inspect/visual/pages/teams-1/desktop`

## GitHub Release publication

Beginning with v1.6.7, the post-deployment worker captures the exact running Render
commit and packages the result outside the repository. It publishes three immutable,
versioned assets to the matching public GitHub Release:

- `dtos-vX.Y.Z-dins-full.zip`
- `dtos-vX.Y.Z-dins-manifest.json`
- `dtos-vX.Y.Z-dins-checksums.json`

The ZIP contains the release manifest, site map, per-page semantic contracts, all
three viewport and full-page screenshots, DOM and accessibility snapshots,
interactions, network/console evidence, and comparison artifacts. ZIP entries are
sorted with fixed timestamps and permissions so identical inputs produce identical
SHA-256 values.

Production queries the public GitHub Release API using its running version, caches
the result briefly, and validates version, build, merge commit, release tag, schema,
manifest checksum, and capture outcome. `/api/inspect/health?refresh=true` bypasses
the short cache after publication. Missing, partial, corrupt, or stale releases never
report complete. No credentials, repository write, provider synchronization, or
intelligence execution occurs in this read-only lookup.

Post-deployment commands:

```powershell
$env:DTOS_PUBLIC_URL='https://dtos.onrender.com'
.\.venv\Scripts\python.exe -m tools.inspection.capture --base-url https://dtos.onrender.com --output <capture-root>
.\.venv\Scripts\python.exe -m tools.inspection.package <capture-namespace> --output <release-assets>
gh release upload vX.Y.Z <release-assets>\* --clobber
```

The v1.6.2 foundation covers five major page types plus the catalog. Future
versions can add Commissioner Desk, Matchups, Transactions, Draft Picks, History,
Settings, schema-diff tooling, and snapshot fixtures.

DINS currently describes stable semantic regions rather than CSS layout,
pixel geometry, responsive breakpoints, or rendered accessibility trees. Those
can be layered onto the schema without coupling the core contract to HTML.

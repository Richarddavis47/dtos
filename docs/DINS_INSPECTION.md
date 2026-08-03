# DTOS AI Inspection System (DINS)

## Purpose

DINS provides a stable JSON description of what major DTOS pages render. It is
designed for automated agents, regression tools, accessibility analysis, and
future presentation-contract verification that should not parse raw HTML.

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

The v1.6.2 foundation covers five major page types plus the catalog. Future
versions can add Commissioner Desk, Matchups, Transactions, Draft Picks, History,
Settings, schema-diff tooling, and snapshot fixtures.

DINS currently describes stable semantic regions rather than CSS layout,
pixel geometry, responsive breakpoints, or rendered accessibility trees. Those
can be layered onto the schema without coupling the core contract to HTML.

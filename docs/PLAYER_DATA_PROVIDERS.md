# Historical Player Data Providers

## nflverse

DTOS selects nflverse player summary statistics as the v1.5.1 enrichment source.

Weekly release files are seasonally available. DTOS treats a missing completed
historical season as a provider gap, while an unpublished current preseason or
future file is explicitly pending/not yet available. It never treats those
states as equivalent or silently suppresses historical HTTP 404 responses.
The public release files cost $0 and are broadly licensed CC-BY-4.0; DTOS retains
provider attribution. Files update nightly during the NFL season and provide weekly
box-score production, targets, carries, air yards, NFL team, position, and GSIS IDs.

The adapter does not claim snaps, routes, first-read targets, injury designations,
or complete red-zone participation. Those metrics remain explicitly unsupported.
No website scraping or paid dependency is used.

## Identity and provenance

GSIS IDs are joined to existing DTOS/Sleeper identities through provider-ID metadata.
Display names are never the sole key. Mappings below 70% confidence and unresolved
IDs are excluded from scoring and signals. Each stored player-week retains provider,
record ID, retrieval time, status, confidence, schema, and importer version.

Raw provider values and DTOS league-scored calculations remain separate immutable
records. Missing fields are `unavailable`; an observed zero remains zero.

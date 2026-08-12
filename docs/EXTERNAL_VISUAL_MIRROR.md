# External Visual Inspection Mirror

DTOS is the canonical live product. GitHub stores only a small, public, read-only
inspection mirror so external assistants can inspect current production even when
their fetch layer cannot render the Render origin.

## Stable entry point

The latest mirrored production manifest is always discoverable at:

`https://github.com/Richarddavis47/dtos/releases/latest/download/dtos-live-inspection-current.json`

The manifest identifies version, build, commit, league, capture time, Projection
Intelligence snapshot, Brain snapshot, Asset Market generation, exact screenshot
hashes, semantic artifacts, and the complete public-surface catalog.

## Publication and registration

Canonical public route registration automatically feeds Live Inspection. Every
inspectable public page is assigned a mirror policy without a mirror-specific
feature list:

- non-parameterized public pages: always capture and mirror;
- parameterized/entity-heavy pages: representative or requested capture;
- APIs and explicitly excluded routes: semantic discovery only.

The hourly and release-triggered GitHub workflow waits for matching production,
complete Live Visual captures, and matching DINS publication. It then copies the
exact verified PNGs and semantic JSON to the immutable release, publishes the
stable current manifest, and verifies anonymous access. Upload retries are bounded.
Old releases are never rewritten by later releases.

## Relationship to DINS

DINS is the full immutable inspection archive. The External Visual Mirror is the
small direct-download layer: individual PNGs, compact semantic JSON, the projection
audit, and discovery metadata. External clients do not need to download the full
DINS ZIP to inspect one page.

## External-assistant workflow

1. Download the stable current manifest from GitHub.
2. Select a surface entry.
3. Download its PNG and semantic JSON directly.
4. Verify the PNG SHA-256 from the manifest.
5. For a matchup, download `dtos-projection-audit-current.json` and reconcile all
   starter projection values and snapshot identities.

The mirror contains no credentials, cookies, environment variables, private paths,
internal addresses, or provider payloads. Publishing it never refreshes providers,
rebuilds intelligence, constructs Asset Market, writes FOIS, or mutates history.

> If a public DTOS surface is visible to the user, it must be discoverable through
> Live Inspection and eligible for visual inspection. Core current surfaces must
> also have externally fetchable visual evidence.

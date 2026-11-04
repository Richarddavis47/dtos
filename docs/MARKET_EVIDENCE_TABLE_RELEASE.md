# Readable Market Evidence — v1.21.11 / build 2111

Baseline: accepted v1.21.10, `4ce754133aa3306faed0c1d4ee22399b1c964984`.
This release changes presentation only; canonical Market architecture and prices
are unchanged. Scout accepted the prior identifier overflow correction.

## Reproduction before edits

The actual Market route `/market?selected=player:10225` was rendered with the
existing canonical-fact fixture and a production-shaped 93-character Brain
snapshot identifier. McBride and Allen are identity examples, not price overrides.
Opening Full Market Evidence inherited `overflow-wrap:anywhere` from
`.technical-details`, reducing table min-content widths to almost single glyphs.
Its inline overflow container remained bounded, but no useful scrolling existed.

Responsive Chromium measurements (pixels, rounded):

| Viewport | Page before/after | Table before | Table after | Container after |
|---|---|---|---|---|
| 320 | 320 / 320 | 296.36 | 710.48 | 292 |
| 375 | 375 / 375 | 347 | 710.48 | 347 |
| 390 | 390 / 390 | 362 | 710.48 | 362 |
| 1280 | 1280 / 1280 | 1192 | 1192 | 1192 |

At 375px, Result/Owner/Market columns were about 24/27/27px before correction.
After correction their natural widths are about 50/49/53px; Confidence and
Agreement retain about 77/79px. Fixture contents determine intrinsic width;
there is no fixed table width or arbitrary 789px minimum.

The earlier test verified page bounds and `overflow-x:auto`, but did not assert
that columns remained readable or that the container actually had a scroll range.
The strengthened browser contract closes that coverage gap.

## Correction and shared scope

`src/ui/theme.py` removes arbitrary wrapping from the disclosure parent and
scopes it to metadata paragraphs, definition-list fields and technical code.
The existing min-width/max-width container bounds remain. Table headers and cells
inherit normal word breaking, retaining natural minimum column sizes. Textual
cells can still wrap at spaces; numbers and ordinary words remain intact.

Market's table uses the existing `.ds-table-wrap` container, with a focusable,
named region and existing visible focus styling. Table/caption/header semantics
remain. No canonical payload, identifier, price, ownership, projection or Trade
calculation is altered. Full identifiers remain selectable and inspectable.

The same disclosure inheritance also affected Draft's Compare all pick evidence.
A focused actual-route browser test covers that table. The shared definition-list
contract continues to cover the helper used by player career evidence, GM profiles
and exact pick identity. No unrelated table styles or pages are redesigned.

## Browser acceptance and release validation

Browser tests cover 320/375/390 plus 1280/1440 responsive Chromium: disclosures
closed/open, complete selectable wrapping Brain/source/hash values, bounded page,
recognizable full headers, numeric cells with normal breaking, real phone scroll
range, mouse-wheel scrolling, ArrowRight keyboard scrolling and Chromium's
synthetic touch gesture. Desktop has no unnecessary horizontal scroll.

Required release validation includes canonical facts, dossier/Market browser
contracts, recent Trade regressions, full regression, all ten canonical gates,
Ruff, compilation, diff/route/API/HTTP checks, ordinary/archive-warmed/combined-read
2GiB lifecycles, and recovery/quiescence. Results are reported in the release PR.
Focused acceptance passes: 15 dossier/canonical/browser tests, 84 recent Trade
regressions, and 141 recovery tests. Full regression passes all 2,476 tests.
The canonical validator passes all ten gates in 343.654 seconds, including
257 method registrations, 236 OpenAPI paths, no duplicates, HTTP smoke and
process cleanup. Ordinary, archive-warmed and combined-read 2GiB lifecycles
all pass with one semantic worker and zero errors; effective memory peaks are
1,425,039,360 / 1,438,101,504 / 1,407,594,496 bytes respectively. Recovery/quiescence
positive and negative checks pass. No gates are weakened. This is responsive Chromium, not physical
iPhone/Safari.

## Production and Scout handoff

Where manager authentication is unavailable, public readiness/liveness, exact
version/build/deployment identity, deployed CSS and normal sign-in routing are
verified. Authenticated live dossier/table acceptance remains for Scout; no new
access bridge is created and no real trades, lineups or Sleeper data are mutated.

Scout: test McBride Technical Details/Brain snapshot and Full Market Evidence at
320/375/390. Require a bounded page, full selectable wrapped identifiers, readable
headers/names/prices, and local table scrolling. Check Source generation, desktop,
one other dossier, Market/dossier/Trade consistency, truthful projections and
recent Trade smoke. Distinguish live production, responsive Chromium and physical
iPhone/Safari. Track free-agent Trade For and roughly 90-second discovery latency
separately; neither is changed in this release.

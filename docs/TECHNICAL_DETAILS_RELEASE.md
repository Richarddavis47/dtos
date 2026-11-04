# Responsive Technical Details — v1.21.10 / build 2110

The baseline is accepted v1.21.9, commit
`c2d88140f6393ac2537413fffd2199b88076645f`. Scout independently accepted its
canonical facts and Trade contracts. This release changes presentation only.

## Reproduction and cause

Market's expanded player detail, `/market?selected=player:10225`, renders the
Brain snapshot in an inline `<code>` inside `.technical-details`. The shared
style previously supplied only margin and summary styling. Unbroken identifiers
had `overflow-wrap: normal`; they could escape a viewport-bounded container.
The standalone `/players/10225` route uses the same class/helper for career
identity evidence; it does not itself render that Brain snapshot field.

Before edits, actual route rendering with a 92-character representative Brain
identifier measured a 637.5625px code box and 671px document width at both 375px
and 390px viewports. Technical containers were 309px and 324px respectively.
Scout's approximately 626px observation used a different identifier length.
An actual retained 64-character historical-dataset hash also expanded the page
to 477px. The new Source generation disclosure already wrapped correctly.

At 320px, the closed expanded detail additionally measured 337px because long
unavailable-value text imposed a minimum width on its metric grid. This directly
blocked the requested 320px closed/open contract; no evidence was removed.

## Small presentation correction

`src/ui/theme.py` makes `.technical-details` shrinkable and bounded, allows safe
arbitrary wrapping, and preserves normal wrapping/white-space for technical code.
Its paragraph and definition-list children can shrink. A separate rule scoped to
`#selected-asset .summary-grid > .metric` lets unavailable reasons wrap at 320px.
There is no global overflow hiding, truncation, new data model or price change.

The existing `technical_details()` renderer and the Market paragraph-based
disclosure share this class. Dossier career identity, GM-profile technical
evidence and exact-pick technical identity inherit the same presentation rule.
Their data and page structure are not redesigned. Wide Market evidence tables
retain their existing local horizontal scroll container.

## Validation and acceptance

The new browser suite renders real Market details for McBride/Allen and the
standalone McBride dossier, plus the exact shared definition-list renderer with
long Brain/source/hash identities and ordinary short values. It checks closed
and open disclosures at 320, 375, 390, 1280 and 1440px, document/body bounds,
complete text selection, visible labels, usable controls and local table scrolling.
Canonical asset-fact/projection/ownership contracts remain release regressions.
All results are responsive Chromium, not physical iPhone/Safari.

Focused browser/canonical-fact coverage passed 14 tests, and the established
focused recent Trade run passed 84 tests. All 2,475 regression tests passed;
the unchanged canonical validator passed all 10 gates in 339.400 seconds.
Route validation covered 257 method registrations, 236 OpenAPI paths and no
duplicates. Authoritative Ruff, compilation, dependencies, all whitespace
checks, tracked HTTP and process cleanup passed. Chromium was 153.0.8010.12.

Ordinary, archive-warmed and combined-read lifecycle gates passed at 2 GiB/no
swap/two CPUs with one semantic worker and zero OOM events. Effective peaks were
1,437,569,024, 1,398,648,832 and 1,414,799,360 bytes respectively. Archive/combined
fixtures retained 12,322 assets and 461,166 historical records. Recovery/quiescence
and all 141 recovery tests passed. No resource limit, fixture scale or gate changed.

CI, release and production provenance are recorded in the PR and final report.
An initial host
fixture preparation was correctly deferred by its shared-host memory guard;
the unchanged guard/gates run in the established dedicated 2 GiB environment.
The copied checkout also required the ordinary container-local Git ownership
configuration for its known `/app` repository before committed whitespace could
run. The final validator used the same Git 2.52 runtime as the workspace.
Existing operations inspection returned 401; no account session/access bridge
was created. Public/basic production checks and independent Scout manager-page
acceptance remain distinct.

## Scout live handoff

Verify the deployed v1.21.10 / build 2110 and record its commit. In Market's
McBride expanded detail, open Technical Details at 375px and 390px (also 320px
if available). The long Brain snapshot must stay inside the page, its complete
value must remain inspectable/selectable, and Source generation must still wrap.
Repeat with another dossier/long identifier. Confirm Market/dossier/Trade value
consistency, truthful projection availability and recent Trade workflows.
Distinguish LIVE PRODUCTION, RESPONSIVE CHROMIUM and PHYSICAL IPHONE/SAFARI.

Continue tracking separately: Slayton/free-agent Trade For leading to an
ownership-blocked workspace, Recommended approximately 95 seconds and Next Five
approximately 91 seconds. Neither is caused or changed by this CSS correction.

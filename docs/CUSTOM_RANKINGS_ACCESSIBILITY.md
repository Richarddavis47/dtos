# Custom Rankings accessibility and phone acceptance — v1.21.88 / build 2188

## Change and preserved contracts

The old renderer replaced row controls, disabled the new boundary direction and then attempted to focus that disabled button. Chromium left keyboard focus on the document body. Focus restoration now checks enabled, visible controls on the same exact asset, prioritizes an available reorder direction, and follows that asset across filtered/page boundaries. Focus remains visible and clear of fixed phone navigation. Move announcements retain the overall position and asset identity.

Collapsed rows show the overall ranking, exact identity, Market and Personal values and saved intent. Edit reveals accessible direction buttons, overall-position entry, Target/Avoid/Protect, tier and supporting evidence. Warnings remain outside the disclosure. Drag handles support native mouse dragging and captured touch/pen gestures; tapping opens controls without saving a move. Pagination appears above and below the list. Search, position filters and Neutral/Custom controls remain above it. Ranking settings and methodology are expandable. The duplicated generic page heading is hidden only on this editor; account/franchise context and normal navigation remain.

No valuation engine, account store, API command semantics, projection, lineup, provider or Trade calculation was changed. Initialization and Restart still use the current compatible Market baseline; tier boundaries remain organizational. Neutral preserves Custom intent. Exact pick/player identity, optimistic revision, CSRF and account/league/franchise isolation remain authoritative. Stale failed responses, as well as successful responses, cannot roll back a fresher render.

## Reproducible responsive Chromium measurements

Measurements use authenticated disposable accounts, 42 deterministic assets, initialized Custom mode and collapsed rows. Before uses unchanged v1.21.87. Coordinates are CSS pixels from document top, at scroll zero. No successful screenshots or DOM archives are retained. Real names, warnings and saved badges can increase row height.

| Viewport | First row, full application shell before → after | Row height before → after | Complete rows per 1,000px of ranking list before → after | Horizontal overflow after |
| --- | --- | --- | --- | --- |
| 320 × 432 | 1,178.5 → 538.5 | 536.7 → 84.5 | 1 → 11 | 0 |
| 375 × 667 | 1,106.0 → 538.0 | 512.7 → 84.5 | 1 → 11 | 0 |
| 390 × 844 | 1,106.0 → 538.0 | 512.7 → 84.5 | 1 → 11 | 0 |
| 1280 × 900 | 925.3 → 610.5 | 276.8 → 84.5 | 3 → 11 | 0 |

The isolated editor's first row moved from 779.3/731.3/731.3/517.4px to 332.5px. Its top pagination begins at 184.6px, before the list; previously pagination followed all 25 rows. In the full phone shell top pagination starts around 386px. At 320 × 432 the first row still requires ordinary scrolling; this is not an above-the-fold claim. Focused editing and pagination controls are checked by hit testing against the sticky navigation.

## Executable evidence

`tests/test_personal_rankings_accessibility_browser.py` covers all four viewports, first/last/repeated moves, 25/26 page crossings, filtered global ordering and visual scroll anchoring, visible focus, disclosure persistence, Neutral/Custom, exact identity, touch cancellation/tap, captured pen reordering, stale GET/write responses and stale optimistic revisions. Existing browser coverage retains native mouse drag and touch reordering, Restart, exact pick protection and personal Trade numerical checks. Existing focus assertions were preserved and strengthened.

Run the focused suite with:

```sh
.venv/bin/python -m unittest tests.test_personal_rankings tests.test_personal_rankings_store tests.test_personal_rankings_integration tests.test_personal_trade_workflows tests.test_personal_rankings_browser tests.test_personal_rankings_accessibility_browser tests.test_personal_trade_browser
```

Optional `DTOS_RANKINGS_UX_EVIDENCE=/private/output` writes numeric component/shell geometry only. It does not enable screenshot publication. The ordinary-edit HTTP test asserts zero calls to provider acquisition, canonical generation, lineup solving, FOIS, historical reconstruction and discovery. Separate release gates retain production-shaped ordinary/archive-warmed/combined-read workloads, 2 GiB limits, liveness, recovery/quiescence and FOIS worker cleanup. Full regression and canonical validation remain required.

## Independent Scout handoff

Use a designated test account for intentional ranking writes. Production acceptance by the implementer is read-only and does not change existing users' rankings or league state.

- At 320 × 432, 375 × 667, 390 × 844 and desktop: verify search, filters, mode and top pagination; compact identity/prices and visible warnings; no page overflow. Expand Edit and verify controls clear sticky navigation.
- With keyboard: move the second asset to first and the penultimate to last; repeat in the opposite direction. Cross positions 25/26 and reorder a filtered position. Focus must stay visibly on an enabled control for the same asset and announce the correct overall position.
- Drag with mouse and touch where available; verify the exact asset and full global order, including filtered lists. Tapping the drag control should open editing, not write an accidental move.
- Save flags/tier, collapse, expand, filter, paginate and reload. Confirm persistence, exact acquired-pick scope, Neutral preserving Custom, and confirmed Restart matching the current compatible Market baseline.
- Confirm Market and Personal remain distinct; tier edits do not change prices and rank edits use the accepted slot curve. Supporting evidence and identity/unavailable warnings must remain discoverable.

Responsive Chromium is not physical iPhone/Safari testing. Physical device accessibility and independent Scout acceptance remain separate checks; no physical-device result is claimed here.

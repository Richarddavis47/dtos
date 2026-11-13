# Visual and rendered journey inventory — before implementation

Baseline production v1.22.36/build2251, merge e7ecd1b72944e36481668554d05dc4e321e7b3de, tree1502404775deac8eb657d62b855bbac62aed374c. Frozen premerge source9943a3c220f0064c281bc9d53803afbf1ab03f49 has this identical tree and is available as a separate read-only worktree. No production browser or owner session is used, and Opera will not be used.

## Existing normal-router harness

`tests/test_product_browser_journey.py` creates two disposable accounts/three league memberships, publishes three warm fixture runtimes, and traverses authentic account middleware and normal product routers using `dtos_app.page`. It forbids request-time Sleeper access and unknown external traffic, asserts legal account isolation and no runtime hydrations, and verifies cleanup. Extension hooks permit capture/audits without a second rendering system. The currently configured two viewports are1280x900 and390x844; the capture extension can use320x432,375x667,390x844,1280x900.

Route inventory traversed: `/` Home; `/league`; `/teams/1`; `/fois`; `/market`; `/trades`; `/trades/create`; `/trades/trade-for`; `/trades/shop`; `/trades/recommended`; `/picks`; `/matchups`; `/matchups/1`; `/transactions`; `/players/1-QB-0`; `/front-offices`; `/settings`; `/commissioner`. Account activation, changing leagues, cross-account403, and correct primary-navigation My Team target already execute. The fixture intentionally has sparse/missing advanced evidence, so these family captures are evidence-limited rather than claims of complete owner data.

## Existing actual Trade capture

`/workspace/2251-trade-for-cost/styled-source-screen.py` uses authenticated loopback HTTP, native exact-target shared evaluator, full normal theme, then two-offer comparison and editable preview/return. Its exact2251 original screenshots/results exist for320/375/390/1280. This baseline is reusable unchanged. The legacy exact-target action initiates one bounded search, then an explicit Generate adds one. Comparing/opening/returning adds zero HTTP. All original2GiB enforcement/cleanup receipts are retained. Its source-tree identity matches the production baseline exactly.

Concrete baseline: normal generated cards render the long decision explanation, repeated Market/availability/depth language, full two-sided consequences, draft capital and before/after lineups in repeated nested detail panels. The320px full-page native Trade screenshot is extremely tall. A fresh matched capture will record per-root-offer bounding height, visible text length, text/fonts and control geometry to compare the exact same prepared offer structure after edits. It must not count nested/exploratory `.tw-offer` elements as root result cards.

## Existing specialised controls to reuse

- `tests/test_my_team_intelligence_browser.py`: five sizes, roster/disclosure keyboard focus, actual roster -> player -> Back, draft capital -> exact pick -> Shop, persistent Trade draft strategy and navigation intent.
- `tests/test_contextual_back.py`: authentic loopback HTTP redirects/static bytes, personal scope/draft/comparison/back mechanisms; no simulated auth redirect.
- `tests/test_trade_for_acquisition_browser.py`: prepared offer role/Neutral cost/extras/FAIR-OPTIONAL fixtures, explicit Generate, editable preview, comparison, keyboard/touch, return/reload; bare component theme in original harness, so must retain normal-theme HTTP captures as visual acceptance.
- Current baseline canonical archive retains all page-family evidence (Home/outlook, My Team, Market, player production, histories, picks/capital, Custom Absolute/Relative, welcome, account/security); exact manifests/hashes in2251 task. These remain historical source-matched controls, not freshly observed live owner pages.

## Planned final acceptance

1. Matched normal-router page-family screenshots at all four sizes and actual overflow/action accessibility checks, with keyboard/touch and no sticky overlap.
2. Matched actual shared-evaluator Trade cards before/after, showing material default height/text reduction with >=existing readable text size, principal risk and Review action visible, no provider/search merely from details/comparison.
3. New focused customer-journey test can extend existing actual-router harness with stable semantic assertions; it must not replace evaluator decisions or weaken old meaningful checks.
4. Complete/partial/missing/retained/loading/capacity/error states should use existing native evidence fixtures and agent-focused rendered controls; each screenshot's fixture/qualification is labelled. No claim of physical iPhone/Safari or authenticated owner live acceptance.

# Premium visual hierarchy

Build 2195 applies the approved v194 visual audit to existing presentation only.
The charcoal palette, green primary interactions, player/position identities and
five main navigation destinations are retained.

## Presentation boundaries

- `src/ui/design_system.py` exposes the same secondary destinations through a
  native disclosure and explicit search/identity page-header variants. The shared
  application shell places the disclosure beside the brand and synchronization
  control. Expanded tools remain in document flow, not an overlapping global menu.
- `src/ui/theme.py` compacts the shared shell and distinguishes header navigation,
  selected Market views and task actions. Account/onboarding content is excluded
  from the generic title/help flex treatment. Specialized Trade/My DTOS headers
  retain their existing scope.
- Home keeps the existing prepared selector, two initial insights, up to four
  total, costs, eligibility, exact offer tokens and explicit Find Trade Ideas.
  The leading insight gains visual priority; source/error states are not hidden.
- Market reorders existing rendering: view selection, search/filter form, count
  and explanatory disclosure. Query fields, values and recovery remain unchanged.
  Its existing Result ordinal receives enough space to avoid overlapping the
  player portrait. On phones it sits above the identity instead of consuming
  the name column. Component checks cover whole-word fit and portrait overlap.
- The dossier formatter reuses its prepared recommendation wording and first
  existing concern/uncertainty. It does not infer a new verdict. The same Market
  value, weekly panel and complete evidence remain available. Supported strengths
  and concerns use quieter sections; Snapshot metadata opens through a native
  disclosure. Exact identity and return links are preserved.
- My Team exposes Roster, Depth and Capital in one compact three-column row,
  with the unchanged strategy-aware action above it. Secondary Trade shortcuts
  remain available inside the existing assessment disclosure, avoiding a tall
  stack before the roster. Accessible link names, anchors and destinations are
  preserved; no extra navigation or assessment computation is created. The strategy
  field keeps room for its selected text on desktop and wraps its label within the
  same row on narrow phones; font size and touch-target height are preserved.

## Resource and integrity contract

No additional provider synchronization, discovery, FOIS generation, historical
reconstruction, solver work, persistence or background job belongs in rendering.
No core service, personal-valuation policy, projection, legal-lineup rule, cached
eligibility or historical qualification changes. Four unsupported Custom assets
retain truthful, revision-checked recovery; production preferences are not edited.

`tests/test_premium_hierarchy_browser.py` covers real routers and disposable
accounts, header tools, phone control geometry, keyboard focus/disclosures,
prepared Home placement, exact capital/cost text, wrapped shortcuts and return
navigation, canonical Market search/filter state and values, and pure formatter
no-work guards. Existing zero-price checks assert available state and the visible
zero metric under the revised markup. The full regression and hosted canonical
validator remain mandatory release gates.

Capture `DTOS_PREMIUM_EVIDENCE` into a disposable output directory for initial
screenshots and DOM geometry at 320x432, 375x667, 390x844 and 1280x900. New captures
must be paired with the pinned v194 baseline; do not interpret scrolled captures
as initial-viewport coordinates. Author Chromium fixtures are not independent
Scout acceptance, physical iPhone/Safari, screen-reader or unfamiliar-human tests.

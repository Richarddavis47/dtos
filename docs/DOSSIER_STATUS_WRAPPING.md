# Readable Dossier Status — v1.21.22 / build 2122

Baseline: v1.21.21, `7847e3a992d3cf17202f2976ebe915c6c22c8052`.

## Root cause and scope

The actual `/players/11563` route renders utility through
`components.asset_intelligence.player_dossier`, with `article.ai-value > b`.
Its inline ASSET_CSS forced two equal phone columns and applied
`overflow-wrap:anywhere` to 30px values. At 320/375/390px the cards were
140/167.5/175px wide, leaving 106/133.5/141px for the status. Chromium split
Unavailable into two lines at all three widths. Document width stayed bounded;
this was readability failure rather than page overflow. Computed word-break was
normal, overflow-wrap anywhere, and columns were the two widths above.

The prior fixture exercised `#selected-asset .summary-grid .metric > b`, a
different Market selected-asset component. Its passing test could not establish
anything about the actual player-dossier utility cards.

Only dossier ASSET_CSS changes: auto-fit columns with a 220px card minimum
(capped at available width), and normal word wrapping on direct headline values.
Cards stack at phone widths and keep the existing 30px type. Four desktop columns
remain at 1280/1440px. Long availability explanations wrap at spaces inside the
existing evidence disclosure; technical tokens and structured tables retain their
separate overflow rules. No calculations, availability semantics or data change.

## Real-route acceptance

`tests/test_dossier_status_browser.py` obtains HTTP 200 HTML from the actual
transactions router, unmodified dossier builder and renderer, then opens the real
Bo Nix and McBride paths in Chromium with the application's CSS.
Sanitized Bo Nix evidence deliberately supports Market pricing but lacks utility
evidence: exactly the three named utility cards show Unavailable. McBride supplies
numeric values. The renderer supports numeric values or Unavailable; it does not
invent shorter utility statuses. Existing short statuses and long missing-evidence
messages elsewhere remain covered by the real dossier/evidence regressions.

At 320/375/390px, after correction cards are 292/347/362px wide and values have
258/313/328px. DOM Range geometry verifies each complete Unavailable occupies one
line, distinct from its label. Supporting Evidence opens, including complete long
missing-evidence explanations, without page overflow. Desktop 1280/1440px retains
289px cards and intact statuses. Numeric utility and Market values remain readable.

These are responsive Chromium route-fixture checks, not physical iPhone/Safari
or authenticated live production checks.

| View | Before | After |
| --- | --- | --- |
| Bo Nix, 320px | [Before](visual/v1.21.22/bo-nix-before-320.png) | [After](visual/v1.21.22/bo-nix-after-320.png) |

[390px](visual/v1.21.22/bo-nix-after-390.png) ·
[Desktop](visual/v1.21.22/bo-nix-after-desktop.png).

Required release validation retains full regression, all ten canonical gates,
real technical/evidence-table browser checks, FOIS and protection accessibility,
Trade/Calculator regression and unchanged 2 GiB lifecycle/recovery gates.

## Scout live handoff

On the deployed release, open Bo Nix `/players/11563` at responsive Chromium
320/375/390px. Check Intrinsic dynasty utility, Season utility and Team-specific
fit: Unavailable stays intact, fully visible, readable and contained; labels and
evidence explanations remain accessible. Compare desktop.

Check McBride and another numeric dossier; full selectable long Brain snapshot
identifiers; readable locally scrollable Full Market Evidence; FOIS long manager
name/score separation at 320px; Shop/Calculator exact-protection tap, keyboard and
dismissal; Calculator balancing/preview/Keep Original/Adopt; Trade basics and
canonical Market consistency. Opening protection details must not change locks.

Report expected versus actual and distinguish LIVE PRODUCTION, RESPONSIVE
CHROMIUM and PHYSICAL IPHONE/SAFARI. Authenticated live dossier acceptance belongs
to Scout when no authorized session is available here.

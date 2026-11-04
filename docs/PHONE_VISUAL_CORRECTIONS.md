# Accessible Phone Details — v1.21.21 / build 2121

Accepted baseline: v1.21.20, `e179735429ec6a6ac61f253d016a1fc804c305c7`.
This release corrects three presentation defects without changing product engines.

## Reproduction and correction

The real FOIS route rendered RichardDavis47's name through x=231.3 at 320px,
while score 86.34 began at x=222: a 9.3px overlap. At 375px the score began at
x=277 and the same name was clear. The mobile grid combined a shrinking manager
column with a fixed score column, while unbroken names painted beyond their cell.

The reusable leaderboard card now stacks at phone widths. Complete manager and
league-specific franchise names wrap within their own section; score and rank
remain separate. Desktop keeps columns, with a content-sized score column and
wrapping identity. No names are truncated and no scoring/ranking logic changes.
The existing unavailable-rank text gets a normal text layout rather than being
forced into a 44px circular numeric-rank badge.

The Shop target identity used a hover-only title, while the Calculator's aggregate
protection summary was plain text. Existing asset rows and alternatives already
had native disclosures. All now reuse that presentation boundary, reading the
existing protected/excluded/required incoming/required outgoing state. No parallel
protection model is introduced.

Native `details`/`summary` supports touch, click, Enter/Space, keyboard focus and
expanded/closed accessibility state. Toggle again to dismiss. Details stay inline,
with no overlay, request, proposal edit or constraint mutation. Asset selection
buttons have an inert lock icon and a separate disclosure, avoiding nested actions.

Explanations distinguish a player/exact pick that cannot go outgoing from a Shop
asset that must remain outgoing and a Trade For target that must remain incoming.
An exact-pick lock does not lock every same-round pick. Shop protection selection
repaints those explanations immediately; releasing one lock retains unrelated
locks and required anchors. Preview and adjustment disclosures use the same facts.

Dossier value cards previously split Unavailable into two lines at 320px. Their
grid now adapts to a sensible minimum card width, and short value words use normal
word wrapping. This is scoped to the selected-asset value cards; technical tokens
still wrap fully and structured evidence tables retain readable local scrolling.
Availability, values, freshness and confidence are unchanged.

## Evidence and validation

Sanitized real FOIS route and existing Trade workspace fixtures cover 320/375/390,
1280 and 1440px. Names include short and long unbroken identities, scores include
decimals, large values and missing evidence, and exact picks include two distinct
same-year/same-round original franchises. Tests compare text geometry, page width,
native disclosure state, keyboard focus and persisted proposals/protections.

| Surface | Before | After |
| --- | --- | --- |
| FOIS, 320px | [Before](visual/v1.21.21/fois-before.png) | [After](visual/v1.21.21/fois-after.png) |
| Dossier status, 320px | [Before](visual/v1.21.21/unavailable-before.png) | [After](visual/v1.21.21/unavailable-after.png) |

[Calculator exact-protection explanation](visual/v1.21.21/protections-after.png).
These are responsive Chromium fixture captures, not authenticated production or
physical iPhone/Safari captures. Required canonical, full regression, HTTP, recent
Trade and unchanged 2 GiB lifecycle/recovery gates remain in force.

## Scout live handoff

On LIVE PRODUCTION v1.21.21 / build 2121:

1. FOIS: RichardDavis47/86.34 or current score at 320px; also another long manager
   and franchise name, 375/390 and desktop. Check separate readable identity,
   score, rank and profile action, with no overlap, clipping or page overflow.
2. Shop: tap the required outgoing badge and an exact protected player/pick.
   Required outgoing does not mean do-not-trade. Check full exact identity, same-
   round distinction, keyboard activation/focus, toggle dismissal and unchanged
   offer/locks. Change a protection and confirm the explanation updates.
3. Calculator: open Exact protections, including an acquired pick and retained
   Shop/Trade For anchor. Verify truthful distinctions, keyboard/tap dismissal and
   no accidental adoption or protection changes. Sample Adjust Offer/preview too.
4. Dossier: Unavailable stays intact at 320px. Open technical identifiers and Full
   Market Evidence: full tokens wrap and wide tables scroll inside their container.
5. Regression: Recommended/Next Five, Shop/Trade For, balancing, Preview/Keep
   Original/Adopt, exact locks, prices/strategy invariance, multi-asset reload and
   explicit target switching. Do not send real trades or change Sleeper/lineups.

Report expected versus actual and distinguish LIVE PRODUCTION, RESPONSIVE
CHROMIUM at 320/375/390 and actual PHYSICAL IPHONE/SAFARI. Physical-device and
authenticated live interaction are independent Scout acceptance where no existing
authenticated session is available to Codex.

# Offer-bound balancing feedback — v1.21.19 / build 2119

## Root cause and correction

The v1.21.18 edit handler incremented the offer revision, cleared the preview and hid prior options. The nearby balancing status was independent DOM text and survived, falsely saying that previews were ready. A deterministic browser reproduction confirmed this before edits.

Balancing feedback now records the offer revision and request generation that produced it. Async completion/error writers must match both. Rendering clears mismatched feedback and releases retained balancing options; it does not clear unrelated workspace messages or non-balancing offers. Asset/team/target changes already invalidate proposal previews. Exact-lock and strategy changes now also clear specifically obsolete balancing previews. Valid Keep Original retains current options/status; Adopt changes the revision and clears feedback for the prior offer.

Feedback is transient and is not stored with the proposal. Reload and new navigation retain appropriate authorized proposals/protections but do not resurrect obsolete completion messages. Existing cancellation, busy/disabled controls, 45-second deadline, request generation, tenant/ownership validation and explicit navigation precedence remain intact.

No Market arithmetic, provider policy, ownership/pick model, balancing candidates or advanced/discovery evaluator changes are made. No cache, query, worker or infrastructure is added.

## Validation

Focused responsive Chromium coverage includes success followed by asset edits; an owned equal-value 180/180 exact-pick swap; fresh rebalancing; Preview / Keep Original / Adopt; outgoing player/exact-pick protections; lock/strategy/counterparty changes; a canceled old response after player/pick edits; error/empty feedback; and reload/new-target/history navigation. Phone widths are 320/375/390px, with page bounds, reserved feedback height and nearby placement checked. Existing loading, timeout, cancellation, pricing, Trade/navigation/security and responsive regressions remain required, alongside all ten canonical gates and unchanged 2 GiB lifecycle/recovery requirements.

## Scout live handoff

On LIVE PRODUCTION v1.21.19/build 2119, balance an unequal priced offer. Confirm options and success feedback appear. Edit players/picks: obsolete options, preview and completion feedback must disappear together. Try the observed equal-value 180/180 pick swap where current canonical prices support it, or another equal-value owned pick pair: Balance should be disabled with no old “options ready” text. Prices are generation-dependent, not fixed product constants.

Rebalance an edited unequal offer and confirm fresh options/status. Verify Preview keeps the original, Keep Original works, Adopt explicitly updates the offer, and exact player/acquired-pick protections persist. Sample empty/error/cancel recovery where safely observable, pending navigation, strategy price invariance, totals and favored side, Shop → Calculator → Advanced Analysis, Trade For and Recommended/Next Five. No real trades or Sleeper mutations.

At 320/375/390px confirm nearby feedback, correct availability, no page overflow or feedback layout jump and usable preview/adoption controls. Distinguish LIVE PRODUCTION, RESPONSIVE CHROMIUM and PHYSICAL IPHONE/SAFARI. Physical-device testing is not claimed; authenticated production interaction is left to Scout when a session is unavailable.

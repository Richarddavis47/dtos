# Proposal tray and primary action visibility

Baseline: v1.21.23 / build 2123, `db424e891abdb9961a135fa84f7507bbf25e3dd6`.
Release: v1.21.24 / build 2124.

## Reproduction and root cause

Scout's authenticated Day Traders observation is independently reproduced using
actual authenticated Trade routes, shared theme and retained two-player proposal.
At 375/390/400px by 677px, Discover is y528.08–572.08 while the fixed tray is
y511–601. Center hit-testing returns `#trade-tray-text`, rather than Discover.
The bottom navigation occupies y610.5–677. The page is bounded; the failure is
pointer interception, not horizontal overflow. At 320×483 the initial action lies
below the viewport, and normal scrolling can place it behind the same tray.

The tray's `position:fixed` and z-index 30 reserve no document space. Workspace
bottom padding only helps the last content scroll past the overlay; it cannot
protect enabled controls at arbitrary scroll positions. Desktop has the same
floating layout risk, though the initial sampled Discover position is clear.

## Shared correction

The existing tray is in normal flow near the start of the workspace, after the
Recommended discovery/session controls. It retains the full summary, Send/Receive
counts, existing View Trade button and exact original state handlers. No collapse
interaction, pass-through pointer rule, extra request or state model is added.
The tray is no longer persistent at the viewport bottom; ordinary scrolling
reaches it and the existing inline View Trade action. Calculator continues to
use its existing visible package panels rather than this tray.

Fixed-tray padding/offset/transform/z-index are removed. The tray owns its border-box sizing even when reused outside the global theme. Shared controls have
scroll margins for the unchanged phone bottom navigation. Responsive summary
text can wrap while the View Trade touch target remains readable. All calculation,
discovery, ownership, security, navigation and protection logic is unchanged.

## Browser acceptance

`tests/test_proposal_tray_browser.py` uses actual router rendering, authenticated
context and persisted proposals. Search/evaluation response outcomes are explicit
bounded fixtures, not assertions about current live search quality or latency.

Recommended matrix: 320×483/844, 375×483/677/844, 390×483/677/844, 400×677 and
1280×900. Cross-workflow checks cover 320/375/390 and desktop, followed by resize.
The original initial 677px-height Discover position is tested before automatic
scrolling. Controls brought into view are checked at their center and opposite
corners using `elementFromPoint`, then activated by real mouse coordinates.

Coverage includes Discover, nearby pending status, Next Five, summary View Trade,
Create/Evaluate, Shop, Trade For, Calculator Balance/Advanced Analysis, Adjust,
Make It Cheaper, Preview, Keep Original and Adopt. Empty/one/two-player proposals,
reload, back/forward, keyboard Enter, empty/error responses and resizing are checked.
Existing regression modules additionally cover multi-asset exact picks, locks,
expanded technical details, long identities and asynchronous intent protection.

This is responsive Chromium testing. Physical iPhone/Safari is outstanding.
Authenticated live acceptance is reported separately from controlled acceptance;
no new access mechanism is authorized.

## Scout live handoff

On the deployed release, retain Day Traders Bo Nix → Joe Burrow and open
Recommended at 320/375/390px, including a taller portrait height. Discover must
receive clicks, show nearby loading and finish normally. The proposal summary now
occupies normal page space; View Trade and Next Five remain usable. Verify real
pointer targeting after scrolling and while details expand.

Sample Shop, Trade For, Create/Evaluate, Calculator Balance, Make It Cheaper and
Preview/Keep Original/Adopt for unobscured actions. Recheck verdict orientation,
exact protections, multi-asset reload, explicit target changes, canonical prices,
acquired-pick layout and free-agent actions. Label live production, responsive
Chromium and physical iPhone/Safari separately; challenge any unverified claim.

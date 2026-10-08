# Explicit Trade Navigation — v1.21.16 / build 2116

## Reproduction and root cause

Main was reconciled at c9018a2cb39e383ed51085250959b757c08fffaa (v1.21.15).
Before editing, real Chromium reproduced both Scout failure classes: Trade For X
then Trade For Y retained X; entering Shop A also retained X. Reload retained X,
while a fresh tab correctly selected A. No player-specific correction is used.

`static/js/trade_workspace.js` restored the single binding-keyed sessionStorage
draft before resolving the URL target. The initializer explicitly let an existing
package outrank the URL. It applied a new target only to an empty package or one
already containing that target, and retained incompatible origin/anchors. Same-tab
state therefore defeated new dossier actions; a fresh tab had no draft to do so.
The old browser test expecting saved offers to defeat different URL targets was
corrected to the authoritative explicit-selection contract.

This is stale client workflow intent (classification A), not evidence of an
authentication mismatch or cross-account exposure. Account/session/league/roster
identity still originates from AccountContextMiddleware, LeagueContextMiddleware
and the server-issued workspace binding. URL owner IDs, history and saved drafts
are not authorization. Backend binding/CSRF/ownership checks remain unchanged.

## Transition and restoration contract

- A valid Shop/Trade For entry must match the restored origin, exact required
  anchor, selected side and absence of an incompatible opposite anchor to retain
  that package. Otherwise the URL selection wins: clear old sent/received assets,
  partner, original/preview/adopted proposals and adjustment instruction; establish
  the new workflow, anchor and actual target owner. Keep exact protected/excluded
  identities within the same authorized binding. A conflicting protection remains
  enforced; it is never silently relaxed to make a target work.
- Matching reload retains the adopted multi-asset package and preview/Keep/Adopt
  behavior. Legacy drafts without history metadata are retained only when their
  target/workflow is compatible, so the old persistent wrong-target URL repairs
  itself rather than surviving another reload.
- Each native browser history entry retains only its small proposal/locks/strategy
  draft, binding, workflow and preload identity. Reload/back-forward may use it
  only after fresh workspace loading confirms that binding and route identity.
  New navigation instead resolves the explicit target against the shared draft.
  Browser BF-cache reactivation makes that document's own draft current again.
  Other consumers' history state is preserved. No result universe, candidate pool,
  canonical facts, authenticated account inference or new server cache is added.
- Build My Own explicitly clears targeted anchors/package and retains locks as
  before. Ordinary targetless manual navigation is not a universal draft reset.
- Unsupported ownership entries stay blocked even when a saved draft exists;
  the production server still rejects a free-agent deep link before an editor.
- Existing intent-revision/run guards invalidate pending old results on departure,
  including evidence retries and loading-state completion. Departed documents cannot
  persist a late workspace load over newer intent. No new upstream or
  account/league lookup, worker, endpoint or trade computation is introduced.

## Acceptance and release validation

`tests.test_trade_explicit_navigation_browser` exercises actual shared player
action links and the production workspace renderer/script in real Chromium:
McBride → CeeDee Trade For; CeeDee → Bijan Shop; Shop → Shop; Shop → Trade For;
both directions and repeated targets; switch then reload; fresh-tab agreement;
adopted package/preview reset with exact player and acquired-pick protections;
per-entry adopted multi-asset history/reload; legacy draft migration; pending old
search completion; foreign history-binding rejection; real free-agent route
rejection; BF-cache state activation; and small history state/no extra search IO.
The target/workflow matrix runs at 320/375/390px responsive Chromium.

Existing authenticated identity/navigation tests retain genuine mismatch and
CSRF rejection, colliding account/league roster IDs, concurrent isolation, valid
league switching, exact owner resolution and the real Daniels/McBride Cheaper →
Build My Own → dossier → Trade For path without an intervening reload. Existing
preview/adoption/reload, exact picks, ownership-aware actions, canonical prices,
capital/strategy invariance, discovery/Next Five/diversity/performance, repair,
technical identifier and locally scrolling evidence-table tests remain required.

Publication requires the canonical ten-gate release validator (full regression,
authoritative Ruff, compilation, diff, startup/routes/OpenAPI/HTTP and cleanup),
all GitHub CI jobs, recovery/quiescence and ordinary/archive-warmed/combined-read
Linux cgroups at unchanged 2 GiB limits. Production checks are read-only.
Authenticated live acceptance is reported separately from sanitized browser
fixtures; no physical iPhone/Safari claim is made.

## Independent Scout live handoff

On deployed v1.21.16/build 2116, without reloading:

1. Trade For McBride → CeeDee dossier → Trade For: CeeDee and his real owner must
   replace McBride. Reload must retain CeeDee, and fresh/same tabs must agree.
2. CeeDee Trade For → Bijan dossier → Shop: Bijan becomes the outgoing anchor;
   CeeDee's package/anchor must not masquerade as the new Shop workflow. Repeat
   Shop → opponent Trade For, Shop A → Shop B, and Trade For A → Trade For B.
3. Adopt a multi-asset proposal; reload without a new selection and verify the
   full package, applicable exact player/pick protections and Preview/Keep/Adopt.
4. Back/forward must restore the appropriate entry, including its adopted draft.
   Navigate while a search is pending; the old response must not restore its
   obsolete target or overwrite the new workflow/results.
5. Repeat Cheaper → Build My Own → dossier → Trade For: no false identity warning.
   Genuine mismatches remain blocked; do not cross account boundaries or submit
   trades. Free-agent deep links remain unavailable with truthful ownership.
6. Sample Recommended/Next Five diversity and timing, Shop, Trade For, Cheaper,
   exact locks, ownership and canonical Market price agreement.
7. Check target names, workflow, protections and feedback at 320/375/390 responsive
   Chromium. Label physical iPhone/Safari separately if actually tested.

Keep cold Recommended latency, below-viewport Next Five feedback, physical-device
coverage and the independent calculator outside this release.

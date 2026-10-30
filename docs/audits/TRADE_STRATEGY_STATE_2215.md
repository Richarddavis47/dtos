# v1.22 / build 2215 — Trade strategy state and discovery clarity

## Reproduced cause

Exact build 2214 browser scripts over disposable authenticated HTTP reproduce both findings. `trade_workspace.js` wrote every strategy selection to `dtos_strategy` through `dtosStrategy.set`; My Team read that cookie and wrote the same field automatically. Focus, payload construction and draft restoration reapplied shared intent. The old goal was session-scoped, not a durable AccountStore preference. This establishes a sufficient cause for Scout's observation, not proof of the owner's historical click sequence.

Two adjacent inline `small` nodes rendered the discovery limitations without separation, yielding `DISCOVERYNOT EXHAUSTIVE`. Existing limitation codes correctly described bounded search; discovery mathematics were not defective.

## Corrected state contracts

- Trade strategy lives only in the existing temporary workspace. All three choices and explicit no-preference restore on reload and contextual Back. Existing request cancellation/revision fences remain; changing another tab's goal does not overwrite active Trade intent.
- Fresh primary Trade entry clears the workspace as before, then starts from the franchise goal. Start New retains the current temporary strategy. No new history or workspace store.
- My Team selection is an explicitly labeled unsaved preview. A native **Save goal** form is the only persistence operation. No automatic import of legacy intent, goal restoration, ranking migration or production preference edit.
- Legacy scoped session cookies remain read-only fallbacks. An explicitly saved empty goal wins over old cookie values. Existing production session intent is neither guessed nor reset.
- Account schema 4 adds one preference-only table in the existing DB, keyed by account, league and exact franchise. Maximum 64 goal rows/account; bounded request body; transactional revision compare-and-swap. Current active account, selected league, membership, franchise and nonexpired/nonrevoked session are rechecked inside the write transaction. Existing origin and CSRF guards are retained. Responses are private/no-store; stale or unauthorized writes preserve the existing value.
- Reading the goal uses an indexed LEFT JOIN in the existing account-context lookup, not an extra provider call or analytical task. Goal revision does not enter source/workspace bindings or personal-ranking revisions.

## Presentation

The Trade control is labeled **Trade strategy** with “Not your saved goal.” My Team uses **Franchise goal**, unsaved feedback and **Save goal**. Discovery shows one wrapping block note: “DTOS explored a limited set of possible offers, not every theoretical trade.” Other limitations remain separate. Zero-result explanations, Shop leads and final bilateral verdict hierarchy are unchanged.

Customer-facing version is **v1.22**; technical SemVer/OpenAPI version and immutable tag remain **1.22.0 / v1.22.0**, build 2215, following existing release tooling.

## Verification and acceptance

Actual disposable storage → account middleware → Trade/Team HTTP → rendered Chromium controls cover temporary choices, explicit saves, reopened DB/new sessions, concurrent/stale writes, membership transitions, wrong scope, revoked/expired access, two accounts/two leagues and bounded storage. Four viewport controls cover keyboard and touch save, readable discovery, visible focus and no page/component overflow. Existing navigation, Preview/Keep/Adopt, cancellation, source-generation, Neutral/Custom and 2214 discovery controls remain mandatory.

The first two local browser attempts failed due to test transport Origin mismatch and redirect handling; the application security guard was preserved. A real loopback fixture server fixed transport fidelity and verifies the native 303 save journey. An existing navigation test expected the old cross-page cookie strategy on fresh entry; it now expects the actual franchise goal while retaining package/reset/Back assertions. Additional test-authoring failures (reading a locator after leaving its page and using a wrong fixture token attribute) were corrected; cancellation now waits for a genuinely held response before releasing it late. Hosted validation also caught added My Team form height; the goal label, selector and Save action now share one compact row, preserving the original roster placement threshold. The multi-league browser fixture now includes the actual navigation router and static navigation assets, so fresh-entry checks exercise deployed behavior. Legacy cross-tab-persistence expectations and old accessible labels were updated to the new explicit-save contract while retaining all package/provenance assertions. Original logs remain in the sanitized handoff. No physical iPhone/Safari claim.

Release requires the complete canonical validator (all ten gates), complete hosted Product/security/navigation jobs, supported Python checks and actual 2 GiB lifecycle controls against the exact final tree. Hosted raw results and lifecycle capacity limitations belong in the release handoff; passing gates alone are not broad capacity clearance. No owner goal save/reset is allowed during live acceptance.

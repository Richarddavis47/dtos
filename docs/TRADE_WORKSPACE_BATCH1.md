# Master Roadmap — Batch 1: Trade Center mechanics

Baseline: immutable v1.14.1 (`7f691f179081eabc95e543a2cbdb778588991502`).
Candidate: v1.15.0 (minor, additive workspace functionality; repository SemVer).

## Scope and execution

One shared, temporary two-party workspace for Create, Trade For, Shop and
Recommended offers. Canonical current ownership, stable pick identities,
selection/search/filter persistence, proposal review/edit, authenticated
evaluation and explicit adjustment outcomes. No new intelligence methodology,
provider integration, permanent proposal storage or external trade submission.
Current Visual, DINS and External Visual Mirror remain retired.

## Before-state proof

The real authenticated Create Trade page reproduces both reported messages for
the shown owned-player proposal: `Ownership changed or evaluation failed.` and
`Adjustment failed.` Source requests send JSON without the CSRF header required
by AccountContextMiddleware. An authenticated regression proves both requests
are rejected with `403 csrf_rejected` before either engine is invoked. The same
valid fixture proposal with its session CSRF header reaches the real evaluator
and returns 200. This is a client/security-boundary integration failure, not
evidence of stale ownership or an intelligence-engine failure.

The current premium enhancement independently fetches the workspace and layers
buttons over a separate dropdown/state implementation. Selecting an opposing
asset dispatches a counterparty change that clears previous incoming choices.
The dropdown can expose the receiving side while the independent board remains
on the sending side. Replace this competing state with one shared workspace.

## Plan / acceptance checklist

- [x] Read all three authoritative prompt parts; inspect baseline/version policy.
- [x] Reproduce real evaluation and adjustment failures without league mutation.
- [x] Authenticated missing-CSRF rejection and valid evaluator-entry regression.
- [x] Shared canonical workspace context and ownership/error contracts.
- [x] Single mobile/desktop board, proposal review/edit and adjustment state.
- [x] All four entry flows; account/league/generation isolation and current picks.
- [x] Focused semantic/security/browser tests and local canonical gate set.
- [ ] Exact-commit authoritative Linux lifecycle and remote browser gates.
- [ ] PR/release/deploy; authenticated real mobile/desktop/multi-league acceptance.
- [ ] Stable restart, post-restart smoke/trade proof and cleanup.

## Frozen roadmap

1. Trade Center mechanics — IN PROGRESS
2. Canonical Data Foundation — NOT STARTED
3. Player + Market Intelligence — NOT STARTED
4. FOIS + Pick Intelligence — NOT STARTED
5. Full Trade Intelligence — NOT STARTED
6. Intelligence + UX Polish — NOT STARTED
7. Season Operations + Final Acceptance — NOT STARTED

Stop after Batch 1 acceptance/report. Do not start Batch 2 automatically.

## Focused evidence (candidate working tree)

- 70 focused Trade/security/history/browser tests passed together.
- Additional current-owner traded-pick regression passed. Its initial fixture
  assertion matched all four rounds rather than the transferred pick; narrowed
  the assertion to the exact immutable season/round/original-franchise ID.
- Authenticated mobile/desktop browser proof passed, including proposal retention
  on an actual ownership rejection and preloaded Trade For/Shop entry.
- Three-breakpoint filter matrix, keyboard edit/repair, and four-workflow native
  disclosure accessibility checks passed. Filter reconstruction originally lost
  keyboard focus; focus now returns to the selected filter.
- Legacy picker/inline-script expectations were replaced with the shared-board
  contract; target-preservation and rejection assertions remain substantive.
- First canonical run `81125d6dc3f64b5aabd645e3353a24b1` was stopped during
  regression, not passed: the product journey waited on retired
  `.ti-roster-browser` markup repeatedly. A read-only stack inspection identified
  Playwright waiting with its fixture server idle. The exact test process tree
  was terminated, trace preserved locally, and temporary `py-spy` removed.
- Corrected product journey passed in 31.841s. It retains all account, league,
  navigation, overflow and accessibility checks. Two explicit resource routes
  now serve the shared workspace JS/CSS; no generic static-file proxy is added.
- Second canonical run completed 1,400 tests with one obsolete test-module
  import error for the removed enhancement helper. The test now checks the shared
  workspace composition rather than loading that retired helper; focused proof
  passed. Its failure log remains preserved locally.
- Final local canonical validation: 10/10 gates, 553.465s; regression 1,406/1,406;
  routes 252 with zero duplicates; OpenAPI 234 paths; HTTP and cleanup passed.
- No Linux, PR, release or production pass claimed yet. Local Docker is unavailable;
  the locally validated candidate must be pushed for the existing Linux workflow.
- Initial restricted GitHub CLI check failed; a network-enabled check confirms
  Richarddavis47 is authenticated. No credential change was needed. No push or
  PR has yet been attempted for this candidate.

# Atomic league imports and lineup metric integrity

Baseline: v1.21.59 / 2159 / 3aeec793b4f85abfa95fab8f4d58c3f68dbf27fc.

## Demonstrated defects

The two HTML import routes saved membership and series/season references in separate transactions before activation checked the account revision. Delayed imports returned409 while adding durable references. A canonical three-team projection fixture rendered an optimal-lineup percentile as “Current Contending Grade / championship readiness,” “83th percentile” and unrelated0% confidence.

## Correction boundary

Both import routes now use AccountStore.commit_import after source resolution and runtime preparation. One BEGIN IMMEDIATE transaction validates account status, expected existing updated_at revision, current linked Sleeper identity and unrevoked/unexpired session before any writes. Existing SQL writers insert membership and series/season references; active selection and revision update commit together. Exceptions roll back. No network work holds the write lock. Existing direct membership/series APIs reuse the same writers without changing their established behavior. Stale conflict feedback exposes a deliberate retry destination. No new schema or state.

Commissioner adapts the already-prepared selected franchise roster evidence. Optimal Projected Lineup retains the existing percentile/letter calculation but explains its narrower basis, selected scoring league/week, supported optimal points and partial comparison population. Competitive Window remains separate. Existing reasons/limitations are available in keyboard-accessible details. No confidence number is inferred. The same legacy HQ explanation is renamed to avoid contradictory interpretation. The engine, projections, values and percentile formula are unchanged.

## Evidence and limits

Deterministic barriers exercise manual/discovered imports versus a different selection and explicit reselection, plus simultaneous imports, rollback, preparation failure, session revocation/expiry, identity/CSRF isolation and later retry. Compare every SQLite table's logical rows/identities/revisions after the newer operation and before the rejected completion. Physical SQLite file identity is not assumed. Real publisher/evaluator-derived Commissioner evidence and HTTP/native browser controls cover supported/partial/zero/missing-scoring states and320×432,375×667,390×844,desktop. Responsive Chromium is author-run, not physical Safari or Scout-independent acceptance. Production checks are read-only; do not race real user imports or modify saved selections.

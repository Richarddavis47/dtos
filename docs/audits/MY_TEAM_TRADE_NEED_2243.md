# My Team → Recommended Trades need handoff (2243)

## Confirmed gap

Baseline build 2242 had general My Team Trade shortcuts and a Shop-only position-need preference. Recommended Trades selected opportunity types, but had no incoming-position control or prepared-need handoff. Reuse the canonical diagnostic flags and existing legal position eligibility; do not invent a need score.

## Evidence and state contract

The My Team action and destination use the existing `prepared_diagnostics` reader, which reapplies availability, age and failed-refresh qualifications. No diagnostic is calculated on a missing read. Only the authorized own franchise's current supported need is eligible. Choose one canonical starter need first, then a resilience/quality-depth need in the existing positional order. Do not infer strategy from that choice.

The hint fingerprints the authenticated workspace, ownership, league/week and diagnostic/projection identity. It is not authorization. Destination membership and current prepared evidence are checked again. A mismatched, stale or unmappable hint opens the general workspace with no need filter. K/DEF remain in legal lineup evidence; they are not forced into the existing four-position player filter. FLEX/Superflex eligibility follows actual league slots.

The visible position filter selects received players (mixed returns remain possible). It is applied at the existing request-only session-filter boundary; full evaluation/verdicts are unchanged. It does not expand the candidate universe or promise a matching qualified offer. Position-filtered results cannot populate the broader Home opportunity cache.

Filter changes do not call the draft-edit reset path. The existing scoped tab draft, valuation mode and strategy remain separate. Up to eight bounded earlier offer contexts are retained in existing session storage, with original package identities and source qualifications. They are displayed separately as not revalidated, never relabeled as results for the new position. This is temporary browser context, not a recommendation database or a full search archive. Home/fresh-entry and account/league boundaries remain in effect. A changed or cleared suggestion stays changed on reload.

## Validation and limits

`tests.test_team_trade_need` covers real prepared/rendered needs, context/qualification rejection, failed refresh, admission-independent read misses, supported positions and unchanged real evaluator verdicts. `tests.test_team_trade_need_browser` uses authenticated disposable native-source fixtures: one-QB/FLEX/K/DEF and Superflex, starter/depth distinctions, four viewports, Custom/draft preservation, explicit search, retained result separation, reload, Back and league switching. No seeded successful recommendation or mocked admission is used in the new controls.

Final release evidence records exact source identity, focused/full/ten-gate/hosted outcomes, original failed attempts and enforced 2 GiB resource controls. Disposable fixture acceptance is not authenticated live owner-league acceptance. Chromium keyboard/touch emulation does not establish physical iPhone/Safari acceptance. No production search, sync, FOIS rebuild or preference mutation is authorized by this handoff verification.
